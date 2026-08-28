"""Tests for klpga.parsers.group_page_parser against a real, trimmed
slice of an actual Windows-run capture of the confirmed group-page
endpoint (tests/fixtures/group_page_sample.html — byte-faithful
excerpt from the real gameCode=2026080001, HTTP 200, 1,357,468-byte
response; see the module's own docstring and
docs/SITE_STRUCTURE_TODO.md section 13 for full provenance).

The fixture keeps round-one's real grouping table (2 rows, 6 real
players) and round-three's real grouping table (3 rows, 9 real
players) plus each round's real (excluded) favorites table, trimmed
down from the full capture but never rewritten — every player_code,
name, tee, and time value below is real, observed data."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.parsers.group_page_parser import parse_round_grouping

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "group_page_sample.html"


@pytest.fixture()
def html():
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parses_real_round_three_grouping_rows(html):
    rows = parse_round_grouping(html, round_number=3)

    codes = {r.player_code for r in rows}
    assert codes == {"8284", "10143", "9136", "9389", "10095", "11056", "9788", "9235", "10481"}
    assert len(rows) == 9  # no duplicates, no dropped slots


def test_real_player_names_and_tee_time_fields_preserved(html):
    rows = {r.player_code: r for r in parse_round_grouping(html, round_number=3)}

    row = rows["8284"]
    assert row.player_name == "최예림"
    assert row.starting_tee == "1"
    assert row.tee_time == "09:10"

    # the trailing "*" marker is preserved verbatim, never interpreted
    row2 = rows["9389"]
    assert row2.player_name == "전우리"
    assert row2.starting_tee == "10"
    assert row2.tee_time == "09:10 *"


def test_group_is_never_fabricated(html):
    """No explicit group/조 number exists in the real markup — this
    parser must never invent one."""
    rows = parse_round_grouping(html, round_number=3)
    assert all(r.group is None for r in rows)


def test_players_sharing_a_row_share_the_same_tee_and_time(html):
    rows = {r.player_code: r for r in parse_round_grouping(html, round_number=3)}
    same_row_codes = ["8284", "10143", "9136"]
    tee_times = {(rows[c].starting_tee, rows[c].tee_time) for c in same_row_codes}
    assert tee_times == {("1", "09:10")}


def test_favorites_toggle_table_is_never_included(html):
    """Round three's favorites table (real, hidden, hard-excluded)
    lists player 8284 too, under a different row shape (no
    fixed-start/text-start classes) — the real table's 8284 row must
    be the only one contributing, and the count must not double."""
    rows = parse_round_grouping(html, round_number=3)
    assert len([r for r in rows if r.player_code == "8284"]) == 1


def test_round_selection_never_leaks_a_different_rounds_players(html):
    """The exact real bug this parser has to get right: all rounds are
    embedded in one page, so scoping to id='round-three' must never
    pick up round-one's real players (or vice versa)."""
    round_one_rows = parse_round_grouping(html, round_number=1)
    round_three_rows = parse_round_grouping(html, round_number=3)

    round_one_codes = {r.player_code for r in round_one_rows}
    round_three_codes = {r.player_code for r in round_three_rows}

    assert round_one_codes == {"8859", "8770", "9174", "8883", "10114", "12571"}
    assert round_one_codes.isdisjoint(round_three_codes)


def test_round_not_published_yet_raises_instead_of_returning_empty(html):
    """Round four's tab BUTTON exists on the real site but its
    tab-pane div does not (not grouped yet, per the real capture) —
    this must raise, never silently return an empty (indistinguishable
    from 'confirmed zero players') result."""
    with pytest.raises(ValueError, match="round-four"):
        parse_round_grouping(html, round_number=4)


def test_invalid_round_number_raises():
    with pytest.raises(ValueError, match="round_number"):
        parse_round_grouping("<html></html>", round_number=5)
