"""Tests for klpga.neo_win.round_update_r3 — the post-Round-3 Monte
Carlo simulation. By R3 the cut is a long-settled fact (determined
after Round 2) — there is no make_cut_pct field here at all, unlike
round_update_r2.py, since there is no cut-related probability left to
report."""
from __future__ import annotations

import random

from klpga.neo_win.beta001c_archive import NeoWinCEntrantSnapshot
from klpga.neo_win.round_update_r3 import (
    PlayerR3SimInput,
    build_r3_sim_inputs_from_frozen_snapshot,
    simulate_post_round3,
)


class _FakeSnapshot:
    def __init__(self, predictions):
        self.predictions = predictions


class _FakeEntrant:
    def __init__(self, player_code, player_name, prior_avg_round_score_to_par, neo_consistency_stddev):
        self.player_code = player_code
        self.player_name = player_name
        self.prior_avg_round_score_to_par = prior_avg_round_score_to_par
        self.neo_consistency_stddev = neo_consistency_stddev


def _entrant(code, name, score_to_par, consistency):
    return _FakeEntrant(code, name, score_to_par, consistency)


# ---------------------------------------------------------------
# build_r3_sim_inputs_from_frozen_snapshot
# ---------------------------------------------------------------


def test_build_sim_inputs_uses_frozen_values_and_real_scores_and_cut():
    snapshot = _FakeSnapshot([_entrant("p1", "A", -1.0, 2.0)])
    inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -3.0}, {"p1": -2.0}, {"p1": -1.0}, {"p1": True}
    )
    assert missing == []
    assert inputs[0].r1_score_to_par == -3.0
    assert inputs[0].r2_score_to_par == -2.0
    assert inputs[0].r3_score_to_par == -1.0
    assert inputs[0].made_cut is True
    assert inputs[0].expected_round_score_to_par == -1.0
    assert inputs[0].spread == 2.0


def test_build_sim_inputs_shrinks_missing_pre_values_to_population_mean():
    snapshot = _FakeSnapshot([
        _entrant("p1", "A", -1.0, 2.0),
        _entrant("p2", "B", None, None),
    ])
    inputs, _ = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot,
        {"p1": -3, "p2": -1},
        {"p1": -2, "p2": 0},
        {"p1": -1, "p2": 1},
        {"p1": True, "p2": True},
    )
    p2 = next(i for i in inputs if i.player_code == "p2")
    assert p2.expected_round_score_to_par == -1.0  # population mean of known scores (-1.0)


# ---------------------------------------------------------------
# BETA #001-C frozen PRE shape (NeoWinCEntrantSnapshot) — regression
# coverage for the real, confirmed production crash: this module read
# e.prior_avg_round_score_to_par / e.neo_consistency_stddev as plain
# top-level attributes, which raises AttributeError for the real
# production PRE snapshot shape (feature_values-only). round_update_r2.py
# already carries the fix (_feature() dual-shape accessor); these tests
# mirror tests/test_round_update_r2.py's own #001-C coverage exactly.
# ---------------------------------------------------------------


def test_build_sim_inputs_reads_beta001c_snapshot_shape_without_crashing():
    """Regression test for the real, confirmed POST-R3 production crash:
    a NeoWinCEntrantSnapshot (the current BETA #001-C production PRE
    shape) stores prior_avg_round_score_to_par / neo_consistency_stddev
    ONLY inside feature_values, never as top-level attributes — the
    previous code (`e.prior_avg_round_score_to_par`) raised AttributeError
    for exactly this shape, which is scripts/run_beta001_r3_update.py's
    (and scripts/46's) DEFAULT/preferred PRE source. This test would have
    failed before the _feature() accessor fix."""
    c_entrant = NeoWinCEntrantSnapshot(
        rank=1, player_code="p1", player_name="A", win_probability=0.10, prior_events_n=10,
        feature_values={"prior_avg_round_score_to_par": -1.5, "neo_consistency_stddev": 2.5},
        player_master_matched=True,
    )
    snapshot = _FakeSnapshot([c_entrant])
    inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -3.0}, {"p1": -2.0}, {"p1": -1.0}, {"p1": True}
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
    inputs, _missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot, r1_scores={"p1": -3.0, "p2": -1.0}, r2_scores={"p1": -2.0, "p2": 0.0},
        r3_scores={"p1": -1.0}, made_cut_by_player={"p1": True, "p2": False},
    )
    p2 = next(i for i in inputs if i.player_code == "p2")
    assert p2.expected_round_score_to_par == -2.0  # population mean of the one known value
    assert p2.spread == 3.0


