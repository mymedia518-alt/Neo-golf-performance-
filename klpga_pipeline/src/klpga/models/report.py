"""Formats the M0-M6 comparison output — the leaderboard table, paired
comparisons, time-stability, and rookie-slice sections — exactly the
report shape requested for this stage
(`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` and this session's
implementation instructions). Pure formatting: every number here comes
from `klpga.models.metrics`/`walk_forward_eval`, nothing is computed
fresh in this module.
"""
from __future__ import annotations

from klpga.models.candidates import MODEL_DESCRIPTIONS, MODEL_FEATURES
from klpga.models.metrics import (
    ModelMetricsSummary,
    calibration_report,
    log_loss,
    paired_comparison,
    summarize_model,
)
from klpga.models.walk_forward_eval import (
    MultiModelEvaluationResult,
    rookie_slice_report,
    time_stability_report,
)


def format_leaderboard(result: MultiModelEvaluationResult) -> str:
    summaries: dict[str, ModelMetricsSummary] = {
        mid: summarize_model(mid, result.predictions_by_model[mid]) for mid in result.model_ids
    }
    m0 = summaries.get("M0")

    header = (
        f"{'Model':<6}{'Features':<45}{'N':>5}{'LogLoss':>10}{'ΔvsM0':>10}"
        f"{'Brier':>9}{'ΔvsM0':>9}{'MedRank':>9}{'Top3':>7}{'Top5':>7}{'Top10':>7}"
    )
    lines = [header, "-" * len(header)]
    for mid in result.model_ids:
        s = summaries[mid]
        features = ", ".join(MODEL_FEATURES[mid]) or "(none)"
        d_ll = s.mean_log_loss - m0.mean_log_loss if m0 else float("nan")
        d_brier = s.mean_brier_norm - m0.mean_brier_norm if m0 else float("nan")
        lines.append(
            f"{mid:<6}{features:<45}{s.tournament_count:>5}{s.mean_log_loss:>10.4f}{d_ll:>+10.4f}"
            f"{s.mean_brier_norm:>9.4f}{d_brier:>+9.4f}{s.median_winner_rank:>9.1f}"
            f"{s.top3_rate*100:>6.1f}%{s.top5_rate*100:>6.1f}%{s.top10_rate*100:>6.1f}%"
        )
    lines.append(
        "\nNo model is declared the winner from this table alone — see the paired comparisons, "
        "time-stability, and rookie-slice sections below (spec Section 11: a smaller number in one "
        "column is not, by itself, a promotion)."
    )
    return "\n".join(lines)


def format_paired_comparisons(result: MultiModelEvaluationResult, baseline_model_id: str = "M1") -> str:
    lines = [
        f"Paired tournament-level Wilcoxon signed-rank test on log loss "
        f"(negative mean/median diff = candidate improved on the comparator):"
    ]
    m0_preds = result.predictions_by_model.get("M0")
    baseline_preds = result.predictions_by_model.get(baseline_model_id)

    for mid in result.model_ids:
        if mid == "M0":
            continue
        preds = result.predictions_by_model[mid]
        row = f"  {mid} vs M0 (uniform):"
        if m0_preds:
            cmp = paired_comparison(preds, m0_preds, metric_fn=log_loss)
            row += (
                f" n={cmp['n']:>3} mean_diff={cmp['mean_diff']:+.4f} "
                f"median_diff={cmp['median_diff']:+.4f} z={cmp['z']:+.3f} p={cmp['p_value']:.4f}"
            )
        lines.append(row)

        if mid != baseline_model_id and baseline_preds:
            cmp_b = paired_comparison(preds, baseline_preds, metric_fn=log_loss)
            lines.append(
                f"  {mid} vs {baseline_model_id} (baseline 1):"
                f" n={cmp_b['n']:>3} mean_diff={cmp_b['mean_diff']:+.4f} "
                f"median_diff={cmp_b['median_diff']:+.4f} z={cmp_b['z']:+.3f} p={cmp_b['p_value']:.4f}"
            )
    lines.append(
        "\nSignificance alone (p < 0.05, two-sided) is Section 11's PRIMARY gate — it is necessary, "
        "not sufficient, for promotion. See docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md Section 11 "
        "for the full criteria (Brier consistency, calibration, stability, threshold sensitivity, "
        "sparse-player behavior, complexity tie-break)."
    )
    return "\n".join(lines)


