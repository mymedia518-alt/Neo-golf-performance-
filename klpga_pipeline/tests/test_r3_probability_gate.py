"""R3 HOUSE: klpga.neo_win.r3_probability_gate -- probability hard gate."""
from __future__ import annotations

import math

import pytest

from klpga.neo_win.r3_probability_gate import ProbabilityGateError, validate_r3_probability_gate


def _forecast(records, **overrides):
    base = {
        "game_code": "TEST0003", "source_round": 3, "n_simulations": 10000,
        "future_data_excluded": True, "records": records,
    }
    base.update(overrides)
    return base


def test_valid_forecast_passes():
    records = [{"player_id": "p1", "win_pct": 10.0, "top5_pct": 30.0, "top10_pct": 60.0, "top20_pct": 90.0}]
    validate_r3_probability_gate(_forecast(records), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_wrong_game_code_hard_stops():
    records = [{"player_id": "p1", "win_pct": 1.0, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    with pytest.raises(ProbabilityGateError, match="wrong tournament"):
        validate_r3_probability_gate(_forecast(records), expected_game_code="OTHER", expected_active_player_ids={"p1"})


def test_wrong_source_round_hard_stops():
    records = [{"player_id": "p1", "win_pct": 1.0, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    with pytest.raises(ProbabilityGateError, match="source_round"):
        validate_r3_probability_gate(_forecast(records, source_round=2), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_zero_simulations_hard_stops():
    records = [{"player_id": "p1", "win_pct": 1.0, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    with pytest.raises(ProbabilityGateError, match="simulation count"):
        validate_r3_probability_gate(_forecast(records, n_simulations=0), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_future_data_not_excluded_hard_stops():
    records = [{"player_id": "p1", "win_pct": 1.0, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    with pytest.raises(ProbabilityGateError, match="future_data_excluded"):
        validate_r3_probability_gate(_forecast(records, future_data_excluded=False), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_population_mismatch_hard_stops():
    records = [{"player_id": "p1", "win_pct": 1.0, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    with pytest.raises(ProbabilityGateError, match="population mismatch"):
        validate_r3_probability_gate(_forecast(records), expected_game_code="TEST0003", expected_active_player_ids={"p1", "p2"})


def test_non_finite_value_hard_stops():
    records = [{"player_id": "p1", "win_pct": math.nan, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    with pytest.raises(ProbabilityGateError, match="not finite"):
        validate_r3_probability_gate(_forecast(records), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_out_of_bounds_value_hard_stops():
    records = [{"player_id": "p1", "win_pct": 101.0, "top5_pct": 101.0, "top10_pct": 101.0, "top20_pct": 101.0}]
    with pytest.raises(ProbabilityGateError, match="out of bounds"):
        validate_r3_probability_gate(_forecast(records), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_monotonicity_violation_hard_stops():
    records = [{"player_id": "p1", "win_pct": 50.0, "top5_pct": 40.0, "top10_pct": 60.0, "top20_pct": 90.0}]
    with pytest.raises(ProbabilityGateError, match="monotonicity"):
        validate_r3_probability_gate(_forecast(records), expected_game_code="TEST0003", expected_active_player_ids={"p1"})


def test_forbidden_result_field_hard_stops():
    """Delegates to r3_leakage_gate.assert_no_forbidden_result_fields,
    which raises its own FutureLeakageError -- same convention as
    r2_probability_gate's identical delegation."""
    from klpga.evidence.manifest import FORBIDDEN_RESULT_FIELDS
    from klpga.neo_win.r3_leakage_gate import FutureLeakageError
    records = [{"player_id": "p1", "win_pct": 1.0, "top5_pct": 1.0, "top10_pct": 1.0, "top20_pct": 1.0}]
    forecast = _forecast(records)
    forecast[sorted(FORBIDDEN_RESULT_FIELDS)[0]] = "x"
    with pytest.raises(FutureLeakageError):
        validate_r3_probability_gate(forecast, expected_game_code="TEST0003", expected_active_player_ids={"p1"})
