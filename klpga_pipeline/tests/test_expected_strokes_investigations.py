"""Tests for klpga.expected_strokes.investigations -- Phase 1 red-team
deep-dives: blank-lie investigation, bunker investigation, the 17
zero-distance/non-홀인 full detail, and the MODEL-ELIGIBILITY
classification. Uses synthetic TransitionRow lists built directly
(never real 2026090002 data, unreachable from this sandbox) since
these functions operate purely on already-built transition rows."""
from __future__ import annotations

from klpga.expected_strokes.investigations import (
    _bucket_label,
    blank_lie_investigation,
    bunker_investigation,
    classify_model_eligibility,
    model_eligibility_summary,
    zero_distance_ambiguous_detail,
)
from klpga.expected_strokes.transitions import TransitionRow


def _row(
    player_code="P1", player_name="선수1", round_number=1, hole=1, shot_no=1,
    par=4, start_distance_yd=None, start_lie="티", end_distance_yd=150.0,
    end_lie="페어웨이", holed=False, zero_distance_ambiguous=False,
    official_hole_score=None, game_code="G",
):
    return TransitionRow(
        game_code=game_code, player_code=player_code, player_name=player_name,
        round_number=round_number, hole=hole, shot_no=shot_no, par=par,
        start_distance_yd=start_distance_yd, start_lie=start_lie,
        end_distance_yd=end_distance_yd, end_lie=end_lie, holed=holed,
        zero_distance_ambiguous=zero_distance_ambiguous,
        official_hole_score=official_hole_score,
    )


# ---------------------------------------------------------------
# _bucket_label
# ---------------------------------------------------------------

def test_bucket_label_covers_all_six_buckets_and_boundaries():
    assert _bucket_label(None) == "unknown"
    assert _bucket_label(0.0) == "0-5"
    assert _bucket_label(5.0) == "0-5"
    assert _bucket_label(5.1) == ">5-20"
    assert _bucket_label(20.0) == ">5-20"
    assert _bucket_label(20.1) == ">20-50"
    assert _bucket_label(50.0) == ">20-50"
    assert _bucket_label(50.1) == ">50-100"
    assert _bucket_label(100.0) == ">50-100"
    assert _bucket_label(100.1) == ">100-200"
    assert _bucket_label(200.0) == ">100-200"
    assert _bucket_label(200.1) == ">200"
    assert _bucket_label(999.0) == ">200"


# ---------------------------------------------------------------
# blank_lie_investigation
# ---------------------------------------------------------------

def test_blank_lie_investigation_separates_start_and_end_blank():
    rows = [
        # hole 1: shot1 tee->blank(10.0), shot2 blank->green(0.0 holed)
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="", end_distance_yd=10.0),
        _row(hole=1, shot_no=2, start_lie="", start_distance_yd=10.0, end_lie="그린", end_distance_yd=2.0),
    ]
    result = blank_lie_investigation(rows)
    assert result["start_blank_count"] == 1  # shot 2's start_lie==""
    assert result["end_blank_count"] == 1  # shot 1's end_lie==""


def test_blank_lie_investigation_by_shot_no_and_par():
    rows = [
        _row(hole=1, shot_no=1, par=3, start_lie="티", start_distance_yd=None, end_lie="", end_distance_yd=100.0),
        _row(hole=2, shot_no=2, par=5, start_lie="페어웨이", start_distance_yd=200.0, end_lie="", end_distance_yd=50.0),
    ]
    result = blank_lie_investigation(rows)
    assert result["end_blank_by_shot_no"] == {1: 1, 2: 1}
    assert result["end_blank_by_par"] == {"par_3": 1, "par_5": 1}


def test_blank_lie_investigation_by_previous_and_next_lie():
    rows = [
        # hole 1: shot1 (tee->fairway), shot2 (fairway-> blank, distance 30), shot3 (blank(start)->green)
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="페어웨이", end_distance_yd=150.0),
        _row(hole=1, shot_no=2, start_lie="페어웨이", start_distance_yd=150.0, end_lie="", end_distance_yd=30.0),
        _row(hole=1, shot_no=3, start_lie="", start_distance_yd=30.0, end_lie="그린", end_distance_yd=5.0),
    ]
    result = blank_lie_investigation(rows)
    # end-blank row is shot_no=2: previous end_lie = 페어웨이 (shot1's end), next start_lie = "" (shot3's start, itself blank)
    assert result["end_blank_by_previous_lie"] == {"페어웨이": 1}
    assert result["end_blank_by_next_lie"] == {"BLANK": 1}
    # start-blank row is shot_no=3: previous end_lie = "" (shot2's end, blank), next -> final shot
    assert result["start_blank_by_previous_lie"] == {"BLANK": 1}
    assert result["start_blank_by_next_lie"] == {"NONE_final_shot": 1}


