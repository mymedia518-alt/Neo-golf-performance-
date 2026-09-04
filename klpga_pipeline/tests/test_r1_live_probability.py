from __future__ import annotations

import random

from klpga.neo_win.r1_live_probability import (
    build_r1_sim_inputs,
    compute_neo_movers,
    cutline_percentiles,
    simulate_r1_live,
    _select_expected_and_spread,
)


def _profile(**windows):
    return {"windows": windows}


def _total(mean, sample_sd=None, population_sd=None):
    return {"components": {"total": {"mean": mean, "sample_sd": sample_sd, "population_sd": population_sd}}}


def test_select_expected_and_spread_prefers_recent5_over_other_windows():
    profile = _profile(recent5=_total(0.5, 0.8), recent10=_total(-1.0, 0.3), current=_total(2.0, 0.1))
    expected, spread, window = _select_expected_and_spread(profile)
    assert window == "recent5"
    assert expected == -0.5  # sign-flipped SG -> score-to-par
    assert spread == 0.8


def test_select_expected_and_spread_falls_back_through_window_chain():
    profile = _profile(recent5=_total(None), recent10=_total(None), recent3=_total(-0.4, 0.6))
    expected, spread, window = _select_expected_and_spread(profile)
    assert window == "recent3"
    assert expected == 0.4


def test_select_expected_and_spread_returns_none_when_no_window_has_data():
    profile = _profile(recent5=_total(None))
    expected, spread, window = _select_expected_and_spread(profile)
    assert expected is None and spread is None and window is None


def test_select_expected_and_spread_falls_back_to_population_sd_when_sample_sd_missing():
    profile = _profile(recent5=_total(0.1, sample_sd=None, population_sd=0.9))
    _expected, spread, _window = _select_expected_and_spread(profile)
    assert spread == 0.9


def test_build_r1_sim_inputs_population_fallback_for_players_with_no_window():
    records = [{"player_id": "1", "current_official_player_name": "A"}, {"player_id": "2", "current_official_player_name": "B"}]
    profiles = [{"player_id": "1", "windows": {"recent5": _total(0.4, 0.5)}}]  # player "2" has no profile at all
    result = build_r1_sim_inputs(records, profiles, {"1": 2, "2": -1})
    assert "2" in result.population_fallback_players
    assert "1" not in result.population_fallback_players
    p2 = next(s for s in result.sim_inputs if s.player_code == "2")
    p1 = next(s for s in result.sim_inputs if s.player_code == "1")
    assert p2.expected_round_score_to_par == p1.expected_round_score_to_par == -0.4  # population mean == the only known value


def test_build_r1_sim_inputs_flags_missing_r1_players_never_silently_drops_them():
    records = [{"player_id": "1", "current_official_player_name": "A"}, {"player_id": "2", "current_official_player_name": "B"}]
    profiles = [{"player_id": "1", "windows": {"recent5": _total(0.4, 0.5)}}]
    result = build_r1_sim_inputs(records, profiles, {"1": 2})  # "2" never posted an R1 score
    assert result.missing_r1_players == ["2"]
    assert len(result.sim_inputs) == 2  # still present, not dropped
    p2 = next(s for s in result.sim_inputs if s.player_code == "2")
    assert p2.r1_score_to_par is None


def test_build_r1_sim_inputs_floors_spread_at_minimum():
    records = [{"player_id": "1", "current_official_player_name": "A"}]
    profiles = [{"player_id": "1", "windows": {"recent5": _total(0.0, 0.001)}}]
    result = build_r1_sim_inputs(records, profiles, {"1": 0})
    assert result.sim_inputs[0].spread == 0.5


def _sim_input(pid, name, expected, spread, r1):
    from klpga.neo_win.round_update import PlayerSimInput
    return PlayerSimInput(player_code=pid, player_name=name, expected_round_score_to_par=expected, spread=spread, r1_score_to_par=r1)


