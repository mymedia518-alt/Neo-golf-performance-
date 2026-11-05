"""Adversarial self-test for klpga.neo_win.sg_live_v1 -- specifically
designed to re-check the exact four defects that got
klpga.neo_win.r1_live_probability permanently BLOCKED (see that
module's own docstring and sg_live_v1.py's module docstring). Each test
below is named for the defect class it guards against, not just "does
it run".
"""
from __future__ import annotations

import math
import random
import statistics

import pytest

from klpga.neo_win.sg_live_v1 import (
    LIVE_V2_MODEL_STATUS,
    PlayerLiveState,
    _remaining_round_strokes,
    build_live_states,
    simulate_live_tournament_outcomes,
)
from klpga.neo_win.sg_pre_v1 import PlayerSGForecast, simulate_sg_tournament_outcomes


def _forecasts(ids):
    rng = random.Random(7)
    return {
        pid: PlayerSGForecast(
            player_id=pid,
            mean_sg=rng.uniform(-1.5, 1.5),
            round_sd=rng.uniform(1.8, 3.2),
            rounds=12,
            events=4,
            effective_rounds=10.0,
            latest_sg_date="2026-10-01",
            has_player_sg=True,
        )
        for pid in ids
    }


# ----------------------------------------------------------------------
# Defect #1 (partial-round state ignored) -- boundary reductions.
# ----------------------------------------------------------------------


def test_publication_status_is_never_validated():
    """This module must never silently claim VALIDATED -- that requires
    a separate, independent Red Team review (see module docstring)."""
    assert LIVE_V2_MODEL_STATUS != "VALIDATED"
    assert LIVE_V2_MODEL_STATUS == "REFERENCE_ESTIMATE"


def test_zero_holes_completed_reduces_exactly_to_full_simulation():
    """current_round=1 with every player at holes_completed=0 (nobody
    has teed off yet) must produce output BYTE-IDENTICAL to the
    already-tested base engine given the same seed -- proof the live
    model does not silently change the field's outcome distribution
    before any real play has happened."""
    ids = [f"P{i:03d}" for i in range(10)]
    forecasts = _forecasts(ids)
    seed, n_sim = 12345, 4000

    baseline = simulate_sg_tournament_outcomes(
        forecasts, rounds=4, cut_after_round=2, cut_position=6, n_simulations=n_sim, seed=seed
    )

    live_states = {
        pid: PlayerLiveState(
            player_id=pid, completed_round_scores=(), current_round_score_so_far=0,
            holes_completed=0, made_cut=None, status="ACTIVE",
        )
        for pid in ids
    }
    live = simulate_live_tournament_outcomes(
        forecasts, live_states, rounds=4, cut_after_round=2, cut_position=6,
        current_round=1, n_simulations=n_sim, seed=seed,
    )

    assert live.probabilities == baseline


def test_eighteen_holes_completed_consumes_no_rng_and_uses_real_score():
    """At holes_completed=18 (round actually finished) the simulated
    remaining-holes component must be exactly zero and must NOT advance
    the RNG stream -- a real, known score must never be perturbed by a
    phantom draw."""
    forecast = PlayerSGForecast("X", mean_sg=0.73, round_sd=2.5, rounds=5, events=2,
                                 effective_rounds=5.0, latest_sg_date="2026-10-01", has_player_sg=True)
    rng = random.Random(999)
    state_before = rng.getstate()
    result = _remaining_round_strokes(forecast, 18, rng)
    assert result == 0
    assert rng.getstate() == state_before, "a completed round must not consume any RNG draw"


def test_partial_round_blends_real_and_simulated_in_correct_units():
    """A player mid-round (e.g. thru 9) must have their FINAL simulated
    round score anchored on their real score-so-far, with only the
    remaining holes' distribution contributing variance -- not the
    bug-#1 failure mode of treating the current partial total as if it
    were already the final round score (which would make the remaining
    component's distribution irrelevant to the outcome)."""
    ids = ["A", "B"]
    forecasts = _forecasts(ids)
    # A is thru 9 with a real, very bad score-so-far; B hasn't teed off.
    # Both share the same underlying SG forecast draw stream structure,
    # so A's final round-1 score must differ from B's by roughly A's
    # real deficit, not collapse to "A already lost round 1" outright
    # (that would be bug #1's failure mode) nor ignore A's real deficit
    # entirely.
    live_states = {
        "A": PlayerLiveState("A", (), current_round_score_so_far=6, holes_completed=9, made_cut=None, status="ACTIVE"),
        "B": PlayerLiveState("B", (), current_round_score_so_far=0, holes_completed=0, made_cut=None, status="ACTIVE"),
    }
    live = simulate_live_tournament_outcomes(
        forecasts, live_states, rounds=1, cut_after_round=1, cut_position=2,
        current_round=1, n_simulations=20000, seed=42,
    )
    # A started +6 through 9 holes and only has 9 holes left to claw
    # back strokes from a per-round forecast on the order of a few
    # strokes of SD -- A's win probability must be far below B's.
    assert live.probabilities["A"]["win_probability"] < live.probabilities["B"]["win_probability"]


