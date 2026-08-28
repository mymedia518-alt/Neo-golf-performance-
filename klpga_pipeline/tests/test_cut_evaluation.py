"""Tests for klpga.neo_win.cut_evaluation — the binary MAKE CUT
probability evaluation (BETA #001 R1 -> R2). Independently testable
with synthetic inputs, per the R1->R2 pipeline's own hard-validation
requirement (Brier calc, log-loss clipping, calibration bucket sums,
WD/DQ never silently treated as missed cut)."""
from __future__ import annotations

import math

import pytest

from klpga.neo_win.cut_evaluation import (
    CALIBRATION_BUCKETS,
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD,
    CUT_OUTCOME_WD_AFTER_R1_START,
    PlayerCutEvaluationRow,
    actual_cut_from_outcome,
    best_and_worst_predictions,
    binary_brier_score,
    binary_log_loss,
    calibration_report,
    summarize_cut_evaluation,
    threshold_accuracy,
    threshold_bucket_survival,
)


def _row(code, name, r1_make_cut_pct, outcome, rank=1, score=-2):
    return PlayerCutEvaluationRow(
        player_code=code, player_name=name, r1_rank=rank, r1_score_to_par=score,
        r1_make_cut_pct=r1_make_cut_pct, r2_outcome=outcome,
    )


# ---------------------------------------------------------------
# actual_cut_from_outcome — WD/DQ/UNRESOLVED policy
# ---------------------------------------------------------------


def test_made_cut_maps_to_1():
    assert actual_cut_from_outcome(CUT_OUTCOME_MADE) == 1


def test_missed_cut_maps_to_0():
    assert actual_cut_from_outcome(CUT_OUTCOME_MISSED) == 0


def test_wd_and_dq_and_unresolved_map_to_none_never_zero():
    assert actual_cut_from_outcome(CUT_OUTCOME_WD) is None
    assert actual_cut_from_outcome(CUT_OUTCOME_DQ) is None
    assert actual_cut_from_outcome(CUT_OUTCOME_UNRESOLVED) is None


def test_unknown_outcome_raises_never_silently_accepted():
    with pytest.raises(ValueError):
        actual_cut_from_outcome("SOME_UNKNOWN_STATUS")


def test_wd_after_r1_start_maps_to_none_and_is_reported_separately():
    assert actual_cut_from_outcome(CUT_OUTCOME_WD_AFTER_R1_START) is None
    rows = [
        _row("p1", "A", 80.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 20.0, CUT_OUTCOME_WD_AFTER_R1_START),
    ]
    summary = summarize_cut_evaluation(rows)
    assert summary["n_evaluated"] == 1  # only p1
    assert summary["wd_after_r1_start_count"] == 1
    assert summary["wd_count"] == 0  # never folded into generic WD


def test_wd_dq_excluded_from_evaluated_set_not_counted_as_missed():
    rows = [
        _row("p1", "A", 80.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 20.0, CUT_OUTCOME_WD),
        _row("p3", "C", 10.0, CUT_OUTCOME_DQ),
    ]
    summary = summarize_cut_evaluation(rows)
    assert summary["n_evaluated"] == 1  # only p1
    assert summary["wd_count"] == 1
    assert summary["dq_count"] == 1
    assert summary["actual_missed_cut_count"] == 0  # WD/DQ never silently counted as missed


# ---------------------------------------------------------------
# binary_brier_score — hand-computed reference values
# ---------------------------------------------------------------


def test_brier_score_hand_computed():
    rows = [
        _row("p1", "A", 100.0, CUT_OUTCOME_MADE),   # (1.0-1)^2 = 0
        _row("p2", "B", 0.0, CUT_OUTCOME_MISSED),   # (0.0-0)^2 = 0
        _row("p3", "C", 75.0, CUT_OUTCOME_MADE),    # (0.75-1)^2 = 0.0625
        _row("p4", "D", 25.0, CUT_OUTCOME_MISSED),  # (0.25-0)^2 = 0.0625
    ]
    expected = (0 + 0 + 0.0625 + 0.0625) / 4
    assert binary_brier_score(rows) == pytest.approx(expected)


def test_brier_score_none_when_nothing_evaluated():
    rows = [_row("p1", "A", 50.0, CUT_OUTCOME_WD)]
    assert binary_brier_score(rows) is None


def test_brier_perfect_prediction_is_zero():
    rows = [_row("p1", "A", 100.0, CUT_OUTCOME_MADE), _row("p2", "B", 0.0, CUT_OUTCOME_MISSED)]
    assert binary_brier_score(rows) == pytest.approx(0.0)


def test_brier_worst_prediction_is_one():
    rows = [_row("p1", "A", 0.0, CUT_OUTCOME_MADE), _row("p2", "B", 100.0, CUT_OUTCOME_MISSED)]
    assert binary_brier_score(rows) == pytest.approx(1.0)


