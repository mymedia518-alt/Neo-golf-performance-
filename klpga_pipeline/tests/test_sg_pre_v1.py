from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.sg_pre_v1 import (  # noqa: E402
    PlayerSGForecast,
    estimate_player_sg_forecasts,
    simulate_sg_tournament_outcomes,
)


def test_sg_forecast_uses_only_strictly_prior_rounds_and_shrinks_sparse_data():
    rows = [
        {"player_id": "a", "game_code": "g1", "round": 1, "scope": "single_round", "date": "2026-08-01", "total": 2.0},
        {"player_id": "a", "game_code": "g2", "round": 1, "scope": "single_round", "date": "2026-08-02", "total": 4.0},
        {"player_id": "b", "game_code": "g2", "round": 1, "scope": "single_round", "date": "2026-08-02", "total": -2.0},
    ]
    forecast = estimate_player_sg_forecasts(
        ["a", "b", "rookie"], rows, cutoff_date="2026-08-02", half_life_days=90, prior_rounds=2
    )
    assert forecast["a"].rounds == 1
    assert forecast["a"].mean_sg < 2.0
    assert forecast["b"].rounds == 0  # same-day SG is excluded
    assert forecast["rookie"].mean_sg == 0.0
    assert not forecast["rookie"].has_player_sg


def test_sg_simulator_is_deterministic_and_all_outcomes_are_nested():
    forecasts = {
        str(i): PlayerSGForecast(str(i), 0.04 * i, 2.3, 30, 8, 25.0, "2026-10-18", True)
        for i in range(35)
    }
    first = simulate_sg_tournament_outcomes(forecasts, n_simulations=2500, seed=42)
    second = simulate_sg_tournament_outcomes(forecasts, n_simulations=2500, seed=42)
    assert first == second
    assert abs(sum(row["win_probability"] for row in first.values()) - 1.0) < 1e-9
    for row in first.values():
        assert row["cut_probability"] >= row["top20_probability"]
        assert row["top20_probability"] >= row["top10_probability"]
        assert row["top10_probability"] >= row["top5_probability"]
        assert row["top5_probability"] >= row["win_probability"]


def test_no_sg_players_remain_in_the_full_simulated_field():
    forecasts = {
        "known": PlayerSGForecast("known", 0.8, 2.5, 30, 8, 24.0, "2026-10-18", True),
        "missing": PlayerSGForecast("missing", 0.0, 2.5, 0, 0, 0.0, None, False),
    }
    outcomes = simulate_sg_tournament_outcomes(
        forecasts, rounds=4, cut_position=1, n_simulations=1000, seed=7
    )
    assert set(outcomes) == {"known", "missing"}
    assert outcomes["missing"]["win_probability"] > 0.0
