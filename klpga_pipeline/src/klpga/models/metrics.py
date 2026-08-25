"""Metrics exactly as defined in
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` Sections 3 and 5:
per-tournament log loss and normalized Brier (PRIMARY), rank/hit-rate
diagnostics (SECONDARY), coarse-bin calibration with tournament-level
bootstrap CIs, and the paired Wilcoxon comparison used for Section 11's
promotion gate.

Every aggregate here treats the TOURNAMENT as the unit of inference
(Section 12: "the tournament, not the individual player-row, is the
key evaluation unit") — nothing in this module computes a per-row
significance test or treats player-target rows as independent trials.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from typing import Callable, Optional

from klpga.models.math_utils import clip_and_renormalize, wilcoxon_signed_rank_test

# Pre-registered log-loss clipping floor (spec Section 3A) — fixed
# before any model exists, identical for every candidate.
LOG_LOSS_EPSILON = 1e-6

# Pre-registered calibration bin edges (spec Section 3C: "no more than
# 4-6 bins"). Fixed before any real predicted-probability distribution
# is seen; a future version MAY refine these against real data, but
# that is a documented, disclosed revision, not a silent tune.
DEFAULT_CALIBRATION_BINS: tuple[tuple[float, float], ...] = (
    (0.0, 0.02),
    (0.02, 0.05),
    (0.05, 0.10),
    (0.10, 0.20),
    (0.20, 1.0 + 1e-9),  # +epsilon so a probability of exactly 1.0 falls in the last bin
)

# Fixed, disclosed bootstrap seed (spec Section 12: "if stochastic
# procedures are used, seed them explicitly") — the ONLY randomized
# procedure in this package; every model-fitting step is deterministic
# (klpga.models.candidates / math_utils.grid_refine_search).
BOOTSTRAP_SEED = 20260825
DEFAULT_BOOTSTRAP_RESAMPLES = 1000
DEFAULT_BOOTSTRAP_CI = 0.90


@dataclass(frozen=True)
class TournamentPrediction:
    """One evaluated tournament's predictions for one model — the unit
    every metric below operates on."""

    target_event_id: str
    target_game_code: str
    target_start_date: str  # ISO date string
    probabilities: dict[str, float]  # already clipped + renormalized, sums to 1.0
    winner: str
    prior_events_n_by_player: dict[str, int] = field(default_factory=dict)

    @property
    def field_size(self) -> int:
        return len(self.probabilities)


def make_prediction(
    target_event_id: str,
    target_game_code: str,
    target_start_date: str,
    raw_probabilities: dict[str, float],
    winner: str,
    prior_events_n_by_player: dict[str, int],
) -> TournamentPrediction:
    """Applies the pre-registered clip-and-renormalize floor once, at
    construction time, so every metric downstream sees the exact same
    already-safe distribution."""
    safe_probs = clip_and_renormalize(raw_probabilities, epsilon=LOG_LOSS_EPSILON)
    return TournamentPrediction(
        target_event_id=target_event_id,
        target_game_code=target_game_code,
        target_start_date=target_start_date,
        probabilities=safe_probs,
        winner=winner,
        prior_events_n_by_player=prior_events_n_by_player,
    )


# ----------------------------------------------------------------
# Per-tournament primary metrics (Section 3)
# ----------------------------------------------------------------


def log_loss(pred: TournamentPrediction) -> float:
    import math

    return -math.log(pred.probabilities[pred.winner])


def brier_raw(pred: TournamentPrediction) -> float:
    total = 0.0
    for player, p in pred.probabilities.items():
        y = 1.0 if player == pred.winner else 0.0
        total += (p - y) ** 2
    return total


def brier_norm(pred: TournamentPrediction) -> float:
    n = pred.field_size
    return brier_raw(pred) / n if n else 0.0


# ----------------------------------------------------------------
# Per-tournament secondary / ranking metrics (Section 5)
# ----------------------------------------------------------------


def winner_rank(pred: TournamentPrediction) -> int:
    """1-based rank of the actual winner by predicted probability,
    descending. Ties broken by player_code (ascending) for a fully
    deterministic, reproducible ordering — never by insertion order,
    which would depend on incidental dict/DB iteration order."""
    ordered = sorted(pred.probabilities.items(), key=lambda kv: (-kv[1], kv[0]))
    for rank, (player, _) in enumerate(ordered, start=1):
        if player == pred.winner:
            return rank
    raise ValueError(f"winner {pred.winner!r} not found in field for {pred.target_event_id}")


def top_k_hit(pred: TournamentPrediction, k: int) -> bool:
    return winner_rank(pred) <= k


def reciprocal_rank(pred: TournamentPrediction) -> float:
    return 1.0 / winner_rank(pred)


# ----------------------------------------------------------------
# Aggregation across tournaments — ALWAYS tournament-level, per
# Section 12's "the tournament, not the individual player-row, is the
# key evaluation unit."
# ----------------------------------------------------------------


@dataclass(frozen=True)
class ModelMetricsSummary:
    model_id: str
    tournament_count: int
    mean_log_loss: float
    mean_brier_norm: float
    mean_brier_raw: float
    mean_winner_rank: float
    median_winner_rank: float
    top3_rate: float
    top5_rate: float
    top10_rate: float
    mean_reciprocal_rank: float


def summarize_model(model_id: str, predictions: list[TournamentPrediction]) -> ModelMetricsSummary:
    if not predictions:
        return ModelMetricsSummary(model_id, 0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), 0.0, 0.0, 0.0, float("nan"))

    ranks = [winner_rank(p) for p in predictions]
    return ModelMetricsSummary(
        model_id=model_id,
        tournament_count=len(predictions),
        mean_log_loss=statistics.mean(log_loss(p) for p in predictions),
        mean_brier_norm=statistics.mean(brier_norm(p) for p in predictions),
        mean_brier_raw=statistics.mean(brier_raw(p) for p in predictions),
        mean_winner_rank=statistics.mean(ranks),
        median_winner_rank=statistics.median(ranks),
        top3_rate=sum(1 for r in ranks if r <= 3) / len(ranks),
        top5_rate=sum(1 for r in ranks if r <= 5) / len(ranks),
        top10_rate=sum(1 for r in ranks if r <= 10) / len(ranks),
        mean_reciprocal_rank=statistics.mean(1.0 / r for r in ranks),
    )


# ----------------------------------------------------------------
# Paired comparison (Section 11's promotion gate) — matched by
# target_event_id, tournament-level differences only.
# ----------------------------------------------------------------


def paired_metric_differences(
    predictions_a: list[TournamentPrediction],
    predictions_b: list[TournamentPrediction],
    metric_fn: Callable[[TournamentPrediction], float],
) -> list[float]:
    """metric_fn(a) - metric_fn(b) for every tournament BOTH lists
    cover (matched by target_event_id — a model evaluated on a
    different tournament set, e.g. a different threshold, cannot be
    paired against one that isn't)."""
    by_target_b = {p.target_event_id: p for p in predictions_b}
    diffs = []
    for pa in predictions_a:
        pb = by_target_b.get(pa.target_event_id)
        if pb is None:
            continue
        diffs.append(metric_fn(pa) - metric_fn(pb))
    return diffs


def paired_comparison(
    predictions_a: list[TournamentPrediction],
    predictions_b: list[TournamentPrediction],
    metric_fn: Callable[[TournamentPrediction], float] = log_loss,
) -> dict:
    """Wilcoxon signed-rank test on the paired per-tournament
    differences (A - B) for `metric_fn` (default: log loss, the
    Section 11 primary gate). A negative mean/median difference means
    A improved on B (lower is better for log loss and Brier)."""
    diffs = paired_metric_differences(predictions_a, predictions_b, metric_fn)
    result = wilcoxon_signed_rank_test(diffs)
    result["metric"] = getattr(metric_fn, "__name__", "metric")
    return result


# ----------------------------------------------------------------
# Calibration (Section 3C)
# ----------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationBin:
    lo: float
    hi: float
    row_count: int
    expected_wins: float  # sum of predicted probabilities in this bin
    actual_wins: int  # count of rows in this bin that were the actual winner
    contributing_tournament_count: int  # tournaments whose winner's own prediction fell in this bin
    expected_wins_ci: Optional[tuple[float, float]] = None
    actual_wins_ci: Optional[tuple[float, float]] = None


def _bin_index(prob: float, bins: tuple[tuple[float, float], ...]) -> Optional[int]:
    for i, (lo, hi) in enumerate(bins):
        if lo <= prob < hi:
            return i
    return None


def _compute_bin_stats(predictions: list[TournamentPrediction], bins: tuple[tuple[float, float], ...]) -> list[dict]:
    stats = [{"row_count": 0, "expected_wins": 0.0, "actual_wins": 0, "tournaments": set()} for _ in bins]
    for pred in predictions:
        for player, prob in pred.probabilities.items():
            idx = _bin_index(prob, bins)
            if idx is None:
                continue
            stats[idx]["row_count"] += 1
            stats[idx]["expected_wins"] += prob
            is_winner = player == pred.winner
            if is_winner:
                stats[idx]["actual_wins"] += 1
                stats[idx]["tournaments"].add(pred.target_event_id)
    return stats


def calibration_report(
    predictions: list[TournamentPrediction],
    bins: tuple[tuple[float, float], ...] = DEFAULT_CALIBRATION_BINS,
    n_bootstrap: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    ci: float = DEFAULT_BOOTSTRAP_CI,
    seed: int = BOOTSTRAP_SEED,
) -> list[CalibrationBin]:
    """Coarse-bin calibration with TOURNAMENT-LEVEL (not row-level)
    bootstrap confidence intervals — resamples whole tournaments with
    replacement, which correctly propagates the within-tournament
    correlation a row-level bootstrap would ignore (spec Section 3C /
    12's "11,189 rows are not 11,189 independent outcomes")."""
    base_stats = _compute_bin_stats(predictions, bins)

    rng = random.Random(seed)
    n = len(predictions)
    boot_expected = [[] for _ in bins]
    boot_actual = [[] for _ in bins]
    if n > 0:
        for _ in range(n_bootstrap):
            resample = [predictions[rng.randrange(n)] for _ in range(n)]
            resample_stats = _compute_bin_stats(resample, bins)
            for i, s in enumerate(resample_stats):
                boot_expected[i].append(s["expected_wins"])
                boot_actual[i].append(float(s["actual_wins"]))

    lower_q = (1 - ci) / 2
    upper_q = 1 - lower_q

    def _percentile(values: list[float], q: float) -> float:
        if not values:
            return float("nan")
        ordered = sorted(values)
        idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return ordered[idx]

    result = []
    for i, (lo, hi) in enumerate(bins):
        s = base_stats[i]
        expected_ci = (
            (_percentile(boot_expected[i], lower_q), _percentile(boot_expected[i], upper_q))
            if boot_expected[i]
            else None
        )
        actual_ci = (
            (_percentile(boot_actual[i], lower_q), _percentile(boot_actual[i], upper_q))
            if boot_actual[i]
            else None
        )
        result.append(
            CalibrationBin(
                lo=lo,
                hi=min(hi, 1.0),
                row_count=s["row_count"],
                expected_wins=s["expected_wins"],
                actual_wins=s["actual_wins"],
                contributing_tournament_count=len(s["tournaments"]),
                expected_wins_ci=expected_ci,
                actual_wins_ci=actual_ci,
            )
        )
    return result