def test_simulate_r1_live_excludes_players_without_r1_score():
    inputs = [_sim_input("1", "A", 0.0, 1.0, -2), _sim_input("2", "B", 0.0, 1.0, None)]
    result = simulate_r1_live(inputs, n_simulations=200, rng=random.Random(1))
    assert "1" in result.probabilities
    assert "2" not in result.probabilities
    assert result.excluded_no_r1_score == ["2"]


def test_simulate_r1_live_a_clearly_better_player_wins_more_often():
    strong = _sim_input("1", "Strong", -1.5, 1.0, -10)
    weak = _sim_input("2", "Weak", 1.5, 1.0, 10)
    result = simulate_r1_live([strong, weak], n_simulations=1000, cut_fraction=1.0, rng=random.Random(2))
    assert result.probabilities["1"]["win_pct"] > result.probabilities["2"]["win_pct"]
    assert result.probabilities["1"]["make_cut_pct"] == 100.0  # cut_fraction=1.0 -> everyone plays on


def test_simulate_r1_live_probabilities_are_never_fabricated_beyond_playable_field():
    only_one_with_score = [_sim_input("1", "A", 0.0, 1.0, 0), _sim_input("2", "B", 0.0, 1.0, None), _sim_input("3", "C", 0.0, 1.0, None)]
    result = simulate_r1_live(only_one_with_score, n_simulations=100, rng=random.Random(3))
    assert set(result.probabilities.keys()) == {"1"}
    assert result.probabilities["1"]["win_pct"] == 100.0  # sole playable entrant always "wins" the simulated field


def test_cutline_percentiles_returns_none_for_empty_distribution():
    assert cutline_percentiles([]) is None


def test_cutline_percentiles_p10_le_p50_le_p90():
    dist = sorted([float(x) for x in range(-10, 11)])
    result = cutline_percentiles(dist)
    assert result["p10"] <= result["p50"] <= result["p90"]


def test_compute_neo_movers_excludes_players_without_pre_baseline_never_defaults_to_zero():
    records = [
        {"player_id": "1", "current_official_player_name": "A", "win_probability": 0.02, "top10_probability": None, "neo_performance_band": "TYPICAL"},
        {"player_id": "2", "current_official_player_name": "B", "win_probability": None, "top10_probability": None, "neo_performance_band": None},
    ]
    probabilities = {"1": {"win_pct": 5.0, "top10_pct": 10.0, "make_cut_pct": 90.0}, "2": {"win_pct": 3.0, "top10_pct": 8.0, "make_cut_pct": 20.0}}
    sim_inputs = [_sim_input("1", "A", 0.0, 1.0, -1), _sim_input("2", "B", 0.0, 1.0, 3)]
    movers = compute_neo_movers(records, probabilities, sim_inputs, top_n=5)
    win_ids = {e.player_id for e in movers["win_pct_risers"] + movers["win_pct_fallers"]}
    assert win_ids == {"1"}  # player "2" has no PRE win_probability -> excluded, never a 0-vs-3 fabricated delta
    assert movers["top10_pct_risers"] == []  # no PRE top10_probability anywhere -> nothing computed


def test_compute_neo_movers_cut_droppers_only_flags_high_band_players():
    records = [
        {"player_id": "1", "current_official_player_name": "HighBandStruggling", "neo_performance_band": "HIGH"},
        {"player_id": "2", "current_official_player_name": "LowBandStruggling", "neo_performance_band": "LOW"},
    ]
    probabilities = {"1": {"make_cut_pct": 20.0}, "2": {"make_cut_pct": 20.0}}
    sim_inputs = [_sim_input("1", "HighBandStruggling", 0.0, 1.0, 3), _sim_input("2", "LowBandStruggling", 0.0, 1.0, 3)]
    movers = compute_neo_movers(records, probabilities, sim_inputs, top_n=5)
    ids = {e.player_id for e in movers["cut_pct_droppers_vs_band"]}
    assert ids == {"1"}  # LOW band struggling to make cut is expected, not a surprise mover
