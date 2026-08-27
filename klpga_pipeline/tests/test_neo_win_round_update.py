"""Tests for klpga.neo_win.round_update — the post-Round-1 Monte Carlo
tournament simulation (BETA #001-R1)."""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.archive import NeoWinEntrantSnapshot
from klpga.neo_win.round_update import (
    PlayerSimInput,
    build_sim_inputs_from_frozen_snapshot,
    estimate_cut_fraction,
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
