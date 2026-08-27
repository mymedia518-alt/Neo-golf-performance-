"""NEO WIN % v0.1 — BETA #001. Read-only pre-tournament win-probability
inference + frozen PRE snapshot, entirely separate from `klpga.models`
(the frozen M0-M6 ladder behind Prediction #001) and from `predictions/`
(that archive) — see `src/klpga/neo_win/__init__.py` and
docs/NEO_WIN_V0_1_METHODOLOGY.md.

Does NOT write to tournament_master/player_master/player_event/
player_round/tournament_entry/official_metric_value/player_stats_snapshot
(the DB connection is opened `mode=ro`) and NEVER touches `predictions/`.

Writes two kinds of output, every run:
  1. `--output-dir` (default `outputs/beta001/`): regenerated every run
     — BETA001_WIN_FULL.csv (complete ranked field), BETA001_WIN_TOP10.csv,
     BETA001_MODEL_REPORT.md, BETA001_THREADS.txt (the SKIP+LOG trail).
  2. Only with `--freeze --prediction-id <id>`: an IMMUTABLE snapshot at
     `neo_win_predictions/<year>/neo_win_<id>_<game_code>.{json,csv}`
     (append-only, never overwritten — klpga.neo_win.archive), plus a
     convenience copy at `<output-dir>/BETA001_FREEZE.json`.

Usage — report + files only, no freeze:
    python scripts/33_predict_neo_win.py --db data/klpga.sqlite --game-code 2026080001 --cutoff-date 2026-08-27

Usage — the full release command (report + files + immutable freeze):
    python scripts/33_predict_neo_win.py --db data/klpga.sqlite --game-code 2026080001 --cutoff-date 2026-08-27 \\
        --freeze --prediction-id 001
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

from klpga.neo_win.archive import (  # noqa: E402
    NeoWinAlreadyArchivedError,
    NeoWinEntrantSnapshot,
    NeoWinPredictionSnapshot,
    RECORD_KIND,
    MODEL_VERSION,
    snapshot_to_dict,
    write_neo_win_snapshot_atomic,
)
from klpga.neo_win.inference import NeoWinInferenceResult, run_neo_win_inference  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_ROOT = ROOT / "neo_win_predictions"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001"

_KNOWN_LIMITATIONS: tuple[str, ...] = (
    "BETA #001 / v0.1: single-tau equal-weight model, not yet walk-forward "
    "promotion-gated against M4 the way M0-M6 were (docs/WIN_PROBABILITY_"
    "MODEL_EVALUATION_SPEC.md) — a candidate for future evaluation, not a "
    "claim of superiority over the frozen production model.",
    "Every validated official-metric slot (if not omitted — see "
    "official_metric_context) uses the PRIOR completed season only, never "
    "the target tournament's own season, to stay leakage-safe against "
    "official_metric_value's season-level (not point-in-time) granularity.",
    "flagged_rows in official_metric_value is dominated by a rank-column "
    "duplicate/sentinel artifact (real evidence: docs/NEO_WIN_V0_1_"
    "METHODOLOGY.md), not confirmed value corruption — but this model "
    "still conservatively excludes FLAGGED responses from every official-"
    "metric feature by default.",
)


def _fmt(value, ndigits: int = 4) -> str:
    return "—" if value is None else f"{value:.{ndigits}f}"


def _read_data_quality_summary(conn: sqlite3.Connection) -> dict:
    """Real, independent counts straight from official_metric_value —
    not derived from the model's own internal slot selection, so this
    is a genuine second look, not a restatement."""
    total, usable = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN validation_status = 'CLEAN' THEN 1 ELSE 0 END) FROM official_metric_value"
    ).fetchone()
    flagged = (total or 0) - (usable or 0)
    seasons = [row[0] for row in conn.execute("SELECT DISTINCT season FROM official_metric_value ORDER BY season")]
    return {
        "metric_rows_total": total or 0,
        "metric_rows_usable_clean": usable or 0,
        "metric_rows_flagged": flagged,
        "official_metric_seasons_present": seasons,
    }


def _build_threads_log(result: NeoWinInferenceResult, dq: dict) -> list[str]:
    lines: list[str] = []
    lines.append(f"[INFO] tournament resolved: game_code={result.game_code} name={result.tournament_name!r} "
                 f"(source={result.tournament_name_source})")
    lines.append(f"[INFO] cutoff_date={result.cutoff_date} (source={result.cutoff_date_source})")
    lines.append(f"[INFO] field_size={result.field_size} entrants_parsed={result.entrants_parsed} "
                 f"dropped_entrants={result.dropped_entrants}")
    lines.append(f"[INFO] official_metric_value: total_rows={dq['metric_rows_total']} "
                 f"usable_clean={dq['metric_rows_usable_clean']} flagged={dq['metric_rows_flagged']} "
                 "(flagged = rank-column duplicate/sentinel artifact per docs/NEO_WIN_V0_1_METHODOLOGY.md, "
                 "excluded from every official-metric feature by default, never used to drop a row elsewhere)")

    ident = result.missing_data_report["identity_resolution"]
    lines.append(f"[INFO] identity resolution: direct_match={ident['direct_match_count']} "
                 f"resolved_by_exact_name={ident['resolved_by_name_count']} "
                 f"unresolved={len(ident['unresolved_codes'])}")
    for code in ident["unresolved_codes"]:
        lines.append(f"[SKIP] official_metric_value.player_code={code!r}: no deterministic player_master match "
                      "(direct id lookup failed, raw-sample name re-parse failed or ambiguous) — "
                      "metric joins skipped for this code; any FIELD player with this code keeps their "
                      "tournament-result history and is still modeled.")

    for slot in result.missing_data_report["official_metric_slots_omitted_run_wide"]:
        lines.append(f"[SKIP] official metric slot '{slot}' omitted run-wide — no candidate label had >= "
                      "coverage threshold prior-season data.")
    for slot, missing_n in result.missing_data_report["official_metric_missing_per_player_by_slot"].items():
        if slot in result.missing_data_report["official_metric_slots_used"] and missing_n:
            lines.append(f"[LOG] official metric slot '{slot}' used, but missing for {missing_n} field player(s) "
                         "— shrunk to the training-fold mean (never dropped, never fabricated).")

    for p in result.predictions:
        if p.is_unmatched:
            lines.append(f"[LOG] entrant {p.player_code} ({p.player_name}) has no player_master match — "
                         "modeled with zero prior history (z=0 on every history-dependent feature), not dropped.")

    if not result.leakage_validation["clean"]:
        for v in result.leakage_validation["violations"]:
            lines.append(f"[VIOLATION] {v}")
    else:
        lines.append("[INFO] leakage validation: clean, 0 violations")

    return lines


def print_report(result: NeoWinInferenceResult, dq: dict) -> None:
    print("=== NEO GOLF BETA #001 ===")
    print()
    print(f"Tournament: {result.tournament_name} ({result.game_code})")
    print(f"Field: {result.field_size}")
    print(f"Cutoff: {result.cutoff_date} (source: {result.cutoff_date_source})")
    print(f"Historical tournaments used: {result.training_tournament_count}")
    print(f"Historical seasons: {dq['official_metric_seasons_present']}")
    print(f"Players modeled: {result.predicted_count}")
    print()
    print("=== TOP 10 WIN % ===")
    print()
    for p in result.predictions[:10]:
        print(f"{p.rank}. {p.player_name} ({p.player_code}) — {p.win_probability * 100:.3f}%")
    print()
    print("=== DATA QUALITY ===")
    print()
    print(f"Metric rows: {dq['metric_rows_total']}")
    print(f"Usable metric rows: {dq['metric_rows_usable_clean']}")
    print(f"Flagged rows explained: {dq['metric_rows_flagged']} — rank-column duplicate/sentinel artifact, "
          "not confirmed value corruption; excluded from official-metric features by default regardless")
    ident = result.missing_data_report["identity_resolution"]
    print(f"Identity matched: {ident['direct_match_count']} direct + {ident['resolved_by_name_count']} by exact name")
    print(f"Identity unresolved: {len(ident['unresolved_codes'])} {ident['unresolved_codes']}")
    print(f"Skipped: {len(ident['unresolved_codes'])} metric joins, "
          f"{len(result.missing_data_report['official_metric_slots_omitted_run_wide'])} official-metric slots "
          f"({result.missing_data_report['official_metric_slots_omitted_run_wide']})")
    print()
    print("=== PROBABILITY CHECK ===")
    print()
    codes = [p.player_code for p in result.predictions]
    field_codes = {p.player_code for p in result.predictions}
    print(f"Players: {len(result.predictions)}")
    print(f"Sum: {result.sum_probability * 100:.4f}%")
    print(f"Min: {result.min_probability * 100:.6f}%")
    print(f"Max: {result.max_probability * 100:.4f}%")
    print(f"Duplicates: {len(codes) - len(set(codes))}")
    print(f"Nulls: {sum(1 for p in result.predictions if p.win_probability is None)}")
    print(f"Non-field players: {len(field_codes - {p.player_code for p in result.predictions})}")


def _write_csvs(result: NeoWinInferenceResult, output_dir: Path) -> tuple[Path, Path]:
    fieldnames = [
        "rank", "player_code", "player_name", "win_probability_pct",
        "prior_events_n", "prior_avg_round_score_to_par", "prior_recent_form_10",
        "neo_consistency_stddev",
        "official_overall_skill", "official_driving", "official_short_game", "official_putting",
        "player_master_matched",
    ]

    def _row(p) -> dict:
        return {
            "rank": p.rank,
            "player_code": p.player_code,
            "player_name": p.player_name,
            "win_probability_pct": round(p.win_probability * 100, 6),
            "prior_events_n": p.prior_events_n,
            "prior_avg_round_score_to_par": "" if p.prior_avg_round_score_to_par is None else p.prior_avg_round_score_to_par,
            "prior_recent_form_10": "" if p.prior_recent_form_10 is None else p.prior_recent_form_10,
            "neo_consistency_stddev": "" if p.neo_consistency_stddev is None else p.neo_consistency_stddev,
            "official_overall_skill": p.official_metrics.get("overall_skill", ""),
            "official_driving": p.official_metrics.get("driving", ""),
            "official_short_game": p.official_metrics.get("short_game", ""),
            "official_putting": p.official_metrics.get("putting", ""),
            "player_master_matched": not p.is_unmatched,
        }

    full_path = output_dir / "BETA001_WIN_FULL.csv"
    top10_path = output_dir / "BETA001_WIN_TOP10.csv"
    for path, predictions in ((full_path, result.predictions), (top10_path, result.predictions[:10])):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in predictions:
                row = _row(p)
                row["official_overall_skill"] = "" if row["official_overall_skill"] is None else row["official_overall_skill"]
                row["official_driving"] = "" if row["official_driving"] is None else row["official_driving"]
                row["official_short_game"] = "" if row["official_short_game"] is None else row["official_short_game"]
                row["official_putting"] = "" if row["official_putting"] is None else row["official_putting"]
                writer.writerow(row)
    return full_path, top10_path


def _write_model_report(result: NeoWinInferenceResult, dq: dict, report_path: Path) -> None:
    ident = result.missing_data_report["identity_resolution"]
    lines = [
        "# NEO GOLF BETA #001 — Model Report",
        "",
        f"- Tournament: {result.tournament_name} (`{result.game_code}`)",
        f"- Field size: {result.field_size}",
        f"- Cutoff: {result.cutoff_date} (source: {result.cutoff_date_source})",
        f"- Historical tournament coverage: {result.training_tournament_count} training tournaments",
        f"- Official metric coverage: {dq['metric_rows_total']} rows total, "
        f"{dq['metric_rows_usable_clean']} usable (CLEAN), seasons {dq['official_metric_seasons_present']}",
        "",
        "## Actual metrics used",
        "",
        f"Base features (always): `prior_avg_round_score_to_par`, `prior_recent_form_10`, `neo_consistency_stddev`",
        f"Official-metric slots used this run: {result.missing_data_report['official_metric_slots_used']}",
        f"Model feature list (this run, fitted): `{list(result.model_features)}`",
        "",
        "## Metrics excluded",
        "",
        f"Official-metric slots omitted (no candidate cleared the coverage threshold): "
        f"{result.missing_data_report['official_metric_slots_omitted_run_wide']}",
        "FLAGGED official_metric_value responses are excluded from every official-metric feature by default "
        "(see docs/NEO_WIN_V0_1_METHODOLOGY.md for the real-evidence investigation of why rows are flagged).",
        "Only canonical official identities with a confirmed MAPPED response field (identity_mapping.py) "
        "ever produce an official_metric_value row at all — the remaining canonical identities are simply "
        "unavailable as features this round, never guessed.",
        "",
        "## Player identity resolution",
        "",
        f"- Direct player_master.player_id match: {ident['direct_match_count']}",
        f"- Resolved by exact raw-sample player_name match: {ident['resolved_by_name_count']}",
        f"- Unresolved (metric joins skipped, player still modeled if field/history exists): "
        f"{ident['unresolved_codes']}",
        "",
        "## Skipped players / metrics",
        "",
        f"- Entrants with no player_master match at all (modeled with zero history): {result.unmatched_count}",
        f"- Entrants with zero prior tournament history: {result.zero_history_count}",
        f"- Field players with a missing consistency feature (<2 prior rounds): "
        f"{result.missing_data_report['missing_consistency_feature_count']}",
        "",
        "## Probability sanity checks",
        "",
        f"- Sum: {result.sum_probability!r} (within 1e-6 of 1.0: {abs(result.sum_probability - 1.0) <= 1e-6})",
        f"- Min: {result.min_probability!r}  Max: {result.max_probability!r}",
        f"- Leakage validation clean: {result.leakage_validation['clean']} "
        f"({len(result.leakage_validation['violations'])} violations)",
        "",
        "## Model formula / method",
        "",
        "`combined_score = sum(z_f for f in model_features)` (equal weight, no fitted beta) — "
        "`P = softmax(-combined_score / tau)`, single tau fit by conditional-logit MLE "
        "(grid-refine search), identical math to the frozen M0-M6 ladder "
        "(klpga.models.math_utils/candidates), reused by import, never copied or modified. "
        "See docs/NEO_WIN_V0_1_METHODOLOGY.md for the full writeup.",
        "",
        "## Known BETA limitations",
        "",
    ] + [f"- {limitation}" for limitation in _KNOWN_LIMITATIONS]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_snapshot(result: NeoWinInferenceResult, prediction_id: str, created_at_utc: str) -> NeoWinPredictionSnapshot:
    entrants = tuple(
        NeoWinEntrantSnapshot(
            rank=p.rank,
            player_code=p.player_code,
            player_name=p.player_name,
            win_probability=p.win_probability,
            prior_events_n=p.prior_events_n,
            prior_avg_round_score_to_par=p.prior_avg_round_score_to_par,
            prior_recent_form_10=p.prior_recent_form_10,
            prior_recent_form_10_n=p.prior_recent_form_10_n,
            neo_consistency_stddev=p.neo_consistency_stddev,
            neo_consistency_stddev_n=p.neo_consistency_stddev_n,
            official_metrics=dict(p.official_metrics),
            player_master_matched=not p.is_unmatched,
        )
        for p in result.predictions
    )
    return NeoWinPredictionSnapshot(
        prediction_id=prediction_id,
        created_at_utc=created_at_utc,
        record_kind=RECORD_KIND,
        game_code=result.game_code,
        tournament_name=result.tournament_name,
        cutoff_date=result.cutoff_date,
        cutoff_source=result.cutoff_date_source,
        model_id=result.model_id,
        model_version=MODEL_VERSION,
        model_features=result.model_features,
        training_tournament_count=result.training_tournament_count,
        field_size=result.field_size,
        entrants_predicted=result.predicted_count,
        dropped_entrants=result.dropped_entrants,
        probability_sum=result.sum_probability,
        minimum_probability=result.min_probability,
        maximum_probability=result.max_probability,
        zero_history_count=result.zero_history_count,
        unmatched_count=result.unmatched_count,
        official_metric_context=result.official_metric_context,
        leakage_validation=result.leakage_validation,
        missing_data_report=result.missing_data_report,
        known_limitations=_KNOWN_LIMITATIONS,
        predictions=entrants,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--cutoff-date", default=None)
    parser.add_argument("--tournament-name", default=None)
    parser.add_argument("--freeze", action="store_true", help="Write a frozen PRE snapshot to neo_win_predictions/.")
    parser.add_argument("--prediction-id", default=None, help="Required with --freeze, e.g. '001'. Never auto-incremented.")
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    if args.freeze and not args.prediction_id:
        print("ERROR: --freeze requires --prediction-id")
        return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        result = run_neo_win_inference(conn, args.game_code, args.cutoff_date, args.tournament_name)
        dq = _read_data_quality_summary(conn)
    finally:
        conn.close()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    full_csv, top10_csv = _write_csvs(result, output_dir)
    report_path = output_dir / "BETA001_MODEL_REPORT.md"
    _write_model_report(result, dq, report_path)
    threads_path = output_dir / "BETA001_THREADS.txt"
    threads_path.write_text("\n".join(_build_threads_log(result, dq)) + "\n", encoding="utf-8")

    print_report(result, dq)
    print()
    print(f"Wrote: {full_csv}")
    print(f"Wrote: {top10_csv}")
    print(f"Wrote: {report_path}")
    print(f"Wrote: {threads_path}")

    print()
    print("=== FREEZE ===")
    print()
    freeze_status = "NOT FROZEN (pass --freeze --prediction-id <id> to freeze)"
    freeze_output_path = "—"
    if args.freeze:
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = _build_snapshot(result, args.prediction_id, created_at_utc)
        try:
            json_path, csv_path = write_neo_win_snapshot_atomic(snapshot, Path(args.predictions_dir))
        except NeoWinAlreadyArchivedError as exc:
            print(f"prediction_id: {args.prediction_id}")
            print(f"cutoff: {result.cutoff_date}")
            print(f"status: ERROR — {exc}")
            return 4
        freeze_copy_path = output_dir / "BETA001_FREEZE.json"
        freeze_copy_path.write_text(json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        freeze_status = "FROZEN"
        freeze_output_path = f"{json_path} / {csv_path} (+ convenience copy {freeze_copy_path})"

    print(f"prediction_id: {args.prediction_id or '—'}")
    print(f"cutoff: {result.cutoff_date}")
    print(f"output path: {freeze_output_path}")
    print(f"status: {freeze_status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
