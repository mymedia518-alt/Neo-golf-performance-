"""Run frozen production inference (model M4) exactly once and archive
its EXACT output atomically as an immutable prediction snapshot.

This is the sanctioned command for every prediction going forward
(`--source live_atomic_inference`). It never retries, never refits,
never recalibrates — it calls `klpga.models.inference.run_inference`
one time and either the result is archived, unmodified, or nothing is
written at all.

It also supports one narrow, explicitly-labeled exception:
`--source rerun_reconstruction`, for recovering a prediction that was
already produced once on the real production DB but whose complete
output was never captured to a machine-readable file (see
`docs/PREDICTION_ARCHIVE.md`). A reconstruction is NEVER archived
unless it is cross-checked against independently-recorded facts from
the real first run (`--verify-*` flags below) and matches every one of
them — any mismatch aborts before anything is written.

Does NOT write to `tournament_master`/`player_master`/`player_event`/
`player_round`/`tournament_entry`/`player_stats_snapshot` (the DB
connection is opened `mode=ro`, exactly like `scripts/23`). Does NOT
modify `klpga.models.inference`, `klpga.models.candidates`,
`klpga.models.math_utils`, or `scripts/23` — this script only imports
and calls them.

Usage — live prediction (#002 onward):
    python scripts/24_archive_prediction.py --db data/klpga.sqlite --game-code 2026080001 \\
        --prediction-id 002 --source live_atomic_inference

Usage — Prediction #001 reconstruction (see docs/PREDICTION_ARCHIVE.md for why
this is necessary and never labeled "original"):
    python scripts/24_archive_prediction.py --db data/klpga.sqlite --game-code 2026080001 \\
        --cutoff-date 2026-08-27 --tournament-name "제15회 KG 레이디스 오픈" \\
        --prediction-id 001 --source rerun_reconstruction \\
        --verify-training-tournament-count 100 --verify-field-size 120 \\
        --verify-dropped-entrants 0 --verify-probability-sum 1.000000 \\
        --verify-top-player-code 11134 --verify-top-player-name "서교림" \\
        --verify-top-player-display-pct 10.097
"""
from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import sys
from datetime import date as date_cls
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.archive.prediction_archive import (  # noqa: E402
    ExpectedFacts,
    PredictionAlreadyArchivedError,
    build_live_atomic_provenance,
    build_rerun_reconstruction_provenance,
    latest_training_tournament_date,
    snapshot_from_inference_result,
    verify_against_observed_facts,
    write_prediction_snapshot_atomic,
)
from klpga.models.inference import run_inference  # noqa: E402


