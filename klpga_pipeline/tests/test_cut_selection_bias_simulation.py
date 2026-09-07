"""Locks in the qualitative findings from
scripts/102_cut_selection_bias_simulation.py as a regression test, using
the same fixed seed so future changes to neo_ranking_v2_candidate.py (or
this simulation) surface a real behavior change rather than silently
drifting. Numeric thresholds are set loosely around the actual observed
values -- the goal is to catch a REGRESSION (e.g. someone reintroducing
the naive event-total method, or breaking pooled_per_round_rate's
near-unbiasedness), not to pin exact floats."""
from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "cut_selection_bias_simulation", ROOT / "scripts" / "102_cut_selection_bias_simulation.py"
)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim  # dataclass() needs the module registered before exec
spec.loader.exec_module(sim)  # type: ignore[union-attr]


def _run(seed=42, n_players=150, n_tournaments=15):
    rng = random.Random(seed)
    return sim.run_simulation(n_players, n_tournaments, identical_skill=0.0, rng=rng)


def test_naive_method_shows_large_cut_selection_bias():
    result = _run()
    made_cut_bias = sim.bias_stats(result["players"], "naive", "made_cut_heavy")["mean_bias"]
    missed_cut_bias = sim.bias_stats(result["players"], "naive", "missed_cut_heavy")["mean_bias"]
    # The naive (current production) method must show a large, opposite-signed
    # bias between made-cut-heavy and missed-cut-heavy players of IDENTICAL
    # true skill -- this is the bug the whole audit is about.
    assert made_cut_bias > 0.2, "naive method should badly overrate frequent cut-survivors"
    assert missed_cut_bias < -0.1, "naive method should badly underrate frequent cut-missers"
    assert made_cut_bias - missed_cut_bias > 0.4


def test_pooled_per_round_rate_greatly_reduces_but_does_not_fully_remove_the_bias():
    result = _run()
    naive_gap = (
        sim.bias_stats(result["players"], "naive", "made_cut_heavy")["mean_bias"]
        - sim.bias_stats(result["players"], "naive", "missed_cut_heavy")["mean_bias"]
    )
    pooled_gap = (
        sim.bias_stats(result["players"], "pooled", "made_cut_heavy")["mean_bias"]
        - sim.bias_stats(result["players"], "pooled", "missed_cut_heavy")["mean_bias"]
    )
    assert pooled_gap < naive_gap, "pooling per-round rate must shrink the made/missed-cut gap"
    assert pooled_gap > 0, (
        "GENUINE FINDING (not a bug to hide): pooling reduces cut-selection bias by roughly "
        "4x in this simulation but does not reduce it to zero -- a residual gap between "
        "frequent cut-survivors and frequent cut-missers of identical true skill remains"
    )
    assert pooled_gap < 0.3, "the residual gap must be small relative to naive's, even if nonzero"


def test_complete_case_fallacy_is_severely_biased():
    result = _run()
    complete_case_bias = sim.bias_stats(result["players"], "complete_case", "all")["mean_bias"]
    pooled_bias = sim.bias_stats(result["players"], "pooled", "all")["mean_bias"]
    # Discarding every missed-cut event (using ONLY completed 4-round events)
    # must show a large positive bias, much larger than the full-data pooled
    # estimator -- this is Test A4's required regression guard so production
    # code can never silently switch to "completed events only" logic.
    assert complete_case_bias > 0.1
    assert complete_case_bias > abs(pooled_bias) * 5


def test_r1r2_common_window_is_nearly_unbiased_but_higher_variance_than_full_data():
    result = _run()
    restricted = sim.bias_stats(result["players"], "restricted_r1r2", "all")
    full = sim.bias_stats(result["players"], "pooled", "all")
    assert abs(restricted["mean_bias"]) < 0.1
    assert abs(full["mean_bias"]) < 0.1
    # Using every available round (including cut-survivors' R3/R4) must not
    # introduce material extra bias over the R1/R2-only control, and should
    # improve precision (lower RMSE) by using more real information.
    assert full["rmse"] <= restricted["rmse"], (
        "the R1/R2-only control must not be MORE precise than using all available rounds -- "
        "if it is, that would suggest later-round data is actively harmful, not just extra"
    )


def test_cutline_noise_produces_a_large_r1r2_gap_between_barely_survivors_and_missers():
    matched_skill = 0.0
    rng = random.Random(7)
    lucky_rates, unlucky_rates = [], []
    for _ in range(200):
        t = sim.play_tournament(matched_skill, rng)
        r1r2 = (t.rounds[0] + t.rounds[1]) / 2
        (lucky_rates if t.made_cut else unlucky_rates).append(r1r2)
    if lucky_rates and unlucky_rates:
        import statistics
        gap = statistics.fmean(lucky_rates) - statistics.fmean(unlucky_rates)
        # For players of IDENTICAL true skill, surviving vs missing the cut is
        # entirely a function of R1/R2 noise -- the gap must be large.
        assert gap > 1.0
