"""Tests for klpga.models.candidates — M0-M6 feature set fidelity to
the frozen spec, shrinkage/standardization correctness, and fit/predict
properties (determinism, valid probability distributions, rookie
handling)."""
from __future__ import annotations

import math

import pytest

from klpga.models.candidates import (
    MODEL_FEATURES,
    MODEL_IDS,
    apply_shrinkage_and_standardize,
    fit_candidate_model,
    fit_shrinkage,
    predict_candidate_model,
)


def test_exactly_m0_through_m6_no_more_no_less():
    assert set(MODEL_IDS) == {"M0", "M1", "M2", "M3", "M4", "M5", "M6"}


def test_frozen_feature_sets_match_spec_exactly():
    assert MODEL_FEATURES["M0"] == ()
    assert MODEL_FEATURES["M1"] == ("prior_avg_round_score_to_par",)
    assert MODEL_FEATURES["M2"] == ("prior_avg_field_relative_round_score",)
    assert MODEL_FEATURES["M3"] == ("prior_avg_round_score_to_par", "prior_recent_form_5")
    assert MODEL_FEATURES["M4"] == ("prior_avg_round_score_to_par", "prior_recent_form_10")
    assert MODEL_FEATURES["M5"] == ("prior_avg_field_relative_round_score", "prior_recent_form_5")
    assert MODEL_FEATURES["M6"] == ("prior_avg_field_relative_round_score", "prior_recent_form_10")


def test_no_forbidden_features_anywhere_in_the_ladder():
    forbidden = {
        "prior_wins", "prior_top5", "prior_top10", "prior_cut_rate", "prior_made_cuts",
        "prior_recent_form_20", "prior_avg_round_to_par",
    }
    used = {f for features in MODEL_FEATURES.values() for f in features}
    assert used.isdisjoint(forbidden), f"forbidden features leaked into the ladder: {used & forbidden}"


# ----------------------------------------------------------------
# Shrinkage / standardization
# ----------------------------------------------------------------


def test_fit_shrinkage_computes_mean_std_median_n_from_known_values():
    rows = [
        {"x": -2.0, "x_n": 4},
        {"x": -1.0, "x_n": 8},
        {"x": 0.0, "x_n": 2},
        {"x": None, "x_n": 0},  # excluded (NULL value)
        {"x": -3.0, "x_n": None},  # excluded (missing n)
    ]
    params = fit_shrinkage(rows, "x")
    assert params.pop_mean == pytest.approx(-1.0)  # mean(-2,-1,0)
    assert params.k == 4.0  # median(4, 8, 2) = 4


def test_fit_shrinkage_empty_returns_neutral_default():
    params = fit_shrinkage([], "x")
    assert params.pop_mean == 0.0
    assert params.pop_std == 1.0
    assert params.k == 1.0


def test_apply_shrinkage_null_value_gives_exact_zero():
    from klpga.models.candidates import ShrinkageParams

    params = ShrinkageParams(pop_mean=-1.5, pop_std=2.0, k=5.0)
    assert apply_shrinkage_and_standardize(None, 0, params) == 0.0
    assert apply_shrinkage_and_standardize(None, None, params) == 0.0
    assert apply_shrinkage_and_standardize(-3.0, 0, params) == 0.0  # n=0 -> full shrinkage regardless of value


def test_apply_shrinkage_full_history_approaches_raw_zscore():
    from klpga.models.candidates import ShrinkageParams

    params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=5.0)
    # n >> k -> weight -> 1 -> shrunk value -> raw value -> z -> raw value
    z_large_n = apply_shrinkage_and_standardize(4.0, 100000, params)
    assert z_large_n == pytest.approx(4.0, rel=1e-3)


def test_apply_shrinkage_partial_history_is_between_zero_and_raw_zscore():
    from klpga.models.candidates import ShrinkageParams

    params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=5.0)
    z = apply_shrinkage_and_standardize(4.0, 5, params)  # n == k -> weight = 0.5
    assert 0 < z < 4.0
    assert z == pytest.approx(2.0)  # weight=0.5 * (4.0-0.0)/1.0