# ---------------------------------------------------------------
# binary_log_loss — clipping documented and verified
# ---------------------------------------------------------------


def test_log_loss_hand_computed():
    rows = [_row("p1", "A", 75.0, CUT_OUTCOME_MADE), _row("p2", "B", 25.0, CUT_OUTCOME_MISSED)]
    expected = (-math.log(0.75) + -math.log(1 - 0.25)) / 2
    assert binary_log_loss(rows) == pytest.approx(expected)


def test_log_loss_clips_0_and_100_pct_never_infinite():
    rows = [_row("p1", "A", 100.0, CUT_OUTCOME_MADE), _row("p2", "B", 0.0, CUT_OUTCOME_MISSED)]
    result = binary_log_loss(rows)
    assert result is not None
    assert math.isfinite(result)
    assert result == pytest.approx(0.0, abs=1e-6)  # clipped near-perfect prediction -> near-zero loss


def test_log_loss_wrong_confident_prediction_is_large_but_finite():
    rows = [_row("p1", "A", 100.0, CUT_OUTCOME_MISSED)]  # confidently wrong
    result = binary_log_loss(rows)
    assert math.isfinite(result)
    assert result > 10  # clipped to eps=1e-15 -> -log(1e-15) ~= 34.5


def test_log_loss_none_when_nothing_evaluated():
    rows = [_row("p1", "A", 50.0, CUT_OUTCOME_DQ)]
    assert binary_log_loss(rows) is None


# ---------------------------------------------------------------
# threshold_accuracy
# ---------------------------------------------------------------


def test_threshold_accuracy_hand_computed():
    rows = [
        _row("p1", "A", 60.0, CUT_OUTCOME_MADE),    # predicted 1, actual 1 -> correct
        _row("p2", "B", 40.0, CUT_OUTCOME_MISSED),  # predicted 0, actual 0 -> correct
        _row("p3", "C", 60.0, CUT_OUTCOME_MISSED),  # predicted 1, actual 0 -> wrong
    ]
    result = threshold_accuracy(rows)
    assert result["n_evaluated"] == 3
    assert result["correct"] == 2
    assert result["accuracy"] == pytest.approx(2 / 3)


def test_threshold_boundary_exactly_50_counts_as_predicted_made_cut():
    rows = [_row("p1", "A", 50.0, CUT_OUTCOME_MADE)]
    result = threshold_accuracy(rows)
    assert result["correct"] == 1  # >= 50 -> predicted 1, actual 1


# ---------------------------------------------------------------
# calibration_report — bucket boundaries + sum-to-evaluated-count
# ---------------------------------------------------------------


def test_calibration_buckets_always_five_rows_even_if_empty():
    rows = [_row("p1", "A", 10.0, CUT_OUTCOME_MADE)]
    report = calibration_report(rows)
    assert len(report) == len(CALIBRATION_BUCKETS) == 5
    assert report[0]["n"] == 1
    assert all(r["n"] in (0, 1) for r in report)


def test_calibration_bucket_counts_sum_to_evaluated_count():
    rows = [
        _row("p1", "A", 10.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 30.0, CUT_OUTCOME_MISSED),
        _row("p3", "C", 55.0, CUT_OUTCOME_MADE),
        _row("p4", "D", 90.0, CUT_OUTCOME_MADE),
        _row("p5", "E", 95.0, CUT_OUTCOME_MISSED),
        _row("p6", "F", 50.0, CUT_OUTCOME_WD),  # excluded — must not be counted in any bucket
    ]
    report = calibration_report(rows)
    total_n = sum(r["n"] for r in report)
    assert total_n == 5  # 6 rows minus the 1 WD


def test_calibration_boundary_exactly_40_goes_to_higher_bucket():
    # 40.0 must land in the 40-60 bucket, not 20-40 (right-open convention, documented in module docstring)
    rows = [_row("p1", "A", 40.0, CUT_OUTCOME_MADE)]
    report = calibration_report(rows)
    bucket_20_40 = next(r for r in report if r["bucket"] == "20-40%")
    bucket_40_60 = next(r for r in report if r["bucket"] == "40-60%")
    assert bucket_20_40["n"] == 0
    assert bucket_40_60["n"] == 1


def test_calibration_boundary_exactly_100_goes_in_final_closed_bucket():
    rows = [_row("p1", "A", 100.0, CUT_OUTCOME_MADE)]
    report = calibration_report(rows)
    bucket_80_100 = next(r for r in report if r["bucket"] == "80-100%")
    assert bucket_80_100["n"] == 1


