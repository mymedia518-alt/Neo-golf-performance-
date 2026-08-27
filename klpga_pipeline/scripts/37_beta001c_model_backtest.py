"""BETA #001-C Phase 7 — walk-forward backtest comparing MODEL A (base
NEO WIN v0.1 features only), MODEL B (A + validated official-metric
domain scores), and MODEL C (B + the 5 win-feature candidates), using
klpga.neo_win.backtest_eval (a NEW, standalone evaluator — never the
frozen M0-M6 klpga.models.walk_forward_eval).

Read-only (DB opened `mode=ro`). Writes outputs/beta001_c/
MODEL_BACKTEST.md and MODEL_BACKTEST.csv. Does NOT select a model or
generate a prediction — that is Phase 8/9 (scripts/38), which reads
this backtest's own output rather than re-deciding anything here.

Usage:
    python scripts/37_beta001c_model_backtest.py --db data/klpga.sqlite --threshold 10
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.models.metrics import calibration_report, log_loss, paired_comparison, summarize_model  # noqa: E402
from klpga.neo_win.backtest_eval import (  # noqa: E402
    NeoWinModelSpec,
    run_neo_win_multi_model_walk_forward,
    select_best_beta001c_model,
)
from klpga.neo_win.beta001c_dataset import MODEL_A_FEATURES, MODEL_B_FEATURES, MODEL_C_FEATURES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001_c"
DEFAULT_TAXONOMY_PATH = ROOT / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
DEFAULT_RAW_SAMPLES_DIR = ROOT / "docs" / "discovery" / "raw_samples"

MODEL_SPECS = (
    NeoWinModelSpec("MODEL_A", MODEL_A_FEATURES),
    NeoWinModelSpec("MODEL_B", MODEL_B_FEATURES),
    NeoWinModelSpec("MODEL_C", MODEL_C_FEATURES),
)


def _write_report(result, output_path: Path) -> dict:
    summaries = {mid: summarize_model(mid, result.predictions_by_model[mid]) for mid in result.model_ids}
    calibrations = {mid: calibration_report(result.predictions_by_model[mid]) for mid in result.model_ids}
    pairs = {
        "MODEL_B_vs_MODEL_A": paired_comparison(
            result.predictions_by_model["MODEL_B"], result.predictions_by_model["MODEL_A"], log_loss
        ),
        "MODEL_C_vs_MODEL_B": paired_comparison(
            result.predictions_by_model["MODEL_C"], result.predictions_by_model["MODEL_B"], log_loss
        ),
    }

    lines = [
        "# BETA #001-C — Phase 7 Model Backtest (MODEL A vs B vs C)",
        "",
        f"- Threshold (min prior usable tournaments): {result.threshold}",
        f"- Total usable tournaments in corpus: {result.total_usable_tournaments}",
        f"- Eligible (evaluated) tournaments: {result.eligible_tournament_count}",
        f"- Skipped (ambiguous/missing winner): {len(result.skipped_ambiguous_winner)} "
        f"{result.skipped_ambiguous_winner if result.skipped_ambiguous_winner else ''}",
        "",
        "## Feature sets",
        "",
        f"- MODEL_A: `{list(MODEL_A_FEATURES)}`",
        f"- MODEL_B: `{list(MODEL_B_FEATURES)}`",
        f"- MODEL_C: `{list(MODEL_C_FEATURES)}`",
        "",
        "## Leaderboard",
        "",
        f"{'Model':<10}{'N':>5}{'LogLoss':>10}{'Brier':>9}{'MedRank':>9}{'Top3':>8}{'Top5':>8}{'Top10':>8}",
    ]
    for mid in result.model_ids:
        s = summaries[mid]
        lines.append(
            f"{mid:<10}{s.tournament_count:>5}{s.mean_log_loss:>10.4f}{s.mean_brier_norm:>9.4f}"
            f"{s.median_winner_rank:>9.1f}{s.top3_rate*100:>7.1f}%{s.top5_rate*100:>7.1f}%{s.top10_rate*100:>7.1f}%"
        )

    lines += ["", "No model is declared the winner from this table alone — see paired comparison below."]

    lines += ["", "## Paired comparison (Wilcoxon signed-rank on per-tournament log-loss difference)", ""]
    for name, res in pairs.items():
        lines.append(f"- {name}: {json.dumps(res, default=str)}")

    lines += ["", "## Calibration (coarse bins, tournament-level bootstrap CI)", ""]
    for mid in result.model_ids:
        lines.append(f"### {mid}")
        for cb in calibrations[mid]:
            lines.append(
                f"  [{cb.lo:.2f}, {cb.hi:.2f}) rows={cb.row_count} expected={cb.expected_wins:.2f} "
                f"actual={cb.actual_wins} tournaments={cb.contributing_tournament_count}"
            )
        lines.append("")

    decision = select_best_beta001c_model(result)
    lines += [
        "## Phase 8 — Model Selection Decision",
        "",
        f"Selected: **{decision['selected_model_id']}**  (pre-registered alpha={decision['alpha']})",
        "",
    ] + [f"- {r}" for r in decision["reasoning"]] + [
        "",
        "Training window: every USABLE historical tournament strictly before each evaluated target "
        "(walk-forward, klpga.backtest.walk_forward.build_walk_forward_dataset). "
        f"Validation window: the {result.eligible_tournament_count} eligible (threshold={result.threshold}) "
        "target tournaments evaluated above, one held-out prediction per target, never re-used as training data "
        "for that same target.",
        f"Sample coverage: {result.total_usable_tournaments} usable tournaments total, "
        f"{result.eligible_tournament_count} eligible/evaluated, "
        f"{len(result.skipped_ambiguous_winner)} skipped (ambiguous/missing winner).",
        "Limitation: this backtest's numbers reflect whatever data was in the DB at run time — a small or "
        "young corpus can leave every paired comparison statistically indistinguishable (p >= alpha), in which "
        "case MODEL_A is correctly selected by the tie-break, not because more features are known to be worse.",
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"summaries": summaries, "pairs": pairs, "decision": decision}


def _write_csv(result, output_path: Path) -> None:
    summaries = {mid: summarize_model(mid, result.predictions_by_model[mid]) for mid in result.model_ids}
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["model_id", "tournament_count", "mean_log_loss", "mean_brier_norm", "median_winner_rank",
                          "top3_rate", "top5_rate", "top10_rate", "mean_reciprocal_rank"])
        for mid in result.model_ids:
            s = summaries[mid]
            writer.writerow([mid, s.tournament_count, s.mean_log_loss, s.mean_brier_norm, s.median_winner_rank,
                              s.top3_rate, s.top5_rate, s.top10_rate, s.mean_reciprocal_rank])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--threshold", type=int, default=10)
    parser.add_argument("--taxonomy-path", default=str(DEFAULT_TAXONOMY_PATH))
    parser.add_argument("--raw-samples-dir", default=str(DEFAULT_RAW_SAMPLES_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3
    taxonomy_path = Path(args.taxonomy_path)
    if not taxonomy_path.exists():
        print(f"ERROR: {taxonomy_path} does not exist.")
        return 3
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        result = run_neo_win_multi_model_walk_forward(
            conn, MODEL_SPECS, args.threshold, taxonomy=taxonomy, raw_samples_dir=Path(args.raw_samples_dir)
        )
    finally:
        conn.close()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "MODEL_BACKTEST.md"
    csv_path = output_dir / "MODEL_BACKTEST.csv"
    context = _write_report(result, md_path)
    _write_csv(result, csv_path)

    print("=== BETA #001-C — PHASE 7 MODEL BACKTEST ===")
    print()
    print(f"Eligible tournaments: {result.eligible_tournament_count} (threshold={args.threshold})")
    for mid in result.model_ids:
        s = context["summaries"][mid]
        print(f"{mid}: logloss={s.mean_log_loss:.4f} brier={s.mean_brier_norm:.4f} "
              f"top10={s.top10_rate*100:.1f}%")
    print()
    print(f"=== PHASE 8 SELECTED MODEL: {context['decision']['selected_model_id']} ===")
    for r in context["decision"]["reasoning"]:
        print(f"  - {r}")
    print()
    print(f"Wrote: {md_path}")
    print(f"Wrote: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