def test_neo_win_c_entrant_snapshot_frozen_pre_to_post_r3_simulation():
    """"NeoWinCEntrantSnapshot frozen PRE -> POST-R3 simulation" — the
    exact end-to-end regression this bug needed: build_r3_sim_inputs_
    from_frozen_snapshot followed by simulate_post_round3, against a
    #001-C-shaped frozen PRE snapshot, for both a cutmaker and a
    confirmed CUT player. Must not raise, and must produce real,
    non-fabricated probabilities."""
    cutmaker = NeoWinCEntrantSnapshot(
        rank=1, player_code="p1", player_name="A", win_probability=0.20, prior_events_n=10,
        feature_values={"prior_avg_round_score_to_par": -1.0, "neo_consistency_stddev": 2.0},
        player_master_matched=True,
    )
    cut_player = NeoWinCEntrantSnapshot(
        rank=2, player_code="p2", player_name="B", win_probability=0.05, prior_events_n=10,
        feature_values={"prior_avg_round_score_to_par": 0.5, "neo_consistency_stddev": 2.5},
        player_master_matched=True,
    )
    snapshot = _FakeSnapshot([cutmaker, cut_player])

    inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot,
        r1_scores={"p1": -3.0, "p2": 2.0},
        r2_scores={"p1": -2.0, "p2": 3.0},
        r3_scores={"p1": -1.0},
        made_cut_by_player={"p1": True, "p2": False},
    )
    assert missing == []

    result = simulate_post_round3(inputs, n_simulations=200, rng=random.Random(42))
    assert result["p1"]["win_pct"] > 0.0
    assert result["p2"] == {"win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0}


def test_cut_player_with_no_r3_score_is_not_reported_missing():
    """A real, confirmed CUT player (made_cut=False) structurally has
    no R3 score at all — they never played it. This must NOT be
    reported in `missing_r3_players`; the module-level fix for the
    original bug where r3 was wrongly required unconditionally."""
    snapshot = _FakeSnapshot([_entrant("p1", "A", -1.0, 2.0)])
    inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -3.0}, {"p1": -2.0}, {}, {"p1": False}
    )
    assert missing == []
    assert inputs[0].r3_score_to_par is None
    assert inputs[0].made_cut is False


def test_cutmaker_missing_r3_score_is_reported_missing():
    """The inverse: a confirmed CUTMAKER (made_cut=True) missing their
    own R3 score IS a real ingestion gap and must be reported."""
    snapshot = _FakeSnapshot([_entrant("p1", "A", -1.0, 2.0)])
    inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -3.0}, {"p1": -2.0}, {}, {"p1": True}
    )
    assert missing == ["p1"]


def test_missing_r1_r2_r3_or_made_cut_reported_and_never_guessed():
    snapshot = _FakeSnapshot([_entrant("p1", "A", -1.0, 2.0), _entrant("p2", "B", -1.0, 2.0)])
    inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
        snapshot,
        r1_scores={"p1": -3.0},
        r2_scores={"p1": -2.0},
        r3_scores={"p1": -1.0},
        made_cut_by_player={"p1": True},
    )
    assert missing == ["p2"]
    p2 = next(i for i in inputs if i.player_code == "p2")
    assert p2.r1_score_to_par is None
    assert p2.r2_score_to_par is None
    assert p2.r3_score_to_par is None
    assert p2.made_cut is None


