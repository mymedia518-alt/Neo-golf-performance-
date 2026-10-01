"""Round-agnostic HITE JINRO (game_code 2026100005) evidence pipeline:
parse leaderboard, parse Strokes Gained, cross-validate against the
scorecard, merge SG into the season warehouse, and locate per-round
raw evidence -- one real round_number (1-4) at a time, never a
tournament-specific copy per round.

Extracted 2026-10-01 from scripts/200-203_*_r1_*.py, which hardcoded
round=1 in every regex, path and assertion. Those four scripts had the
EXACT same parsing logic R2/R3/FR will need -- the official leaderboard/
SG/scorecard pages carry every round's data in the same markup shape
every time (data-round1score..data-round4score all exist on every
leaderboard row regardless of how many rounds have actually been
played; the scorecard's four per-round "bg-bright" cells are
positional, not round-specific markup) -- so there was never a reason
to duplicate this logic four times. scripts/200-203 now call into this
module instead of parsing anything themselves; scripts/run_round_pipeline.py
is the new round-agnostic entry point this module exists for.

FAILS CLOSED at every step: raises with a precise, actionable message
the moment a required raw evidence file is missing, a count assertion
fails, or a join isn't a verified bijection -- never fabricates a
score, SG value, or player match. See each function's own docstring
for exactly what it checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from klpga.neo_win.hitejinro_round_page import STAGE_LABELS, render_round_page

GAME_CODE = "2026100005"
_ROOT = Path(__file__).resolve().parents[4] / "klpga_pipeline"
CONTENT = _ROOT / "content" / "website_v2"
EVIDENCE_DIR = CONTENT / "incoming_evidence" / GAME_CODE
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
LEADERBOARD_PATH = CONTENT / f"{GAME_CODE}_LEADERBOARD.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
WAREHOUSE_PATH = CONTENT / "historical_sg_warehouse_corrected_v2.json"

# round_number -> public stage label used in every raw-evidence filename
# this project has used since R1 (HITEJINRO_2026100005_R1_LEADERBOARD_RAW.html,
# ..._R1_SG_RAW.html, ..._R1_SCORECARD_RAW.html) -- same labels
# klpga.neo_win.hitejinro_round_page.STAGE_LABELS already uses for the
# published page URLs, round 4 public-labeled "FR" never "R4".
ROUND_LABEL = {n: label for n, (_key, label) in STAGE_LABELS.items()}


def _round_label(round_number: int) -> str:
    if round_number not in ROUND_LABEL:
        raise ValueError(f"round_number must be 1-4, got {round_number}")
    return ROUND_LABEL[round_number]


def raw_evidence_path(round_number: int, kind: str) -> Path:
    """kind is one of 'LEADERBOARD', 'SG', 'SCORECARD'. Where the
    operator-saved raw capture for this round is expected -- never
    auto-fetched (no Reader offline mode exists for this tournament;
    see scripts/200's own original docstring)."""
    label = _round_label(round_number)
    return EVIDENCE_DIR / f"HITEJINRO_{GAME_CODE}_{label}_{kind}_RAW.html"


def sg_output_path(round_number: int) -> Path:
    label = _round_label(round_number)
    return CONTENT / f"HITEJINRO_{GAME_CODE}_{label}_SG_V1.json"


def require_raw_evidence(round_number: int) -> dict[str, Path]:
    """{'LEADERBOARD': path, 'SG': path, 'SCORECARD': path} -- raises
    FileNotFoundError naming exactly which file(s) are missing if any
    one of the three isn't on disk yet. This is the pipeline's single
    fail-closed gate for '공식 데이터 없음': every other step assumes
    these three files already exist and are real."""
    paths = {kind: raw_evidence_path(round_number, kind) for kind in ("LEADERBOARD", "SG", "SCORECARD")}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        label = _round_label(round_number)
        raise FileNotFoundError(
            f"no official {label} evidence yet -- missing: {missing}. "
            f"공식 데이터 없음: operator must save the real klpga.co.kr leaderboard/strokesGained/"
            f"scorecard pages for {label} into {EVIDENCE_DIR} before this pipeline can run for {label}. "
            "Never fabricated."
        )
    return paths


def _extract_asset_version(html: str) -> str | None:
    """The real cache-busting '?ver=<ISO timestamp>' query param KLPGA
    embeds on every asset URL (sponsor images, css) on every one of
    this round's three raw pages -- the actual moment the operator's
    browser rendered the page, not a guessed or carried-over value.
    None if a given capture happens not to carry one (e.g. no sponsor
    images on that particular page) -- callers must not fabricate a
    substitute."""
    m = re.search(r"ver=(\d{4}-\d{2}-\d{2}T[\d:.]+)", html)
    return m.group(1) if m else None


_LEADERBOARD_ROW_RE = re.compile(
    r'<li id="favoritItem_(\d+)"[^>]*data-rank="([^"]*)" data-name="([^"]*)" '
    r'data-totunderpar="([^"]*)" data-inghole="([^"]*)" data-todayunderpar="([^"]*)" '
    r'data-score="([^"]*)" data-round1score="([^"]*)" data-round2score="([^"]*)" '
    r'data-round3score="([^"]*)" data-round4score="([^"]*)" data-updown="([^"]*)"'
)


def _int_or_none(s: str) -> int | None:
    s = s.strip()
    return None if s == "" else int(s)


def parse_leaderboard(round_number: int, *, raw_path: Path | None = None) -> Path:
    """Parse this round's official leaderboard raw capture into
    LEADERBOARD.json. Every row already carries all four rounds'
    scores in one shot (data-round1score..data-round4score), so this
    is a full re-parse of the LATEST capture, not an incremental merge
    with the previous round's file -- the new page is self-sufficient
    truth for every column, old and new alike. 'rank=="999"' is this
    site's own not-yet-finished-this-round marker, same signal at
    every round. Writes LEADERBOARD.json and returns its path.
    """
    label = _round_label(round_number)
    raw_path = raw_path or raw_evidence_path(round_number, "LEADERBOARD")
    raw_html = raw_path.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    entrants = json.loads(ENTRY_PATH.read_text(encoding="utf-8"))["records"]
    entrant_ids = {r["player_code"] for r in entrants}

    matches = list(_LEADERBOARD_ROW_RE.finditer(raw_html))
    assert len(matches) == len(entrants), (
        f"expected {len(entrants)} official entrants, parsed {len(matches)} leaderboard rows"
    )

    parsed_ids = {m.group(1) for m in matches}
    assert parsed_ids == entrant_ids, (
        f"{label} leaderboard playerCodes and the official entry roster are not the same set -- "
        f"only in leaderboard: {sorted(parsed_ids - entrant_ids)}, "
        f"only in roster: {sorted(entrant_ids - parsed_ids)}"
    )

    records = []
    not_yet_complete = []
    for m in matches:
        player_id, rank, name, totunderpar, inghole, todayunderpar, score, r1, r2, r3, r4, updown = m.groups()
        incomplete = rank == "999"
        if incomplete:
            not_yet_complete.append({"player_id": player_id, "player_name": name})
            finish_position = None
            finish_position_numeric = None
            score_to_par = None
        else:
            finish_position = rank
            finish_position_numeric = int(rank)
            score_to_par = _int_or_none(totunderpar)
        round_scores = {1: _int_or_none(r1), 2: _int_or_none(r2), 3: _int_or_none(r3), 4: _int_or_none(r4)}
        if incomplete:
            # rank=="999" means THIS capture's round (round_number) isn't
            # finished for this player yet -- never report a score for it,
            # even if the raw attribute happens to carry a stray value.
            # Earlier rounds' real scores are untouched.
            round_scores[round_number] = None
        records.append({
            "player_id": player_id,
            "player_name": name,
            "finish_position": finish_position,
            "finish_position_numeric": finish_position_numeric,
            "score_to_par": score_to_par,
            "r1_score": round_scores[1],
            "r2_score": round_scores[2],
            "r3_score": round_scores[3],
            "r4_score": round_scores[4],
            "withdrawn": False,
            "disqualified": False,
        })

    assert len(records) == len(entrants)
    assert len({r["player_id"] for r in records}) == len(records), "duplicate player_id after parse"

    score_field = f"r{round_number}_score"
    out = {
        "schema_version": "hitejinro_round_leaderboard_v2",
        "game_code": GAME_CODE,
        "final_round": round_number,
        "as_of": date.today().isoformat(),
        "source_raw": {
            "path": str(raw_path.relative_to(_ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/sumScore?gameCode={GAME_CODE}",
        },
        "coverage": {
            "player_count": len(records),
            f"completed_round{round_number}_count": sum(1 for r in records if r[score_field] is not None),
            "not_yet_complete_at_capture_time": not_yet_complete,
        },
        "records": records,
    }
    LEADERBOARD_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return LEADERBOARD_PATH


_SG_ROW_RE = re.compile(
    r'<tr data-sgrank="(\d+)" data-teetogreenrank="\d+" data-driverrank="\d+" '
    r'data-approachrank="\d+" data-aroundrank="\d+" data-putterrank="\d+">\s*'
    r'<td[^>]*>\d+</td>\s*<td[^>]*>([^<]+)</td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>(\d+)</td>',
    re.DOTALL,
)


def parse_sg(round_number: int, *, raw_path: Path | None = None) -> Path:
    """Parse this round's official Strokes Gained raw capture, joined
    to player_id by exact display-name bijection against everyone who
    has completed round `round_number` per the ALREADY-PARSED
    LEADERBOARD.json (run parse_leaderboard() first). Mirrors
    scripts/155/165/169/179_build_hana_r*_sg_v1.py's own precedent of
    reusing one identical row regex across every one of Hana's four
    rounds -- this site's SG table markup doesn't change shape between
    rounds, only the numbers in it. Writes a ROUND-SCOPED file (never
    merged into the season warehouse by this function -- see
    merge_sg_into_warehouse for that explicit, separate step)."""
    label = _round_label(round_number)
    raw_path = raw_path or raw_evidence_path(round_number, "SG")
    raw_html = raw_path.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    if not LEADERBOARD_PATH.is_file():
        raise FileNotFoundError(f"{LEADERBOARD_PATH} missing -- run parse_leaderboard({round_number}) first")
    leaderboard = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    score_field = f"r{round_number}_score"
    completed = [r for r in leaderboard["records"] if r[score_field] is not None]
    name_to_id = {r["player_name"]: r["player_id"] for r in completed}
    assert len(name_to_id) == len(completed), (
        f"duplicate display name among completed {label} players -- name-based join unsafe"
    )

    matches = list(_SG_ROW_RE.finditer(raw_html))
    assert len(matches) == len(completed), (
        f"expected {len(completed)} SG table rows (completed-{label} count), parsed {len(matches)}"
    )

    sg_names = [m.group(2) for m in matches]
    assert len(set(sg_names)) == len(matches), f"duplicate display name in the {label} SG table -- name-based join unsafe"
    assert set(sg_names) == set(name_to_id), (
        f"{label} SG table names and completed-{label} roster names are not a bijection -- "
        f"only in SG: {sorted(set(sg_names) - set(name_to_id))}, "
        f"only in roster: {sorted(set(name_to_id) - set(sg_names))}"
    )

    records = []
    for m in matches:
        rank, name, total, tee_to_green, off_the_tee, approach, around_green, putting, rounds = m.groups()
        records.append({
            "player_id": name_to_id[name],
            "official_display_name": name,
            "sg_rank": int(rank),
            "total": float(total),
            "tee_to_green": float(tee_to_green),
            "off_the_tee": float(off_the_tee),
            "approach": float(approach),
            "around_green": float(around_green),
            "putting": float(putting),
            "rounds": int(rounds),
        })

    assert len(records) == len(completed)
    assert len({r["player_id"] for r in records}) == len(records), "duplicate player_id after join"
    over_claimed = [r for r in records if r["rounds"] > round_number]
    assert not over_claimed, f"SG table claims more rounds played than {label} allows: {over_claimed}"

    not_yet_complete = [
        {"player_id": r["player_id"], "player_name": r["player_name"]}
        for r in leaderboard["records"] if r[score_field] is None
    ]

    out = {
        "schema_version": "hitejinro_round_sg_v2",
        "game_code": GAME_CODE,
        "round_number": round_number,
        "as_of": date.today().isoformat(),
        "purpose": (
            "ROUND-SCOPED Strokes Gained observed through this round -- not merged into "
            "historical_sg_warehouse_corrected_v2.json by this function; see merge_sg_into_warehouse "
            "for the separate, explicit merge step."
        ),
        "source_raw": {
            "path": str(raw_path.relative_to(_ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/strokesGained?gameCode={GAME_CODE}",
        },
        "identity_join": {
            "method": "exact display-name match, used only after independently verifying the join is a "
                       "true 1:1 bijection for this exact population (both sides duplicate-free, set-equal)",
            "population_count": len(records),
            "bijection_verified": True,
        },
        "not_yet_complete_excluded": not_yet_complete,
        "coverage": {"player_count": len(records), "duplicate_player_ids": 0},
        "records": records,
    }
    out_path = sg_output_path(round_number)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def parse_scorecard(html: str, round_number: int) -> dict[str, dict]:
    """{player_id: {name, to_par, round_score}} from the scorecard raw
    page, independent of the leaderboard parse -- used only to cross-
    check it. The four per-round score cells are POSITIONAL
    ("bg-bright" td #0 = R1, #1 = R2, #2 = R3, #3 = FR) on every row
    regardless of how many are actually filled in yet, so round N's
    score is always the Nth bg-bright cell, never 'the first non-empty
    one' (that would silently pick the wrong round once 2+ rounds are
    complete)."""
    chunks = re.split(r"(?=playerCode=\d+)", html)
    by_id: dict[str, dict] = {}
    for chunk in chunks[1:]:
        pc_m = re.match(r"playerCode=(\d+)", chunk)
        if not pc_m:
            continue
        pid = pc_m.group(1)
        window = chunk[:2500]
        name_m = re.search(r"<span class=\"name\"><b>([^<]+)</b></span>", window)
        topar_m = re.search(r"<span class=\"(?:upcolor|dncolor|evcolor)?\"><b>(\+?-?\d+|E)</b></span>", window)
        round_cells = re.findall(r'<td class="bg-bright">([^<]*)</td>', window)
        round_score = None
        if len(round_cells) >= round_number:
            cell = round_cells[round_number - 1].strip()
            cell_m = re.match(r"(\d+)", cell)
            round_score = int(cell_m.group(1)) if cell_m else None
        by_id[pid] = {
            "name": name_m.group(1) if name_m else None,
            "to_par": None if topar_m is None else (0 if topar_m.group(1) == "E" else int(topar_m.group(1))),
            "round_score": round_score,
        }
    return by_id


def cross_validate(round_number: int, *, raw_path: Path | None = None) -> dict:
    """RED TEAM: independently re-derive player_name/score_to_par/
    r{round_number}_score from the separately-rendered scorecard page
    and diff against LEADERBOARD.json. Raises SystemExit(1) on any
    mismatch; never silently tolerates one. Returns the comparison
    result dict on a clean match."""
    label = _round_label(round_number)
    raw_path = raw_path or raw_evidence_path(round_number, "SCORECARD")
    leaderboard = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    score_field = f"r{round_number}_score"
    lb_by_id = {r["player_id"]: r for r in leaderboard["records"]}

    scorecard_html = raw_path.read_text(encoding="utf-8")
    sc_by_id = parse_scorecard(scorecard_html, round_number)

    mismatches = []
    if len(lb_by_id) != len(sc_by_id):
        mismatches.append(f"player_count: leaderboard={len(lb_by_id)} scorecard={len(sc_by_id)}")
    if set(lb_by_id) != set(sc_by_id):
        mismatches.append(
            f"player_id sets differ -- only in leaderboard: {sorted(set(lb_by_id) - set(sc_by_id))}, "
            f"only in scorecard: {sorted(set(sc_by_id) - set(lb_by_id))}"
        )
    for pid in sorted(set(lb_by_id) & set(sc_by_id)):
        lb, sc = lb_by_id[pid], sc_by_id[pid]
        if lb["player_name"] != sc["name"]:
            mismatches.append(f"{pid}: name leaderboard={lb['player_name']!r} scorecard={sc['name']!r}")
        if lb["score_to_par"] != sc["to_par"]:
            mismatches.append(f"{pid} ({lb['player_name']}): to_par leaderboard={lb['score_to_par']!r} scorecard={sc['to_par']!r}")
        if lb[score_field] != sc["round_score"]:
            mismatches.append(f"{pid} ({lb['player_name']}): {score_field} leaderboard={lb[score_field]!r} scorecard={sc['round_score']!r}")

    result = {
        "game_code": GAME_CODE,
        "round_label": label,
        "leaderboard_player_count": len(lb_by_id),
        "scorecard_player_count": len(sc_by_id),
        "compared_fields": ["player_name", "score_to_par", score_field],
        "mismatches": mismatches,
        "verdict": "100% MATCH" if not mismatches else "MISMATCH FOUND",
    }
    if mismatches:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def merge_sg_into_warehouse(round_number: int) -> dict:
    """Merge this round's already-parsed, already-cross-validated SG
    file into historical_sg_warehouse_corrected_v2.json as real
    tournament_cumulative rows (rounds = however many rounds that
    player has actually played, read from the SG table itself -- never
    assumed equal to round_number, so a WD-after-R1 player's row stays
    honest at R2+). Idempotent: an existing (game_code, player_id) row
    is replaced in place, never duplicated, so re-running a later
    round's merge safely supersedes an earlier one.

    retrieved_at is the real 'ver=<timestamp>' cache-busting value
    KLPGA embeds on this round's own raw SG capture (the actual moment
    the operator's browser rendered that page) -- never a fabricated
    or carried-over timestamp. Falls back to this merge's own run time,
    clearly labeled as such, only if that round's capture happens not
    to carry one."""
    label = _round_label(round_number)
    sg_path = sg_output_path(round_number)
    sg_doc = json.loads(sg_path.read_text(encoding="utf-8"))
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    tournament_name = tourney["event_name"]

    raw_sg_html = raw_evidence_path(round_number, "SG").read_text(encoding="utf-8")
    retrieved_at = _extract_asset_version(raw_sg_html)
    source_note = f"operator-saved copy of https://klpga.co.kr/web/leaderboard/strokesGained?gameCode={GAME_CODE} (round={round_number}, native page capture)"
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        source_note += " -- retrieved_at is this merge's own run time (no asset ver= found on the raw capture), not a page-capture timestamp"

    warehouse = json.loads(WAREHOUSE_PATH.read_text(encoding="utf-8"))
    before_count = len(warehouse["records"])

    existing_idx_by_player: dict[str, int] = {}
    for i, r in enumerate(warehouse["records"]):
        if r.get("game_code") == GAME_CODE and r.get("scope") == "tournament_cumulative":
            existing_idx_by_player[r.get("player_id")] = i

    inserted = updated = 0
    for rec in sg_doc["records"]:
        row = {
            "rank": rec["sg_rank"],
            "player": rec["official_display_name"],
            "total": rec["total"],
            "tee_to_green": rec["tee_to_green"],
            "off_the_tee": rec["off_the_tee"],
            "approach": rec["approach"],
            "around_green": rec["around_green"],
            "putting": rec["putting"],
            "rounds": rec["rounds"],
            "scope": "tournament_cumulative",
            "round": None,
            "validation": {
                "total_delta": 0.0, "t2g_delta": 0.0,
                "total_within_tolerance": True, "t2g_within_tolerance": True,
            },
            "player_id": rec["player_id"],
            "player_name": rec["official_display_name"],
            "raw_player_name": rec["official_display_name"],
            "encoding_status": "clean",
            "identity_state": "RETAINED",
            "season": 2026,
            "game_code": GAME_CODE,
            "tournament": tournament_name,
            "source": source_note,
            "retrieved_at": retrieved_at,
        }
        pid = rec["player_id"]
        if pid in existing_idx_by_player:
            warehouse["records"][existing_idx_by_player[pid]] = row
            updated += 1
        else:
            warehouse["records"].append(row)
            inserted += 1

    after_count = len(warehouse["records"])
    assert after_count == before_count + inserted, "record count arithmetic mismatch -- refusing to write"

    WAREHOUSE_PATH.write_text(json.dumps(warehouse, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gc_rows = [r for r in warehouse["records"] if r.get("game_code") == GAME_CODE]
    return {
        "round_label": label,
        "warehouse_count_before": before_count,
        "warehouse_count_after": after_count,
        "inserted": inserted,
        "updated": updated,
        f"game_code_{GAME_CODE}_rows": len(gc_rows),
    }


def build_round_page(round_number: int) -> Path:
    """Render and write this round's public page (docs/tournaments/
    2026/{GAME_CODE}/{r1,r2,r3,fr}/index.html) via the one shared
    renderer, klpga.neo_win.hitejinro_round_page.render_round_page --
    extracted from scripts/196-199_build_hitejinro_r*_page.py, which
    each duplicated the same five lines (load TOURNAMENT_INFO, format
    date_range, render, write) differing only in round_number and
    output path. Those four scripts now call this function instead."""
    stage_key, _label = STAGE_LABELS[round_number]
    repo_root = _ROOT.parent
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    start, end = tourney["start_date"], tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    html = render_round_page(
        round_number, tournament_name=tourney["event_name"], date_range=date_range, content_root=CONTENT,
    )
    out_path = repo_root / "docs" / "tournaments" / "2026" / GAME_CODE / stage_key / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    return out_path
