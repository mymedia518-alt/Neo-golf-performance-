"""Pure-Python, dependency-free numerical primitives shared by the
modeling layer: a deterministic grid-refine optimizer (no numpy/scipy —
consistent with this project's existing "no pandas" precedent, see
`klpga.db.export_csv`), a numerically-stable softmax, and the Wilcoxon
signed-rank paired test used for Section 11's promotion gate.

Everything here is deterministic given its inputs — no randomness, no
seed required (the evaluation spec's "prefer deterministic methods
where possible" — grid-refine search and the closed-form Wilcoxon
normal approximation both satisfy this without needing a Monte Carlo
step).
"""
from __future__ import annotations

import itertools
import math
from typing import Callable, Optional, Sequence


def softmax_from_logits(logits: dict[str, float]) -> dict[str, float]:
    """Numerically-stable softmax over an arbitrary-size field. Always
    returns strictly positive values that sum to exactly 1.0 (up to
    float rounding) — softmax mathematically cannot produce a zero or
    negative probability for a finite input, which is exactly the
    Section 1 hard constraint every candidate model relies on this
    function to satisfy."""
    if not logits:
        return {}
    max_logit = max(logits.values())
    exps = {k: math.exp(v - max_logit) for k, v in logits.items()}
    total = sum(exps.values())
    return {k: v / total for k, v in exps.items()}


def clip_and_renormalize(probs: dict[str, float], epsilon: float = 1e-6) -> dict[str, float]:
    """Pre-registered safety floor (docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md
    Section 3A): clip every probability to [epsilon, 1] and renormalize
    the field back to sum to 1. Softmax output should never actually
    need this (it's strictly positive by construction), but float
    underflow on an extreme logit spread is a real, if rare,
    possibility this guards against. epsilon is fixed here, identically
    for every candidate model — never tuned per model or after seeing
    results."""
    clipped = {k: min(max(v, epsilon), 1.0) for k, v in probs.items()}
    total = sum(clipped.values())
    if total <= 0:
        # Every value clipped to epsilon (pathological all-zero input) —
        # fall back to uniform rather than dividing by zero.
        n = len(clipped)
        return {k: 1.0 / n for k in clipped}
    return {k: v / total for k, v in clipped.items()}


def _linspace(lo: float, hi: float, n: int) -> list[float]:
    if n == 1:
        return [(lo + hi) / 2]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def grid_refine_search(
    objective: Callable[..., float],
    bounds: Sequence[tuple[float, float]],
    n_points: int = 15,
    rounds: int = 3,
) -> tuple[tuple[float, ...], float]:
    """Deterministic global-ish maximizer for a smooth, low-dimensional
    (1-2 parameter) objective: an initial grid over `bounds`, then
    `rounds - 1` refinement passes that narrow each dimension's range
    around the best point found so far. No randomness — reproducible
    to the last bit given the same objective and bounds.

    Chosen over a stochastic/gradient method because the candidate
    models (docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md Section 6.1)
    are deliberately kept to <=2 free parameters ("prefer simplicity"),
    for which a grid search is simple to reason about, fully
    deterministic, and cheap enough — no gradient computation, no
    convergence-tuning, no local-optimum risk from a bad start point.

    `n_points`/`rounds` are fixed computational-budget constants, not
    hyperparameters tuned to favor any particular model's results.

    Returns (best_params, best_objective_value). `best_params` has the
    same length/order as `bounds`.
    """
    if not bounds:
        return (), objective()

    current_bounds = list(bounds)
    best_params: Optional[tuple[float, ...]] = None
    best_value = float("-inf")

    for _ in range(rounds):
        axis_grids = [_linspace(lo, hi, n_points) for lo, hi in current_bounds]
        for combo in itertools.product(*axis_grids):
            value = objective(*combo)
            if value > best_value:
                best_value = value
                best_params = combo

        next_bounds = []
        for dim, (lo, hi) in enumerate(current_bounds):
            span = (hi - lo) / (n_points - 1) if n_points > 1 else (hi - lo)
            center = best_params[dim]
            next_bounds.append((center - span, center + span))
        current_bounds = next_bounds

    return best_params, best_value


def normal_cdf(z: float) -> float:
    """Standard normal CDF via the closed-form error function
    (`math.erf`, stdlib) — no scipy dependency needed."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def wilcoxon_signed_rank_test(differences: Sequence[float]) -> dict:
    """Paired Wilcoxon signed-rank test, normal approximation (valid
    for the tournament counts this project works with, n >~ 20 —
    docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md Section 11 names this
    exact test for the primary promotion gate). Closed-form, no
    randomness, no scipy — average-rank tie handling for both zero
    differences (dropped, per the standard Wilcoxon convention) and
    tied absolute values (shared average rank).

    `differences[i]` should be metric_A(tournament_i) - metric_B(tournament_i)
    for a metric where LOWER is better (log loss, Brier) — a negative
    mean difference means A improved on B. Returns a dict with the
    signed-rank statistic, z, two-sided p-value, n (after dropping
    zeros), and the mean/median raw difference for direct reporting.
    """
    non_zero = [d for d in differences if d != 0]
    n = len(non_zero)
    if n == 0:
        return {"statistic": 0.0, "z": 0.0, "p_value": 1.0, "n": 0, "mean_diff": 0.0, "median_diff": 0.0}

    abs_sorted = sorted(range(n), key=lambda i: abs(non_zero[i]))
    ranks = [0.0] * n
    i = 0
    rank_cursor = 1
    while i < n:
        j = i
        while j + 1 < n and abs(non_zero[abs_sorted[j + 1]]) == abs(non_zero[abs_sorted[i]]):
            j += 1
        # Tied group [i, j] (inclusive) shares the average rank.
        avg_rank = (rank_cursor + (rank_cursor + (j - i))) / 2.0
        for k in range(i, j + 1):
            ranks[abs_sorted[k]] = avg_rank
        rank_cursor += (j - i + 1)
        i = j + 1

    w_plus = sum(ranks[idx] for idx, d in enumerate(non_zero) if d > 0)
    mean_w = n * (n + 1) / 4.0
    std_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    if std_w == 0:
        z = 0.0
    else:
        # Continuity correction toward the mean.
        if w_plus > mean_w:
            z = (w_plus - 0.5 - mean_w) / std_w
        elif w_plus < mean_w:
            z = (w_plus + 0.5 - mean_w) / std_w
        else:
            z = 0.0
    p_value = 2 * (1 - normal_cdf(abs(z)))
    p_value = min(1.0, max(0.0, p_value))

    sorted_diffs = sorted(differences)
    m = len(sorted_diffs)
    median_diff = (
        sorted_diffs[m // 2] if m % 2 == 1 else (sorted_diffs[m // 2 - 1] + sorted_diffs[m // 2]) / 2.0
    )

    return {
        "statistic": w_plus,
        "z": z,
        "p_value": p_value,
        "n": n,
        "mean_diff": sum(differences) / len(differences),
        "median_diff": median_diff,
    }
