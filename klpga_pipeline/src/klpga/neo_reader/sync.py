"""NEO Sync orchestrator -- the real implementation of the 6-stage
pipeline (collect, normalize, warehouse, validate, review, publish)
the operator specified. Stops on the first failed stage; never writes
fabricated data for a stage that failed (same discipline every existing
collector script in this project already follows).

Two sync stages are supported, matching the tournament lifecycle:

  "pre"      Tournament Info + Entry List + K-Ranking -- everything
             collectible BEFORE a round has been played. This is the
             stage tournament 2026100001 (제26회 하이트진로 챔피언십,
             not yet started) needs right now.
  "results"  Adds round-leaderboard collection on top of "pre" --
             only meaningful once at least one round has real data;
             klpga.collectors.leaderboard.discover_final_round raises
             if no round has any player rows yet, so this stage is
             never attempted implicitly.

This module makes ZERO live network calls of its own beyond what
klpga.collectors.tournaments.fetch_game_list, klpga.collectors.entry_list
.fetch_entry_list, klpga.neo_reader.kranking's two fetchers, and (for
"results") klpga.collectors.leaderboard.collect_all_rounds_for_game
already do -- these are the exact same, already-confirmed primitives
scripts/04_collect_single_tournament.py and scripts/15_collect_entry_
list.py call. Nothing here reimplements or second-guesses their
parsing logic."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga import config
from klpga.collectors.aggregate import build_rows, merge_player_rows, resolve_winner_score
from klpga.collectors.entry_list import (
    build_tournament_entry_rows,
    fetch_entry_list,
    match_entries_to_player_master,
)
from klpga.collectors.leaderboard import collect_all_rounds_for_game
from klpga.collectors.tournaments import fetch_game_list, parse_game_list_entry
from klpga.db.migrate import ensure_tournament_entry_schema
from klpga.db.upsert import (
    finish_collection_run,
    start_collection_run,
    update_tournament_winner_score,
    upsert_player,
    upsert_player_event,
    upsert_player_round,
    upsert_tournament,
    upsert_tournament_entry,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError
from klpga.neo_reader import kranking
from klpga.neo_reader.raw_archive import RawCaptureAlreadyExists, archive_raw, existing_capture
from klpga.parsers.group_page_parser import parse_round_grouping
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html

ROOT = Path(__file__).resolve().parents[3]  # klpga_pipeline/
SCHEMA_PATH = ROOT / "src" / "klpga" / "db" / "schema.sql"
KRANKING_SCRIPT_PATH = ROOT / "scripts" / "87_collect_kranking_top120.py"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_tournament_info(match) -> dict:
    """Pure: TournamentListing -> the TOURNAMENT_INFO.json shape. The
    ONLY place this mapping is implemented -- both the live "collect"
    stage and the offline "read an already-archived game_list.json"
    stage call this, so the normalized shape is byte-for-byte identical
    regardless of where `match` came from."""
    return {
        "game_code": match.game_code,
        "event_name": match.game_title,
        "event_eng_name": match.game_eng_title,
        "season": match.season,
        "start_date": match.start_date_raw,
        "end_date": match.end_date_raw,
        "course_name": match.course_text,
        "course_eng_name": match.course_eng_text,
        "out_course_text": match.out_course_text,
        "in_course_text": match.in_course_text,
        "game_finish": match.game_finish,
        "prize_money": match.prize_money,
        "game_method": match.game_method,
        "is_completed": match.is_completed,
        "is_regular_tour": match.is_regular_tour,
        "is_stroke_play": match.is_stroke_play,
        "collected_at": _now_iso(),
        "source": config.GAME_LIST_ENDPOINT,
    }


def build_tournament_row(match) -> dict:
    """Pure: TournamentListing -> the tournament_master UPSERT row. See
    build_tournament_info's docstring -- same reuse discipline."""
    return {
        "event_id": match.game_code, "game_code": match.game_code, "event_name": match.game_title,
        "season": match.season,
        "start_date": match.start_date.isoformat() if match.start_date else match.start_date_raw,
        "end_date": match.end_date.isoformat() if match.end_date else match.end_date_raw,
        "course_name": match.course_text, "course_location": None, "par": None, "course_yards": None,
        "rounds_scheduled": None, "rounds_completed": None, "field_size": None,
        "winner": match.winner_name, "winner_score": None, "official_url": None,
    }


