"""NEO STANDARD ARTIFACT (POST_TOURNAMENT_REPORT) -- generic Monte
Carlo run summary: mean/median/standard deviation/95% CI of a
simulated score distribution.

No new model: this does not fit or invent anything. It either (a)
summarizes raw trial outcomes the caller already has, or (b)
reproduces the exact Normal(expected, spread) draw the production
round-update engines already use (klpga.neo_win.round_update /
round_update_r2 / round_update_r3), with the SAME recorded seed and
n_simulations, purely to capture per-trial values for reporting --
the production artifacts' own win/topN percentages are never
recomputed or overwritten by this.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class MonteCarloRunSummary:
    n_simulations: int
    seed: int
    mean: float
    median: float
    stddev: float
    ci95_low: float
    ci95_high: float


def summarize_trials(n_simulations: int, seed: int, trials: Sequence[float]) -> MonteCarloRunSummary:
    """Summarize an already-drawn array of per-trial outcomes (e.g. a
    simulated final score-to-par per trial)."""
    if len(trials) == 0:
        raise ValueError("cannot summarize zero trials")
    arr = np.asarray(trials, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    margin = 1.96 * std / math.sqrt(len(arr)) if len(arr) > 1 else 0.0
    return MonteCarloRunSummary(
        n_simulations=n_simulations,
        seed=seed,
        mean=mean,
        median=float(np.median(arr)),
        stddev=std,
        ci95_low=mean - margin,
        ci95_high=mean + margin,
    )


def summarize_normal_draw(
    *, expected: float, spread: float, n_simulations: int, seed: int,
) -> MonteCarloRunSummary:
    """Reproduces the production engines' own Normal(expected, spread)
    draw with the given seed/n_simulations so a report can quote
    mean/median/stddev/95% CI without needing the engine to have
    persisted raw trials. Bit-identical to the production draw for the
    same (expected, spread, seed, n_simulations) -- pure reporting
    diagnostic, not a new model."""
    rng = np.random.default_rng(seed)
    trials = rng.normal(loc=expected, scale=spread, size=n_simulations)
    return summarize_trials(n_simulations, seed, trials)