def test_blank_lie_investigation_distance_buckets_and_top30():
    rows = [
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="", end_distance_yd=3.0),
        _row(hole=2, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="", end_distance_yd=567.4),
    ]
    result = blank_lie_investigation(rows)
    assert result["end_blank_distance_buckets"] == {"0-5": 1, ">200": 1}
    assert len(result["end_blank_top30_longest"]) == 2
    assert result["end_blank_top30_longest"][0]["end_distance_yd"] == 567.4
    assert result["end_blank_top30_longest"][0]["is_final_shot"] is True


def test_blank_lie_investigation_top30_caps_at_30():
    rows = [
        _row(game_code="G", player_code=f"P{i}", hole=i, shot_no=1, start_lie="티",
             start_distance_yd=None, end_lie="", end_distance_yd=float(i))
        for i in range(1, 41)
    ]
    result = blank_lie_investigation(rows)
    assert result["end_blank_count"] == 40
    assert len(result["end_blank_top30_longest"]) == 30
    assert result["end_blank_top30_longest"][0]["end_distance_yd"] == 40.0


# ---------------------------------------------------------------
# bunker_investigation
# ---------------------------------------------------------------

def test_bunker_investigation_counts_and_distance_stats():
    rows = [
        _row(hole=1, shot_no=2, par=4, start_lie="벙커", start_distance_yd=58.5, end_lie="그린", end_distance_yd=3.0),
        _row(hole=2, shot_no=3, par=5, start_lie="벙커", start_distance_yd=308.6, end_lie="페어웨이", end_distance_yd=150.0),
        _row(hole=3, shot_no=1, par=4, start_lie="티", start_distance_yd=None, end_lie="페어웨이", end_distance_yd=200.0),
    ]
    result = bunker_investigation(rows)
    assert result["start_bunker_shots"] == 2
    assert result["distance_stats"]["shots"] == 2
    assert result["distance_stats"]["min"] == 58.5
    assert result["distance_stats"]["max"] == 308.6
    assert result["by_par"] == {"par_4": 1, "par_5": 1}
    assert result["by_shot_no"] == {2: 1, 3: 1}
    assert result["end_lie_distribution"] == {"그린": 1, "페어웨이": 1}
    assert len(result["examples"]) == 2
    assert result["examples"][0]["start_distance_yd"] == 308.6  # sorted desc


# ---------------------------------------------------------------
# zero_distance_ambiguous_detail
# ---------------------------------------------------------------

def test_zero_distance_ambiguous_detail_full_context():
    rows = [
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="그린", end_distance_yd=0.0, zero_distance_ambiguous=True),
        _row(hole=1, shot_no=2, start_lie="그린", start_distance_yd=0.0, end_lie="홀인", end_distance_yd=0.0, holed=True, zero_distance_ambiguous=False),
    ]
    detail = zero_distance_ambiguous_detail(rows)
    assert len(detail) == 1
    d = detail[0]
    assert d["shot_no"] == 1
    assert d["end_lie"] == "그린"
    assert d["end_distance_yd"] == 0.0
    assert d["next_start_lie"] == "그린"  # shot 2's start_lie
    assert d["is_final_shot"] is False


def test_zero_distance_ambiguous_detail_final_shot_flag():
    rows = [_row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="그린", end_distance_yd=0.0, zero_distance_ambiguous=True)]
    detail = zero_distance_ambiguous_detail(rows)
    assert len(detail) == 1
    assert detail[0]["is_final_shot"] is True
    assert detail[0]["next_start_lie"] is None


def test_zero_distance_ambiguous_detail_empty_when_none_flagged():
    rows = [_row(hole=1, shot_no=1, end_lie="홀인", end_distance_yd=0.0, holed=True, zero_distance_ambiguous=False)]
    assert zero_distance_ambiguous_detail(rows) == []


