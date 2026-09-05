import random

import pytest

from klpga.neo_win.round_update_r2 import (
    PlayerR2SimInput,
    simulate_post_round2,
)


def _players():
    return [
        PlayerR2SimInput(
            player_code="A",
            player_name="A",
            expected_round_score_to_par=-1.0,
            spread=1.0,
            r1_score_to_par=-2.0,
            r2_score_to_par=-2.0,
            made_cut=True,
        ),
        PlayerR2SimInput(
            player_code="B",
            player_name="B",
            expected_round_score_to_par=0.0,
            spread=1.0,
            r1_score_to_par=-1.0,
            r2_score_to_par=-1.0,
            made_cut=True,
        ),
        PlayerR2SimInput(
            player_code="C",
            player_name="C",
            expected_round_score_to_par=1.0,
            spread=1.0,
            r1_score_to_par=0.0,
            r2_score_to_par=0.0,
            made_cut=False,
        ),
    ]


def test_54_hole_event_simulates_one_remaining_round():
    result = simulate_post_round2(
        _players(),
        remaining_rounds=1,
        n_simulations=500,
        rng=random.Random(12345),
    )

    assert set(result) == {"A", "B", "C"}
    assert result["C"]["win_pct"] == 0.0
    assert result["C"]["make_cut_pct"] == 0.0
    assert result["A"]["make_cut_pct"] == 100.0
    assert result["B"]["make_cut_pct"] == 100.0


def test_72_hole_event_preserves_two_remaining_round_default():
    default_result = simulate_post_round2(
        _players(),
        n_simulations=500,
        rng=random.Random(9876),
    )

    explicit_result = simulate_post_round2(
        _players(),
        remaining_rounds=2,
        n_simulations=500,
        rng=random.Random(9876),
    )

    assert default_result == explicit_result


def test_remaining_rounds_changes_forecast_path():
    one = simulate_post_round2(
        _players(),
        remaining_rounds=1,
        n_simulations=1000,
        rng=random.Random(42),
    )

    two = simulate_post_round2(
        _players(),
        remaining_rounds=2,
        n_simulations=1000,
        rng=random.Random(42),
    )

    assert one != two


def test_invalid_remaining_rounds_hard_stops():
    with pytest.raises(ValueError):
        simulate_post_round2(
            _players(),
            remaining_rounds=0,
            n_simulations=10,
            rng=random.Random(1),
        )