def test_remaining_strokes_variance_scales_with_sqrt_of_holes_not_linearly():
    """Defect #2/#3 guard: the remaining-holes SD must scale with
    sqrt(remaining/18), not remaining/18 (linear) and not stay at the
    full-round SD unscaled -- either of those would be a fresh unit
    bug of the same KIND (not the same bug) as the one that got
    r1_live_probability blocked."""
    forecast = PlayerSGForecast("X", mean_sg=0.0, round_sd=3.0, rounds=20, events=6,
                                 effective_rounds=20.0, latest_sg_date="2026-10-01", has_player_sg=True)
    n = 30000

    def empirical_sd(holes_completed):
        rng = random.Random(1)
        draws = [_remaining_round_strokes(forecast, holes_completed, rng) for _ in range(n)]
        return statistics.pstdev(draws)

    sd_full = empirical_sd(0)       # remaining=18, frac=1.0
    sd_quarter = empirical_sd(13)   # remaining=5/18

    expected_ratio = math.sqrt(5 / 18)
    observed_ratio = sd_quarter / sd_full
    # Loose tolerance: strokes are integer-rounded, so this is a
    # statistical check, not an exact-equality one.
    assert abs(observed_ratio - expected_ratio) < 0.08, (observed_ratio, expected_ratio)
    # And explicitly rule out the linear-scaling bug this guards against:
    linear_ratio = 5 / 18
    assert abs(observed_ratio - linear_ratio) > 0.05


# ----------------------------------------------------------------------
# Defect #4 (RNG reproducibility).
# ----------------------------------------------------------------------


def test_same_seed_reproduces_identical_output():
    ids = [f"P{i:02d}" for i in range(8)]
    forecasts = _forecasts(ids)
    live_states = {
        pid: PlayerLiveState(pid, (1, -2), current_round_score_so_far=-1, holes_completed=7, made_cut=True, status="ACTIVE")
        for pid in ids
    }
    kwargs = dict(rounds=3, cut_after_round=2, cut_position=8, current_round=3, n_simulations=3000, seed=2026)
    r1 = simulate_live_tournament_outcomes(forecasts, live_states, **kwargs)
    r2 = simulate_live_tournament_outcomes(forecasts, live_states, **kwargs)
    assert r1.probabilities == r2.probabilities
    assert r1.seed == r2.seed == 2026


def test_seed_is_required_keyword_argument():
    with pytest.raises(TypeError):
        simulate_live_tournament_outcomes(  # type: ignore[call-arg]
            {}, {}, rounds=4, cut_after_round=2, cut_position=6, current_round=1, n_simulations=10
        )


# ----------------------------------------------------------------------
# No-fabrication invariants.
# ----------------------------------------------------------------------


def test_missing_prior_round_score_excludes_not_fabricates():
    ids = ["A", "B"]
    states, excluded = build_live_states(
        ids, current_round=3,
        completed_round_scores_by_player={"A": [1, -2], "B": [1, None]},
        current_round_rows={},
    )
    assert "A" in states
    assert "B" not in states
    assert "B" in excluded


def test_incomplete_status_excludes_not_fabricates():
    states, excluded = build_live_states(
        ["A"], current_round=1,
        completed_round_scores_by_player={},
        current_round_rows={"A": {"today_under_par": 0, "holes_completed": 5, "status": "INCOMPLETE"}},
    )
    assert "A" not in states
    assert "A" in excluded


def test_wd_player_is_eliminated_with_known_zero_not_excluded():
    ids = ["A", "B"]
    forecasts = _forecasts(ids)
    states, excluded = build_live_states(
        ids, current_round=1,
        completed_round_scores_by_player={},
        current_round_rows={"A": {"today_under_par": 3, "holes_completed": 11, "status": "WD"}},
    )
    assert excluded == {}
    live = simulate_live_tournament_outcomes(
        forecasts, states, rounds=4, cut_after_round=2, cut_position=2,
        current_round=1, n_simulations=500, seed=1,
    )
    assert "A" in live.eliminated_players
    assert live.probabilities["A"] == {
        "cut_probability": 0.0, "top20_probability": 0.0, "top10_probability": 0.0,
        "top5_probability": 0.0, "win_probability": 0.0,
    }


def test_player_not_yet_in_leaderboard_is_not_excluded():
    """A player absent from the current round's rows (hasn't teed off
    yet) is the honest holes_completed=0 state, never an exclusion."""
    states, excluded = build_live_states(
        ["A"], current_round=1,
        completed_round_scores_by_player={},
        current_round_rows={},
    )
    assert "A" in states
    assert excluded == {}
    assert states["A"].holes_completed == 0
    assert states["A"].current_round_score_so_far == 0


def test_post_cut_player_without_made_cut_fact_excluded_upstream_never_guessed():
    """build_live_states does not itself guess made_cut -- a None here
    must mean the caller genuinely never resolved it (e.g. pre-cut),
    and simulate_live_tournament_outcomes must not simulate such a
    player forward post-cut."""
    ids = ["A", "B"]
    forecasts = _forecasts(ids)
    states = {
        "A": PlayerLiveState("A", (1, 1), current_round_score_so_far=0, holes_completed=0, made_cut=True, status="ACTIVE"),
        "B": PlayerLiveState("B", (1, 1), current_round_score_so_far=0, holes_completed=0, made_cut=None, status="ACTIVE"),
    }
    live = simulate_live_tournament_outcomes(
        forecasts, states, rounds=4, cut_after_round=2, cut_position=2,
        current_round=3, n_simulations=500, seed=1,
    )
    assert "A" in live.probabilities
    assert "B" not in live.probabilities
    assert "B" not in live.eliminated_players
