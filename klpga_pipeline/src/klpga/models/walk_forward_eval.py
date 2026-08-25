"""Orchestrates the walk-forward evaluation of M0-M6 exactly per
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` Sections 2, 3, 7, 8:
for each ELIGIBLE target tournament at a given threshold, fit every
candidate model on strictly-prior USABLE tournaments only, predict the
target's field, and collect metrics.

TRAIN/EVALUATE POPULATIONS (see klpga.backtest.walk_forward's own
"POPULATION DEFINITIONS" section for the canonical terms):
  - EVALUATED tournaments = ELIGIBLE-AT-THRESHOLD-k targets (must have
    >= threshold OTHER usable tournaments before them — this is what
    Section 5's "95 eligible target tournaments" refers to).
  - TRAINING rows for a given target = every row belonging to a USABLE
    tournament (not threshold-filtered) strictly before that target's
    effective date — see the frozen spec's Section 8: restricting
    training to only OTHER eligible tournaments would leave the
    earliest eligible target with an empty (or needlessly small)
    training set, which is neither what the frozen spec's Section 8
    describes nor useful for MLE fitting.

This module never re-derives point-in-time features — every feature
value comes straight from `klpga.backtest.walk_forward.
build_walk_forward_dataset()`'s rows, called exactly once per
evaluation run.
"""
from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field
from typing import Callable, Optional

from klpga.backtest.walk_forward import build_walk_forward_dataset
from klpga.models.candidates import fit_candidate_model, predict_candidate_model
from klpga.models.metrics import TournamentPrediction, brier_norm, log_loss, make_prediction

ProgressCallback = Callable[[int, int, "TargetInfo", Optional[str], bool], None]


@dataclass(frozen=True)
class TargetInfo:
    event_id: str
    game_code: str
    start_date: str


@dataclass(frozen=True)
class MultiModelEvaluationResult:
    threshold: int
    model_ids: tuple[str, ...]
    predictions_by_model: dict[str, list[TournamentPrediction]]
    total_usable_tournaments: int
    eligible_tournament_count: int
    skipped_no_date_event_ids: list[str] = field(default_factory=list)
    skipped_empty_field_event_ids: list[str] = field(default_factory=list)
    # (event_id, winner_row_count) for eligible targets excluded because
    # they had 0 or >1 rows with label_is_winner=True — never silently
    # scored against an ambiguous or missing ground truth.
    skipped_ambiguous_winner: list[tuple[str, int]] = field(default_factory=list)


def _group_rows_by_target(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["target_event_id"], []).append(row)
    return grouped


def run_multi_model_walk_forward(
    conn: sqlite3.Connection,
    model_ids: tuple[str, ...],
    threshold: int,
    progress_callback: Optional[ProgressCallback] = None,
) -> MultiModelEvaluationResult:
    """The one entry point real evaluation code should call: fits and
    predicts every model in `model_ids` across every eligible target at
    `threshold`, sharing the per-target training/target row lookup
    across models (fitting itself is still done once per model, since
    each model's feature set/parameters differ).

    `progress_callback(target_index_1based, total_targets, target_info,
    model_id_or_None, skipped_bool)` is invoked once per (target,
    model) pair — `model_id=None, skipped=True` marks a target skipped
    entirely (ambiguous/missing winner) before any model runs on it.
    """
    dataset = build_walk_forward_dataset(conn)
    rows_by_target = _group_rows_by_target(dataset.rows)
    eligible_targets = [t for t in dataset.target_order if t.prior_tournament_count >= threshold]

    predictions_by_model: dict[str, list[TournamentPrediction]] = {mid: [] for mid in model_ids}
    skipped_ambiguous: list[tuple[str, int]] = []

    total = len(eligible_targets)
    for idx, target in enumerate(eligible_targets, start=1):
        target_info = TargetInfo(target.event_id, target.game_code, target.effective_date.isoformat())
        target_rows = rows_by_target.get(target.event_id, [])

        winners = [r["player_code"] for r in target_rows if r.get("label_is_winner")]
        if len(winners) != 1:
            skipped_ambiguous.append((target.event_id, len(winners)))
            if progress_callback:
                progress_callback(idx, total, target_info, None, True)
            continue
        winner = winners[0]
        prior_n_by_player = {r["player_code"]: r.get("prior_events_n", 0) for r in target_rows}

        # Training set: every USABLE (not threshold-filtered) tournament
        # strictly before this target — see module docstring.
        training_rows: list[dict] = []
        for other in dataset.target_order:
            if other.effective_date < target.effective_date:
                training_rows.extend(rows_by_target.get(other.event_id, []))

        for model_id in model_ids:
            fitted = fit_candidate_model(model_id, training_rows)
            raw_probs = predict_candidate_model(fitted, target_rows)
            pred = make_prediction(
                target.event_id, target.game_code, target.effective_date.isoformat(),
                raw_probs, winner, prior_n_by_player,
            )
            predictions_by_model[model_id].append(pred)
            if progress_callback:
                progress_callback(idx, total, target_info, model_id, False)

    return MultiModelEvaluationResult(
        threshold=threshold,
        model_ids=tuple(model_ids),
        predictions_by_model=predictions_by_model,
        total_usable_tournaments=len(dataset.target_order),
        eligible_tournament_count=total,
        skipped_no_date_event_ids=dataset.skipped_no_date_event_ids,
        skipped_empty_field_event_ids=dataset.skipped_empty_field_event_ids,
        skipped_ambiguous_winner=skipped_ambiguous,
    )


