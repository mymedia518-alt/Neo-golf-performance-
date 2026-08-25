"""Read-only M0-M6 win-probability model comparison against the real
production DB — the FIRST MODEL EXPERIMENTATION STAGE, implemented
exactly against the frozen
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`.

Fits and evaluates M0 (uniform) through M6 (field-relative strength +
recent10) under the walk-forward protocol
(`klpga.models.walk_forward_eval`), and prints the full comparison
report (leaderboard, paired Wilcoxon comparisons vs M0 and Baseline 1,
calibration, time-stability, rookie/sparse-history audit) for one or
more eligibility thresholds.

Does NOT write anything — no `tournament_master`/`player_master`/
`player_event`/`player_round`/`tournament_entry` row is touched, and
this script does NOT select a "winning" model or compute a live
KG Ladies Open probability. It only produces the evidence Section 11
of the frozen spec requires for that decision to be made by a human.

Usage (on a machine with the real production data/klpga.sqlite):
    python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite
    python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 5,8,10
    python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 5 --models M0,M1,M2
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.models.candidates import MODEL_DESCRIPTIONS, MODEL_FEATURES, MODEL_IDS  # noqa: E402
from klpga.models.report import format_full_report  # noqa: E402
from klpga.models.walk_forward_eval import run_multi_model_walk_forward  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _git_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _print_reproducibility_header(db_path: Path, thresholds: tuple[int, ...], model_ids: tuple[str, ...]) -> None:
    print("=" * 100)
    print("REPRODUCIBILITY")
    print("=" * 100)
    print(f"  git commit          : {_git_commit_hash()}")
    print(f"  db path             : {db_path}")
    print(f"  models evaluated    : {', '.join(model_ids)}")
    for mid in model_ids:
        features = ", ".join(MODEL_FEATURES[mid]) or "(none)"
        print(f"      {mid} = {MODEL_DESCRIPTIONS[mid]} — features: {features}")
    print(f"  thresholds          : {list(thresholds)}")
    print("  training rule       : expanding window — every USABLE tournament strictly before the")
    print("                        target's effective date (see klpga.models.walk_forward_eval module")
    print("                        docstring); NEVER threshold-filtered, NEVER includes the target itself")
    print("                        or any later tournament")
    print("  fitting method      : deterministic grid-refine MLE (klpga.models.math_utils.grid_refine_search)")
    print("                        — no randomness, no seed needed for model fitting")
    print("  stochastic elements : ONLY the calibration bootstrap CI (klpga.models.metrics.BOOTSTRAP_SEED,")
    print("                        fixed and disclosed) — model fitting/prediction itself is fully")
    print("                        deterministic; identical inputs always produce identical predictions")
    print("  primary metrics     : mean per-tournament log loss (1e-6 clip floor) and field-size-normalized")
    print("                        multiclass Brier score — see docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md")
    print("                        Section 3 for exact definitions")
    print("  spec document       : docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md (frozen 2026-08-25)")
    print()


def run(conn: sqlite3.Connection, db_path: Path, thresholds: tuple[int, ...], model_ids: tuple[str, ...]) -> dict:
    _print_reproducibility_header(db_path, thresholds, model_ids)

    results = {}
    overall_start = time.monotonic()

    for threshold in thresholds:
        print("=" * 100)
        print(f"THRESHOLD = {threshold} — fitting/predicting {len(model_ids)} model(s) walk-forward")
        print("=" * 100)

        threshold_start = time.monotonic()
        last_printed_target = None

        def progress(idx, total, target_info, model_id, skipped, _threshold=threshold):
            nonlocal last_printed_target
            elapsed = time.monotonic() - threshold_start
            if skipped:
                print(f"  [{idx:>4}/{total}] {target_info.event_id:<14} SKIPPED (ambiguous/missing winner)  "
                      f"elapsed={elapsed:6.1f}s")
                return
            # One line per (target, model) — keeps the terminal visibly
            # moving even if a single fit is slow, per explicit instruction.
            print(f"  [{idx:>4}/{total}] {target_info.event_id:<14} model={model_id:<3}  elapsed={elapsed:6.1f}s")

        result = run_multi_model_walk_forward(conn, model_ids, threshold, progress_callback=progress)
        threshold_elapsed = time.monotonic() - threshold_start
        print(f"\nThreshold={threshold} done in {threshold_elapsed:.1f}s "
              f"({result.eligible_tournament_count} eligible tournament(s), "
              f"{len(model_ids)} model(s)).\n")

        print(format_full_report(result))
        print()
        results[threshold] = result

    overall_elapsed = time.monotonic() - overall_start
    print("=" * 100)
    print(f"TOTAL elapsed: {overall_elapsed:.1f}s across {len(thresholds)} threshold(s)")
    print("=" * 100)
    print(
        "\nNo model has been selected as a production candidate by this script. "
        "See docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md Section 11 for the promotion criteria "
        "this output must be judged against — including consistency across the thresholds above."
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--thresholds", default="5", help="comma-separated list, e.g. 5,8,10 (default: 5)")
    parser.add_argument("--models", default=",".join(MODEL_IDS), help=f"comma-separated model ids (default: all {MODEL_IDS})")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    thresholds = tuple(int(t.strip()) for t in args.thresholds.split(","))
    model_ids = tuple(m.strip() for m in args.models.split(","))
    for mid in model_ids:
        if mid not in MODEL_IDS:
            print(f"ERROR: unknown model id {mid!r} — must be one of {MODEL_IDS}", file=sys.stderr)
            return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        run(conn, db_path, thresholds, model_ids)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
