"""M0-M6 candidate model definitions, fitting, and prediction — exactly
the feature sets frozen in `docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`
Section 6.1. No other feature (wins, top5, top10, cut_rate, recent20,
SG/GIR/driving/putting/course-par) is used anywhere in this module —
those remain future challengers, not part of this stage.

======================================================================
MODEL FORM
======================================================================
Every candidate (other than M0) is a conditional-logit / softmax model
over 1-2 STANDARDIZED, SHRUNK point-in-time features:

  combined_score_i = z1_i                     (1-feature models: M1, M2)
  combined_score_i = z1_i + beta * z2_i        (2-feature models: M3-M6)

  P(i) = softmax(-combined_score_i / tau)      over the field

`tau` (and `beta` for 2-feature models) are the model's ONLY free
parameters — <=2 per model, per the frozen spec's "prefer simplicity."
Both are fit by maximizing the training fold's log-likelihood of the
ACTUAL historical winners (a standard conditional-logit / rank-1
Plackett-Luce MLE), via `klpga.models.math_utils.grid_refine_search` —
a deterministic grid search, never a hand-picked value.

`z_i` is NOT the raw feature — see "SHRINKAGE" below.

======================================================================
SHRINKAGE (Section 4 of the spec: "statistically defensible
training-only fallback / shrinkage mechanism")
======================================================================
For each feature, fit from the TRAINING FOLD ONLY (never the target
tournament, never later tournaments):

  pop_mean = mean of the feature's non-NULL values across training rows
  pop_std  = sample std of those same values (1.0 if <2 data points)
  k        = median of the feature's own `_n` sample-size companion
             across training rows with a non-NULL value (a simple,
             data-driven — not hand-picked — shrinkage strength: "shrink
             toward the mean by an amount that halves at the typical
             amount of history seen in this training fold")

For a player with `_n` observations behind this feature (0 if the
value is NULL — a rookie, or a player whose feature genuinely has zero
supporting rounds/events):

  shrunk  = pop_mean + (n / (n + k)) * (raw_value - pop_mean)
          = pop_mean                                    if n == 0

  z = (shrunk - pop_mean) / pop_std = (n / (n + k)) * (raw_value - pop_mean) / pop_std

A zero-history player therefore gets z = 0 exactly (the training
fold's average strength) — NOT a dropped row, NOT a fabricated
constant, and NOT probability zero (a z=0 player still receives a real,
non-trivial softmax probability). A player with a little history gets
partially shrunk toward the mean; a player with lots of history is
barely shrunk at all. This is a disclosed simplification of full
empirical-Bayes shrinkage (which would separately estimate a
per-observation variance) — appropriate for the "smallest reproducible"
scope of this stage; a more elaborate shrinkage model is a candidate
future refinement, not silently assumed better without evidence.

This IS how zero-history and sparse-history players are handled —
see docs/SITE_STRUCTURE_TODO.md section 8 (or the model comparison
report) for the exact same statement made in the production report.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from klpga.models.math_utils import grid_refine_search, softmax_from_logits

# Exactly the frozen M0-M6 feature sets — see module docstring. Adding
# a feature here without updating the frozen spec first is exactly the
# "moving the goalposts" this whole exercise exists to prevent.
MODEL_FEATURES: dict[str, tuple[str, ...]] = {
    "M0": (),
    "M1": ("prior_avg_round_score_to_par",),
    "M2": ("prior_avg_field_relative_round_score",),
    "M3": ("prior_avg_round_score_to_par", "prior_recent_form_5"),
    "M4": ("prior_avg_round_score_to_par", "prior_recent_form_10"),
    "M5": ("prior_avg_field_relative_round_score", "prior_recent_form_5"),
    "M6": ("prior_avg_field_relative_round_score", "prior_recent_form_10"),
}

MODEL_DESCRIPTIONS: dict[str, str] = {
    "M0": "Uniform baseline",
    "M1": "Career scoring strength only",
    "M2": "Field-relative strength only",
    "M3": "Career scoring strength + Recent5",
    "M4": "Career scoring strength + Recent10",
    "M5": "Field-relative strength + Recent5",
    "M6": "Field-relative strength + Recent10",
}

MODEL_IDS: tuple[str, ...] = ("M0", "M1", "M2", "M3", "M4", "M5", "M6")

# Fixed computational-budget constants for the deterministic MLE fit —
# not hyperparameters tuned to favor any model's results. Wider/denser
# for the 2-parameter models since they have a larger search space.
_TAU_LOG_BOUNDS = (math.log(0.02), math.log(50.0))
_BETA_BOUNDS = (-4.0, 4.0)
_GRID_POINTS_1D = 25
_GRID_ROUNDS_1D = 4
_GRID_POINTS_2D = 11
_GRID_ROUNDS_2D = 4


@dataclass(frozen=True)
class ShrinkageParams:
    pop_mean: float
    pop_std: float
    k: float


@dataclass(frozen=True)
class FittedModel:
    model_id: str
    feature_columns: tuple[str, ...]
    shrinkage: dict[str, ShrinkageParams] = field(default_factory=dict)
    beta: Optional[float] = None
    tau: Optional[float] = None
    training_tournament_count: int = 0


def fit_shrinkage(training_rows: list[dict], feature_col: str) -> ShrinkageParams:
    """Fit pop_mean/pop_std/k for one feature from TRAINING rows only —
    see module docstring. Never reads a target-tournament row (callers
    only ever pass training_rows here)."""
    n_col = f"{feature_col}_n"
    known = [
        (row[feature_col], row[n_col])
        for row in training_rows
        if row.get(feature_col) is not None and row.get(n_col)
    ]
    if not known:
        return ShrinkageParams(pop_mean=0.0, pop_std=1.0, k=1.0)

    values = [v for v, _ in known]
    pop_mean = sum(values) / len(values)
    if len(values) >= 2:
        variance = statistics.variance(values)
        pop_std = math.sqrt(variance) if variance > 0 else 1.0
    else:
        pop_std = 1.0

    ns = sorted(n for _, n in known)
    median_n = ns[len(ns) // 2]
    k = float(median_n) if median_n > 0 else 1.0

    return ShrinkageParams(pop_mean=pop_mean, pop_std=pop_std, k=k)


def apply_shrinkage_and_standardize(value: Optional[float], n: Optional[int], params: ShrinkageParams) -> float:
    """Returns the shrunk, standardized z-score for one player's raw
    feature value (see module docstring for the exact formula). A NULL
    value or zero sample size returns exactly 0.0 — full shrinkage to
    the training fold's mean, never a dropped player."""
    if value is None or not n:
        return 0.0
    weight = n / (n + params.k)
    shrunk = params.pop_mean + weight * (value - params.pop_mean)
    if params.pop_std == 0:
        return 0.0
    return (shrunk - params.pop_mean) / params.pop_std


