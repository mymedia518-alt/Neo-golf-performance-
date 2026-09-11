"""FINAL R2 EVIDENCE-GATE TASK (2026-09-11): real-evidence regression
coverage for klpga.collectors.score_record.parse_score_record_round_table.

The fixture (tests/fixtures/klpga_r2_2026090003_official_round_two_
trimmed.html) is extracted VERBATIM -- byte-for-byte for every row,
class name, and text this parser reads -- from a real, user-supplied
captured KLPGA response for gameCode=2026090003 (saved-from comment:
"saved from url=(0066)https://klpga.co.kr/web/tourRecord/scoreRecord
?gameCode=2026090003"), trimmed only to drop the ~20,000 lines of
unrelated global site chrome/JS/other-tab content around the single
#round-two tab-pane this parser actually reads. No row content, class,
or text inside that tab-pane was altered.

This was NOT independently fetched by this session (klpga.co.kr is
proxy-blocked in this sandbox, confirmed 403 on CONNECT) -- see this
task's own final report [OFFICIAL EVIDENCE CONTRACT] field for the
full, honest provenance statement.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.collectors.score_record import parse_score_record_round_table

FIXTURE = Path(__file__).parent / "fixtures" / "klpga_r2_2026090003_official_round_two_trimmed.html"


@pytest.fixture(scope="module")
def real_result():
    html = FIXTURE.read_text(encoding="utf-8")
    return parse_score_record_round_table(html, round_tab_id="round-two")


# ---------------------------------------------------------------------
# G. table-cut exists / Missed Cut marker exists
# ---------------------------------------------------------------------

def test_real_fixture_contains_the_table_cut_marker():
    html = FIXTURE.read_text(encoding="utf-8")
    assert 'class="table-cut"' in html
    assert "Missed Cut" in html


def test_real_fixture_cut_boundary_is_detected(real_result):
    assert real_result["cut_boundary_published"] is True


# ---------------------------------------------------------------------
# G. boundary between T58 and T72 (real, not hardcoded assumption --
# this reads the actual fixture content, never assumes the number)
# ---------------------------------------------------------------------

def test_real_fixture_boundary_sits_between_t58_and_t72(real_result):
    rows = real_result["rows"]
    last_t58_idx = max(i for i, r in enumerate(rows) if r["rank_display"] == "T58")
    first_t72_idx = min(i for i, r in enumerate(rows) if r["rank_display"] == "T72")
    assert first_t72_idx == last_t58_idx + 1  # adjacent in the real row list -- the boundary row itself is excluded from `rows`

    # every T58 row is NOT cut; every T72 row IS cut (SECTION-DERIVED,
    # from real document position, never from the rank number itself)
    for r in rows:
        if r["rank_display"] == "T58":
            assert r["official_status"] is None
        if r["rank_display"] == "T72":
            assert r["official_status"] == "CUT"


# ---------------------------------------------------------------------
# G. WD preserved (real player, real position AFTER the boundary)
# ---------------------------------------------------------------------

def test_real_wd_player_stays_wd_never_becomes_cut(real_result):
    wd_rows = [r for r in real_result["rows"] if r["player_name"] == "양서후"]
    assert len(wd_rows) == 1
    assert wd_rows[0]["official_status"] == "WD"
    assert wd_rows[0]["rank_display"] == "WD"


def test_wd_row_is_physically_after_the_boundary_in_the_real_document(real_result):
    """Documents WHY the precedence rule matters -- this is not a
    hypothetical edge case, it is the REAL layout of the real fixture:
    the one WD row in the real page is the LAST row, physically after
    every CUT-section row, which is exactly the scenario that would
    silently corrupt WD into CUT without the explicit-status-wins rule."""
    rows = real_result["rows"]
    wd_idx = next(i for i, r in enumerate(rows) if r["official_status"] == "WD")
    cut_idxs = [i for i, r in enumerate(rows) if r["official_status"] == "CUT"]
    assert wd_idx > max(cut_idxs)


# ---------------------------------------------------------------------
# G. no DQ fabricated
# ---------------------------------------------------------------------

def test_no_dq_or_dns_fabricated_in_real_fixture(real_result):
    """The real page has no DQ or DNS player -- this parser must never
    invent one. Only WD (real, explicit) and CUT (real, section-
    derived from the real boundary) appear."""
    statuses = {r["official_status"] for r in real_result["rows"]}
    assert statuses == {None, "CUT", "WD"}
    assert sum(r["official_status"] == "DQ" for r in real_result["rows"]) == 0
    assert sum(r["official_status"] == "DNS" for r in real_result["rows"]) == 0


# ---------------------------------------------------------------------
# G. cut_known True only because explicit official evidence exists --
# not because of row count, rank arithmetic, or any other proxy.
# ---------------------------------------------------------------------

def test_cut_known_would_be_false_without_the_real_boundary_row():
    """Removing ONLY the divider row (keeping every real player row
    unchanged) must flip cut_boundary_published back to False -- proving
    the signal really is the boundary row's own presence, not
    something else about the page (row count, T-number range, etc.)
    that would remain true even without it."""
    html = FIXTURE.read_text(encoding="utf-8")
    stripped = html.replace(
        '<tr class="table-cut">\n\t\t\t\t\t\t\t\t\t\t\t\t    <td colspan="31" style="padding: 0;"><div class="bartitle-green">Missed Cut</div></td>\n\t\t\t\t\t\t\t\t\t\t\t\t</tr>',
        "",
    )
    # Fall back to a plain-text removal if the exact whitespace above
    # doesn't match byte-for-byte (still proves the same point: cutting
    # the one row that carries BOTH the confirmed class and text is
    # what flips the signal, nothing else).
    if stripped == html:
        import re
        stripped = re.sub(r'<tr class="table-cut">.*?</tr>', "", html, count=1, flags=re.DOTALL)
    assert stripped != html, "test setup failed to actually remove the boundary row from the real fixture"

    from klpga.collectors.score_record import parse_score_record_round_table
    result = parse_score_record_round_table(stripped, round_tab_id="round-two")
    assert result["cut_boundary_published"] is False
    # every player row is still real and present -- only the divider is gone
    assert len(result["rows"]) == 118
    # and with no boundary, nobody is section-derived CUT anymore
    assert sum(r["official_status"] == "CUT" for r in result["rows"]) == 0


def test_real_row_count_is_118_players_plus_the_one_divider():
    html = FIXTURE.read_text(encoding="utf-8")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    tbody = soup.select_one("#round-two table tbody")
    all_trs = tbody.find_all("tr", recursive=False)
    assert len(all_trs) == 119  # 118 real players + 1 real divider row


# ---------------------------------------------------------------------
# Missing-round / missing-tab HARD FAIL (never a silent empty result)
# ---------------------------------------------------------------------

def test_missing_round_tab_raises_never_returns_empty():
    with pytest.raises(ValueError, match="not found"):
        parse_score_record_round_table("<html><body></body></html>", round_tab_id="round-two")


def test_round_not_yet_played_raises_for_round_three(real_result):
    """The real fixture is the full page's #round-two tab only, but
    demonstrates the same contract: a round tab-id that was never
    published (round-three/round-four, per this task's own real
    archaeology -- absent from the real page since R3 hadn't started)
    must raise, never silently return zero rows as if R2 had zero
    players."""
    html = FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="not found"):
        parse_score_record_round_table(html, round_tab_id="round-three")
