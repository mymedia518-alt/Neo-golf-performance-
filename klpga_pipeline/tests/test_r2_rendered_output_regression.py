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

R2 CUT SURVIVORS ONLY (fix/kb-r2-official-cut-gate-20260911, later on
this same branch): the public main table population contract changed
again -- it now shows ONLY officially-advancing (status=="ACTIVE")
players, never CUT/WD/DQ/DNS. This file's population/spot-check tests
are scoped to the ACTIVE population accordingly; a dedicated test below
proves every CUT/WD player is positively ABSENT from the rendered page
(never merely untested).

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


def _active_ids(real_freeze: dict) -> set[str]:
    return {str(r["player_id"]) for r in real_freeze["records"] if r.get("status", "ACTIVE") == "ACTIVE"}


def _non_advancing_ids(real_freeze: dict) -> set[str]:
    return {str(r["player_id"]) for r in real_freeze["records"] if r.get("status", "ACTIVE") != "ACTIVE"}


# ---------------------------------------------------------------------
# Population-scale sanity: the real page shows exactly the ADVANCING
# (status=="ACTIVE") subset of the real freeze -- CUT/WD/DQ/DNS players
# are positively excluded, never merely untested -- and rendered fields
# are not universally empty/broken at population scale (the exact shape
# of the real production failure).
# ---------------------------------------------------------------------

def test_rendered_population_matches_the_advancing_subset_of_real_freeze(real_freeze, rendered_rows_by_player_id):
    active_ids = _active_ids(real_freeze)
    assert set(rendered_rows_by_player_id) == active_ids
    assert len(rendered_rows_by_player_id) == 71, "real KB R2 official advancing field is 71 players"


def test_no_cut_wd_dq_dns_player_appears_in_the_rendered_page(real_freeze, real_html, rendered_rows_by_player_id):
    non_advancing_ids = _non_advancing_ids(real_freeze)
    assert non_advancing_ids, "test setup: real freeze must have real CUT/WD players to prove exclusion against"
    assert non_advancing_ids.isdisjoint(rendered_rows_by_player_id)
    for pid in non_advancing_ids:
        assert f"data-player-id='{pid}'" not in real_html


def test_rank_population_is_not_universally_t1_or_missing(real_freeze, rendered_rows_by_player_id):
    """The exact real production failure: every rank collapsed to a
    fake tied T1. A real leaderboard population must have real,
    distinct ranks across a meaningful fraction of the advancing
    players with real, complete scores."""
    active_ids = sorted(_active_ids(real_freeze))
    ranks = [_cell(rendered_rows_by_player_id[pid], "순위") for pid in active_ids]
    distinct_ranks = set(ranks)
    assert len(distinct_ranks) > 10, f"rank population is far too uniform: {sorted(distinct_ranks)[:10]}..."
    assert ranks.count("T1") < len(ranks), "every player rendered as a fake tied T1 -- the real production bug"
    assert "1" in distinct_ranks or "T1" in distinct_ranks  # a real leader must exist


def test_total_and_2r_are_not_universally_empty_for_the_advancing_population(real_freeze, rendered_rows_by_player_id):
    active_ids = sorted(_active_ids(real_freeze))
    assert active_ids, "test setup: real freeze must have an advancing population"
    totals = [_cell(rendered_rows_by_player_id[pid], "합계") for pid in active_ids]
    twos = [_cell(rendered_rows_by_player_id[pid], "2R") for pid in active_ids]
    assert totals.count("—") == 0, "TOTAL rendered empty for advancing players with real, complete scores"
    assert twos.count("—") == 0, "2R rendered empty for advancing players with real, complete scores"


# ---------------------------------------------------------------------
# Per-player spot checks: rendered rank/TOTAL/2R for REAL advancing
# player identities, compared directly against the frozen official
# evidence -- not merely "the HTML element exists".
# ---------------------------------------------------------------------

def test_every_advancing_player_has_the_exact_real_total_and_2r(real_freeze, rendered_rows_by_player_id):
    checked = 0
    for record in real_freeze["records"]:
        if record.get("status", "ACTIVE") != "ACTIVE":
            continue
        pid = str(record["player_id"])
        expected_total = _real_total_to_par(record)
        expected_2r = record.get("r2_score_to_par")
        row = rendered_rows_by_player_id[pid]
        assert _cell(row, "합계") == _expected_to_par_display(expected_total), f"TOTAL mismatch for {record['player_name']} ({pid})"
        assert _cell(row, "2R") == _expected_to_par_display(expected_2r), f"2R mismatch for {record['player_name']} ({pid})"
        checked += 1
    assert checked == 71, "sanity: should have checked exactly the real 71-player advancing population"


def test_no_status_badge_appears_in_the_public_main_table(rendered_rows_by_player_id):
    """Every rendered row is an ACTIVE (advancing) player, and ACTIVE
    players never carry a status badge (STATUS_LABEL["ACTIVE"] == "") --
    so no 'status-badge' span should exist anywhere among the rendered
    rows. Complements test_no_cut_wd_dq_dns_player_appears_in_the_
    rendered_page: that test proves non-advancing players are excluded
    by id, this one proves nothing CUT/WD-shaped leaked into an
    otherwise-ACTIVE row either."""
    for pid, row in rendered_rows_by_player_id.items():
        assert "status-badge" not in row, f"unexpected status badge in advancing player's row ({pid})"


def test_cut_players_never_share_the_active_leaders_rank(real_freeze, rendered_rows_by_player_id):
    """The exact real symptom: CUT players displayed as T1 alongside
    real leaders. Now that CUT players are excluded from the public
    table entirely, the strongest available proof is that no rank in
    the rendered table is ever attributable to a CUT player -- restated
    as: the leader's rank is real and unique, and the rendered
    population contains zero CUT-status ids (proven separately above)."""
    leader_pid = min(
        (r for r in real_freeze["records"] if r.get("status", "ACTIVE") == "ACTIVE"),
        key=lambda r: _real_total_to_par(r) if _real_total_to_par(r) is not None else float("inf"),
    )["player_id"]
    leader_rank = _cell(rendered_rows_by_player_id[str(leader_pid)], "순위")
    assert leader_rank in ("1", "T1")

    cut_ids = {str(r["player_id"]) for r in real_freeze["records"] if r.get("status") == "CUT"}
    assert cut_ids.isdisjoint(rendered_rows_by_player_id), "a CUT player rendered in the public main table at all"


def test_footer_reports_the_exact_real_advancing_count(real_freeze, real_html):
    active_count = len(_active_ids(real_freeze))
    assert active_count == 71
    assert f"총 {active_count}명 (컷 통과 선수만 표시)" in real_html
