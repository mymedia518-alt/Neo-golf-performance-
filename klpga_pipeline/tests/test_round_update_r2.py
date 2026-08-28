"""Tests for klpga.neo_win.round_update_r2 — the post-Round-2 Monte
Carlo simulation. The cut is a REAL, KNOWN fact here (unlike post-R1,
where it's still simulated) — these tests specifically pin that
distinction."""
from __future__ import annotations

import random

from klpga.neo_win.archive import NeoWinEntrantSnapshot
from klpga.neo_win.beta001c_archive import NeoWinCEntrantSnapshot
from klpga.neo_win.round_update_r2 import (
    PlayerR2SimInput,
    build_r2_sim_inputs_from_frozen_snapshot,
    simulate_post_round2,
)


class _FakeSnapshot:
    def __init__(self, predictions):
        self.predictions = predictions


def _entrant(code, name, win_prob, score_to_par, consistency):
    return NeoWinEntrantSnapshot(
        rank=1, player_code=code, player_name=name, win_probability=win_prob,
        prior_events_n=10, prior_avg_round_score_to_par=score_to_par, prior_recent_form_10=score_to_par,
        prior_recent_form_10_n=10, neo_consistency_stddev=consistency, neo_consistency_stddev_n=10,
        official_metrics={}, player_master_matched=True,
    )


# ---------------------------------------------------------------
# build_r2_sim_inputs_from_frozen_snapshot
# ---------------------------------------------------------------


def test_build_sim_inputs_uses_frozen_values_and_real_scores_and_cut():
    snapshot = _FakeSnapshot([_entrant("p1", "A", 0.10, -1.0, 2.0)])
    inputs, missing = build_r2_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -3.0}, {"p1": -2.0}, {"p1": True}
    )
    assert missing == []
    assert inputs[0].r1_score_to_par == -3.0
    assert inputs[0].r2_score_to_par == -2.0
    assert inputs[0].made_cut is True
    assert inputs[0].expected_round_score_to_par == -1.0
    assert inputs[0].spread == 2.0


def test_build_sim_inputs_shrinks_missing_pre_values_to_population_mean():
    snapshot = _FakeSnapshot([
        _entrant("p1", "A", 0.10, -1.0, 2.0),
        _entrant("p2", "B", 0.05, None, None),
    ])
    inputs, _ = build_r2_sim_inputs_from_frozen_snapshot(snapshot, {"p1": -3, "p2": -1}, {"p1": -2, "p2": 0}, {"p1": True, "p2": False})
    p2 = next(i for i in inputs if i.player_code == "p2")
    assert p2.expected_round_score_to_par == -1.0  # population mean of known scores (-1.0)


def test_missing_r1_r2_or_made_cut_reported_and_never_guessed():
    snapshot = _FakeSnapshot([_entrant("p1", "A", 0.10, -1.0, 2.0), _entrant("p2", "B", 0.05, -1.0, 2.0)])
    inputs, missing = build_r2_sim_inputs_from_frozen_snapshot(
        snapshot, r1_scores={"p1": -3.0}, r2_scores={"p1": -2.0}, made_cut_by_player={"p1": True}
    )
    assert missing == ["p2"]
    p2 = next(i for i in inputs if i.player_code == "p2")
    assert p2.r1_score_to_par is None
    assert p2.r2_score_to_par is None
    assert p2.made_cut is None


def test_build_sim_inputs_reads_beta001c_snapshot_shape_without_crashing():
    """Regression test for the real, confirmed R1->R2 pipeline-preparation
    bug: a NeoWinCEntrantSnapshot (the current BETA #001-C production PRE
    shape) stores prior_avg_round_score_to_par / neo_consistency_stddev
    ONLY inside feature_values, never as top-level attributes — the
    previous code (`e.prior_avg_round_score_to_par`) raised AttributeError
    for exactly this shape, which is scripts/44's DEFAULT/preferred path.
    This test would have failed before the _feature() accessor fix."""
    c_entrant = NeoWinCEntrantSnapshot(
        rank=1, player_code="p1", player_name="A", win_probability=0.10, prior_events_n=10,
        feature_values={"prior_avg_round_score_to_par": -1.5, "neo_consistency_stddev": 2.5},
        player_master_matched=True,
    )
    snapshot = _FakeSnapshot([c_entrant])
    inputs, missing = build_r2_sim_inputs_from_frozen_snapshot(
        snapshot, r1_scores={"p1": -3.0}, r2_scores={"p1": -2.0}, made_cut_by_player={"p1": True}
    )
    assert missing == []
    assert inputs[0].expected_round_score_to_par == -1.5
    assert inputs[0].spread == 2.5