# ---------------------------------------------------------------
# simulate_post_round3 — the cut is long-decided; NO make_cut_pct field
# anywhere in the result — only win/top-N over the single remaining round.
# ---------------------------------------------------------------


def _sim_input(code, expected, spread, r1, r2, r3, made_cut):
    return PlayerR3SimInput(
        player_code=code, player_name=code, expected_round_score_to_par=expected, spread=spread,
        r1_score_to_par=r1, r2_score_to_par=r2, r3_score_to_par=r3, made_cut=made_cut,
    )


def test_cut_player_gets_real_known_zero_never_estimated():
    """A complete-data player recorded made_cut=False alongside a real
    R3 score is a genuine data inconsistency at this stage (they
    shouldn't have an R3 score at all) — gets a real, known 0.0 for
    everything, same convention as round_update_r2.py's cut-player case."""
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, -1.0, True),
        _sim_input("p2", 2.0, 1.5, 5.0, 5.0, 6.0, False),
    ]
    result = simulate_post_round3(inputs, n_simulations=200, rng=random.Random(1))
    assert result["p2"] == {"win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0}


def test_result_dict_never_contains_a_make_cut_pct_field():
    """The cut is long-decided by R3 — there is nothing cut-related
    left to report. Locks in the deliberate absence of make_cut_pct."""
    inputs = [_sim_input("p1", -1.0, 1.5, -3.0, -2.0, -1.0, True)]
    result = simulate_post_round3(inputs, n_simulations=100, rng=random.Random(1))
    assert "make_cut_pct" not in result["p1"]
    assert set(result["p1"].keys()) == {"win_pct", "top5_pct", "top10_pct", "top20_pct"}


def test_sole_cutmaker_wins_every_simulation():
    inputs = [_sim_input("p1", -1.0, 1.5, -3.0, -2.0, -1.0, True)]
    result = simulate_post_round3(inputs, n_simulations=200, rng=random.Random(1))
    assert result["p1"]["win_pct"] == 100.0


def test_player_missing_any_required_field_excluded_from_result():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, -1.0, True),
        _sim_input("p2", -1.0, 1.5, None, -2.0, -1.0, True),  # missing r1
        _sim_input("p3", -1.0, 1.5, -3.0, -2.0, -1.0, None),  # missing made_cut
        _sim_input("p4", -1.0, 1.5, -3.0, -2.0, None, True),  # missing r3
    ]
    result = simulate_post_round3(inputs, n_simulations=100, rng=random.Random(2))
    assert set(result.keys()) == {"p1"}


def test_win_probabilities_sum_to_one_among_cutmakers():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, -1.0, True),
        _sim_input("p2", -0.5, 1.5, -2.0, -2.0, -1.0, True),
        _sim_input("p3", 3.0, 1.5, 6.0, 6.0, 6.0, False),
    ]
    result = simulate_post_round3(inputs, n_simulations=2000, rng=random.Random(3))
    total_win = sum(v["win_pct"] for v in result.values())
    assert abs(total_win - 100.0) < 0.5  # p3's 0.0 contributes nothing; p1+p2 sum to ~100


def test_stronger_player_gets_higher_win_probability_among_cutmakers():
    inputs = [
        _sim_input("strong", -3.0, 1.0, -6.0, -6.0, -6.0, True),
        _sim_input("weak", 1.0, 1.0, 0.0, 0.0, 0.0, True),
    ]
    result = simulate_post_round3(inputs, n_simulations=2000, rng=random.Random(4))
    assert result["strong"]["win_pct"] > result["weak"]["win_pct"]


def test_deterministic_with_seeded_rng():
    inputs = [
        _sim_input("p1", -1.0, 1.5, -3.0, -2.0, -1.0, True),
        _sim_input("p2", 0.5, 1.5, -1.0, -1.0, -1.0, True),
    ]
    r1 = simulate_post_round3(inputs, n_simulations=500, rng=random.Random(42))
    r2 = simulate_post_round3(inputs, n_simulations=500, rng=random.Random(42))
    assert r1 == r2
