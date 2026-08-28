"""Tests for klpga.neo_win.round_update — the post-Round-1 Monte Carlo
tournament simulation (BETA #001-R1)."""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

import pytest

from klpga.models.candidates import ShrinkageParams
from klpga.neo_win.archive import NeoWinEntrantSnapshot
from klpga.neo_win.round_update import (
    PlayerSimInput,
    build_post_r1_n_lookup,
    build_sim_inputs_from_frozen_snapshot,
    estimate_cut_fraction,
    fit_post_r1_shrink_params,
    shrink_to_original_units,
    simulate_post_round1,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


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
# estimate_cut_fraction
# ---------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.sqlite")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def test_estimate_cut_fraction_real_ratio(conn):
    conn.execute("INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) VALUES ('E1','G1','T',2026,'2026-01-01')")
    for i in range(10):
        conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (f"p{i}", f"p{i}"))
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, rounds_played) "
            "VALUES ('E1','G1',2026,?,?,?)",
            (f"p{i}", f"p{i}", 4 if i < 6 else 2),
        )
    conn.commit()
    assert estimate_cut_fraction(conn) == pytest.approx(0.6)


def test_estimate_cut_fraction_defaults_when_no_history(conn):
    assert estimate_cut_fraction(conn) == 0.65


# ---------------------------------------------------------------
# build_sim_inputs_from_frozen_snapshot
# ---------------------------------------------------------------


def test_build_sim_inputs_uses_frozen_values_directly():
    snapshot = _FakeSnapshot([_entrant("p1", "A", 0.5, -1.0, 2.0)])
    sim_inputs, missing = build_sim_inputs_from_frozen_snapshot(snapshot, {"p1": -3.0})
    assert missing == []
    assert sim_inputs[0].expected_round_score_to_par == -1.0
    assert sim_inputs[0].spread == 2.0
    assert sim_inputs[0].r1_score_to_par == -3.0


def test_build_sim_inputs_shrinks_missing_values_to_population_mean():
    snapshot = _FakeSnapshot([
        _entrant("p1", "A", 0.6, -2.0, 3.0),
        _entrant("p2", "B", 0.4, None, None),  # missing PRE features
    ])
    sim_inputs, missing = build_sim_inputs_from_frozen_snapshot(snapshot, {"p1": -1.0, "p2": 0.0})
    p2 = next(s for s in sim_inputs if s.player_code == "p2")
    assert p2.expected_round_score_to_par == -2.0  # shrinks to the only known value (population mean of 1 sample)
    assert p2.spread == 3.0


def test_build_sim_inputs_reports_missing_r1_players():
    snapshot = _FakeSnapshot([_entrant("p1", "A", 0.5, -1.0, 2.0), _entrant("p2", "B", 0.5, -1.0, 2.0)])
    sim_inputs, missing = build_sim_inputs_from_frozen_snapshot(snapshot, {"p1": -3.0})
    assert missing == ["p2"]
    p2 = next(s for s in sim_inputs if s.player_code == "p2")
    assert p2.r1_score_to_par is None


# ---------------------------------------------------------------
# shrink_to_original_units (BETA #001 R1 FINAL calibration fix)
# ---------------------------------------------------------------


def test_shrink_to_original_units_returns_raw_when_value_missing():
    params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=5.0)
    assert shrink_to_original_units(None, 10, params) is None


def test_shrink_to_original_units_returns_raw_when_n_missing_or_zero():
    params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=5.0)
    assert shrink_to_original_units(3.0, None, params) == 3.0
    assert shrink_to_original_units(3.0, 0, params) == 3.0


def test_shrink_to_original_units_matches_hand_computed_weight_formula():
    # weight = n/(n+k); shrunk = pop_mean + weight*(raw-pop_mean) — same formula as
    # klpga.models.candidates.apply_shrinkage_and_standardize, before the final /pop_std step.
    params = ShrinkageParams(pop_mean=2.0, pop_std=1.5, k=4.0)
    result = shrink_to_original_units(raw=10.0, n=4, params=params)
    expected_weight = 4 / (4 + 4)
    expected = 2.0 + expected_weight * (10.0 - 2.0)
    assert result == pytest.approx(expected)
    assert result == pytest.approx(6.0)  # halfway toward pop_mean when n == k


def test_shrink_to_original_units_large_n_stays_close_to_raw():
    params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=2.0)
    result = shrink_to_original_units(raw=100.0, n=10_000, params=params)
    assert result == pytest.approx(100.0, abs=0.05)  # weight ~= 1 for n >> k


# ---------------------------------------------------------------
# build_sim_inputs_from_frozen_snapshot — opt-in shrinkage
# ---------------------------------------------------------------


def test_build_sim_inputs_without_shrink_args_is_byte_identical_to_before():
    """Omitting n_lookup/avg_shrink_params/stddev_shrink_params (every
    pre-existing caller/test) must preserve the exact prior behavior."""
    snapshot = _FakeSnapshot([_entrant("p1", "A", 0.5, -1.0, 2.0)])
    sim_inputs, _ = build_sim_inputs_from_frozen_snapshot(snapshot, {"p1": -3.0})
    assert sim_inputs[0].expected_round_score_to_par == -1.0
    assert sim_inputs[0].spread == 2.0


