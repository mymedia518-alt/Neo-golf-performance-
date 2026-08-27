"""NEO WIN v0.1 — model fitting and prediction. Deliberately NOT a
member of `klpga.models.candidates.MODEL_FEATURES` (the frozen M0-M6
ladder) — a new, separate model, reusing that module's already-
validated PURE math (`fit_shrinkage`, `apply_shrinkage_and_standardize`,
`klpga.models.math_utils.softmax_from_logits`/`clip_and_renormalize`/
`grid_refine_search`) unmodified, never its frozen model-selection
dict.

======================================================================
MODEL FORM (deliberately simpler than the M3-M6 2-feature form)
======================================================================
  combined_score_i = sum(z_f_i for f in NEO_WIN_FEATURES)   (EQUAL weight,
                                                               no fitted beta)
  P(i) = softmax(-combined_score_i / tau)                    over the field

`tau` is the ONLY free parameter, fit by the same conditional-logit MLE
(`grid_refine_search` over log-tau) already used for every M0-M6
candidate. Equal-weighting (rather than fitting a separate beta per
feature, as M3-M6 do for their 2nd feature) is a deliberate v0.1
choice: 4 features means up to 3 free beta ratios, and this project's
"prefer simplicity" evaluation philosophy (docs/WIN_PROBABILITY_MODEL_
EVALUATION_SPEC.md Section 6.1) plus a modest training-tournament count
argue for keeping v0.1 to its single free parameter — a per-feature-
weight variant is a natural, disclosed future refinement, evaluated the
same promotion-gate way M0-M6 were, not silently assumed better without
evidence.

Each `z_f_i` uses the exact same shrink-toward-training-mean +
standardize formula as `klpga.models.candidates.apply_shrinkage_and_
standardize` — a zero-history/missing-metric player gets z=0 (the
training fold's average), never a dropped row or a fabricated
non-zero value. `neo_official_metric` rows must already be oriented
(see klpga.neo_win.official_metrics.oriented_value) before reaching
this module — model.py treats every feature identically, "lower z is
more winning-favorable," with no per-feature sign logic of its own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from klpga.models.candidates import ShrinkageParams, apply_shrinkage_and_standardize, fit_shrinkage
from klpga.models.math_utils import clip_and_renormalize, grid_refine_search, softmax_from_logits

MODEL_ID = "NEO_WIN_V0_1"

NEO_WIN_FEATURES: tuple[str, ...] = (
    "prior_avg_round_score_to_par",
    "prior_recent_form_10",
    "neo_consistency_stddev",
    "neo_official_metric",
)

_TAU_LOG_BOUNDS = (math.log(0.02), math.log(50.0))
_GRID_POINTS = 25
_GRID_ROUNDS = 4


@dataclass(frozen=True)
class FittedNeoWinModel:
    model_id: str
    feature_columns: tuple[str, ...]
    shrinkage: dict[str, ShrinkageParams] = field(default_factory=dict)
    tau: Optional[float] = None
    training_tournament_count: int = 0


def _combined_score(row: dict, feature_columns: tuple[str, ...], shrinkage: dict[str, ShrinkageParams]) -> float:
    return sum(
        apply_shrinkage_and_standardize(row.get(f), row.get(f"{f}_n"), shrinkage[f]) for f in feature_columns
    )


def fit_neo_win_model(training_rows: list[dict], feature_columns: tuple[str, ...] = NEO_WIN_FEATURES) -> FittedNeoWinModel:
    """Fits tau using ONLY `training_rows` — callers are responsible for
    ensuring these are strictly-prior, usable training tournaments (see
    klpga.neo_win.dataset.build_neo_win_training_rows, the intended
    caller)."""
    shrinkage = {f: fit_shrinkage(training_rows, f) for f in feature_columns}

    by_target: dict[str, list[dict]] = {}
    for row in training_rows:
        by_target.setdefault(row["target_event_id"], []).append(row)

    tournaments: list[tuple[list[tuple[str, float]], str]] = []
    for target_rows in by_target.values():
        entries = []
        winner = None
        for row in target_rows:
            entries.append((row["player_code"], _combined_score(row, feature_columns, shrinkage)))
            if row.get("label_is_winner"):
                winner = row["player_code"]
        if winner is not None:
            tournaments.append((entries, winner))

    if not tournaments:
        return FittedNeoWinModel(
            model_id=MODEL_ID, feature_columns=feature_columns, shrinkage=shrinkage, tau=1.0, training_tournament_count=0
        )

    def log_likelihood(tau: float) -> float:
        total = 0.0
        for entries, winner in tournaments:
            logits = {player: -score / tau for player, score in entries}
            probs = softmax_from_logits(logits)
            total += math.log(max(probs[winner], 1e-300))
        return total

    def objective(log_tau: float) -> float:
        return log_likelihood(math.exp(log_tau))

    (log_tau_best,), _ = grid_refine_search(objective, [_TAU_LOG_BOUNDS], n_points=_GRID_POINTS, rounds=_GRID_ROUNDS)
    tau = math.exp(log_tau_best)

    return FittedNeoWinModel(
        model_id=MODEL_ID,
        feature_columns=feature_columns,
        shrinkage=shrinkage,
        tau=tau,
        training_tournament_count=len(tournaments),
    )


def predict_neo_win_model(fitted: FittedNeoWinModel, field_rows: list[dict]) -> dict[str, float]:
    """Every player in `field_rows` gets a strictly-positive
    probability (softmax's guarantee); `clip_and_renormalize` is
    applied on top as the same disclosed safety floor `klpga.models.
    inference.run_inference` uses — the field sums to 1.0 within
    float precision, never approximately "100%"."""
    if not field_rows:
        return {}
    logits = {
        row["player_code"]: -_combined_score(row, fitted.feature_columns, fitted.shrinkage) / fitted.tau
        for row in field_rows
    }
    return clip_and_renormalize(softmax_from_logits(logits))
