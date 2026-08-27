"""BETA #001-C Phase 7 — a NEW, standalone walk-forward backtest
evaluator for `klpga.neo_win.model`-style models (the `fit_neo_win_
model(training_rows, feature_columns=...)` / `predict_neo_win_model`
signature).

Deliberately reuses:
  - `klpga.backtest.walk_forward.build_walk_forward_dataset` for target/
    training-row discovery (identical eligible-target and strictly-
    prior-training-set logic every model in this project already
    trusts) — never re-derived.
  - `klpga.models.metrics`'s fully generic primitives (TournamentPrediction,
    make_prediction, log_loss, brier_norm, summarize_model, calibration_
    report, paired_comparison) — these operate on plain
    {player_code: probability} dicts + a winner string, with zero
    dependency on which model produced them, so they need no changes
    to serve a second model family.

Deliberately does NOT reuse `klpga.models.walk_forward_eval.run_multi_
model_walk_forward` — that orchestrator is hard-coded to `klpga.models.
candidates.fit_candidate_model`/`predict_candidate_model`'s different
signature (model_id string dispatch into the frozen M0-M6 ladder), and
this module never touches or duplicates that frozen file. The walk-
forward LOOP STRUCTURE below is intentionally the same shape (fit on
strictly-prior USABLE tournaments, evaluate ELIGIBLE-AT-THRESHOLD
targets, skip ambiguous/missing winners) because that loop logic is
correct and belongs to no single model family — but it is written fresh
here against `klpga.neo_win.model`'s own fit/predict signature.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from klpga.backtest.point_in_time_features import load_corpus
from klpga.backtest.walk_forward import build_walk_forward_dataset
from klpga.models.metrics import TournamentPrediction, log_loss, make_prediction, paired_comparison
from klpga.neo_win.beta001c_dataset import augment_rows_with_beta001c_features
from klpga.neo_win.model import fit_neo_win_model, predict_neo_win_model

DEFAULT_PROMOTION_ALPHA = 0.05
"""Pre-registered two-sided significance threshold, matching the same
gate `docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` Section 11 uses
for the frozen M0-M6 ladder's own promotion decision — never tuned
after seeing this run's actual p-values."""


@dataclass(frozen=True)
class NeoWinModelSpec:
    model_id: str
    feature_columns: tuple[str, ...]


@dataclass(frozen=True)
class NeoWinBacktestResult:
    threshold: int
    model_ids: tuple[str, ...]
    predictions_by_model: dict[str, list[TournamentPrediction]]
    total_usable_tournaments: int
    eligible_tournament_count: int
    skipped_ambiguous_winner: list = field(default_factory=list)


def _group_rows_by_target(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["target_event_id"], []).append(row)
    return grouped


def run_neo_win_multi_model_walk_forward(
    conn: sqlite3.Connection,
    model_specs: tuple[NeoWinModelSpec, ...],
    threshold: int,
    *,
    taxonomy: dict,
    raw_samples_dir,
) -> NeoWinBacktestResult:
    """Fits and predicts every spec in `model_specs` across every
    eligible target at `threshold`, sharing the per-target training/
    target row lookup across models (each model still fits separately,
    since each spec's feature_columns differ)."""
    corpus = load_corpus(conn)
    dataset = build_walk_forward_dataset(conn, corpus=corpus)
    augmented_rows = augment_rows_with_beta001c_features(
        conn, dataset.rows, corpus, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir
    )
    rows_by_target = _group_rows_by_target(augmented_rows)
    eligible_targets = [t for t in dataset.target_order if t.prior_tournament_count >= threshold]

    predictions_by_model: dict[str, list[TournamentPrediction]] = {spec.model_id: [] for spec in model_specs}
    skipped_ambiguous: list = []

    for target in eligible_targets:
        target_rows = rows_by_target.get(target.event_id, [])
        winners = [r["player_code"] for r in target_rows if r.get("label_is_winner")]
        if len(winners) != 1:
            skipped_ambiguous.append((target.event_id, len(winners)))
            continue
        winner = winners[0]
        prior_n_by_player = {r["player_code"]: r.get("prior_events_n", 0) for r in target_rows}

        training_rows: list[dict] = []
        for other in dataset.target_order:
            if other.effective_date < target.effective_date:
                training_rows.extend(rows_by_target.get(other.event_id, []))

        for spec in model_specs:
            fitted = fit_neo_win_model(training_rows, feature_columns=spec.feature_columns)
            raw_probs = predict_neo_win_model(fitted, target_rows)
            pred = make_prediction(
                target.event_id, target.game_code, target.effective_date.isoformat(),
                raw_probs, winner, prior_n_by_player,
            )
            predictions_by_model[spec.model_id].append(pred)

    return NeoWinBacktestResult(
        threshold=threshold,
        model_ids=tuple(spec.model_id for spec in model_specs),
        predictions_by_model=predictions_by_model,
        total_usable_tournaments=len(dataset.target_order),
        eligible_tournament_count=len(eligible_targets),
        skipped_ambiguous_winner=skipped_ambiguous,
    )


