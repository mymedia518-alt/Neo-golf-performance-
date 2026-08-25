"""Tests for klpga.models.metrics — primary metrics (log loss, Brier),
rank/hit-rate diagnostics, calibration, and the paired comparison, all
hand-computed against known values."""
from __future__ import annotations

import math

import pytest

from klpga.models.metrics import (
    LOG_LOSS_EPSILON,
    brier_norm,
    brier_raw,
    calibration_report,
    log_loss,
    make_prediction,
    paired_comparison,
    reciprocal_rank,
    summarize_model,
    top_k_hit,
    winner_rank,
)


def test_make_prediction_clips_and_renormalizes():
    pred = make_prediction("T", "T", "2026-01-01", {"A": 1.0, "B": 0.0}, "A", {})
    assert pred.probabilities["B"] > 0
    assert abs(sum(pred.probabilities.values()) - 1.0) < 1e-9


def test_log_loss_known_value():
    pred = make_prediction("T", "T", "2026-01-01", {"A": 0.25, "B": 0.75}, "A", {})
    assert log_loss(pred) == pytest.approx(-math.log(0.25), rel=1e-6)


def test_brier_raw_and_norm_known_value():
    pred = make_prediction("T", "T", "2026-01-01", {"A": 0.5, "B": 0.3, "C": 0.2}, "A", {})
    expected_raw = (0.5 - 1) ** 2 + (0.3 - 0) ** 2 + (0.2 - 0) ** 2
    assert brier_raw(pred) == pytest.approx(expected_raw, rel=1e-6)
    assert brier_norm(pred) == pytest.approx(expected_raw / 3, rel=1e-6)


def test_winner_rank_and_top_k_hit():
    pred = make_prediction("T", "T", "2026-01-01", {"A": 0.1, "B": 0.5, "C": 0.4}, "C", {})
    assert winner_rank(pred) == 2  # B(0.5) > C(0.4) > A(0.1)
    assert top_k_hit(pred, 2) is True
    assert top_k_hit(pred, 1) is False
    assert reciprocal_rank(pred) == pytest.approx(0.5)


def test_winner_rank_tie_break_is_deterministic_by_player_code():
    pred = make_prediction("T", "T", "2026-01-01", {"A": 0.5, "B": 0.5}, "B", {})
    # A sorts before B alphabetically on an exact tie -> A rank 1, B rank 2.
    assert winner_rank(pred) == 2


def test_summarize_model_aggregates_across_tournaments():
    preds = [
        make_prediction("T1", "T1", "2026-01-01", {"A": 0.5, "B": 0.5}, "A", {}),
        make_prediction("T2", "T2", "2026-02-01", {"A": 0.5, "B": 0.5}, "B", {}),
    ]
    summary = summarize_model("TEST", preds)
    assert summary.tournament_count == 2
    assert summary.mean_log_loss == pytest.approx(-math.log(0.5), rel=1e-6)
    assert summary.top3_rate == 1.0


def test_summarize_model_empty_list_does_not_crash():
    summary = summarize_model("EMPTY", [])
    assert summary.tournament_count == 0
    assert math.isnan(summary.mean_log_loss)


def test_paired_comparison_matches_by_target_event_id_only():
    preds_a = [
        make_prediction("T1", "T1", "2026-01-01", {"A": 0.9, "B": 0.1}, "A", {}),
        make_prediction("T2", "T2", "2026-02-01", {"A": 0.9, "B": 0.1}, "A", {}),
    ]
    preds_b = [
        make_prediction("T1", "T1", "2026-01-01", {"A": 0.5, "B": 0.5}, "A", {}),
        # T2 missing from B entirely -> only T1 is paired
    ]
    cmp = paired_comparison(preds_a, preds_b, metric_fn=log_loss)
    assert cmp["n"] == 1


def test_calibration_report_bin_counts_and_expected_actual_wins():
    preds = [
        make_prediction("T1", "T1", "2026-01-01", {"A": 0.5, "B": 0.5}, "A", {}),
        make_prediction("T2", "T2", "2026-02-01", {"A": 0.5, "B": 0.5}, "B", {}),
    ]
    bins = calibration_report(preds, n_bootstrap=20)
    last_bin = bins[-1]  # [0.20, 1.0] bucket should hold all four 0.5-probability rows
    assert last_bin.row_count == 4
    assert last_bin.actual_wins == 2
    assert last_bin.expected_wins == pytest.approx(2.0, rel=1e-6)
    assert last_bin.contributing_tournament_count == 2


def test_calibration_report_empty_predictions_does_not_crash():
    bins = calibration_report([], n_bootstrap=10)
    assert all(b.row_count == 0 for b in bins)


def test_log_loss_epsilon_is_the_documented_pre_registered_value():
    assert LOG_LOSS_EPSILON == 1e-6
