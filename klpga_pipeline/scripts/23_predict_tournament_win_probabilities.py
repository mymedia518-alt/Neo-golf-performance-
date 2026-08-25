"""Read-only PRODUCTION win-probability inference for one UPCOMING
tournament's live entry list (`tournament_entry`), using the FROZEN v1
model M4 (`prior_avg_round_score_to_par` + `prior_recent_form_10`).

M4 was frozen as the v1 production candidate on 2026-08-25 — see
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` and the freeze decision
recorded in `docs/SITE_STRUCTURE_TODO.md` section 10 (M4 had the best
LogLoss at every swept eligibility threshold: 5, 8, and 10). This
script does NOT retune, cap, re-weight, or hand-calibrate M4 in any
way — it is a pure orchestration layer over
`klpga.models.inference.run_inference`, which itself reuses the
already-frozen backtest/modeling code unchanged (see that module's
docstring for the full reuse chain).

Does NOT write anything — no `tournament_master`/`player_master`/
`player_event`/`player_round`/`tournament_entry`/`player_stats_snapshot`
row is touched (the DB connection is opened `mode=ro`), and no
probability table is created.

Usage:
    python scripts/23_predict_tournament_win_probabilities.py --db data/klpga.sqlite --game-code 2026080001

If `tournament_master` has no usable row for this `--game-code` (no
row at all, or no resolvable start_date/end_date), you MUST also pass
--cutoff-date explicitly:
    python scripts/23_predict_tournament_win_probabilities.py --db data/klpga.sqlite \\
        --game-code 2026080001 --cutoff-date 2026-08-28 --tournament-name "제15회 KG 레이디스 오픈"

This script never guesses a cutoff date (e.g. "today") — see
`klpga.models.inference.resolve_cutoff_date`.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.models.inference import InferenceResult, run_inference  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _fmt(value, ndigits: int = 4) -> str:
    return "—" if value is None else f"{value:.{ndigits}f}"


def print_report(result: InferenceResult) -> None:
    print("=" * 110)
    print("KLPGA WIN-PROBABILITY INFERENCE — PRODUCTION v1 (frozen model M4)")
    print("=" * 110)
    print(f"  tournament name        : {result.tournament_name or '(unavailable — pass --tournament-name)'} "
          f"[source: {result.tournament_name_source}]")
    print(f"  gameCode                : {result.game_code}")
    print(f"  field size (entrants)   : {result.field_size}")
    print(f"  historical cutoff date  : {result.cutoff_date} [source: {result.cutoff_date_source}]")
    print(f"  historical training     : {result.training_tournament_count} usable tournament(s) strictly before cutoff")
    print(f"  model                   : {result.model_id}")
    print(f"  model features          : {', '.join(result.model_features)}")
    print("  known limitation        : coarse calibration diagnostics suggest over-confidence in some")
    print("                            higher probability bins, especially ~10-20% (documented, not corrected")
    print("                            by this script — see docs/SITE_STRUCTURE_TODO.md section 10)")
    print("  NOTE                    : field-relative score is not Strokes Gained; this model contains no")
    print("                            SG/GIR/driving/putting/course-par proxy of any kind")
    print()

    print("-" * 110)
    header = (
        f"{'rank':>4}  {'player_code':<12} {'player_name':<16} {'win_prob':>10} {'win_prob_%':>10}  "
        f"{'prior_n':>7} {'avg_score_to_par':>16} {'recent_form_10':>15} {'rf10_n':>6}  {'history_slice':<18}"
    )
    print(header)
    print("-" * 110)
    for pred in result.predictions:
        print(
            f"{pred.rank:>4}  {pred.player_code:<12} {pred.player_name:<16} "
            f"{_fmt(pred.win_probability, 6):>10} {_fmt(pred.win_probability * 100, 3):>10}  "
            f"{pred.prior_events_n:>7} {_fmt(pred.prior_avg_round_score_to_par, 2):>16} "
            f"{_fmt(pred.prior_recent_form_10, 2):>15} {pred.prior_recent_form_10_n:>6}  "
            f"{pred.history_slice:<18}"
            f"{'  [UNMATCHED vs player_master]' if pred.is_unmatched else ''}"
        )
    print("-" * 110)
    print()

    print(f"  sum_probability          : {result.sum_probability:.8f}")
    print(f"  minimum_probability      : {result.min_probability:.8f}")
    print(f"  maximum_probability      : {result.max_probability:.8f}")
    print(f"  zero-history entrants    : {result.zero_history_count}")
    print(f"  unmatched entrants       : {result.unmatched_count}")
    print(f"  entrants predicted       : {result.predicted_count}")
    print()

    print("=" * 110)
    print("REQUIRED FINAL CHECKS")
    print("=" * 110)
    checks = [
        ("entrants parsed = field size", result.entrants_parsed == result.field_size,
         f"{result.entrants_parsed} == {result.field_size}"),
        ("entrants predicted = field size", result.predicted_count == result.field_size,
         f"{result.predicted_count} == {result.field_size}"),
        ("dropped entrants = 0", result.dropped_entrants == 0, f"{result.dropped_entrants}"),
        ("duplicate player_codes = 0", result.duplicate_player_codes == 0, f"{result.duplicate_player_codes}"),
        ("probability sum = 1.000000 +/- 1e-6", abs(result.sum_probability - 1.0) <= 1e-6,
         f"{result.sum_probability:.8f}"),
    ]
    all_pass = True
    for label, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {label}  ({detail})")
    print()
    if all_pass:
        print("ALL REQUIRED CHECKS PASSED.")
    else:
        print("ONE OR MORE REQUIRED CHECKS FAILED — see above.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True, help="tournament_entry.game_code, e.g. 2026080001")
    parser.add_argument(
        "--cutoff-date", default=None,
        help="ISO-8601 YYYY-MM-DD historical cutoff. Required if tournament_master has no usable row for "
             "--game-code. Never guessed by this script.",
    )
    parser.add_argument(
        "--tournament-name", default=None,
        help="Display name. Falls back to tournament_master.event_name if not given; otherwise unavailable.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        try:
            result = run_inference(
                conn,
                args.game_code,
                cutoff_date_arg=args.cutoff_date,
                tournament_name_arg=args.tournament_name,
            )
        except (ValueError, RuntimeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print_report(result)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
