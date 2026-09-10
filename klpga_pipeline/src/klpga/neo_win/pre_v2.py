"""NEO PRE 5-probability V2.

V2 keeps the already-frozen M4 pre-event strength model unchanged.  Its
WIN value is M4's exact conditional-logit probability.  TOP5/TOP10/TOP20
are inclusion probabilities from a Plackett-Luce finish order using those
same M4 weights.  CUT is fitted separately because cut truth is binary:
the target is ``player_event.made_cut`` and never ``rounds_played == 4``.

All fitted values are learned from the caller-supplied, strictly-prior
training fold.  This module has no tournament ID, date, player, sponsor,
or post-start input and performs no model tuning.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from klpga.models.candidates import (
    apply_shrinkage_and_standardize,
    fit_shrinkage,
)

MODEL_ID = "NEO_PRE_5PROB_V2"
CUT_MODEL_ID = "M4_BINARY_LOGIT_MADE_CUT"
MODEL_FEATURES = ("prior_avg_round_score_to_par", "prior_recent_form_10")
DEFAULT_N_SIMULATIONS = 100_000
NUMERICAL_RIDGE = 1e-8


@dataclass(frozen=True)
class CutModel:
    features: tuple[str, ...]
    coefficients: tuple[float, ...]
    shrinkage: dict
    training_row_count: int


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        if abs(augmented[col][col]) < 1e-12:
            augmented[col][col] = 1e-12
        divisor = augmented[col][col]
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [
                augmented[row][idx] - factor * augmented[col][idx]
                for idx in range(n + 1)
            ]
    return [augmented[idx][-1] for idx in range(n)]


def fit_cut_model(training_rows: list[dict], features: tuple[str, ...] = MODEL_FEATURES) -> CutModel:
    """Fit a deterministic binary logistic MLE to explicit made_cut truth."""
    if not training_rows:
        raise ValueError("CUT model requires a non-empty strictly-prior training fold")
    for row in training_rows:
        if "label_made_cut" not in row:
            raise ValueError("CUT truth must be explicit label_made_cut from player_event.made_cut")
    shrinkage = {feature: fit_shrinkage(training_rows, feature) for feature in features}
    xs: list[list[float]] = []
    ys: list[float] = []
    for row in training_rows:
        xs.append(
            [1.0]
            + [
                apply_shrinkage_and_standardize(
                    row.get(feature), row.get(f"{feature}_n"), shrinkage[feature]
                )
                for feature in features
            ]
        )
        ys.append(1.0 if row["label_made_cut"] else 0.0)

    coefficients = [0.0] * len(xs[0])
    for _ in range(50):
        gradient = [0.0] * len(coefficients)
        information = [[0.0] * len(coefficients) for _ in coefficients]
        for x, y in zip(xs, ys):
            eta = max(-30.0, min(30.0, sum(beta * value for beta, value in zip(coefficients, x))))
            probability = 1.0 / (1.0 + math.exp(-eta))
            variance = max(1e-9, probability * (1.0 - probability))
            for i in range(len(coefficients)):
                gradient[i] += x[i] * (y - probability)
                for j in range(len(coefficients)):
                    information[i][j] += variance * x[i] * x[j]
        for i in range(1, len(coefficients)):
            information[i][i] += NUMERICAL_RIDGE
        step = _solve(information, gradient)
        coefficients = [value + delta for value, delta in zip(coefficients, step)]
        if max(abs(delta) for delta in step) < 1e-9:
            break
    return CutModel(features, tuple(coefficients), shrinkage, len(training_rows))


def predict_cut(model: CutModel, field_rows: list[dict]) -> dict[str, float]:
    predictions: dict[str, float] = {}
    for row in field_rows:
        x = [1.0] + [
            apply_shrinkage_and_standardize(
                row.get(feature), row.get(f"{feature}_n"), model.shrinkage[feature]
            )
            for feature in model.features
        ]
        eta = max(-30.0, min(30.0, sum(beta * value for beta, value in zip(model.coefficients, x))))
        predictions[str(row["player_code"])] = 1.0 / (1.0 + math.exp(-eta))
    return predictions


def simulate_finish_tiers(
    win_weights: dict[str, float], *, n_simulations: int = DEFAULT_N_SIMULATIONS, seed: int
) -> dict[str, dict[str, float]]:
    """Return PL inclusion probabilities for TOP5/TOP10/TOP20.

    Exponential-race sampling is exactly equivalent to a
    Plackett-Luce ranking.  One sampled order feeds every tier, so the
    returned Monte Carlo values are structurally nested.
    """
    if not win_weights:
        return {}
    if n_simulations <= 0:
        raise ValueError("n_simulations must be positive")
    codes = sorted(win_weights)
    if any(not math.isfinite(win_weights[code]) or win_weights[code] <= 0 for code in codes):
        raise ValueError("every frozen M4 win weight must be finite and strictly positive")
    rng = random.Random(seed)
    counts = {tier: {code: 0 for code in codes} for tier in ("top5", "top10", "top20")}
    for _ in range(n_simulations):
        ranking = sorted(
            codes,
            key=lambda code: -math.log(max(rng.random(), 1e-300)) / win_weights[code],
        )
        for tier, size in (("top5", 5), ("top10", 10), ("top20", 20)):
            for code in ranking[: min(size, len(ranking))]:
                counts[tier][code] += 1
    return {
        code: {
            "top5_probability": counts["top5"][code] / n_simulations,
            "top10_probability": counts["top10"][code] / n_simulations,
            "top20_probability": counts["top20"][code] / n_simulations,
        }
        for code in codes
    }


def combine_probabilities(
    cut_probabilities: dict[str, float],
    win_probabilities: dict[str, float],
    tier_probabilities: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    expected = set(win_probabilities)
    if set(cut_probabilities) != expected or set(tier_probabilities) != expected:
        raise ValueError("CUT/WIN/TOP probability populations must be identical")
    result = {}
    for code in sorted(expected):
        row = {
            "cut_probability": cut_probabilities[code],
            **tier_probabilities[code],
            "win_probability": win_probabilities[code],
        }
        chain = [row["win_probability"], row["top5_probability"], row["top10_probability"], row["top20_probability"]]
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in row.values()):
            raise ValueError(f"non-finite or out-of-bounds probability for {code}")
        if not all(a <= b + 1e-12 for a, b in zip(chain, chain[1:])):
            raise ValueError(f"probability monotonicity failed for {code}: {chain}")
        result[code] = row
    return result
