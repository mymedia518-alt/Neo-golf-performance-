"""BETA #001-C Phase 9 — generates the corrected PRE-tournament
prediction. Runs Phase 7's backtest (klpga.neo_win.backtest_eval) to
select the best-supported model (Phase 8's evidence-only complexity
tie-break), fits that model on strictly-prior training data, predicts
the live field, validates, and freezes an IMMUTABLE snapshot at
prediction_id=001-C — NEVER prediction_id=001 (klpga.neo_win.
beta001c_archive is a separate archive from both klpga.archive.
prediction_archive and klpga.neo_win.archive; no code path here can
touch either).

Read-only (DB opened `mode=ro`). Writes outputs/beta001_c/
BETA001C_WIN_FULL.csv, BETA001C_WIN_TOP20.csv, BETA001C_MODEL_REPORT.md
every run; --freeze additionally writes the immutable snapshot plus a
convenience copy at BETA001C_FREEZE.json.

Usage:
    python scripts/38_predict_beta001c.py --db data/klpga.sqlite \\
        --game-code 2026080001 --cutoff-date 2026-08-27 --freeze --prediction-id 001-C
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.backtest_eval import (  # noqa: E402
    NeoWinModelSpec,
    run_neo_win_multi_model_walk_forward,
    select_best_beta001c_model,
)
from klpga.neo_win.beta001c_archive import (  # noqa: E402
    NeoWinCAlreadyArchivedError,
    NeoWinCEntrantSnapshot,
    NeoWinCPredictionSnapshot,
    RECORD_KIND,
    snapshot_to_dict,
    write_neo_win_c_snapshot_atomic,
)
from klpga.neo_win.beta001c_dataset import (  # noqa: E402
    MODEL_A_FEATURES,
    MODEL_B_FEATURES,
    MODEL_C_FEATURES,
    build_beta001c_live_field,
    build_beta001c_live_training_rows,
)
from klpga.neo_win.model import fit_neo_win_model, predict_neo_win_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_ROOT = ROOT / "neo_win_c_predictions"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001_c"
DEFAULT_TAXONOMY_PATH = ROOT / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
DEFAULT_RAW_SAMPLES_DIR = ROOT / "docs" / "discovery" / "raw_samples"

FEATURES_BY_MODEL_ID = {"MODEL_A": MODEL_A_FEATURES, "MODEL_B": MODEL_B_FEATURES, "MODEL_C": MODEL_C_FEATURES}
BACKTEST_MODEL_SPECS = tuple(NeoWinModelSpec(mid, feats) for mid, feats in FEATURES_BY_MODEL_ID.items())

_KNOWN_LIMITATIONS: tuple[str, ...] = (
    "BETA #001-C: domain-aggregate official-metric features and win-feature candidates are the plain mean/"
    "count of whichever underlying metrics cleared MIN_PLAYER_COVERAGE that prior season — a genuinely thin "
    "prior season leaves some or all of these None for many players, shrunk to the training-fold mean rather "
    "than fabricated.",
    "The selected model (MODEL_A/B/C) is decided fresh, in this same run, by Phase 7/8's evidence-only "
    "backtest — never hand-picked, never re-run after inspecting this prediction's own player-level numbers.",
    "Every official-metric domain feature uses the PRIOR completed season only (leakage-safe against official_"
    "metric_value's season-level, not point-in-time, granularity) — identical convention to BETA #001.",
)


def print_report(field_size, entrants_predicted, decision, sum_prob, min_prob, max_prob, dup, null, non_field,
                  ranked, training_tournament_count) -> None:
    print("=== NEO GOLF BETA #001-C ===")
    print()
    print(f"Field: {field_size}  Predicted: {entrants_predicted}")
    print(f"Historical tournaments used: {training_tournament_count}")
    print(f"Selected model: {decision['selected_model_id']}")
    for r in decision["reasoning"]:
        print(f"  - {r}")
    print()
    print("=== TOP 10 WIN % ===")
    print()
    for rank, player_code, player_name, prob in ranked[:10]:
        print(f"{rank}. {player_name} ({player_code}) — {prob * 100:.3f}%")
    print()
    print("=== BETA #001-C VALIDATION ===")
    print()
    print(f"Sum: {sum_prob * 100:.4f}%")
    print(f"Min: {min_prob * 100:.6f}%  Max: {max_prob * 100:.4f}%")
    print(f"Duplicates: {dup}")
    print(f"Nulls: {null}")
    print(f"Non-field players: {non_field}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--cutoff-date", required=True)
    parser.add_argument("--tournament-name", default=None)
    parser.add_argument("--threshold", type=int, default=10, help="Backtest eligibility threshold (Phase 7/8).")
    parser.add_argument("--taxonomy-path", default=str(DEFAULT_TAXONOMY_PATH))
    parser.add_argument("--raw-samples-dir", default=str(DEFAULT_RAW_SAMPLES_DIR))
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--prediction-id", default=None, help="Required with --freeze, e.g. '001-C'. Never '001'.")
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    if args.freeze and not args.prediction_id:
        print("ERROR: --freeze requires --prediction-id")
        return 2
    if args.prediction_id == "001":
        print("ERROR: prediction_id '001' is reserved for the frozen BETA #001 PRE snapshot — never reuse it here.")
        return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3
    taxonomy_path = Path(args.taxonomy_path)
    if not taxonomy_path.exists():
        print(f"ERROR: {taxonomy_path} does not exist.")
        return 3
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    raw_samples_dir = Path(args.raw_samples_dir)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        backtest_result = run_neo_win_multi_model_walk_forward(
            conn, BACKTEST_MODEL_SPECS, args.threshold, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir
        )
        decision = select_best_beta001c_model(backtest_result)
        feature_columns = FEATURES_BY_MODEL_ID[decision["selected_model_id"]]

        cutoff_date_obj = datetime.strptime(args.cutoff_date, "%Y-%m-%d").date()
        training_rows, training_tournament_count = build_beta001c_live_training_rows(
            conn, args.game_code, cutoff_date_obj, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir
        )
        live_field = build_beta001c_live_field(
            conn, args.game_code, cutoff_date_obj, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir
        )
        tournament_row = conn.execute(
            "SELECT event_name FROM tournament_master WHERE game_code = ?", (args.game_code,)
        ).fetchone()
        tournament_name = args.tournament_name or (tournament_row[0] if tournament_row else None)
    finally:
        conn.close()

    fitted = fit_neo_win_model(training_rows, feature_columns=feature_columns)
    field_rows = live_field["field_rows"]
    probabilities = predict_neo_win_model(fitted, field_rows)

    field_codes = {row["player_code"] for row in field_rows}
    codes = list(probabilities.keys())
    sum_prob = sum(probabilities.values())
    min_prob = min(probabilities.values()) if probabilities else 0.0
    max_prob = max(probabilities.values()) if probabilities else 0.0
    duplicate_count = len(codes) - len(set(codes))
    null_count = sum(1 for v in probabilities.values() if v is None)
    non_field_count = len(set(codes) - field_codes)

    row_by_code = {row["player_code"]: row for row in field_rows}
    ranked = sorted(
        ((row_by_code[code]["player_name"], code, prob) for code, prob in probabilities.items()),
        key=lambda t: -t[2],
    )
    ranked = [(i + 1, code, name, prob) for i, (name, code, prob) in enumerate(ranked)]
    ranked_for_print = [(r, code, name, prob) for r, code, name, prob in ranked]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = ["rank", "player_code", "player_name", "win_probability_pct", "prior_events_n"] + list(feature_columns)

    def _csv_row(rank, code, name, prob) -> dict:
        row = row_by_code[code]
        out = {
            "rank": rank, "player_code": code, "player_name": name,
            "win_probability_pct": round(prob * 100, 6),
            "prior_events_n": row.get("prior_events_n", 0),
        }
        for f in feature_columns:
            v = row.get(f)
            out[f] = "" if v is None else v
        return out

    full_path = output_dir / "BETA001C_WIN_FULL.csv"
    top20_path = output_dir / "BETA001C_WIN_TOP20.csv"
    for path, entries in ((full_path, ranked), (top20_path, ranked[:20])):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rank, code, name, prob in entries:
                writer.writerow(_csv_row(rank, code, name, prob))

    report_path = output_dir / "BETA001C_MODEL_REPORT.md"
    report_lines = [
        "# NEO GOLF BETA #001-C — Model Report",
        "",
        f"- Tournament: {tournament_name} (`{args.game_code}`)",
        f"- Cutoff: {args.cutoff_date}",
        f"- Field size: {len(field_rows)}  Predicted: {len(probabilities)}",
        f"- Historical training tournaments: {training_tournament_count}",
        f"- Selected model (Phase 7/8 backtest): {decision['selected_model_id']}",
        f"- Model feature list: `{list(feature_columns)}`",
        "",
        "## Selection reasoning",
        "",
    ] + [f"- {r}" for r in decision["reasoning"]] + [
        "",
        "## Validation",
        "",
        f"- Sum: {sum_prob!r}",
        f"- Min: {min_prob!r}  Max: {max_prob!r}",
        f"- Duplicates: {duplicate_count}",
        f"- Nulls: {null_count}",
        f"- Non-field players: {non_field_count}",
        "",
        "## Known limitations",
        "",
    ] + [f"- {lim}" for lim in _KNOWN_LIMITATIONS]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print_report(
        len(field_rows), len(probabilities), decision, sum_prob, min_prob, max_prob,
        duplicate_count, null_count, non_field_count, ranked_for_print, training_tournament_count,
    )
    print()
    print(f"Wrote: {full_path}")
    print(f"Wrote: {top20_path}")
    print(f"Wrote: {report_path}")

    print()
    print("=== FREEZE ===")
    print()
    freeze_status = "NOT FROZEN (pass --freeze --prediction-id <id> to freeze)"
    freeze_output_path = "—"
    if args.freeze:
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entrants = tuple(
            NeoWinCEntrantSnapshot(
                rank=rank, player_code=code, player_name=name, win_probability=prob,
                prior_events_n=row_by_code[code].get("prior_events_n", 0),
                feature_values={f: row_by_code[code].get(f) for f in feature_columns},
                player_master_matched=row_by_code[code].get("in_player_master", True),
            )
            for rank, code, name, prob in ranked
        )
        snapshot = NeoWinCPredictionSnapshot(
            prediction_id=args.prediction_id,
            created_at_utc=created_at_utc,
            record_kind=RECORD_KIND,
            game_code=args.game_code,
            tournament_name=tournament_name,
            cutoff_date=args.cutoff_date,
            cutoff_source="explicit_arg",
            selected_model_id=decision["selected_model_id"],
            model_features=feature_columns,
            selection_decision=decision,
            training_tournament_count=training_tournament_count,
            field_size=len(field_rows),
            entrants_predicted=len(probabilities),
            probability_sum=sum_prob,
            minimum_probability=min_prob,
            maximum_probability=max_prob,
            duplicate_count=duplicate_count,
            null_count=null_count,
            non_field_count=non_field_count,
            known_limitations=_KNOWN_LIMITATIONS,
            predictions=entrants,
        )
        try:
            json_path, csv_path = write_neo_win_c_snapshot_atomic(snapshot, Path(args.predictions_dir))
        except NeoWinCAlreadyArchivedError as exc:
            print(f"prediction_id: {args.prediction_id}")
            print(f"status: ERROR — {exc}")
            return 4
        freeze_copy_path = output_dir / "BETA001C_FREEZE.json"
        freeze_copy_path.write_text(
            json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        freeze_status = "FROZEN"
        freeze_output_path = f"{json_path} / {csv_path} (+ convenience copy {freeze_copy_path})"

    print(f"prediction_id: {args.prediction_id or '—'}")
    print(f"cutoff: {args.cutoff_date}")
    print(f"output path: {freeze_output_path}")
    print(f"status: {freeze_status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