def _significant_improvement(comparison: dict, alpha: float) -> bool:
    """True only if the paired Wilcoxon test rejects the null AND the
    direction favors the first (more complex) model — mirrors spec
    Section 11 gate 1 exactly: statistical significance in the
    improving direction, never a bare "the number moved" check."""
    p_value = comparison.get("p_value")
    mean_diff = comparison.get("mean_diff")
    return p_value is not None and mean_diff is not None and p_value < alpha and mean_diff < 0


def select_best_beta001c_model(result: NeoWinBacktestResult, *, alpha: float = DEFAULT_PROMOTION_ALPHA) -> dict:
    """Phase 8 — BETA #001-C's model selection, evidence-only: applies
    the SAME sequential complexity tie-break `docs/WIN_PROBABILITY_
    MODEL_EVALUATION_SPEC.md` Section 11 gate 7 already established for
    the frozen M0-M6 ladder ("if two candidates are NOT statistically
    distinguishable [on paired log loss], the SIMPLER model is
    preferred"), applied here sequentially A -> B -> C: MODEL_A is the
    default; MODEL_B is only selected if it significantly beats
    MODEL_A on paired per-tournament log loss (Wilcoxon, two-sided,
    pre-registered alpha); MODEL_C is only THEN considered, and only
    selected if it significantly beats the already-selected MODEL_B.
    If MODEL_B does not beat MODEL_A, MODEL_C is never evaluated
    further — the release's own instruction: "If MODEL C... does NOT
    outperform MODEL B, do not include explicit wins." This function
    contains the ENTIRE selection decision — no number in its output
    is eyeballed or hand-picked after the fact."""
    b_vs_a = paired_comparison(result.predictions_by_model["MODEL_B"], result.predictions_by_model["MODEL_A"], log_loss)
    selected = "MODEL_A"
    reasoning = [
        "MODEL_A is the default per the complexity tie-break (spec Section 11 gate 7): "
        "a more complex model is promoted only on significant paired-log-loss evidence."
    ]
    comparisons = {"MODEL_B_vs_MODEL_A": b_vs_a}

    if _significant_improvement(b_vs_a, alpha):
        selected = "MODEL_B"
        reasoning.append(
            f"MODEL_B significantly improves log loss over MODEL_A (paired Wilcoxon p={b_vs_a['p_value']:.4f} "
            f"< alpha={alpha}, mean_diff={b_vs_a['mean_diff']:.4f}, n={b_vs_a['n']})."
        )
        c_vs_b = paired_comparison(result.predictions_by_model["MODEL_C"], result.predictions_by_model["MODEL_B"], log_loss)
        comparisons["MODEL_C_vs_MODEL_B"] = c_vs_b
        if _significant_improvement(c_vs_b, alpha):
            selected = "MODEL_C"
            reasoning.append(
                f"MODEL_C significantly improves log loss over MODEL_B (paired Wilcoxon p={c_vs_b['p_value']:.4f} "
                f"< alpha={alpha}, mean_diff={c_vs_b['mean_diff']:.4f}, n={c_vs_b['n']})."
            )
        else:
            reasoning.append(
                f"MODEL_C does NOT significantly improve log loss over MODEL_B "
                f"(p={c_vs_b.get('p_value')}, mean_diff={c_vs_b.get('mean_diff')}) — win features excluded, "
                "per the release's explicit instruction."
            )
    else:
        reasoning.append(
            f"MODEL_B does NOT significantly improve log loss over MODEL_A "
            f"(p={b_vs_a.get('p_value')}, mean_diff={b_vs_a.get('mean_diff')}) — staying with MODEL_A. "
            "MODEL_C was not evaluated further (its base, MODEL_B, was already rejected)."
        )

    return {"selected_model_id": selected, "reasoning": reasoning, "comparisons": comparisons, "alpha": alpha}