# ----------------------------------------------------------------
# fit_candidate_model / predict_candidate_model
# ----------------------------------------------------------------


def _row(target, player, is_winner, **features):
    row = {"target_event_id": target, "player_code": player, "label_is_winner": is_winner}
    row.update(features)
    return row


def _training_rows():
    rows = []
    for t in range(10):
        rows.append(_row(f"T{t}", "A", t % 3 == 0,
                          prior_avg_round_score_to_par=-2.5, prior_avg_round_score_to_par_n=8,
                          prior_avg_field_relative_round_score=-2.0, prior_avg_field_relative_round_score_n=8,
                          prior_recent_form_5=-6.0, prior_recent_form_5_n=3,
                          prior_recent_form_10=-6.0, prior_recent_form_10_n=5))
        rows.append(_row(f"T{t}", "B", t % 3 != 0,
                          prior_avg_round_score_to_par=-0.5, prior_avg_round_score_to_par_n=8,
                          prior_avg_field_relative_round_score=-0.2, prior_avg_field_relative_round_score_n=8,
                          prior_recent_form_5=-1.0, prior_recent_form_5_n=3,
                          prior_recent_form_10=-1.0, prior_recent_form_10_n=5))
    return rows


def test_m0_has_no_parameters_and_predicts_exact_uniform():
    fitted = fit_candidate_model("M0", [])
    assert fitted.tau is None and fitted.beta is None
    field = [_row("T", "A", True), _row("T", "B", False), _row("T", "C", False)]
    preds = predict_candidate_model(fitted, field)
    assert preds == {"A": pytest.approx(1 / 3), "B": pytest.approx(1 / 3), "C": pytest.approx(1 / 3)}


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_every_model_predicts_a_valid_field_distribution(model_id):
    training = _training_rows()
    fitted = fit_candidate_model(model_id, training)
    field = [
        _row("TARGET", "A", True, prior_avg_round_score_to_par=-2.5, prior_avg_round_score_to_par_n=8,
             prior_avg_field_relative_round_score=-2.0, prior_avg_field_relative_round_score_n=8,
             prior_recent_form_5=-6.0, prior_recent_form_5_n=3, prior_recent_form_10=-6.0, prior_recent_form_10_n=5),
        _row("TARGET", "B", False, prior_avg_round_score_to_par=-0.5, prior_avg_round_score_to_par_n=8,
             prior_avg_field_relative_round_score=-0.2, prior_avg_field_relative_round_score_n=8,
             prior_recent_form_5=-1.0, prior_recent_form_5_n=3, prior_recent_form_10=-1.0, prior_recent_form_10_n=5),
        _row("TARGET", "ROOKIE", False),  # every feature NULL/0
    ]
    preds = predict_candidate_model(fitted, field)
    assert set(preds) == {"A", "B", "ROOKIE"}
    assert abs(sum(preds.values()) - 1.0) < 1e-9
    for player, p in preds.items():
        assert math.isfinite(p)
        assert p > 0, f"{model_id}: {player} got non-positive probability"


def test_fit_is_deterministic_across_repeated_calls():
    training = _training_rows()
    fitted_a = fit_candidate_model("M4", training)
    fitted_b = fit_candidate_model("M4", training)
    assert fitted_a.tau == fitted_b.tau
    assert fitted_a.beta == fitted_b.beta


def test_fit_with_no_training_tournaments_falls_back_without_crashing():
    fitted = fit_candidate_model("M1", [])
    assert fitted.tau == 1.0
    field = [_row("T", "A", True), _row("T", "B", False)]
    preds = predict_candidate_model(fitted, field)
    assert abs(sum(preds.values()) - 1.0) < 1e-9


def test_predict_on_empty_field_returns_empty_dict():
    fitted = fit_candidate_model("M1", _training_rows())
    assert predict_candidate_model(fitted, []) == {}
