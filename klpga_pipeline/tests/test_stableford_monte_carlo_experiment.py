"""Tests for klpga.website_v2.stableford_monte_carlo_experiment -- the
EXPERIMENTAL HJ 2026100004 Monte Carlo engine (2026-10-07). Covers the
operator's explicit VALIDATION checklist: probability sums, official
scoring, field identity, target leakage, cut rule, reproducibility,
and that the frozen V1 snapshot is never written to."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from klpga.website_v2.stableford_monte_carlo_experiment import (  # noqa: E402
    OUTCOMES,
    PlayerDistribution,
    SimulationConfig,
    field_neutral_prior_counts,
    load_field,
    run_monte_carlo,
    validate_cut_rule,
    validate_field_identity,
    validate_no_impossible_outcome,
    validate_probability_sums_exactly,
    validate_probability_vectors,
    validate_reproducibility,
    validate_scoring_table,
    validate_target_leakage,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "klpga_pipeline" / "content" / "website_v2" / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"


def _synthetic_field(n: int = 70) -> list[PlayerDistribution]:
    players = [PlayerDistribution(
        "P1", "Strong", "KOR", "", 1, "OK", 50, 900, (1, 20, 300, 500, 70, 9), "own_sample",
    )]
    for i in range(2, n + 1):
        players.append(PlayerDistribution(
            f"P{i}", f"Avg{i}", "KOR", "", i, "OK", 50, 900, (0, 5, 180, 650, 120, 45), "own_sample",
        ))
    return players


# ---------------------------------------------------------------- scoring / probabilities

def test_scoring_table_order_and_values_exact():
    validate_scoring_table()  # raises on any drift


def test_probability_vectors_sum_to_one_on_real_field():
    players = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    validate_probability_vectors(players)


def test_player_with_zero_count_total_rejected():
    with pytest.raises(ValueError):
        PlayerDistribution("X", "Zero", "KOR", "", None, "DATA_LIMITED_NO_PRIOR_DATA", None, None, (0, 0, 0, 0, 0, 0), "own_sample")


# ---------------------------------------------------------------- field loading / leakage

def test_target_leakage_zero_on_real_snapshot():
    validate_target_leakage(SNAPSHOT_PATH)  # raises on any violation


def test_field_is_108_with_no_duplicates():
    players = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    validate_field_identity(players, expected_size=108)


def test_exclude_policy_drops_field_to_106():
    players = load_field(SNAPSHOT_PATH, no_prior_data_policy="exclude")
    validate_field_identity(players, expected_size=106)
    assert all(p.data_status != "DATA_LIMITED_NO_PRIOR_DATA" for p in players)


def test_no_prior_data_players_get_field_neutral_prior_never_fabricated_strong_or_weak():
    players = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    no_prior = [p for p in players if p.data_status == "DATA_LIMITED_NO_PRIOR_DATA"]
    assert len(no_prior) == 2
    for p in no_prior:
        assert p.prior_source == "field_neutral_prior"
    # both share the exact same neutral distribution (same source pool)
    assert no_prior[0].probabilities == no_prior[1].probabilities
    # the neutral prior must sit near the middle of the field's own expected-points range,
    # never at either extreme -- confirms it's a genuine average, not an arbitrary strong/weak guess
    all_eph = [p.expected_points_per_hole() for p in players if p.data_status == "OK"]
    neutral_eph = no_prior[0].expected_points_per_hole()
    assert min(all_eph) < neutral_eph < max(all_eph)


def test_frozen_v1_snapshot_untouched_after_loading_field():
    before = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
    load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    load_field(SNAPSHOT_PATH, no_prior_data_policy="exclude")
    after = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
    assert before == after


def test_field_neutral_prior_never_reads_pre_event_rank():
    import inspect
    src = inspect.getsource(field_neutral_prior_counts)
    assert "pre_event_rank" not in src


def test_expected_points_per_hole_matches_v1_net_expected_value_exactly():
    import json
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    players = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    by_code = {p.player_code: p for p in players}
    checked = 0
    for r in snapshot["records"]:
        if r["data_status"] != "OK":
            continue
        p = by_code[r["player_code"]]
        # V1's own net_expected_value is stored round(x, 4) (stableford_player_value.
        # from_season_rates) -- compare at that same rounding, not raw float equality.
        assert round(p.expected_points_per_hole(), 4) == r["net_expected_value"], r["player_name"]
        checked += 1
    assert checked >= 100  # sanity: we actually checked most of the 106 OK/thin-sample field


# ---------------------------------------------------------------- simulation engine

def test_simulation_reproducible_with_same_seed():
    players = _synthetic_field(40)
    cfg = SimulationConfig(n_sims=1000, seed=5, cut_size=20)
    validate_reproducibility(players, cfg)  # raises on any mismatch


def test_different_seed_gives_different_but_similar_win_pct():
    players = _synthetic_field(40)
    r1 = run_monte_carlo(players, SimulationConfig(n_sims=3000, seed=1, cut_size=20))
    r2 = run_monte_carlo(players, SimulationConfig(n_sims=3000, seed=2, cut_size=20))
    assert not np.array_equal(r1.win_pct, r2.win_pct)
    assert np.abs(r1.win_pct - r2.win_pct).max() < 0.15  # no wild swing for the strongest player


def test_win_pct_sums_to_one_across_field():
    players = _synthetic_field(40)
    res = run_monte_carlo(players, SimulationConfig(n_sims=2000, seed=3, cut_size=20))
    validate_probability_sums_exactly(res)


def test_cut_rule_top_n_plus_ties():
    players = _synthetic_field(50)
    res = run_monte_carlo(players, SimulationConfig(n_sims=1500, seed=9, cut_size=25))
    validate_cut_rule(res, cut_size=25)
    assert (res.made_cut.sum(axis=0) >= 25).all()


def test_no_impossible_score():
    players = _synthetic_field(30)
    res = run_monte_carlo(players, SimulationConfig(n_sims=1000, seed=11, cut_size=15))
    validate_no_impossible_outcome(res)


def test_tied_winners_split_credit_equally():
    # two players with IDENTICAL distributions must average to equal win%
    players = [
        PlayerDistribution("A", "A", "KOR", "", 1, "OK", 50, 900, (0, 10, 200, 600, 70, 20), "own_sample"),
        PlayerDistribution("B", "B", "KOR", "", 2, "OK", 50, 900, (0, 10, 200, 600, 70, 20), "own_sample"),
    ]
    for i in range(3, 25):
        players.append(PlayerDistribution(f"P{i}", f"P{i}", "KOR", "", i, "OK", 50, 900, (0, 2, 120, 700, 130, 48), "own_sample"))
    res = run_monte_carlo(players, SimulationConfig(n_sims=20000, seed=42, cut_size=15))
    assert abs(res.win_pct[0] - res.win_pct[1]) < 0.02  # identical distributions -> near-identical win% at 20k sims


def test_higher_variance_player_can_beat_higher_cut_pct_peer_on_topn():
    """Red Team item 6 regression lock: at near-equal expected value, the
    higher-variance (higher birdie AND higher double+) player's top10%
    must not be suppressed below the lower-variance peer's -- cut alone
    must not erase upside."""
    low_var = PlayerDistribution("L", "LowVar", "KOR", "", 1, "OK", 50, 900, (0, 2, 125, 700, 125, 48), "own_sample")
    high_var = PlayerDistribution("H", "HighVar", "KOR", "", 2, "OK", 50, 900, (0, 5, 160, 660, 115, 60), "own_sample")
    field = [low_var, high_var]
    for i in range(3, 60):
        field.append(PlayerDistribution(f"P{i}", f"P{i}", "KOR", "", i, "OK", 50, 900, (0, 1, 100, 720, 130, 49), "own_sample"))
    res = run_monte_carlo(field, SimulationConfig(n_sims=20000, seed=100, cut_size=30))
    assert res.top10_pct[1] > res.top10_pct[0]  # HighVar beats LowVar on top10%


# ---------------------------------------------------------------- never leaks into V1

def test_module_never_writes_the_frozen_snapshot_path():
    import inspect
    import klpga.website_v2.stableford_monte_carlo_experiment as mod
    src = inspect.getsource(mod)
    assert "write_text" not in src
    assert "open(" not in src or "write" not in src.lower().split("open(")[1][:50]


def test_module_never_references_historical_actual_results():
    import inspect
    import klpga.website_v2.stableford_monte_carlo_experiment as mod
    src = inspect.getsource(mod)
    for forbidden in ("2023", "2024", "2025", "방신실", "김민별", "이정민", "이가영"):
        assert forbidden not in src
