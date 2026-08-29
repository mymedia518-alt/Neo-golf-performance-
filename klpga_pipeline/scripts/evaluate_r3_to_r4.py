"""BETA #001 FINAL validation — R3 -> R4 next-round prediction
evaluation. READ-ONLY against the DB (opened `mode=ro`) and every
existing frozen artifact (PRE snapshot, tournament_history). Writes
ONLY new files: a comparison CSV under --output-dir and, with
--freeze, a new R3->R4 evaluation record under --archive-root (never
neo_tournament_history/, never BETA_R3_FULL.csv, never any PRE/R1/R2/R3
frozen file).

Re-obtains mu/sigma (expected_round_score_to_par / spread) by calling
klpga.neo_win.round_update_r3.build_r3_sim_inputs_from_frozen_snapshot
directly — the EXACT, unmodified production function POST-R3 itself
uses. This script never re-derives that formula and never lets Round-4
data reach it: r1_scores/r2_scores/r3_scores/made_cut_by_player are
read via three independent round_number IN (1,2,3) queries plus one
player_event query, and Round-4 data is read separately, afterward,
into `actual_r4_scores` only — the one and only place round_number=4
is ever queried. See docs/BETA001_R3_R4_EVALUATION_NOTES.md for the
full leakage-guard rationale and the neo_consistency_stddev sample-vs-
population-stddev implementation note this script's frozen record also
carries.

HARD STOPS (writes nothing) if:
  - zero real round_number=4 rows exist for --game-code yet (R4 hasn't
    happened), or
  - klpga.neo_win.player_status.assess_field_readiness at round_number=4
    reports READINESS_HARD_STOP (a real ingestion gap).

Usage (once R4 has officially concluded):
    python scripts/evaluate_r3_to_r4.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-cutoff-date 2026-08-27 --freeze
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.player_status import (  # noqa: E402
    READINESS_HARD_STOP,
    READINESS_WARN,
    assess_field_readiness,
)
from klpga.neo_win.r3_r4_evaluation import (  # noqa: E402
    aggregate_r3_r4_evaluation,
    build_r3_r4_evaluation_rows,
    compute_input_fingerprint,
    write_r3_r4_evaluation_csv,
)
from klpga.neo_win.r3_r4_evaluation_archive import (  # noqa: E402
    RECORD_KIND,
    STAGE_TRANSITION_R3_TO_R4,
    R3R4EvaluationAlreadyRecordedError,
    R3R4EvaluationSnapshot,
    write_evaluation_atomic,
)
from klpga.neo_win.round_update_r3 import build_r3_sim_inputs_from_frozen_snapshot  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "r3_r4_evaluation"
DEFAULT_ARCHIVE_ROOT = ROOT / "neo_r3_r4_evaluation"

KNOWN_LIMITATIONS: tuple[str, ...] = (
    "klpga.neo_win.consistency.compute_consistency_feature()'s docstring says \"population standard "
    "deviation\", but the implementation uses statistics.stdev() (sample standard deviation, n-1 "
    "denominator), not statistics.pstdev() (population, n denominator). Confirmed by direct code read; "
    "the #001/#001-C model code was NOT changed to resolve this discrepancy -- documented here as a fact "
    "for future model design (e.g. #002) to consider deliberately, not silently inherited.",
    "This evaluation's mu/sigma are exactly the values klpga.neo_win.round_update_r3."
    "build_r3_sim_inputs_from_frozen_snapshot produces from the frozen PRE snapshot alone -- per that "
    "function's own code, they do NOT depend on r1_scores/r2_scores/r3_scores/made_cut_by_player "
    "numerically (population-mean shrinkage is computed over every pre_snapshot.predictions entrant, "
    "independent of live DB round data). source_r1_r2_r3_made_cut_input_sha256 on this record documents "
    "exactly what live DB state was read at evaluation time; it is provenance, not evidence that mu/sigma "
    "would differ under a different one.",
)


def _r4_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 4", (game_code,)
    ).fetchone()[0]


def _round_scores(conn: sqlite3.Connection, game_code: str, round_number: int) -> dict:
    return dict(conn.execute(
        "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = ? "
        "AND round_to_par IS NOT NULL",
        (game_code, round_number),
    ).fetchall())


def _made_cut(conn: sqlite3.Connection, game_code: str) -> dict:
    return {
        pid: bool(mc) for pid, mc in conn.execute(
            "SELECT player_id, made_cut FROM player_event WHERE game_code = ?", (game_code,)
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--c-predictions-dir", default=str(DEFAULT_C_PREDICTIONS_DIR))
    parser.add_argument("--pre-prediction-id", default=None, help="Omit to auto-prefer BETA #001-C, else BETA #001's '001'.")
    parser.add_argument("--pre-cutoff-date", required=True, help="cutoff_date of the PRE snapshot, to locate its archive path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE_ROOT))
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r4_count = _r4_row_count(conn, args.game_code)
        if r4_count == 0:
            print("STATUS: NOT_READY")
            print(f"REASON: zero real round_number=4 rows exist for game_code={args.game_code!r} yet — "
                  "Round 4 has not officially concluded. Nothing written.")
            return 0

        readiness = assess_field_readiness(conn, args.game_code, round_number=4)
        if readiness.verdict == READINESS_HARD_STOP:
            print("STATUS: HARD_STOP")
            print(f"REASON: {readiness.reason}")
            return 0

        r1_scores = _round_scores(conn, args.game_code, 1)
        r2_scores = _round_scores(conn, args.game_code, 2)
        r3_scores = _round_scores(conn, args.game_code, 3)
        made_cut = _made_cut(conn, args.game_code)
        actual_r4_scores = _round_scores(conn, args.game_code, 4)  # the ONLY round_number=4 read in this script

        pre_snapshot = None
        pre_source = None
        if args.pre_prediction_id is None or args.pre_prediction_id == "001-C":
            c_path = Path(args.c_predictions_dir) / args.pre_cutoff_date[:4] / f"neo_win_c_001-C_{args.game_code}.json"
            if c_path.exists():
                pre_snapshot = read_neo_win_c_snapshot(c_path)
                pre_source = c_path
        if pre_snapshot is None:
            pid = args.pre_prediction_id or "001"
            pre_path, _c = archive_paths(Path(args.predictions_dir), pid, args.game_code, args.pre_cutoff_date)
            if not pre_path.exists():
                print(f"ERROR: no frozen PRE snapshot found at {pre_path} (or BETA #001-C equivalent).")
                return 4
            pre_snapshot = read_neo_win_snapshot(pre_path)
            pre_source = pre_path

        pre_snapshot_sha256 = hashlib.sha256(Path(pre_source).read_bytes()).hexdigest()
        input_fingerprint = compute_input_fingerprint(r1_scores, r2_scores, r3_scores, made_cut)

        # STEP5 — mu/sigma reproduced via the EXACT, unmodified production function.
        sim_inputs, missing_r1_r2_r3 = build_r3_sim_inputs_from_frozen_snapshot(
            pre_snapshot, r1_scores, r2_scores, r3_scores, made_cut
        )
    finally:
        conn.close()

    rows, missing_r4 = build_r3_r4_evaluation_rows(sim_inputs, actual_r4_scores)
    aggregate = aggregate_r3_r4_evaluation(rows)

    output_dir = Path(args.output_dir)
    csv_path = write_r3_r4_evaluation_csv(rows, output_dir / f"{args.game_code}_R3_R4_EVALUATION.csv")

    freeze_status = "NOT FROZEN (pass --freeze to freeze + record the evaluation)"
    if args.freeze:
        prediction_id = getattr(pre_snapshot, "prediction_id", "") or "unknown"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = R3R4EvaluationSnapshot(
            game_code=args.game_code, prediction_id=prediction_id, stage_transition=STAGE_TRANSITION_R3_TO_R4,
            record_kind=RECORD_KIND, recorded_at_utc=now,
            source_pre_snapshot_path=str(pre_source), source_pre_snapshot_sha256=pre_snapshot_sha256,
            source_r1_r2_r3_made_cut_input_sha256=input_fingerprint,
            aggregate=aggregate, rows=tuple(rows), known_limitations=KNOWN_LIMITATIONS,
        )
        try:
            path = write_evaluation_atomic(snapshot, Path(args.archive_root))
            freeze_status = f"RECORDED at {path}"
        except R3R4EvaluationAlreadyRecordedError as exc:
            freeze_status = f"SKIP + LOG — already recorded ({exc})"

    print("=== NEO GOLF DATA BETA #001 FINAL — R3 -> R4 EVALUATION ===")
    print()
    print("STATUS: DATA_COMPLETE" + (f" (readiness verdict: {readiness.verdict})" if readiness.verdict == READINESS_WARN else ""))
    print(f"R4 DATA: {len(actual_r4_scores)} real round_number=4 rows found for game_code={args.game_code!r}")
    print(f"PRE snapshot source: {pre_source}")
    print(f"PRE snapshot SHA-256: {pre_snapshot_sha256}")
    print(f"R1/R2/R3/made_cut input SHA-256: {input_fingerprint}")
    print("MU/SIGMA SOURCE: klpga.neo_win.round_update_r3.build_r3_sim_inputs_from_frozen_snapshot "
          "(unmodified production function — never re-derived here)")
    print(f"FUTURE DATA LEAKAGE GUARD: PASS (round_number=4 was read into a separate dict, after "
          f"mu/sigma were already derived from r1/r2/r3/made_cut only)")
    if missing_r1_r2_r3:
        print(f"Excluded from simulation upstream (missing r1/r2/r3/cut, SKIP+LOG): {missing_r1_r2_r3}")
    if missing_r4:
        print(f"MISSING R4 (real WD/DQ or ingestion gap, SKIP+LOG, excluded from every aggregate): {missing_r4}")
    print()
    print(f"EVALUATED_PLAYERS: {aggregate['evaluated_players']}")
    print(f"MAE: {aggregate['mae']}")
    print(f"ME (bias): {aggregate['me']}")
    print(f"RMSE: {aggregate['rmse']}")
    print(f"WITHIN ±1 STROKE: {aggregate['within_1_stroke_pct']}%")
    print(f"WITHIN ±SIGMA: {aggregate['within_sigma_pct']}%")
    print()
    print(f"CSV: {csv_path}")
    print(f"FREEZE: {freeze_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