# ----------------------------------------------------------------
# Section 8 of this stage's instructions: time-stability (early/
# middle/late thirds).
# ----------------------------------------------------------------


def time_stability_report(predictions: list[TournamentPrediction]) -> dict:
    ordered = sorted(predictions, key=lambda p: p.target_start_date)
    n = len(ordered)
    if n < 3:
        return {"periods": {}, "note": f"only {n} evaluated tournament(s) — cannot split into 3 periods"}

    third = n // 3
    early, mid, late = ordered[:third], ordered[third: 2 * third], ordered[2 * third:]

    periods = {}
    for name, group in (("early", early), ("middle", mid), ("late", late)):
        if not group:
            periods[name] = {"tournament_count": 0}
            continue
        periods[name] = {
            "tournament_count": len(group),
            "start_date_range": (group[0].target_start_date, group[-1].target_start_date),
            "mean_log_loss": statistics.mean(log_loss(p) for p in group),
            "mean_brier_norm": statistics.mean(brier_norm(p) for p in group),
        }
    return {"periods": periods}


# ----------------------------------------------------------------
# Rookie / sparse-history audit (Section 9 of this stage's
# instructions; Section 7 of the frozen spec).
# ----------------------------------------------------------------

ROOKIE_SLICES: tuple[tuple[str, int, Optional[int]], ...] = (
    ("cold_0", 0, 0),
    ("very_sparse_1_4", 1, 4),
    ("sparse_5_9", 5, 9),
    ("moderate_10_19", 10, 19),
    ("established_20plus", 20, None),
)


def _slice_for_n(n: int) -> str:
    for name, lo, hi in ROOKIE_SLICES:
        if n >= lo and (hi is None or n <= hi):
            return name
    raise ValueError(f"prior_events_n={n} did not match any rookie slice")


def rookie_slice_report(predictions: list[TournamentPrediction]) -> dict:
    """Per Section 7 of the frozen spec / Section 9 of this stage: row
    count, actual winner count, assigned-probability distribution, and
    slice-restricted log loss for each prior_events_n slice. Never
    drops a slice for having few observations — reports the count and
    moves on."""
    slices: dict[str, dict] = {
        name: {"row_count": 0, "sum_prob": 0.0, "min_prob": None, "max_prob": None,
               "winner_row_count": 0, "winner_tournament_log_losses": []}
        for name, _, _ in ROOKIE_SLICES
    }

    for pred in predictions:
        for player, prob in pred.probabilities.items():
            n = pred.prior_events_n_by_player.get(player)
            if n is None:
                continue
            s = slices[_slice_for_n(n)]
            s["row_count"] += 1
            s["sum_prob"] += prob
            s["min_prob"] = prob if s["min_prob"] is None else min(s["min_prob"], prob)
            s["max_prob"] = prob if s["max_prob"] is None else max(s["max_prob"], prob)
            if player == pred.winner:
                s["winner_row_count"] += 1

        winner_n = pred.prior_events_n_by_player.get(pred.winner)
        if winner_n is not None:
            slices[_slice_for_n(winner_n)]["winner_tournament_log_losses"].append(log_loss(pred))

    report = {}
    for name, _, _ in ROOKIE_SLICES:
        s = slices[name]
        report[name] = {
            "row_count": s["row_count"],
            "mean_assigned_probability": (s["sum_prob"] / s["row_count"]) if s["row_count"] else None,
            "min_probability": s["min_prob"],
            "max_probability": s["max_prob"],
            "winner_row_count": s["winner_row_count"],
            "tournaments_won_from_this_slice": len(s["winner_tournament_log_losses"]),
            "mean_log_loss_when_winner_in_slice": (
                statistics.mean(s["winner_tournament_log_losses"]) if s["winner_tournament_log_losses"] else None
            ),
        }
    return report
