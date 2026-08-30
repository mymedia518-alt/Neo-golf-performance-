"""Reusable core for collecting ONE KLPGA tournament end-to-end —
extracted from scripts/04_collect_single_tournament.py so a second
caller (scripts/final_close_preflight.py) never re-implements the same
getGameList -> roundLeaderboard -> upsert flow. scripts/04's CLI now
calls this function; its printed output is unchanged for the case
where no new flag is passed (force_refresh_rounds=frozenset(),
expected_final_round=None), matching the project's existing "thin CLI
wrapper around an importable core" pattern (run_beta001_r3_update.py,
47_record_final_result.py, evaluate_r3_to_r4.py, ...).

======================================================================
THE EXPECTED-FINAL-ROUND SAFETY GATE
======================================================================
klpga.collectors.leaderboard.discover_final_round probes DOWNWARD from
config.PROBE_MAX_ROUNDS using the on-disk HTTP cache by default. If
this project (or any earlier run) ever fetched round N for this
game_code BEFORE round N had actually been played, the site's real
response was an empty leaderboard — and PoliteHttpClient cached that
empty response. A later run, once round N has genuinely concluded,
would keep silently discovering an EARLIER round as "the final round"
unless the caller either (a) forces a fresh fetch for round N via
`force_refresh_rounds`, or (b) explicitly states what round it expects
to reach via `expected_final_round`.

This module does NOT prevent (a) from being skipped — the caller
decides whether to force-refresh. What it DOES guarantee is: if
`expected_final_round` is given and the round actually discovered
falls short of it, `collect_and_persist_tournament` returns
`STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND` instead of
`STATUS_SUCCESS` — a caller (a CLI script) must treat that as a loud
failure, never print a normal "collected successfully" message for
it. Whatever real rounds WERE found are still persisted (upserting
genuinely-collected R1..R(N-1) data is not fabrication and is useful
on its own); only the SUCCESS framing is withheld.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Optional

import requests

from klpga.collectors.aggregate import build_rows, merge_player_rows, resolve_winner_score
from klpga.collectors.leaderboard import collect_all_rounds_for_game
from klpga.collectors.tournaments import fetch_game_list
from klpga.db.upsert import (
    finish_collection_run,
    start_collection_run,
    update_tournament_winner_score,
    upsert_player,
    upsert_player_event,
    upsert_player_round,
    upsert_tournament,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError

STATUS_SUCCESS = "SUCCESS"
STATUS_GAME_CODE_NOT_FOUND = "GAME_CODE_NOT_FOUND"
STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND = "HARD_STOP_BELOW_EXPECTED_FINAL_ROUND"


@dataclass
class SingleTournamentCollectionResult:
    status: str
    game_code: str
    reason: Optional[str] = None
    match: object = None  # klpga.collectors.tournaments.TournamentListing, or None
    rounds_data: dict = field(default_factory=dict)
    """{round_number: [PlayerRoundRow, ...]}, exactly as fetched — only
    the rounds discover_final_round/collect_all_rounds_for_game actually
    reached, never padded with a guessed round."""
    final_round: Optional[int] = None
    expected_final_round: Optional[int] = None
    player_rows: list = field(default_factory=list)
    player_event_rows: list = field(default_factory=list)
    player_round_rows: list = field(default_factory=list)
    winner_score: Optional[str] = None


def collect_and_persist_tournament(
    conn: sqlite3.Connection,
    client: PoliteHttpClient,
    season: int,
    game_code: str,
    *,
    force_refresh_rounds: frozenset[int] = frozenset(),
    expected_final_round: Optional[int] = None,
    collection_run_source: str = "collect_and_persist_tournament",
) -> SingleTournamentCollectionResult:
    """Real network fetch (getGameList + roundLeaderboard) + real DB
    upsert (player_master / player_event / player_round). Never
    fabricates a row. `force_refresh_rounds` and `expected_final_round`
    default to today's exact 04_collect_single_tournament.py behavior
    (empty set / None) — passing neither changes nothing.

    Commits the DB transaction itself (matching
    scripts/04_collect_single_tournament.py's existing behavior) so a
    caller can immediately read back what was just written."""
    run_id = start_collection_run(conn, collection_run_source, target=game_code, started_at=_now_iso())
    conn.commit()

    try:
        listings = fetch_game_list(client, season=season, tour_type=_tour_type_regular())
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        raise
    except requests.exceptions.RequestException as exc:
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        raise

    match = next((entry for entry in listings if entry.game_code == game_code), None)
    if match is None:
        finish_collection_run(
            conn, run_id, status="error", finished_at=_now_iso(),
            error_message=f"gameCode {game_code} not found in season={season} tourType=RE list",
        )
        conn.commit()
        return SingleTournamentCollectionResult(
            status=STATUS_GAME_CODE_NOT_FOUND, game_code=game_code,
            reason=f"gameCode={game_code!r} not found in season={season} tourType=RE getGameList "
                   f"response ({len(listings)} entries returned).",
        )

    tournament_row = {
        "event_id": match.game_code,
        "game_code": match.game_code,
        "event_name": match.game_title,
        "season": match.season,
        "start_date": match.start_date.isoformat() if match.start_date else match.start_date_raw,
        "end_date": match.end_date.isoformat() if match.end_date else match.end_date_raw,
        "course_name": match.course_text,
        "course_location": None,
        "par": None,
        "course_yards": None,
        "rounds_scheduled": None,
        "rounds_completed": None,
        "field_size": None,
        "winner": match.winner_name,
        "winner_score": None,
        "official_url": None,
    }
    upsert_tournament(conn, tournament_row)
    conn.commit()

    try:
        rounds_data = collect_all_rounds_for_game(
            client, game_code, force_refresh_rounds=force_refresh_rounds
        )
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        raise
    except requests.exceptions.RequestException as exc:
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        raise

    merged = merge_player_rows(rounds_data)
    final_round = max(rounds_data.keys())
    player_rows, player_event_rows, player_round_rows = build_rows(
        game_code, match.season, match.game_code, merged, final_round
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

    result = SingleTournamentCollectionResult(
        status=STATUS_SUCCESS, game_code=game_code, match=match,
        rounds_data=rounds_data, final_round=final_round, expected_final_round=expected_final_round,
        player_rows=player_rows, player_event_rows=player_event_rows, player_round_rows=player_round_rows,
        winner_score=winner_score,
    )

    if expected_final_round is not None and final_round < expected_final_round:
        finish_collection_run(
            conn, run_id, status="error", finished_at=_now_iso(), rows_written=len(player_rows),
            error_message=(
                f"HARD_STOP_BELOW_EXPECTED_FINAL_ROUND: discovered final_round={final_round} < "
                f"expected_final_round={expected_final_round} (real R1..final_round data was still "
                "persisted; the expected round was never reached) -- collection_runs.status is 'error' "
                "here because 'hard_stop' is not a valid terminal status; see error_message for the "
                "real classification."
            ),
        )
        conn.commit()
        result.status = STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND
        result.reason = (
            f"Collection discovered final_round={final_round}, but "
            f"expected_final_round={expected_final_round} was required. Rounds up to "
            f"{final_round} WERE persisted (this is real data, not withheld) — round "
            f"{expected_final_round} itself was never reached. This is the exact signature of a "
            f"stale-cache-hidden round (see klpga.collectors.leaderboard.collect_all_rounds_for_game's "
            f"force_refresh_rounds) — pass force_refresh_rounds/--force-refresh-round for "
            f"{expected_final_round} and re-run."
        )
        return result

    finish_collection_run(conn, run_id, status="success", finished_at=_now_iso(), rows_written=len(player_rows))
    conn.commit()
    return result


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _tour_type_regular() -> str:
    from klpga import config
    return config.TOUR_TYPE_REGULAR