def _combined_score(zs: tuple[float, ...], beta: Optional[float]) -> float:
    if len(zs) == 1:
        return zs[0]
    return zs[0] + beta * zs[1]


def _group_rows_by_target(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["target_event_id"], []).append(row)
    return grouped


def fit_candidate_model(model_id: str, training_rows: list[dict]) -> FittedModel:
    """Fits `model_id` (one of MODEL_IDS) using ONLY the rows passed in
    — callers are responsible for ensuring `training_rows` contains
    only strictly-prior USABLE tournaments (see
    klpga.models.walk_forward_eval, which is the only intended caller
    for real evaluation; tests may call this directly with a
    deliberately-controlled row set)."""
    feature_columns = MODEL_FEATURES[model_id]
    if not feature_columns:
        return FittedModel(model_id=model_id, feature_columns=(), training_tournament_count=0)

    shrinkage = {f: fit_shrinkage(training_rows, f) for f in feature_columns}

    by_target = _group_rows_by_target(training_rows)
    tournaments: list[tuple[list[tuple[str, tuple[float, ...]]], str]] = []
    for target_rows in by_target.values():
        entries = []
        winner = None
        for row in target_rows:
            zs = tuple(
                apply_shrinkage_and_standardize(row.get(f), row.get(f"{f}_n"), shrinkage[f])
                for f in feature_columns
            )
            entries.append((row["player_code"], zs))
            if row.get("label_is_winner"):
                winner = row["player_code"]
        if winner is not None:
            tournaments.append((entries, winner))

    if not tournaments:
        # No usable training tournament yet (e.g. the very first usable
        # tournament in the corpus) — fall back to a fixed, documented,
        # neutral default (tau=1, beta=0) rather than crash. This is a
        # deterministic default, not a fitted value, and only ever
        # applies when there is genuinely nothing to fit against.
        return FittedModel(
            model_id=model_id,
            feature_columns=feature_columns,
            shrinkage=shrinkage,
            beta=(0.0 if len(feature_columns) == 2 else None),
            tau=1.0,
            training_tournament_count=0,
        )

    def log_likelihood(beta: Optional[float], tau: float) -> float:
        total = 0.0
        for entries, winner in tournaments:
            logits = {player: -_combined_score(zs, beta) / tau for player, zs in entries}
            probs = softmax_from_logits(logits)
            total += math.log(max(probs[winner], 1e-300))
        return total

    if len(feature_columns) == 1:
        def objective(log_tau: float) -> float:
            return log_likelihood(None, math.exp(log_tau))

        (log_tau_best,), _ = grid_refine_search(
            objective, [_TAU_LOG_BOUNDS], n_points=_GRID_POINTS_1D, rounds=_GRID_ROUNDS_1D
        )
        tau = math.exp(log_tau_best)
        beta = None
    else:
        def objective(beta_val: float, log_tau: float) -> float:
            return log_likelihood(beta_val, math.exp(log_tau))

        (beta_best, log_tau_best), _ = grid_refine_search(
            objective, [_BETA_BOUNDS, _TAU_LOG_BOUNDS], n_points=_GRID_POINTS_2D, rounds=_GRID_ROUNDS_2D
        )
        tau = math.exp(log_tau_best)
        beta = beta_best

    return FittedModel(
        model_id=model_id,
        feature_columns=feature_columns,
        shrinkage=shrinkage,
        beta=beta,
        tau=tau,
        training_tournament_count=len(tournaments),
    )


def predict_candidate_model(fitted: FittedModel, field_rows: list[dict]) -> dict[str, float]:
    """Field-conditional probabilities for one target tournament's
    field, using an ALREADY-FITTED model. Every player in `field_rows`
    receives a strictly-positive probability (softmax's mathematical
    guarantee — see math_utils.softmax_from_logits); the field sums to
    1.0 up to float precision."""
    if not field_rows:
        return {}
    if not fitted.feature_columns:
        n = len(field_rows)
        return {row["player_code"]: 1.0 / n for row in field_rows}

    logits = {}
    for row in field_rows:
        zs = tuple(
            apply_shrinkage_and_standardize(row.get(f), row.get(f"{f}_n"), fitted.shrinkage[f])
            for f in fitted.feature_columns
        )
        combined = _combined_score(zs, fitted.beta)
        logits[row["player_code"]] = -combined / fitted.tau
    return softmax_from_logits(logits)