def format_time_stability(result: MultiModelEvaluationResult) -> str:
    lines = ["Time-stability (early/middle/late thirds by target date):"]
    for mid in result.model_ids:
        ts = time_stability_report(result.predictions_by_model[mid])
        if not ts["periods"]:
            lines.append(f"  {mid}: {ts.get('note')}")
            continue
        parts = []
        for period_name in ("early", "middle", "late"):
            p = ts["periods"].get(period_name, {})
            if p.get("tournament_count"):
                parts.append(f"{period_name}(n={p['tournament_count']}) LL={p['mean_log_loss']:.3f}")
            else:
                parts.append(f"{period_name}(n=0)")
        lines.append(f"  {mid}: " + "  ".join(parts))
    return "\n".join(lines)


def format_rookie_audit(result: MultiModelEvaluationResult) -> str:
    lines = ["Rookie / sparse-history audit (prior_events_n slices):"]
    for mid in result.model_ids:
        lines.append(f"  {mid}:")
        report = rookie_slice_report(result.predictions_by_model[mid])
        for slice_name, s in report.items():
            if s["row_count"] == 0:
                lines.append(f"    {slice_name:<20} n=0 rows")
                continue
            mean_p = s["mean_assigned_probability"]
            lines.append(
                f"    {slice_name:<20} rows={s['row_count']:>5} mean_p={mean_p:.4f} "
                f"range=[{s['min_probability']:.2e}, {s['max_probability']:.2e}] "
                f"won={s['tournaments_won_from_this_slice']}"
            )
    return "\n".join(lines)


def format_calibration(result: MultiModelEvaluationResult) -> str:
    lines = [
        "Calibration (coarse bins, tournament-level bootstrap 90% CI — "
        "see docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md Section 3C for why bins are this coarse):"
    ]
    for mid in result.model_ids:
        preds = result.predictions_by_model[mid]
        lines.append(f"  {mid}:")
        bins = calibration_report(preds)
        for b in bins:
            if b.row_count == 0:
                lines.append(f"    [{b.lo:.2f},{b.hi:.2f}) rows=0")
                continue
            exp_ci = f"[{b.expected_wins_ci[0]:.2f},{b.expected_wins_ci[1]:.2f}]" if b.expected_wins_ci else "n/a"
            act_ci = f"[{b.actual_wins_ci[0]:.1f},{b.actual_wins_ci[1]:.1f}]" if b.actual_wins_ci else "n/a"
            lines.append(
                f"    [{b.lo:.2f},{b.hi:.2f}) rows={b.row_count:>5} "
                f"expected_wins={b.expected_wins:.2f} (CI {exp_ci})  "
                f"actual_wins={b.actual_wins:>3} (CI {act_ci})  "
                f"contributing_tournaments={b.contributing_tournament_count}"
            )
    return "\n".join(lines)


def format_full_report(result: MultiModelEvaluationResult, baseline_model_id: str = "M1") -> str:
    sections = [
        f"THRESHOLD = {result.threshold}",
        f"Usable tournaments in corpus: {result.total_usable_tournaments}",
        f"Eligible target tournaments (>= {result.threshold} prior usable tournaments): "
        f"{result.eligible_tournament_count}",
        f"Skipped (no resolvable date): {len(result.skipped_no_date_event_ids)}",
        f"Skipped (empty field): {len(result.skipped_empty_field_event_ids)}",
        f"Skipped (ambiguous/missing winner): {len(result.skipped_ambiguous_winner)} "
        f"{result.skipped_ambiguous_winner if result.skipped_ambiguous_winner else ''}",
        "",
        format_leaderboard(result),
        "",
        format_paired_comparisons(result, baseline_model_id=baseline_model_id),
        "",
        format_calibration(result),
        "",
        format_time_stability(result),
        "",
        format_rookie_audit(result),
    ]
    return "\n".join(sections)