def test_build_sim_inputs_beta001c_missing_feature_shrinks_to_population_mean():
    """A NeoWinCEntrantSnapshot with a feature genuinely absent from
    feature_values (not just a missing top-level attribute) still shrinks
    to the population mean, same convention as the legacy shape."""
    known = NeoWinCEntrantSnapshot(
        rank=1, player_code="p1", player_name="A", win_probability=0.10, prior_events_n=10,
        feature_values={"prior_avg_round_score_to_par": -2.0, "neo_consistency_stddev": 3.0},
        player_master_matched=True,
    )
    missing_feature = NeoWinCEntrantSnapshot(
        rank=2, player_code="p2", player_name="B", win_probability=0.05, prior_events_n=0,
        feature_values={}, player_master_matched=True,
    )
    snapshot = _FakeSnapshot([known, missing_feature])
    inputs, _missing = build_r2_sim_inputs_from_frozen_snapshot(
        snapshot, r1_scores={"p1": -3.0, "p2": -1.0}, r2_scores={"p1": -2.0, "p2": 0.0},
        made_cut_by_player={"p1": True, "p2": False},
    )
    p2 = next(i for i in inputs if i.player_code == "p2")
    assert p2.expected_round_score_to_par == -2.0  # population mean of the one known value
    assert p2.spread == 3.0


# ---------------------------------------------------------------
# simulate_post_round2 — cut is a real fact, never simulated
# ---------------------------------------------------------------


def _sim_input(code, expected, spread, r1, r2, made_cut):
    return PlayerR2SimInput(
        player_code=code, player_name=code, expected_round_score_to_par=expected, spread=spread,
        r1_score_to_par=r1, r2_score_to_par=r2, made_cut=made_cut,
    )


def test_cut_player_gets_real_known_zero_never_estimated():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, True),
        _sim_input("p2", 2.0, 1.5, 5.0, 5.0, False),
    ]
    result = simulate_post_round2(inputs, n_simulations=200, rng=random.Random(1))
    assert result["p2"] == {"win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0, "make_cut_pct": 0.0}


def test_cutmaker_gets_real_known_hundred_percent_make_cut():
    inputs = [_sim_input("p1", -1.0, 1.5, -3.0, -2.0, True)]
    result = simulate_post_round2(inputs, n_simulations=200, rng=random.Random(1))
    assert result["p1"]["make_cut_pct"] == 100.0
    assert result["p1"]["win_pct"] == 100.0  # sole cutmaker, always wins


def test_player_missing_any_required_field_excluded_from_result():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, True),
        _sim_input("p2", -1.0, 1.5, None, -2.0, True),  # missing r1
        _sim_input("p3", -1.0, 1.5, -3.0, -2.0, None),  # missing made_cut
    ]
    result = simulate_post_round2(inputs, n_simulations=100, rng=random.Random(2))
    assert set(result.keys()) == {"p1"}


def test_win_probabilities_sum_to_one_among_cutmakers():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, True),
        _sim_input("p2", -0.5, 1.5, -2.0, -2.0, True),
        _sim_input("p3", 3.0, 1.5, 6.0, 6.0, False),
    ]
    result = simulate_post_round2(inputs, n_simulations=2000, rng=random.Random(3))
    total_win = sum(v["win_pct"] for v in result.values())
    assert abs(total_win - 100.0) < 0.5  # p3's 0.0 contributes nothing; p1+p2 sum to ~100


def test_stronger_player_gets_higher_win_probability_among_cutmakers():
    inputs = [
        _sim_input("strong", -3.0, 1.0, -6.0, -6.0, True),
        _sim_input("weak", 1.0, 1.0, 0.0, 0.0, True),
    ]
    result = simulate_post_round2(inputs, n_simulations=2000, rng=random.Random(4))
    assert result["strong"]["win_pct"] > result["weak"]["win_pct"]


def test_deterministic_with_seeded_rng():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, True),
        _sim_input("p2", 0.5, 1.5, -1.0, -1.0, True),
    ]
    r1 = simulate_post_round2(inputs, n_simulations=500, rng=random.Random(42))
    r2 = simulate_post_round2(inputs, n_simulations=500, rng=random.Random(42))
    assert r1 == r2