def _load_script_23():
    """Reuses scripts/23's exact `print_report` formatting rather than
    duplicating it — the on-screen report for a run archived by this
    script must look identical to the one `scripts/23` alone prints."""
    path = ROOT / "scripts" / "23_predict_tournament_win_probabilities.py"
    spec = importlib.util.spec_from_file_location("predict_tournament_win_probabilities_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _print_db_state_report(conn: sqlite3.Connection, game_code: str, cutoff_date_obj, result) -> None:
    print("=" * 110)
    print("DATABASE-STATE DIAGNOSTIC (read before approving an archive)")
    print("=" * 110)
    latest_date = latest_training_tournament_date(conn, game_code, cutoff_date_obj)
    print(f"  historical training tournament count : {result.training_tournament_count}")
    print(f"  latest historical tournament date used : {latest_date}")
    print(f"  field size                             : {result.field_size}")
    print(f"  zero-history count                     : {result.zero_history_count}")
    print(f"  unmatched count                         : {result.unmatched_count}")
    print("  NOTE: no checksum/hash of the database was captured before the first")
    print("        production run, so \"the DB has not materially changed since then\"")
    print("        cannot be cryptographically proven from here — the checks below are")
    print("        an operator-supplied cross-check against independently recorded")
    print("        facts, not a database integrity proof.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--cutoff-date", default=None)
    parser.add_argument("--tournament-name", default=None)
    parser.add_argument("--prediction-id", required=True, help='e.g. "001", "002" — short, explicit, never auto-incremented')
    parser.add_argument(
        "--source", required=True, choices=["live_atomic_inference", "rerun_reconstruction"],
        help="live_atomic_inference for #002 onward; rerun_reconstruction ONLY for recovering an "
             "already-produced-but-uncaptured earlier run (see docs/PREDICTION_ARCHIVE.md)",
    )
    parser.add_argument("--predictions-dir", default=str(ROOT / "predictions"))

    # rerun_reconstruction-only flags.
    parser.add_argument("--reconstruction-reason", default=(
        "The first successful production run was displayed in CMD but the complete "
        "120-row output was not captured to a machine-readable file."
    ))
    parser.add_argument("--original-run-status", default="successful_pre_tournament_run_observed")
    parser.add_argument("--original-snapshot-available", action="store_true", default=False)
    parser.add_argument("--verify-training-tournament-count", type=int, default=None)
    parser.add_argument("--verify-field-size", type=int, default=None)
    parser.add_argument("--verify-dropped-entrants", type=int, default=None)
    parser.add_argument("--verify-probability-sum", type=float, default=None)
    parser.add_argument("--verify-zero-history-count", type=int, default=None)
    parser.add_argument("--verify-unmatched-count", type=int, default=None)
    parser.add_argument("--verify-top-player-code", default=None)
    parser.add_argument("--verify-top-player-name", default=None)
    parser.add_argument("--verify-top-player-display-pct", type=float, default=None)

    args = parser.parse_args()

    if args.source == "rerun_reconstruction":
        required = {
            "--verify-training-tournament-count": args.verify_training_tournament_count,
            "--verify-field-size": args.verify_field_size,
            "--verify-dropped-entrants": args.verify_dropped_entrants,
            "--verify-probability-sum": args.verify_probability_sum,
            "--verify-top-player-code": args.verify_top_player_code,
            "--verify-top-player-display-pct": args.verify_top_player_display_pct,
        }
        missing = [flag for flag, value in required.items() if value is None]
        if missing:
            print(
                f"ERROR: --source rerun_reconstruction requires {missing} — a reconstruction is never "
                "archived without a cross-check against the real first run's observed facts.",
                file=sys.stderr,
            )
            return 2

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    script23 = _load_script_23()

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        try:
            result = run_inference(
                conn, args.game_code, cutoff_date_arg=args.cutoff_date, tournament_name_arg=args.tournament_name,
            )
        except (ValueError, RuntimeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        script23.print_report(result)

        cutoff_date_obj = date_cls.fromisoformat(result.cutoff_date)
        _print_db_state_report(conn, args.game_code, cutoff_date_obj, result)

        if args.source == "rerun_reconstruction":
            expected = ExpectedFacts(
                game_code=args.game_code,
                field_size=args.verify_field_size,
                model_id="M4",
                training_tournament_count=args.verify_training_tournament_count,
                entrants_predicted=args.verify_field_size,
                dropped_entrants=args.verify_dropped_entrants,
                probability_sum=args.verify_probability_sum,
                zero_history_count=args.verify_zero_history_count,
                unmatched_count=args.verify_unmatched_count,
                top_player_code=args.verify_top_player_code,
                top_player_name=args.verify_top_player_name,
                top_player_display_probability_pct=args.verify_top_player_display_pct,
            )
            mismatches = verify_against_observed_facts(result, expected)
            print("=" * 110)
            print("RECONSTRUCTION CROSS-CHECK")
            print("=" * 110)
            if mismatches:
                for m in mismatches:
                    print(f"  [MISMATCH] {m}")
                print()
                print("ABORTED: the reconstruction does not match the observed facts from the real first run.")
                print("No archive file was written.")
                return 2
            print("  All observed first-run facts verified — reconstruction matches.")
            print()

            provenance = build_rerun_reconstruction_provenance(
                original_run_status=args.original_run_status,
                original_machine_readable_snapshot_available=args.original_snapshot_available,
                reconstruction_reason=args.reconstruction_reason,
                verification={
                    "first_run_top_player_code": args.verify_top_player_code,
                    "first_run_top_player_name": args.verify_top_player_name,
                    "first_run_top_player_display_probability_pct": args.verify_top_player_display_pct,
                    "first_run_training_tournament_count": args.verify_training_tournament_count,
                    "first_run_field_size": args.verify_field_size,
                    "first_run_dropped_entrants": args.verify_dropped_entrants,
                    "first_run_probability_sum": args.verify_probability_sum,
                    "first_run_zero_history_count": args.verify_zero_history_count,
                    "first_run_unmatched_count": args.verify_unmatched_count,
                },
            )
        else:
            provenance = build_live_atomic_provenance()

        snapshot = snapshot_from_inference_result(
            result,
            prediction_id=args.prediction_id,
            created_at_utc=_now_utc_iso(),
            provenance=provenance,
        )

        try:
            json_path, csv_path = write_prediction_snapshot_atomic(snapshot, Path(args.predictions_dir))
        except PredictionAlreadyArchivedError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        print("=" * 110)
        print("ARCHIVED")
        print("=" * 110)
        print(f"  provenance.source : {provenance['source']}")
        print(f"  JSON              : {json_path}")
        print(f"  CSV               : {csv_path}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