def test_calibration_gap_formula():
    rows = [
        _row("p1", "A", 90.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 90.0, CUT_OUTCOME_MISSED),
    ]
    report = calibration_report(rows)
    bucket = next(r for r in report if r["bucket"] == "80-100%")
    assert bucket["avg_predicted_pct"] == pytest.approx(90.0)
    assert bucket["actual_made_cut_rate_pct"] == pytest.approx(50.0)
    assert bucket["calibration_gap_pct"] == pytest.approx(50.0 - 90.0)  # actual - predicted


# ---------------------------------------------------------------
# best_and_worst_predictions — explicit, deterministic ranking rule
# ---------------------------------------------------------------


def test_best_and_worst_ranked_by_absolute_error():
    rows = [
        _row("p1", "A", 95.0, CUT_OUTCOME_MADE),    # error 0.05 -> best
        _row("p2", "B", 5.0, CUT_OUTCOME_MADE),      # error 0.95 -> worst
        _row("p3", "C", 50.0, CUT_OUTCOME_MISSED),   # error 0.50
    ]
    best, worst = best_and_worst_predictions(rows, n=1)
    assert best[0].player_code == "p1"
    assert worst[0].player_code == "p2"


def test_best_worst_deterministic_tie_break_by_player_code():
    rows = [
        _row("p2", "B", 50.0, CUT_OUTCOME_MADE),  # error 0.5
        _row("p1", "A", 50.0, CUT_OUTCOME_MADE),  # error 0.5, same error -> p1 sorts first
    ]
    best, _worst = best_and_worst_predictions(rows, n=2)
    assert [r.player_code for r in best] == ["p1", "p2"]


def test_best_worst_excludes_wd_dq():
    rows = [_row("p1", "A", 50.0, CUT_OUTCOME_MADE), _row("p2", "B", 90.0, CUT_OUTCOME_WD)]
    best, worst = best_and_worst_predictions(rows, n=5)
    codes = {r.player_code for r in best} | {r.player_code for r in worst}
    assert "p2" not in codes


# ---------------------------------------------------------------
# summarize_cut_evaluation — full integration of the above
# ---------------------------------------------------------------


def test_summarize_reports_all_required_fields():
    rows = [
        _row("p1", "A", 80.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 20.0, CUT_OUTCOME_MISSED),
        _row("p3", "C", 50.0, CUT_OUTCOME_WD),
        _row("p4", "D", 50.0, CUT_OUTCOME_DQ),
        _row("p5", "E", 50.0, CUT_OUTCOME_UNRESOLVED),
    ]
    summary = summarize_cut_evaluation(rows)
    assert summary["n_r1_players"] == 5
    assert summary["n_evaluated"] == 2
    assert summary["wd_count"] == 1
    assert summary["dq_count"] == 1
    assert summary["unresolved_count"] == 1
    assert summary["brier_score"] is not None
    assert summary["log_loss"] is not None
    assert 0 <= summary["threshold_accuracy_pct"] <= 100


def test_summarize_all_none_when_no_evaluated_players():
    rows = [_row("p1", "A", 50.0, CUT_OUTCOME_WD)]
    summary = summarize_cut_evaluation(rows)
    assert summary["n_evaluated"] == 0
    assert summary["brier_score"] is None
    assert summary["log_loss"] is None
    assert summary["threshold_accuracy_pct"] is None


# ---------------------------------------------------------------
# threshold_bucket_survival
# ---------------------------------------------------------------


def test_threshold_bucket_survival_counts_real_players_at_or_above():
    rows = [
        _row("p1", "A", 80.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 45.0, CUT_OUTCOME_MADE),
        _row("p3", "C", 40.0, CUT_OUTCOME_MISSED),
        _row("p4", "D", 20.0, CUT_OUTCOME_MISSED),
    ]
    result = threshold_bucket_survival(rows, 40.0)
    assert result["threshold_pct"] == 40.0
    assert result["n_at_or_above"] == 3  # p1, p2, p3
    assert result["n_made_cut"] == 2  # p1, p2


def test_threshold_bucket_survival_excludes_wd_dq_unresolved():
    rows = [
        _row("p1", "A", 80.0, CUT_OUTCOME_MADE),
        _row("p2", "B", 80.0, CUT_OUTCOME_WD),
        _row("p3", "C", 80.0, CUT_OUTCOME_UNRESOLVED),
    ]
    result = threshold_bucket_survival(rows, 40.0)
    assert result["n_at_or_above"] == 1
    assert result["n_made_cut"] == 1


def test_threshold_bucket_survival_zero_when_nothing_at_or_above():
    rows = [_row("p1", "A", 10.0, CUT_OUTCOME_MISSED)]
    result = threshold_bucket_survival(rows, 40.0)
    assert result["n_at_or_above"] == 0
    assert result["n_made_cut"] == 0