# ---------------------------------------------------------------
# classify_model_eligibility / model_eligibility_summary
# ---------------------------------------------------------------

def test_classify_model_eligibility_no_flags_is_eligible():
    row = _row(hole=1, shot_no=2, start_lie="페어웨이", start_distance_yd=150.0, end_lie="그린", end_distance_yd=10.0)
    state, flags = classify_model_eligibility(row)
    assert state == "ELIGIBLE"
    assert flags == []


def test_model_eligibility_summary_eligible_row():
    rows = [_row(hole=1, shot_no=2, start_lie="페어웨이", start_distance_yd=150.0, end_lie="그린", end_distance_yd=10.0)]
    result = model_eligibility_summary(rows)
    assert result["total_shots"] == 1
    assert result["ELIGIBLE"] == 1
    assert result["sum_check"] == 1
    assert "not an approved training sample" in result["note"].lower() or "not an approved" in result["note"]


def test_model_eligibility_summary_single_flag_categories():
    rows = [
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="페어웨이", end_distance_yd=150.0),  # FIRST_SHOT only
        _row(hole=2, shot_no=2, start_lie="", start_distance_yd=30.0, end_lie="그린", end_distance_yd=5.0),  # UNKNOWN_LIE only (start blank)
        _row(hole=3, shot_no=2, start_lie="그린", start_distance_yd=5.0, end_lie="그린", end_distance_yd=0.0, zero_distance_ambiguous=True),  # ZERO_DISTANCE_UNKNOWN only
        _row(hole=4, shot_no=2, start_lie="벙커", start_distance_yd=100.0, end_lie="그린", end_distance_yd=10.0),  # SAND_SPARSE only
    ]
    result = model_eligibility_summary(rows)
    assert result["FIRST_SHOT_DISTANCE_MISSING"] == 1
    assert result["UNKNOWN_LIE"] == 1
    assert result["ZERO_DISTANCE_UNKNOWN"] == 1
    assert result["SAND_SPARSE"] == 1
    assert result["MULTIPLE_FLAGS"] == 0
    assert result["sum_check"] == 4


def test_model_eligibility_summary_overlap_goes_to_multiple_flags_with_combination_recorded():
    rows = [
        # shot_no==1 AND blank end_lie -> FIRST_SHOT_DISTANCE_MISSING+UNKNOWN_LIE overlap
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="", end_distance_yd=100.0),
        # start_lie blank AND bunker end_lie -> UNKNOWN_LIE+SAND_SPARSE overlap
        _row(hole=2, shot_no=2, start_lie="", start_distance_yd=50.0, end_lie="벙커", end_distance_yd=80.0),
    ]
    result = model_eligibility_summary(rows)
    assert result["MULTIPLE_FLAGS"] == 2
    assert result["ELIGIBLE"] == 0
    assert result["MULTIPLE_FLAGS_combinations"] == {
        "FIRST_SHOT_DISTANCE_MISSING+UNKNOWN_LIE": 1,
        "UNKNOWN_LIE+SAND_SPARSE": 1,
    }
    assert result["sum_check"] == 2


def test_model_eligibility_summary_no_double_counting_sum_equals_total():
    rows = [
        _row(hole=1, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="페어웨이", end_distance_yd=150.0),
        _row(hole=1, shot_no=2, start_lie="페어웨이", start_distance_yd=150.0, end_lie="그린", end_distance_yd=10.0),
        _row(hole=2, shot_no=1, start_lie="티", start_distance_yd=None, end_lie="", end_distance_yd=100.0),
        _row(hole=3, shot_no=2, start_lie="벙커", start_distance_yd=100.0, end_lie="그린", end_distance_yd=0.0, zero_distance_ambiguous=True),
    ]
    result = model_eligibility_summary(rows)
    component_sum = (
        result["ELIGIBLE"] + result["FIRST_SHOT_DISTANCE_MISSING"]
        + result["UNKNOWN_LIE"] + result["ZERO_DISTANCE_UNKNOWN"]
        + result["SAND_SPARSE"] + result["MULTIPLE_FLAGS"]
    )
    assert component_sum == result["total_shots"] == len(rows)
    assert result["sum_check"] == result["total_shots"]
