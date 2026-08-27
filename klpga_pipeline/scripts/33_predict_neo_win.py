"""NEO WIN % v0.1 — BETA #001. Read-only pre-tournament win-probability
inference + frozen PRE snapshot, entirely separate from `klpga.models`
(the frozen M0-M6 ladder behind Prediction #001) and from `predictions/`
(that archive) — see `src/klpga/neo_win/__init__.py` and
docs/NEO_WIN_V0_1_METHODOLOGY.md.

Does NOT write to tournament_master/player_master/player_event/
player_round/tournament_entry/official_metric_value/player_stats_snapshot
(the DB connection is opened `mode=ro`) and NEVER touches `predictions/`.
The only file it can create is a NEW `neo_win_predictions/<year>/
neo_win_<id>_<game_code>.{json,csv}` pair, and only when `--freeze` is
passed — append-only, never overwritten (klpga.neo_win.archive).

Usage — report only, no file written:
    python scripts/33_predict_neo_win.py --db data/klpga.sqlite --game-code 2026080001 --cutoff-date 2026-08-27

Usage — report + freeze a PRE snapshot (prediction-id required, never auto-incremented):
    python scripts/33_predict_neo_win.py --db data/klpga.sqlite --game-code 2026080001 --cutoff-date 2026-08-27 \\
        --freeze --prediction-id 001
"""
from __future__ import annotations

import argparse
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
    write_neo_win_snapshot_atomic,
)
from klpga.neo_win.inference import NeoWinInferenceResult, run_neo_win_inference  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_ROOT = ROOT / "neo_win_predictions"

_KNOWN_LIMITATIONS: tuple[str, ...] = (
    "BETA #001 / v0.1: single-tau equal-weight model, not yet walk-forward "
    "promotion-gated against M4 the way M0-M6 were (docs/WIN_PROBABILITY_"
    "MODEL_EVALUATION_SPEC.md) — a candidate for future evaluation, not a "
    "claim of superiority over the frozen production model.",
    "The validated official-metric feature (if not omitted — see "
    "official_metric_context) uses the PRIOR completed season only, never "
    "the target tournament's own season, to stay leakage-safe against "
    "official_metric_value's season-level (not point-in-time) granularity.",
)


def _fmt(value, ndigits: int = 4) -> str:
    return "—" if value is None else f"{value:.{ndigits}f}"


def print_report(result: NeoWinInferenceResult) -> None:
    print("=== NEO WIN % v0.1 (BETA #001) ===")
    print(f"game_code: {result.game_code}")
    print(f"tournament_name: {result.tournament_name} (source: {result.tournament_name_source})")
    print(f"cutoff_date: {result.cutoff_date} (source: {result.cutoff_date_source})")
    print(f"model_id: {result.model_id}  features: {result.model_features}")
    print(f"training_tournament_count: {result.training_tournament_count}")
    print()
    print("--- ENTRY FIELD / DB MATCH ---")
    print(f"entrants_parsed: {result.entrants_parsed}  predicted: {result.predicted_count}  dropped: {result.dropped_entrants}")
    print(f"unmatched_against_player_master: {result.unmatched_count}")
    print()
    print("--- OFFICIAL METRIC FEATURE ---")
    ctx = result.official_metric_context
    if ctx["official_metric_label"] is None:
        print("omitted: no allowlisted official metric had sufficient prior-season coverage")
    else:
        print(
            f"label: {ctx['official_metric_label']}  orientation: {ctx['official_metric_orientation']}  "
            f"prior_season: {ctx['prior_season']}  players_covered: {ctx['official_metric_player_coverage']}"
        )
    print()
    print("--- PROBABILITY-SUM VALIDATION ---")
    print(f"sum={result.sum_probability!r}  min={result.min_probability!r}  max={result.max_probability!r}")
    print(f"within 1e-6 of 1.0: {abs(result.sum_probability - 1.0) <= 1e-6}")
    print()
    print("--- LEAKAGE VALIDATION ---")
    print(f"clean: {result.leakage_validation['clean']}  violations: {len(result.leakage_validation['violations'])}")
    for v in result.leakage_validation["violations"][:10]:
        print(f"  - {v}")
    print()
    print("--- MISSING-DATA REPORT ---")
    for k, v in result.missing_data_report.items():
        print(f"  {k}: {v}")
    print()
    print("--- TOP 10 NEO WIN % ---")
    for p in result.predictions[:10]:
        print(
            f"  {p.rank:>3}. {p.player_name:<14} {p.win_probability * 100:6.3f}%  "
            f"score_to_par={_fmt(p.prior_avg_round_score_to_par)}  form10={_fmt(p.prior_recent_form_10)}  "
            f"consistency={_fmt(p.neo_consistency_stddev)}  official={_fmt(p.neo_official_metric)}  "
            f"unmatched={p.is_unmatched}"
        )


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
            neo_official_metric=p.neo_official_metric,
            neo_official_metric_n=p.neo_official_metric_n,
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
    finally:
        conn.close()

    print_report(result)

    if args.freeze:
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = _build_snapshot(result, args.prediction_id, created_at_utc)
        try:
            json_path, csv_path = write_neo_win_snapshot_atomic(snapshot, Path(args.predictions_dir))
        except NeoWinAlreadyArchivedError as exc:
            print(f"\nERROR: {exc}")
            return 4
        print(f"\nFrozen PRE snapshot written: {json_path} / {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