def test_build_sim_inputs_applies_shrinkage_when_all_three_args_given():
    snapshot = _FakeSnapshot([_entrant("p1", "A", 0.5, raw_score := -6.0, raw_stddev := 8.0)])
    avg_params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=1.0)
    stddev_params = ShrinkageParams(pop_mean=3.0, pop_std=1.0, k=1.0)
    n_lookup = {"p1": (1, 1)}  # n == k for both -> weight 0.5

    sim_inputs, _ = build_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -1.0},
        n_lookup=n_lookup, avg_shrink_params=avg_params, stddev_shrink_params=stddev_params,
    )
    p1 = sim_inputs[0]
    assert p1.expected_round_score_to_par == pytest.approx(0.0 + 0.5 * (raw_score - 0.0))  # -3.0
    assert p1.spread == pytest.approx(3.0 + 0.5 * (raw_stddev - 3.0))  # 5.5


def test_build_sim_inputs_shrinkage_skips_players_with_missing_raw_value():
    """A player with NO raw frozen value still falls back to the simple
    population mean (unchanged fallback), never crashes on a missing
    n_lookup entry."""
    snapshot = _FakeSnapshot([
        _entrant("p1", "A", 0.5, -2.0, 3.0),
        _entrant("p2", "B", 0.5, None, None),
    ])
    avg_params = ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=1.0)
    stddev_params = ShrinkageParams(pop_mean=3.0, pop_std=1.0, k=1.0)
    n_lookup = {"p1": (5, 5)}  # p2 deliberately absent from the lookup

    sim_inputs, _ = build_sim_inputs_from_frozen_snapshot(
        snapshot, {"p1": -1.0, "p2": 0.0},
        n_lookup=n_lookup, avg_shrink_params=avg_params, stddev_shrink_params=stddev_params,
    )
    p2 = next(s for s in sim_inputs if s.player_code == "p2")
    assert p2.expected_round_score_to_par == -2.0  # population mean of the only known raw value
    assert p2.spread == 3.0


# ---------------------------------------------------------------
# fit_post_r1_shrink_params / build_post_r1_n_lookup — real DB wiring
# ---------------------------------------------------------------


def test_fit_post_r1_shrink_params_and_n_lookup_use_real_prior_history(conn):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('E1','G1','Prior Event',2026,'2026-01-01')"
    )
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('E2','TARGET','Target Event',2026,'2026-06-01')"
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1','Player One')")
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, rounds_played, score_to_par) "
        "VALUES ('E1','G1',2026,'p1','Player One',4,-2)"
    )
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_to_par) "
        "VALUES ('E1','G1',2026,1,'p1','Player One',-1)"
    )
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_to_par) "
        "VALUES ('E1','G1',2026,4,'p1','Player One',-1)"
    )
    conn.commit()

    import datetime
    n_lookup = build_post_r1_n_lookup(conn, "TARGET", datetime.date(2026, 6, 1), ["p1", "p2"])
    assert n_lookup["p1"] == (4, 2)  # 4 rounds_played toward the rate, 2 real round_to_par values
    assert n_lookup["p2"] == (0, 0)  # no history at all — real zero, not missing

    avg_params, stddev_params = fit_post_r1_shrink_params(conn, "TARGET", datetime.date(2026, 6, 1))
    assert isinstance(avg_params, ShrinkageParams)
    assert isinstance(stddev_params, ShrinkageParams)


# ---------------------------------------------------------------
# simulate_post_round1
# ---------------------------------------------------------------


def _sim_inputs(n=20, seed_scores=None):
    inputs = []
    for i in range(n):
        score = -3.0 + i * 0.1 if seed_scores is None else seed_scores[i]
        inputs.append(PlayerSimInput(player_code=f"p{i}", player_name=f"P{i}", expected_round_score_to_par=score, spread=2.0, r1_score_to_par=score))
    return inputs


def test_simulate_probabilities_sum_and_bounds():
    inputs = _sim_inputs(20)
    result = simulate_post_round1(inputs, cut_fraction=0.6, n_simulations=500, rng=random.Random(42))
    total_win = sum(r["win_pct"] for r in result.values())
    assert total_win == pytest.approx(100.0, abs=0.5)
    for r in result.values():
        assert 0 <= r["win_pct"] <= 100
        assert 0 <= r["make_cut_pct"] <= 100
        assert r["top5_pct"] <= r["top10_pct"] <= r["top20_pct"] or r["top20_pct"] == 0


def test_simulate_excludes_players_missing_r1_score():
    inputs = _sim_inputs(5)
    inputs[0] = PlayerSimInput(player_code="p0", player_name="P0", expected_round_score_to_par=-3.0, spread=2.0, r1_score_to_par=None)
    result = simulate_post_round1(inputs, cut_fraction=0.6, n_simulations=200, rng=random.Random(1))
    assert "p0" not in result


def test_simulate_stronger_player_gets_higher_win_probability():
    inputs = _sim_inputs(10, seed_scores=[-10.0] + [0.0] * 9)  # p0 is far stronger than the rest
    result = simulate_post_round1(inputs, cut_fraction=0.8, n_simulations=1000, rng=random.Random(7))
    assert result["p0"]["win_pct"] > result["p1"]["win_pct"]


def test_simulate_deterministic_with_seeded_rng():
    inputs = _sim_inputs(8)
    r1 = simulate_post_round1(inputs, cut_fraction=0.6, n_simulations=300, rng=random.Random(99))
    r2 = simulate_post_round1(inputs, cut_fraction=0.6, n_simulations=300, rng=random.Random(99))
    assert r1 == r2


def test_simulate_cut_fraction_matches_empirical_make_cut_rate():
    inputs = _sim_inputs(20)
    result = simulate_post_round1(inputs, cut_fraction=0.5, n_simulations=2000, rng=random.Random(3))
    made_cut_avg = sum(r["make_cut_pct"] for r in result.values()) / len(result)
    assert made_cut_avg == pytest.approx(50.0, abs=3.0)
