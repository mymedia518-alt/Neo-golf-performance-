"""Regression tests for klpga.parsers.round_progress -- the real-source,
OUT/IN-tee-aware completed-hole calculation that replaces a naive
raw-data-inghole passthrough (which is wrong for any IN/10-tee start)."""
from __future__ import annotations

from klpga.parsers.group_page_parser import GroupingRow
from klpga.parsers.leaderboard_parser import PlayerRoundRow
from klpga.parsers.round_progress import (
    HolesCompletedResult,
    resolve_completed_holes,
    resolve_round_progress,
)


def _row(player_code="1", holes_completed=None, status=None):
    return PlayerRoundRow(
        game_code="2026120001", player_code=player_code, player_name="선수",
        player_eng_name=None, round_number=1,
        rank_display="1", rank=1, tie_flag=False, status=status,
        total_under_par_display="-1", total_under_par=-1,
        today_under_par_display="-1", today_under_par=-1,
        total_strokes=None, holes_completed=holes_completed,
        round1_score=None, round2_score=None, round3_score=None, round4_score=None,
    )


def _grouping(player_code="1", starting_tee=None):
    return GroupingRow(player_code=player_code, player_name="선수", starting_tee=starting_tee, tee_time="09:10")


# --- required minimum cases -------------------------------------------------

def test_1_tee_start_seven_holes_played_is_7h():
    result = resolve_completed_holes(raw_inghole="7", starting_tee="1", status=None)
    assert result == HolesCompletedResult(completed=7, display="7H", assumed_default_start=False)


def test_10_tee_start_played_holes_10_through_16_is_7h_not_16h():
    # The exact bug this module fixes: raw current-hole is "16", but
    # the player only played 7 holes (10,11,...,16).
    result = resolve_completed_holes(raw_inghole="16", starting_tee="10", status=None)
    assert result.completed == 7
    assert result.display == "7H"


def test_pre_round_player_not_teed_off_is_0h():
    result = resolve_completed_holes(raw_inghole=None, starting_tee="1", status=None)
    assert result == HolesCompletedResult(completed=0, display="0H", assumed_default_start=False)


def test_pre_round_empty_string_is_also_0h():
    result = resolve_completed_holes(raw_inghole="", starting_tee="10", status=None)
    assert result.completed == 0
    assert result.display == "0H"


def test_finished_round_1_tee_start_is_18h():
    result = resolve_completed_holes(raw_inghole="18", starting_tee="1", status=None)
    assert result.completed == 18
    assert result.display == "18H"


def test_finished_round_10_tee_start_is_18h_not_9h():
    # An IN starter finishes on real hole 9 (10..18,1..9); the naive
    # raw value "9" must NOT be displayed as "9H".
    result = resolve_completed_holes(raw_inghole="9", starting_tee="10", status=None)
    assert result.completed == 18
    assert result.display == "18H"


# --- defensive: WD/DQ/CUT/INCOMPLETE/missing data never corrupt the calc ---

def test_wd_status_never_computes_a_count():
    result = resolve_completed_holes(raw_inghole="9", starting_tee="1", status="WD")
    assert result.completed is None
    assert result.display == ""


def test_dq_status_never_computes_a_count():
    result = resolve_completed_holes(raw_inghole="12", starting_tee="10", status="DQ")
    assert result.completed is None


def test_cut_status_never_computes_a_count():
    result = resolve_completed_holes(raw_inghole="", starting_tee=None, status="CUT")
    assert result.completed is None


def test_incomplete_sentinel_status_never_computes_a_count():
    # The confirmed real "999 rank" -> status="INCOMPLETE" sentinel.
    result = resolve_completed_holes(raw_inghole="14", starting_tee="1", status="INCOMPLETE")
    assert result.completed is None
    assert result.display == ""


def test_missing_starting_tee_falls_back_to_out_start_and_flags_it():
    result = resolve_completed_holes(raw_inghole="7", starting_tee=None, status=None)
    assert result.completed == 7
    assert result.assumed_default_start is True


def test_garbage_starting_tee_is_never_trusted_falls_back_and_flags_it():
    result = resolve_completed_holes(raw_inghole="7", starting_tee="not-a-hole", status=None)
    assert result.completed == 7
    assert result.assumed_default_start is True


def test_garbage_current_hole_is_never_guessed_treated_as_pre_round():
    result = resolve_completed_holes(raw_inghole="not-a-hole", starting_tee="10", status=None)
    assert result.completed == 0
    assert result.display == "0H"


def test_out_of_range_hole_number_is_never_guessed():
    result = resolve_completed_holes(raw_inghole="19", starting_tee="1", status=None)
    assert result.completed == 0


# --- real join across the two confirmed real endpoints ----------------------

def test_resolve_round_progress_joins_leaderboard_rows_with_grouping_by_player_code():
    rows = [
        _row(player_code="11134", holes_completed="16", status=None),  # 10-tee, played 10-16
        _row(player_code="20099", holes_completed="7", status=None),   # 1-tee, played 1-7
        _row(player_code="30055", holes_completed=None, status="CUT"),
    ]
    groupings = [
        _grouping(player_code="11134", starting_tee="10"),
        _grouping(player_code="20099", starting_tee="1"),
    ]
    progress = resolve_round_progress(rows, groupings)

    assert progress["11134"].display == "7H"
    assert progress["20099"].display == "7H"
    assert progress["30055"].completed is None


def test_resolve_round_progress_never_drops_a_player_missing_from_grouping():
    rows = [_row(player_code="99999", holes_completed="7", status=None)]
    progress = resolve_round_progress(rows, groupings=[])

    assert "99999" in progress
    assert progress["99999"].completed == 7
    assert progress["99999"].assumed_default_start is True


def test_resolve_round_progress_skips_rows_with_no_player_code():
    rows = [_row(player_code=None, holes_completed="7", status=None)]
    progress = resolve_round_progress(rows, groupings=[])
    assert progress == {}
