"""Task L (fix/kb-r2-official-cut-gate-20260911): REAL PRODUCTION VISUAL
QA FAILURE -- rendered-output regression against the actual real
gameCode=2026090003 artifacts.

The user visually verified the real, committed production R2 page
(docs/tournaments/2026/2026090003/r2/index.html at commit 39ba15e) and
found: every leaderboard rank effectively "T1" (including CUT players),
TOTAL always "--", 2R always "--" -- while SG and forecast probabilities
WERE correctly populated.

ROOT CAUSE (see klpga.neo_win.r2_real_page._total_to_par's own
docstring for the full trace): the renderer read `row.get(
"total_to_par")` and `row.get("round_to_par")`, but the REAL R2 freeze
schema (klpga.neo_win.r2_freeze, written by scripts/112) has NEVER
carried those field names -- every real row only ever has
`r1_score_to_par` and `r2_score_to_par`. So `total_to_par` was always
None for every real row, which made every player's rank sort key
identical -- hence the universal fake "T1".

WHY 168/168 EXISTING TESTS MISSED IT: every fixture in
tests/test_r2_real_page.py (before this fix) manually constructed
synthetic `records` using the WRONG field names (`round_to_par`/
`total_to_par`) -- i.e. exactly the shape the (buggy) renderer expected
-- so those tests were self-consistently testing a fictional contract
that the real collector/freeze writer never actually produces. No test
anywhere previously parsed ACTUAL rendered HTML and cross-checked it
against the REAL frozen evidence artifact -- this file is that missing
check.

Every test here reads the REAL, committed artifacts directly:
content/website_v2/2026090003_R2_FROZEN_EVIDENCE.json (the frozen
official R2 result) and the REAL, regenerated docs/tournaments/2026/
2026090003/r2/index.html (rebuilt with the fixed renderer against those
same real artifacts, never against a synthetic fixture)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
REAL_FREEZE_PATH = ROOT / "content" / "website_v2" / "2026090003_R2_FROZEN_EVIDENCE.json"
REAL_PAGE_PATH = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html"


@pytest.fixture(scope="module")
def real_freeze() -> dict:
    assert REAL_FREEZE_PATH.is_file(), "real committed R2 freeze artifact must exist"
    return json.loads(REAL_FREEZE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def real_html() -> str:
    assert REAL_PAGE_PATH.is_file(), "real regenerated R2 docs page must exist"
    return REAL_PAGE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendered_rows_by_player_id(real_html: str) -> dict[str, str]:
    """Parses every <tr data-player-id='...'>...</tr> block, keyed by
    the REAL player_id the renderer itself stamped on the row -- never
    joined by display name (invariant 9)."""
    body = real_html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = re.findall(r"<tr data-player-id='([^']+)'>((?:(?!</tr>).)*)</tr>", body)
    return {pid: row for pid, row in rows}


def _cell(row: str, label: str) -> str:
    m = re.search(rf"data-label='{label}'[^>]*>([^<]*)<", row)
    assert m is not None, f"missing data-label='{label}' cell in row"
    return m.group(1)


def _real_total_to_par(record: dict):
    r1 = record.get("r1_score_to_par")
    r2 = record.get("r2_score_to_par")
    if r1 is None or r2 is None:
        return None
    return float(r1) + float(r2)


def _expected_to_par_display(v) -> str:
    if v is None:
        return "—"
    n = int(v)
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


# ---------------------------------------------------------------------
# Population-scale sanity: the real page has exactly the real freeze's
# own population, and rendered fields are not universally empty/broken
# at population scale (the exact shape of the real production failure).
# ---------------------------------------------------------------------

def test_rendered_population_matches_real_freeze_exactly(real_freeze, rendered_rows_by_player_id):
    freeze_ids = {str(r["player_id"]) for r in real_freeze["records"]}
    assert set(rendered_rows_by_player_id) == freeze_ids
    assert len(rendered_rows_by_player_id) == real_freeze["observed_player_count"]


def test_rank_population_is_not_universally_t1_or_missing(real_freeze, rendered_rows_by_player_id):
    """The exact real production failure: every rank collapsed to a
    fake tied T1. A real leaderboard population must have real,
    distinct ranks across a meaningful fraction of ACTIVE/CUT players
    with real, complete scores."""
    active_or_cut_ids = [str(r["player_id"]) for r in real_freeze["records"] if r["status"] in ("ACTIVE", "CUT")]
    ranks = [_cell(rendered_rows_by_player_id[pid], "순위") for pid in active_or_cut_ids]
    distinct_ranks = set(ranks)
    assert len(distinct_ranks) > 10, f"rank population is far too uniform: {sorted(distinct_ranks)[:10]}..."
    assert ranks.count("T1") < len(ranks), "every player rendered as a fake tied T1 -- the real production bug"
    assert "1" in distinct_ranks or "T1" in distinct_ranks  # a real leader must exist


def test_total_and_2r_are_not_universally_empty_for_active_and_cut_players(real_freeze, rendered_rows_by_player_id):
    ids_with_complete_real_data = [
        str(r["player_id"]) for r in real_freeze["records"]
        if r["status"] in ("ACTIVE", "CUT") and r.get("r1_score_to_par") is not None and r.get("r2_score_to_par") is not None
    ]
    assert ids_with_complete_real_data, "test setup: real freeze must have some complete ACTIVE/CUT rows"
    totals = [_cell(rendered_rows_by_player_id[pid], "합계") for pid in ids_with_complete_real_data]
    twos = [_cell(rendered_rows_by_player_id[pid], "2R") for pid in ids_with_complete_real_data]
    assert totals.count("—") == 0, "TOTAL rendered empty for players with real, complete scores"
    assert twos.count("—") == 0, "2R rendered empty for players with real, complete scores"


# ---------------------------------------------------------------------
# Per-player spot checks: rendered rank/TOTAL/2R/status for REAL player
# identities, compared directly against the frozen official evidence --
# not merely "the HTML element exists".
# ---------------------------------------------------------------------

def test_every_active_or_cut_player_with_complete_data_has_the_exact_real_total_and_2r(real_freeze, rendered_rows_by_player_id):
    checked = 0
    for record in real_freeze["records"]:
        if record["status"] not in ("ACTIVE", "CUT"):
            continue
        pid = str(record["player_id"])
        expected_total = _real_total_to_par(record)
        expected_2r = record.get("r2_score_to_par")
        row = rendered_rows_by_player_id[pid]
        assert _cell(row, "합계") == _expected_to_par_display(expected_total), f"TOTAL mismatch for {record['player_name']} ({pid})"
        assert _cell(row, "2R") == _expected_to_par_display(expected_2r), f"2R mismatch for {record['player_name']} ({pid})"
        checked += 1
    assert checked > 50, "sanity: should have checked a real, population-scale number of players"


def test_every_player_with_missing_score_data_renders_empty_never_fabricated(real_freeze, rendered_rows_by_player_id):
    checked_any = False
    for record in real_freeze["records"]:
        if record.get("r1_score_to_par") is not None and record.get("r2_score_to_par") is not None:
            continue
        pid = str(record["player_id"])
        row = rendered_rows_by_player_id[pid]
        assert _cell(row, "합계") == "—", f"TOTAL fabricated for incomplete-data player {record['player_name']}"
        assert _cell(row, "2R") == "—" or record.get("r2_score_to_par") is not None
        assert _cell(row, "순위") == "—", f"rank fabricated for incomplete-data player {record['player_name']}"
        checked_any = True
    assert checked_any, "test setup: real freeze must have at least one incomplete-data row (e.g. the real WD player)"


def test_status_badge_matches_frozen_evidence_for_every_non_active_player(real_freeze, rendered_rows_by_player_id):
    checked = 0
    for record in real_freeze["records"]:
        if record["status"] == "ACTIVE":
            continue
        pid = str(record["player_id"])
        row = rendered_rows_by_player_id[pid]
        assert f"<span class='status-badge'>{record['status']}</span>" in row, f"status badge mismatch for {record['player_name']}"
        checked += 1
    assert checked > 0


def test_cut_players_never_share_the_active_leaders_rank(real_freeze, rendered_rows_by_player_id):
    """The exact real symptom: CUT players displayed as T1 alongside
    real leaders. A CUT player's real total must always be worse (a
    real, distinct rank number) than the field leader's, never equal to
    rank 1/T1 unless their own real score genuinely ties for the lead
    (never true for a real CUT boundary)."""
    leader_pid = min(
        (r for r in real_freeze["records"] if r["status"] == "ACTIVE"),
        key=lambda r: _real_total_to_par(r) if _real_total_to_par(r) is not None else float("inf"),
    )["player_id"]
    leader_rank = _cell(rendered_rows_by_player_id[str(leader_pid)], "순위")

    cut_ranks = {
        _cell(rendered_rows_by_player_id[str(r["player_id"])], "순위")
        for r in real_freeze["records"] if r["status"] == "CUT"
    }
    assert leader_rank not in cut_ranks, "a CUT player shares the real leader's rank -- the exact production bug"
    assert "T1" not in cut_ranks and "1" not in cut_ranks