def _load_kranking_module():
    spec = importlib.util.spec_from_file_location("neo_sync_kranking_script", KRANKING_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class StageResult:
    name: str
    status: str  # "success" | "blocked" | "error" | "skipped"
    detail: dict = field(default_factory=dict)
    error_message: Optional[str] = None


# BUG FIX (2026-09-30, found via the first real end-to-end run against
# gameCode=2026100001): kranking used to be treated as blocking, the
# same as tournament_info/entry_list -- so a K-Ranking-only failure
# (e.g. the K-Ranking site's response shape not matching the parser
# right now) reported the ENTIRE sync as failed even though Tournament
# Info and Entry List had both genuinely succeeded against live data.
# K-Ranking is the one stage this module's own validate.py already
# treats as SKIP-able when absent (see validate_sync's kranking_present
# check) -- SyncResult.ok now matches that: a "kranking" stage in
# ("error", "blocked") does not by itself make ok False, so the other,
# genuinely required stages' real results are never hidden behind it.
NON_BLOCKING_STAGES = frozenset({"kranking", "grouping"})


@dataclass
class SyncResult:
    game_code: str
    season: int
    stage: str
    stages: list = field(default_factory=list)  # list[StageResult]

    @property
    def ok(self) -> bool:
        return all(
            s.status in ("success", "skipped") or s.name in NON_BLOCKING_STAGES
            for s in self.stages
        )

    def add(self, result: StageResult) -> StageResult:
        self.stages.append(result)
        return result


def run_sync(
    game_code: str,
    season: int,
    *,
    stage: str = "pre",
    db_path: Path,
    raw_root: Path,
    normalized_root: Path,
    reports_root: Path,
    content_root: Path,
    cache_dir: Path,
    client: Optional[PoliteHttpClient] = None,
) -> SyncResult:
    """Runs stages 1-4 (collect, normalize, warehouse, validate) for one
    gameCode. Stages 5 (review report) and 6 (git publish) are separate
    callables in neo_reader.review_report / neo_reader.publish -- kept
    out of this function so a caller (e.g. --dry-run) can run 1-4 alone
    and inspect the result before anything is written as a report or
    pushed anywhere.

    Every stage appends exactly one StageResult; the function returns
    immediately after the first non-"success"/"skipped" stage -- no
    later stage ever runs against a failed/partial earlier stage's
    output."""
    if client is None:
        client = PoliteHttpClient(cache_dir=cache_dir)

    result = SyncResult(game_code=game_code, season=season, stage=stage)

    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    else:
        conn = sqlite3.connect(db_path)
    ensure_tournament_entry_schema(conn, SCHEMA_PATH)

    run_id = start_collection_run(conn, "neo_reader.sync", target=game_code, started_at=_now_iso())
    conn.commit()

    # ---------------------------------------------------------------
    # STAGE 1+2+3: Tournament Info (collect -> normalize -> warehouse)
    # ---------------------------------------------------------------
    try:
        listings = fetch_game_list(client, season=season, tour_type=config.TOUR_TYPE_REGULAR)
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit(); conn.close()
        return _fail(result, "tournament_info", "blocked", str(exc))
    except Exception as exc:  # noqa: BLE001 -- network/shape errors, never fabricate past this
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit(); conn.close()
        return _fail(result, "tournament_info", "error", str(exc))

    match = next((l for l in listings if l.game_code == game_code), None)
    if match is None:
        msg = f"gameCode={game_code} not found in season={season} tourType=RE getGameList response ({len(listings)} entries)"
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=msg)
        conn.commit(); conn.close()
        return _fail(result, "tournament_info", "error", msg)

    _try_archive(raw_root, game_code, "game_list", json.dumps(match.raw, ensure_ascii=False, indent=2), config.GAME_LIST_ENDPOINT, "json")

    normalized_dir = normalized_root / game_code
    normalized_dir.mkdir(parents=True, exist_ok=True)
    tournament_info_path = normalized_dir / "TOURNAMENT_INFO.json"
    tournament_info = build_tournament_info(match)
    tournament_info_path.write_text(json.dumps(tournament_info, ensure_ascii=False, indent=2), encoding="utf-8")
    _copy_to_content(content_root, game_code, "TOURNAMENT_INFO", tournament_info)

    tournament_row = build_tournament_row(match)
    upsert_tournament(conn, tournament_row)
    conn.commit()
    result.add(StageResult("tournament_info", "success", {
        "event_name": match.game_title, "start_date": match.start_date_raw, "end_date": match.end_date_raw,
        "is_completed": match.is_completed,
    }))

    # ---------------------------------------------------------------
    # STAGE 1+2+3: Entry List
    # ---------------------------------------------------------------
    try:
        entry_html = fetch_entry_list(client, game_code)
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit(); conn.close()
        return _fail(result, "entry_list", "blocked", str(exc))
    except Exception as exc:  # noqa: BLE001
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit(); conn.close()
        return _fail(result, "entry_list", "error", str(exc))

    _try_archive(raw_root, game_code, "entry_list", entry_html, config.ENTRY_LIST_ENDPOINT, "html")

    from klpga.parsers.entry_list_parser import parse_entry_list_html, parse_entry_summary
    summary = parse_entry_summary(entry_html)
    parsed = parse_entry_list_html(entry_html)
    match_result = match_entries_to_player_master(conn, parsed.rows)
    collected_at = _now_iso()
    entry_rows = build_tournament_entry_rows(
        game_code=game_code, entry_rows=parsed.rows, source=config.ENTRY_LIST_ENDPOINT, collected_at=collected_at,
    )
    for row in entry_rows:
        upsert_tournament_entry(conn, row)
    conn.commit()

    entry_snapshot_path = normalized_dir / "ENTRY_SNAPSHOT.json"
    entry_snapshot = {
        "game_code": game_code,
        "collected_at": collected_at,
        "source": config.ENTRY_LIST_ENDPOINT,
        "page_summary_counts": summary.counts,
        "parsed_row_count": len(parsed.rows),
        "unparsed_row_count": parsed.unparsed_row_count,
        "duplicate_player_codes": match_result.duplicate_player_codes,
        "matched_count": match_result.matched_count,
        "unmatched_count": match_result.unmatched_count,
        "records": [
            {
                "player_code": r.player_code, "player_name": r.player_name, "nationality": r.nationality,
                "qualification_category": r.qualification_category, "qualification_reason": r.qualification_reason,
            }
            for r in parsed.rows
        ],
    }
    entry_snapshot_path.write_text(json.dumps(entry_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    _copy_to_content(content_root, game_code, "ENTRY_SNAPSHOT", entry_snapshot)

    result.add(StageResult("entry_list", "success", {
        "parsed_row_count": len(parsed.rows), "unparsed_row_count": parsed.unparsed_row_count,
        "matched_count": match_result.matched_count, "unmatched_count": match_result.unmatched_count,
    }))

    # ---------------------------------------------------------------
    # STAGE 1+2+3: K-Ranking
    # ---------------------------------------------------------------
    try:
        period_html = kranking.fetch_period_html(client)
        full_table_html = kranking.fetch_full_table_html(client)
    except RateLimitBlockedError as exc:
        result.add(StageResult("kranking", "blocked", error_message=str(exc)))
        period_html = full_table_html = None
    except Exception as exc:  # noqa: BLE001
        result.add(StageResult("kranking", "error", error_message=str(exc)))
        period_html = full_table_html = None

    if period_html is not None and full_table_html is not None:
        try:
            period_capture = _try_archive(raw_root, game_code, "kranking_period", period_html, kranking.ACQUISITION_URL, "html")
            full_capture = _try_archive(raw_root, game_code, "kranking_full_table", full_table_html, kranking.CANONICAL_URL, "html")
            kr = _load_kranking_module()
            combined = kr.combine_official_evidence(period_capture.path, full_capture.path, _now_iso())
            kranking_path = normalized_dir / "KRANKING_TOP120.json"
            kranking_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
            _copy_to_content(content_root, game_code, "KRANKING_TOP120", combined)
            result.add(StageResult("kranking", "success", {
                "ranking_week": combined["ranking_week"], "full_population_count": combined["full_population_count"],
            }))
        except RawCaptureAlreadyExists as exc:
            result.add(StageResult("kranking", "skipped", error_message=str(exc)))
        except Exception as exc:  # noqa: BLE001 -- crosscheck failure, malformed page, etc: real, not fabricated past
            result.add(StageResult("kranking", "error", error_message=str(exc)))

    # ---------------------------------------------------------------
    # STAGE "results" (opt-in only): round leaderboard
    # ---------------------------------------------------------------
    if stage == "results":
        try:
            rounds_data = collect_all_rounds_for_game(client, game_code)
        except RateLimitBlockedError as exc:
            result.add(StageResult("leaderboard", "blocked", error_message=str(exc)))
        except Exception as exc:  # noqa: BLE001 -- includes "no round has any data yet", a real, expected state
            result.add(StageResult("leaderboard", "error", error_message=str(exc)))
        else:
            from klpga.collectors.leaderboard import fetch_round_leaderboard_html
            for rnd in sorted(rounds_data.keys()):
                # Cache hit, not a new request: collect_all_rounds_for_game
                # already fetched this exact (game_code, round) via the
                # same PoliteHttpClient/cache_dir, so this only reads the
                # already-cached response back to archive it human-readably.
                raw_html = fetch_round_leaderboard_html(client, game_code, rnd)
                _try_archive(raw_root, game_code, f"round_leaderboard_r{rnd}", raw_html, config.ROUND_LEADERBOARD_ENDPOINT, "html")
            merged = merge_player_rows(rounds_data)
            final_round = max(rounds_data.keys())
            player_rows, player_event_rows, player_round_rows = build_rows(
                game_code, season, match.game_code, merged, final_round
            )
            for row in player_rows:
                upsert_player(conn, row)
            for row in player_event_rows:
                upsert_player_event(conn, row)
            for row in player_round_rows:
                upsert_player_round(conn, row)
            conn.commit()
            winner_score = resolve_winner_score(player_event_rows, match.winner_code)
            if winner_score is not None:
                update_tournament_winner_score(conn, match.game_code, winner_score)
                conn.commit()

            leaderboard_path = normalized_dir / "LEADERBOARD.json"
            leaderboard_path.write_text(
                json.dumps({"game_code": game_code, "final_round": final_round, "records": player_event_rows}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _copy_to_content(content_root, game_code, "LEADERBOARD", {"game_code": game_code, "final_round": final_round, "records": player_event_rows})
            result.add(StageResult("leaderboard", "success", {
                "final_round": final_round, "player_count": len(player_rows), "winner_score": winner_score,
            }))

    finish_collection_run(conn, run_id, status="success" if result.ok else "error", finished_at=_now_iso())
    conn.commit()
    conn.close()
    return result


def run_sync_offline(
    game_code: str,
    season: int,
    *,
    stage: str = "pre",
    db_path: Path,
    raw_root: Path,
    normalized_root: Path,
    content_root: Path,
) -> SyncResult:
    """Offline counterpart to run_sync -- makes ZERO network calls. Reads
    already-archived raw captures back from raw/<game_code>/ (the exact
    write-once files archive_raw already produces: game_list.json,
    entry_list.html, kranking_period.html, kranking_full_table.html,
    round_leaderboard_r<n>.html for "results") and feeds them into the
    SAME parse/build functions run_sync itself uses (parse_game_list_
    entry, build_tournament_info, build_tournament_row, parse_entry_
    list_html, parse_entry_summary, match_entries_to_player_master,
    build_tournament_entry_rows, kranking.combine_official_evidence,
    parse_round_leaderboard_html, merge_player_rows, build_rows,
    resolve_winner_score). None of that parsing logic is reimplemented
    here -- only re-wired to a disk source instead of a live fetch, so
    online and offline sync always produce byte-for-byte the same
    normalized shape from the same underlying raw bytes.

    A stage whose raw capture is missing from disk fails closed with a
    real "not found" error naming the exact expected path -- exactly
    like run_sync fails closed on a real network error -- never
    fabricating normalized output for data that was never actually
    captured. Unlike run_sync, this never touches raw_root for writing
    (it only reads what's already there) and never calls
    archive_raw/_try_archive."""
    result = SyncResult(game_code=game_code, season=season, stage=stage)

    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    else:
        conn = sqlite3.connect(db_path)
    ensure_tournament_entry_schema(conn, SCHEMA_PATH)

    run_id = start_collection_run(conn, "neo_reader.sync_offline", target=game_code, started_at=_now_iso())
    conn.commit()

    # ---------------------------------------------------------------
    # STAGE: Tournament Info -- read game_list.json back from raw/
    # ---------------------------------------------------------------
    game_list_path = existing_capture(raw_root, game_code, "game_list")
    if game_list_path is None:
        msg = (
            f"no archived raw capture found at {raw_root / game_code / 'game_list.json'} "
            "-- run online sync (or copy a real raw/<game_code>/game_list.json capture into place) first"
        )
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=msg)
        conn.commit(); conn.close()
        return _fail(result, "tournament_info", "error", msg)

    entry_dict = json.loads(game_list_path.read_text(encoding="utf-8"))
    match = parse_game_list_entry(entry_dict, season)

    normalized_dir = normalized_root / game_code
    normalized_dir.mkdir(parents=True, exist_ok=True)
    tournament_info_path = normalized_dir / "TOURNAMENT_INFO.json"
    tournament_info = build_tournament_info(match)
    tournament_info_path.write_text(json.dumps(tournament_info, ensure_ascii=False, indent=2), encoding="utf-8")
    _copy_to_content(content_root, game_code, "TOURNAMENT_INFO", tournament_info)

    tournament_row = build_tournament_row(match)
    upsert_tournament(conn, tournament_row)
    conn.commit()
    result.add(StageResult("tournament_info", "success", {
        "event_name": match.game_title, "start_date": match.start_date_raw, "end_date": match.end_date_raw,
        "is_completed": match.is_completed, "source": "offline:raw/game_list.json",
    }))

    # ---------------------------------------------------------------
    # STAGE: Entry List -- read entry_list.html back from raw/
    # ---------------------------------------------------------------
    entry_list_path = existing_capture(raw_root, game_code, "entry_list")
    if entry_list_path is None:
        msg = (
            f"no archived raw capture found at {raw_root / game_code / 'entry_list.html'} "
            "-- run online sync (or copy a real raw/<game_code>/entry_list.html capture into place) first"
        )
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=msg)
        conn.commit(); conn.close()
        return _fail(result, "entry_list", "error", msg)

    entry_html = entry_list_path.read_text(encoding="utf-8")
    from klpga.parsers.entry_list_parser import parse_entry_list_html, parse_entry_summary
    summary = parse_entry_summary(entry_html)
    parsed = parse_entry_list_html(entry_html)
    match_result = match_entries_to_player_master(conn, parsed.rows)
    collected_at = _now_iso()
    entry_rows = build_tournament_entry_rows(
        game_code=game_code, entry_rows=parsed.rows, source=config.ENTRY_LIST_ENDPOINT, collected_at=collected_at,
    )
    for row in entry_rows:
        upsert_tournament_entry(conn, row)
    conn.commit()

    entry_snapshot_path = normalized_dir / "ENTRY_SNAPSHOT.json"
    entry_snapshot = {
        "game_code": game_code,
        "collected_at": collected_at,
        "source": config.ENTRY_LIST_ENDPOINT,
        "page_summary_counts": summary.counts,
        "parsed_row_count": len(parsed.rows),
        "unparsed_row_count": parsed.unparsed_row_count,
        "duplicate_player_codes": match_result.duplicate_player_codes,
        "matched_count": match_result.matched_count,
        "unmatched_count": match_result.unmatched_count,
        "records": [
            {
                "player_code": r.player_code, "player_name": r.player_name, "nationality": r.nationality,
                "qualification_category": r.qualification_category, "qualification_reason": r.qualification_reason,
            }
            for r in parsed.rows
        ],
    }
    entry_snapshot_path.write_text(json.dumps(entry_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    _copy_to_content(content_root, game_code, "ENTRY_SNAPSHOT", entry_snapshot)

    result.add(StageResult("entry_list", "success", {
        "parsed_row_count": len(parsed.rows), "unparsed_row_count": parsed.unparsed_row_count,
        "matched_count": match_result.matched_count, "unmatched_count": match_result.unmatched_count,
    }))

    # ---------------------------------------------------------------
    # STAGE: K-Ranking -- read both archived pages back from raw/
    # ---------------------------------------------------------------
    period_path = existing_capture(raw_root, game_code, "kranking_period")
    full_path = existing_capture(raw_root, game_code, "kranking_full_table")
    if period_path is None or full_path is None:
        result.add(StageResult(
            "kranking", "skipped",
            error_message=(
                f"no archived raw capture for kranking_period/kranking_full_table under {raw_root / game_code} "
                "-- run online sync first"
            ),
        ))
    else:
        try:
            kr = _load_kranking_module()
            combined = kr.combine_official_evidence(period_path, full_path, _now_iso())
            kranking_path = normalized_dir / "KRANKING_TOP120.json"
            kranking_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
            _copy_to_content(content_root, game_code, "KRANKING_TOP120", combined)
            result.add(StageResult("kranking", "success", {
                "ranking_week": combined["ranking_week"], "full_population_count": combined["full_population_count"],
            }))
        except Exception as exc:  # noqa: BLE001 -- crosscheck failure, malformed capture, etc: real, not fabricated past
            result.add(StageResult("kranking", "error", error_message=str(exc)))

    # ---------------------------------------------------------------
    # STAGE: Grouping / tee-times -- read grouping.html back from raw/
    # and reuse klpga.parsers.group_page_parser.parse_round_grouping,
    # the real, already-confirmed parser for this page (see that
    # module's docstring: tests/fixtures/group_page_sample.html is a
    # byte-faithful slice of a real capture). This parser was never
    # wired into ANY sync stage before (online or offline) -- unlike
    # course/history_record/pin_placement (no parser exists for those
    # anywhere in this repo), grouping's gap was a missing adapter, not
    # a missing parser, so it is wired here rather than reimplemented.
    # Non-blocking like kranking: grouping data only exists once a
    # round has actually been grouped, which can lag "pre" entirely.
    # ---------------------------------------------------------------
    grouping_path = existing_capture(raw_root, game_code, "grouping")
    if grouping_path is None:
        result.add(StageResult(
            "grouping", "skipped",
            error_message=f"no archived raw capture found at {raw_root / game_code / 'grouping.html'} -- run online sync first",
        ))
    else:
        grouping_html = grouping_path.read_text(encoding="utf-8")
        rounds_grouped: dict[int, list[dict]] = {}
        for rnd in (1, 2, 3, 4):
            try:
                rows = parse_round_grouping(grouping_html, rnd)
            except ValueError:
                continue  # that round not published yet on this capture -- real, expected, never fabricated
            rounds_grouped[rnd] = [asdict(r) for r in rows]

        if not rounds_grouped:
            result.add(StageResult(
                "grouping", "error",
                error_message=(
                    "grouping.html was archived but no round (1-4) tab-pane parsed -- this capture's "
                    "structure does not match group_page_parser's confirmed shape"
                ),
            ))
        else:
            grouping_out_path = normalized_dir / "GROUPING.json"
            grouping_payload = {"game_code": game_code, "rounds": rounds_grouped}
            grouping_out_path.write_text(json.dumps(grouping_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            _copy_to_content(content_root, game_code, "GROUPING", grouping_payload)
            result.add(StageResult("grouping", "success", {
                "rounds_present": sorted(rounds_grouped.keys()),
                "player_counts": {r: len(rows) for r, rows in rounds_grouped.items()},
            }))

    # ---------------------------------------------------------------
    # STAGE "results" (opt-in only): round leaderboard, read back from
    # raw/<game_code>/round_leaderboard_r<n>.html. The "final round" is
    # discovered the same way run_sync's own discover_final_round does
    # in spirit (the highest round number with real data) -- just
    # discovered from what's actually archived on disk instead of
    # probed live, since there is no network here to probe with.
    # ---------------------------------------------------------------
    if stage == "results":
        game_dir = raw_root / game_code
        archived_rounds = sorted(
            int(p.stem.rsplit("_r", 1)[1])
            for p in (game_dir.glob("round_leaderboard_r*.html") if game_dir.is_dir() else [])
        )
        if not archived_rounds:
            result.add(StageResult(
                "leaderboard", "error",
                error_message=(
                    f"no archived round_leaderboard_r<n>.html captures found under {game_dir} "
                    "-- run online sync first"
                ),
            ))
        else:
            rounds_data = {}
            for rnd in archived_rounds:
                html = (game_dir / f"round_leaderboard_r{rnd}.html").read_text(encoding="utf-8")
                rounds_data[rnd] = parse_round_leaderboard_html(html, game_code=game_code, round_number=rnd)
            merged = merge_player_rows(rounds_data)
            final_round = max(rounds_data.keys())
            player_rows, player_event_rows, player_round_rows = build_rows(
                game_code, season, match.game_code, merged, final_round
            )
            for row in player_rows:
                upsert_player(conn, row)
            for row in player_event_rows:
                upsert_player_event(conn, row)
            for row in player_round_rows:
                upsert_player_round(conn, row)
            conn.commit()
            winner_score = resolve_winner_score(player_event_rows, match.winner_code)
            if winner_score is not None:
                update_tournament_winner_score(conn, match.game_code, winner_score)
                conn.commit()

            leaderboard_path = normalized_dir / "LEADERBOARD.json"
            leaderboard_path.write_text(
                json.dumps({"game_code": game_code, "final_round": final_round, "records": player_event_rows}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _copy_to_content(content_root, game_code, "LEADERBOARD", {"game_code": game_code, "final_round": final_round, "records": player_event_rows})
            result.add(StageResult("leaderboard", "success", {
                "final_round": final_round, "player_count": len(player_rows), "winner_score": winner_score,
            }))

    finish_collection_run(conn, run_id, status="success" if result.ok else "error", finished_at=_now_iso())
    conn.commit()
    conn.close()
    return result


def _fail(result: SyncResult, stage_name: str, status: str, message: str) -> SyncResult:
    result.add(StageResult(stage_name, status, error_message=message))
    return result


def _try_archive(raw_root: Path, game_code: str, label: str, content, source_url: str, extension: str):
    try:
        return archive_raw(raw_root, game_code, label, content, source_url, extension)
    except RawCaptureAlreadyExists:
        # A raw capture already exists for this exact (game_code, label)
        # -- write-once per OPERATING_RULES.md; re-running sync for the
        # same gameCode still needs the already-archived path back so
        # downstream normalize/kranking steps can read it.
        from klpga.neo_reader.raw_archive import existing_capture
        existing = existing_capture(raw_root, game_code, label)
        from klpga.neo_reader.raw_archive import RawCapture
        import hashlib as _hashlib
        text = existing.read_text(encoding="utf-8")
        return RawCapture(
            label=label, path=existing, sha256=_hashlib.sha256(text.encode("utf-8")).hexdigest(),
            byte_count=len(text.encode("utf-8")), source_url=source_url, fetched_at="(pre-existing capture)",
        )


def _copy_to_content(content_root: Path, game_code: str, name: str, payload: dict) -> None:
    """Also writes into content/website_v2/<game_code>_<NAME>.json,
    matching this repo's existing naming convention (see e.g.
    HANA_2026090002_ENTRY_SNAPSHOT.json) so the already-established
    139/151/160/174/181/156 build scripts can read NEO Sync's output
    with the same file-naming pattern they already expect."""
    content_root.mkdir(parents=True, exist_ok=True)
    (content_root / f"{game_code}_{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
