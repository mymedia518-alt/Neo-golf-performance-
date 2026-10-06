"""Tests for klpga.collectors.score_record.extract_hole_outcomes -- the
new per-hole outcome extractor built for the Modified Stableford
data-source discovery task (HJ 2026100004 gap, continued 2026-10-06).

Verified against the ONE real scoreRecord fixture this repo has
(tests/fixtures/score_record_2026120001_r1.html, a real stroke-play
capture) -- NOT yet against any real Modified Stableford gameCode
response, because none exists in this repo yet. This fixture, despite
its "r1" filename, was discovered (while writing these tests) to
actually contain TWO per-round `table.table-scorecard` blocks -- one
headed "1R" (120 players) and one headed "2R" (60 players) -- which is
exactly the mechanism that recovers per-round boundaries (needed to
reproduce a per-round Stableford point split, e.g. +7/+14/+14/+16, once
real Stableford HTML is available). The specific numbers asserted below
were derived by hand from that real fixture's own raw markup (see this
test file's own comments) and independently cross-checked against that
same row's own td.today cell -- not assumed."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_scoring import HoleOutcomeCounts

FIXTURE = Path(__file__).parent / "fixtures" / "score_record_2026120001_r1.html"


def test_rejects_html_with_no_scorecard_table():
    with pytest.raises(ValueError):
        extract_hole_outcomes("<html><body>no table here</body></html>")


def test_real_fixture_has_two_round_tables_keyed_by_their_own_header_label():
    by_round = extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))
    assert set(by_round.keys()) == {"1R", "2R"}
    assert len(by_round["1R"]) == 120
    assert len(by_round["2R"]) == 60


def test_real_fixture_extracts_known_player_hole_outcomes_exactly():
    """양효진's real 1R row (fixture lines ~4884-4927): holes 1-9 are
    bogey(5),bogey(5),birdie(2),par(4),birdie(4),par(4),par(4),birdie(2),
    par(5) [OUT=35, matches 5+5+2+4+4+4+4+2+5]; holes 10-18 are
    par(4),birdie(4),par(3),par(4),par(4),par(5),birdie(3),par(3),
    birdie(3) [IN=33, matches 4+4+3+4+4+5+3+3+3] -> bogey=2, birdie=6,
    par=10, eagle=0, albatross=0, double_or_worse=0, 18 holes total."""
    by_round = extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))
    counts = by_round["1R"]["양효진"]
    assert counts == HoleOutcomeCounts(birdie=6, par=10, bogey=2)
    assert counts.total_holes == 18


def test_real_fixture_hole_outcomes_cross_check_against_official_today_column():
    """Independent arithmetic check: this player's real td.today cell in
    the same fixture's 1R table reads "-4" (stroke-play score-to-par).
    birdie(-1 each) + bogey(+1 each), with par/eagle/double all zero or
    absent here, must reproduce exactly that -4 -- proving the
    class->outcome mapping is reading the real per-hole classification
    correctly, not just counting cells that happen to sum to 18."""
    by_round = extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))
    counts = by_round["1R"]["양효진"]
    score_to_par = counts.birdie * -1 + counts.bogey * 1 + counts.eagle * -2 + counts.double_or_worse * 2
    assert score_to_par == -4


def test_real_fixture_same_player_has_different_real_rows_in_each_round():
    """최예림 appears in BOTH round tables with DIFFERENT real hole
    outcomes -- this is what first revealed the two-tables-per-page
    structure (an earlier, round-unaware version of this function
    raised a false "conflicting rows" error on exactly this player).
    1R: birdie=3,par=10,bogey=5. 2R real row starts birdie(3),par(4),
    par(3),par(4),birdie(4),... -- different round, different round,
    legitimately different counts, not a parsing bug."""
    by_round = extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))
    assert "최예림" in by_round["1R"]
    assert "최예림" in by_round["2R"]
    assert by_round["1R"]["최예림"] != by_round["2R"]["최예림"]
    assert by_round["1R"]["최예림"].total_holes == 18
    assert by_round["2R"]["최예림"].total_holes == 18


def test_real_fixture_every_extracted_player_has_zero_or_eighteen_holes():
    """Sanity check across the whole real field, not just one row --
    every player this function extracts a row for, in every round, must
    have either exactly 18 classified hole cells (a completed round) or
    exactly 0 (a real WD player who never started -- this fixture's own
    known WD case, 박결, is exactly this: an empty row, confirmed by the
    existing test_score_record_collector.py asserting 2 WD players
    among the 120). Anything strictly between 0 and 18 would indicate a
    genuine parsing bug (e.g. the earlier Dbogeys case-sensitivity bug
    this test caught, which silently dropped 2 real cells from a
    completed round) -- checked by hand across the whole real fixture
    before writing this assertion: no such case exists."""
    by_round = extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))
    for round_label, by_name in by_round.items():
        for name, counts in by_name.items():
            assert counts.total_holes in (0, 18), f"{round_label}/{name}: {counts.total_holes} holes (expected 0 or 18)"


def test_stableford_points_formula_applies_to_real_extracted_hole_data():
    """Plumbing demonstration ONLY: this fixture is a real STROKE-PLAY
    tournament, not Modified Stableford -- applying stableford_scoring's
    official point table to its real hole-outcome counts does not claim
    this event was Stableford. It proves the real HTML -> HoleOutcomeCounts
    -> Stableford points pipeline works end-to-end on genuine data, which
    is the exact mechanism needed once a real 2025100001 (or other
    Stableford gameCode) scoreRecord capture exists to run this same
    extractor against."""
    by_round = extract_hole_outcomes(FIXTURE.read_text(encoding="utf-8"))
    counts = by_round["1R"]["양효진"]
    # 6 birdies * 2 - 2 bogeys * 1 = 10 Stableford points, computed via
    # the official table, not re-derived ad hoc here.
    assert counts.total_points() == 10
