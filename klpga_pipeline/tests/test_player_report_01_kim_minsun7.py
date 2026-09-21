"""Targeted tests for the pure helper functions in
scripts/player_report_01_kim_minsun7.py -- classification, distance
banding, hole grouping, lie metrics, green-entry/green-finish
detection, and continuity checking. Synthetic data only (never real
2026090002 data, unreachable from this sandbox)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scripts.player_report_01_kim_minsun7 import (
    classify_score_to_par,
    compute_lie_metrics,
    distance_band,
    green_entry_shot,
    green_finish_shot_count,
    group_by_hole,
    qualifying_shots_150_175,
    sample_size_flag,
    shot_no_continuity_ok,
)
from klpga.expected_strokes.transitions import TransitionRow


def _row(round_number=1, hole=1, shot_no=1, par=4, start_distance_yd=None, start_lie="티",
         end_distance_yd=150.0, end_lie="페어웨이", holed=False, zero_distance_ambiguous=False,
         player_code="P1", player_name="김민선7", game_code="G"):
    return TransitionRow(
        game_code=game_code, player_code=player_code, player_name=player_name,
        round_number=round_number, hole=hole, shot_no=shot_no, par=par,
        start_distance_yd=start_distance_yd, start_lie=start_lie,
        end_distance_yd=end_distance_yd, end_lie=end_lie, holed=holed,
        zero_distance_ambiguous=zero_distance_ambiguous, official_hole_score=None,
    )


# ---------------------------------------------------------------
# classify_score_to_par
# ---------------------------------------------------------------

def test_classify_score_to_par_categories():
    assert classify_score_to_par(-2) == "birdie_or_better"
    assert classify_score_to_par(-1) == "birdie_or_better"
    assert classify_score_to_par(0) == "par"
    assert classify_score_to_par(1) == "bogey"
    assert classify_score_to_par(2) == "double_or_worse"
    assert classify_score_to_par(5) == "double_or_worse"
    assert classify_score_to_par(None) is None


# ---------------------------------------------------------------
# distance_band
# ---------------------------------------------------------------

def test_distance_band_all_boundaries():
    assert distance_band(0.0) == "<100"
    assert distance_band(99.9) == "<100"
    assert distance_band(100.0) == "100-125"
    assert distance_band(124.9) == "100-125"
    assert distance_band(125.0) == "125-150"
    assert distance_band(149.9) == "125-150"
    assert distance_band(150.0) == "150-175"
    assert distance_band(175.0) == "150-175"
    assert distance_band(175.1) == "175-200"
    assert distance_band(200.0) == "175-200"
    assert distance_band(200.1) == "200+"
    assert distance_band(400.0) == "200+"


def test_distance_band_no_overlap_no_gap_across_a_dense_sweep():
    # every 0.1yd step from 0 to 300 must land in exactly one band --
    # proven by re-deriving from distance_band itself (never silently
    # double counted or skipped) via a boundary-crossing sanity check.
    d = 0.0
    prev_band = distance_band(d)
    seen_order = [prev_band]
    while d < 300.0:
        d += 0.1
        b = distance_band(round(d, 1))
        if b != prev_band:
            seen_order.append(b)
            prev_band = b
    assert seen_order == ["<100", "100-125", "125-150", "150-175", "175-200", "200+"]


# ---------------------------------------------------------------
# group_by_hole / shot_no_continuity_ok
# ---------------------------------------------------------------

def test_group_by_hole_groups_and_sorts_by_shot_no():
    rows = [
        _row(round_number=1, hole=1, shot_no=2),
        _row(round_number=1, hole=1, shot_no=1),
        _row(round_number=1, hole=2, shot_no=1),
    ]
    groups = group_by_hole(rows)
    assert set(groups.keys()) == {(1, 1), (1, 2)}
    assert [r.shot_no for r in groups[(1, 1)]] == [1, 2]


def test_shot_no_continuity_ok_true_and_false():
    ok = [_row(shot_no=1), _row(shot_no=2), _row(shot_no=3)]
    assert shot_no_continuity_ok(ok) is True
    gap = [_row(shot_no=1), _row(shot_no=3)]
    assert shot_no_continuity_ok(gap) is False


# ---------------------------------------------------------------
# compute_lie_metrics
# ---------------------------------------------------------------

def test_compute_lie_metrics_terminal_integrity_and_unknown_end_exclusion():
    a1 = _row(hole=1, shot_no=1, start_lie="페어웨이", start_distance_yd=160.0, end_lie="그린", end_distance_yd=20.0)
    a2 = _row(hole=1, shot_no=2, start_lie="그린", start_distance_yd=20.0, end_lie="홀인", end_distance_yd=0.0, holed=True)
    b1 = _row(hole=2, shot_no=1, start_lie="페어웨이", start_distance_yd=155.0, end_lie="", end_distance_yd=5.0)
    b2 = _row(hole=2, shot_no=2, start_lie="", start_distance_yd=5.0, end_lie="홀인", end_distance_yd=0.0, holed=True)
    c1 = _row(hole=3, shot_no=1, start_lie="페어웨이", start_distance_yd=165.0, end_lie="그린", end_distance_yd=20.0)
    c2 = _row(hole=3, shot_no=2, start_lie="그린", start_distance_yd=20.0, end_lie="그린", end_distance_yd=5.0)  # never holes out
    rows = [a1, a2, b1, b2, c1, c2]
    hg = group_by_hole(rows)
    shots = [r for r in rows if r.start_lie == "페어웨이"]
    m = compute_lie_metrics(shots, hg)
    assert m.n == 3
    assert m.avg_remaining_denominator == 2  # b1 excluded (end_lie=="")
    assert m.avg_remaining_excluded_unknown_end == 1
    assert m.terminal_integrity_failures == 1  # hole 3
    assert m.avg_strokes_after_denominator == 2  # a1, b1 count; c1 excluded
    assert m.avg_strokes_after == 1.0


def test_qualifying_shots_150_175_boundary_and_missing_distance():
    rows = [
        _row(hole=1, shot_no=1, start_lie="페어웨이", start_distance_yd=149.9),
        _row(hole=2, shot_no=1, start_lie="페어웨이", start_distance_yd=150.0),
        _row(hole=3, shot_no=1, start_lie="페어웨이", start_distance_yd=175.0),
        _row(hole=4, shot_no=1, start_lie="페어웨이", start_distance_yd=175.1),
        _row(hole=5, shot_no=1, start_lie="페어웨이", start_distance_yd=None),
        _row(hole=6, shot_no=1, start_lie="러프", start_distance_yd=160.0),
    ]
    fw = qualifying_shots_150_175(rows, "페어웨이")
    assert len(fw) == 2  # 150.0 and 175.0 only
    rough = qualifying_shots_150_175(rows, "러프")
    assert len(rough) == 1


def test_sample_size_flag():
    assert sample_size_flag(0) == "VERY_SMALL_SAMPLE"
    assert sample_size_flag(4) == "VERY_SMALL_SAMPLE"
    assert sample_size_flag(5) == "SMALL_SAMPLE"
    assert sample_size_flag(9) == "SMALL_SAMPLE"
    assert sample_size_flag(10) == ""


# ---------------------------------------------------------------
# green_entry_shot / green_finish_shot_count
# ---------------------------------------------------------------

def test_green_entry_shot_finds_first_green_lie_and_none_when_absent():
    hole_rows = [
        _row(shot_no=1, end_lie="페어웨이"),
        _row(shot_no=2, end_lie="그린", end_distance_yd=10.0),
        _row(shot_no=3, end_lie="홀인", end_distance_yd=0.0, holed=True),
    ]
    entry = green_entry_shot(hole_rows)
    assert entry.shot_no == 2

    no_green = [_row(shot_no=1, end_lie="페어웨이"), _row(shot_no=2, end_lie="홀인", end_distance_yd=0.0, holed=True)]
    assert green_entry_shot(no_green) is None


def test_green_finish_shot_count_normal_and_terminal_failure():
    hole_rows = [
        _row(shot_no=1, end_lie="그린", end_distance_yd=10.0),
        _row(shot_no=2, end_lie="그린", end_distance_yd=3.0),
        _row(shot_no=3, end_lie="홀인", end_distance_yd=0.0, holed=True),
    ]
    assert green_finish_shot_count(hole_rows, entry_shot_no=1) == 2

    bad_terminal = [
        _row(shot_no=1, end_lie="그린", end_distance_yd=10.0),
        _row(shot_no=2, end_lie="그린", end_distance_yd=3.0),  # never holes out
    ]
    assert green_finish_shot_count(bad_terminal, entry_shot_no=1) is None
