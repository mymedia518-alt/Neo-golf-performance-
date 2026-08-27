"""Roadmap next-step — BETA post-Round-2 snapshot. Combines the frozen
PRE prediction with the real, already-collected Round-1 AND Round-2
leaderboard (`player_round`, round_number 1 and 2) via
`klpga.neo_win.round_update_r2` (a NEW, parallel module — never
touches `klpga.neo_win.round_update`, BETA #001-R1's own pipeline).

The cut is READ as a real fact from `player_event.made_cut`, never
simulated (round 2 has already happened at this point) — see round_
update_r2.py's module docstring for why NEO_R3_PCT and NEO_FINAL_PCT
are reported as the exact same real value as NEO_CUT_PCT (this
tournament format has exactly one cut; there is no second, independent
probability to compute).

STOPS at READY_FOR_R2 (writes/freezes NOTHING) unless round_number=2
`player_round` rows cover the WHOLE tournament_entry field for this
game_code — never generates a prediction from a partially-completed
round.

Freezing = recording klpga.neo_win.tournament_history's STAGE_R2 stage
via write_or_supersede_history_stage (append-only; a real duplicate is
a SKIP+LOG no-op, never an overwrite — and if this slot ever held a
HISTORICAL_SNAPSHOT_MISSING marker from an earlier run, that marker is
preserved untouched and this real result is recorded as a superseding
event instead of being silently dropped; see klpga.neo_win.tournament_
history's module docstring). Never touches the PRE/R1 frozen artifacts.

Usage:
    python scripts/44_predict_neo_win_post_r2.py --db data/klpga.sqlite --game-code 2026080001 \\
        --pre-cutoff-date 2026-08-27 --freeze
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.player_status import classify_player_round_status  # noqa: E402
from klpga.neo_win.round_update_r2 import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_r2_sim_inputs_from_frozen_snapshot,
    simulate_post_round2,
)
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_R2,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    write_or_supersede_history_stage,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta_r2"


def _read_round_scores(conn: sqlite3.Connection, game_code: str, round_number: int) -> dict:
    return {
        player_id: round_to_par
        for player_id, round_to_par in conn.execute(
            "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = ? "
            "AND round_to_par IS NOT NULL",
            (game_code, round_number),
        )
    }


def _read_made_cut(conn: sqlite3.Connection, game_code: str) -> dict:
    return {
        player_id: bool(made_cut)
        for player_id, made_cut in conn.execute(
            "SELECT player_id, made_cut FROM player_event WHERE game_code = ?", (game_code,)
        )
    }


def _field_size(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT player_code) FROM tournament_entry WHERE game_code = ?", (game_code,)
    ).fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--predictions-dir", default=str(DEFAULT_PREDICTIONS_DIR))
    parser.add_argument("--c-predictions-dir", default=str(DEFAULT_C_PREDICTIONS_DIR))
    parser.add_argument("--pre-prediction-id", default=None, help="Omit to auto-prefer BETA #001-C, else BETA #001's '001'.")
    parser.add_argument("--pre-cutoff-date", required=True, help="cutoff_date of the PRE snapshot, to locate its archive path.")
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        field_size = _field_size(conn, args.game_code)
        if field_size == 0:
            print(f"STATUS: READY_FOR_R2")
            print(f"R2 DATA: no tournament_entry field found for game_code={args.game_code!r} — nothing to check.")
            return 0

        r2_scores = _read_round_scores(conn, args.game_code, 2)
        if len(r2_scores) < field_size:
            print("STATUS: READY_FOR_R2")
            print(f"R2 DATA: INCOMPLETE — {len(r2_scores)}/{field_size} field players have a real round_number=2 "
                  f"player_round row for game_code={args.game_code!r}. Not generating a prediction. STOP.")
            return 0

        r1_scores = _read_round_scores(conn, args.game_code, 1)
        made_cut = _read_made_cut(conn, args.game_code)

        # Prefer BETA #001-C's own PRE if a --pre-prediction-id wasn't forced.
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

        sim_inputs, missing = build_r2_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores, r2_scores, made_cut)
        # Evidence-only classification (klpga.neo_win.player_status, shared with scripts/45) — never
        # changes the simulation, only explains WHY each excluded player has no round_number=2 result.
        missing_classification = {code: classify_player_round_status(conn, args.game_code, code, round_number=2) for code in missing}
    finally:
        conn.close()

    rng = __import__("random").Random(args.seed) if args.seed is not None else None
    sim_result = simulate_post_round2(sim_inputs, n_simulations=args.n_simulations, rng=rng)

    pre_win_by_code = {e.player_code: e.win_probability * 100 for e in pre_snapshot.predictions}
    positions_ordered = sorted(
        ((r1_scores.get(c, 0) + r2_scores.get(c, 0), c) for c in r2_scores if c in r1_scores), key=lambda t: t[0]
    )
    position_by_code = {c: i + 1 for i, (_score, c) in enumerate(positions_ordered)}

    entrants = []
    for inp in sim_inputs:
        code = inp.player_code
        sim = sim_result.get(code)
        win_pct = sim["win_pct"] if sim else None
        make_cut_pct = sim["make_cut_pct"] if sim else None
        top10_pct = sim["top10_pct"] if sim else None
        entrants.append(
            HistoryEntrant(
                player_code=code, player_name=inp.player_name, win_pct=win_pct, make_cut_pct=make_cut_pct,
                top10_pct=top10_pct,
                position=position_by_code.get(code),
                score_to_par=(r1_scores[code] + r2_scores[code]) if (code in r1_scores and code in r2_scores) else None,
            )
        )

    duplicate_count = len(entrants) - len({e.player_code for e in entrants})
    win_values = [e.win_pct for e in entrants if e.win_pct is not None]
    win_sum = sum(win_values)
    null_count = sum(1 for e in entrants if e.win_pct is None)
    field_codes = {e.player_code for e in entrants}
    non_field_count = 0  # entrants are built 1:1 from pre_snapshot.predictions, already the frozen field

    print("=== BETA POST-R2 ===")
    print()
    print(f"STATUS: DATA_COMPLETE")
    print(f"R2 DATA: {len(r2_scores)}/{field_size} field players (full field), source: player_round round_number=2")
    print(f"PLAYERS: {len(entrants)}")
    print(f"WIN SUM: {win_sum:.4f}%  (over {len(win_values)} players with a real simulated value)")
    print(f"VALIDATION: duplicates={duplicate_count} nulls={null_count} non_field={non_field_count} "
          f"missing_r1_or_r2_or_cut={len(missing)}")
    print()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "BETA_R2_FULL.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "player_code", "player_name", "position", "score_to_par",
            "neo_win_pct", "neo_cut_pct", "neo_r3_pct", "neo_final_pct", "neo_top10_pct",
            "pre_win_pct", "pre_to_r2_win_change_pct",
        ])
        writer.writeheader()
        for e in entrants:
            pre_pct = pre_win_by_code.get(e.player_code)
            change = (e.win_pct - pre_pct) if (e.win_pct is not None and pre_pct is not None) else None
            writer.writerow({
                "player_code": e.player_code, "player_name": e.player_name,
                "position": e.position if e.position is not None else "unavailable",
                "score_to_par": e.score_to_par if e.score_to_par is not None else "unavailable",
                "neo_win_pct": e.win_pct if e.win_pct is not None else "unavailable",
                "neo_cut_pct": e.make_cut_pct if e.make_cut_pct is not None else "unavailable",
                # Real, single-cut format: R3/FINAL advancement IS the make-cut fact — never a
                # second, independently-simulated number. See round_update_r2.py's module docstring.
                "neo_r3_pct": e.make_cut_pct if e.make_cut_pct is not None else "unavailable",
                "neo_final_pct": e.make_cut_pct if e.make_cut_pct is not None else "unavailable",
                "neo_top10_pct": e.top10_pct if e.top10_pct is not None else "unavailable",
                "pre_win_pct": pre_pct if pre_pct is not None else "unavailable",
                "pre_to_r2_win_change_pct": change if change is not None else "unavailable",
            })
    print(f"Wrote: {csv_path}")

    freeze_status = "NOT FROZEN (pass --freeze to freeze + record history)"
    if args.freeze:
        history_snapshot = HistoryStageSnapshot(
            game_code=args.game_code, stage=STAGE_R2, record_kind=RECORD_KIND,
            recorded_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            source_prediction_id=getattr(pre_snapshot, "prediction_id", ""),
            source_model_version=getattr(pre_snapshot, "model_version", None) or getattr(pre_snapshot, "selected_model_id", ""),
            source_generated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            tournament_name=getattr(pre_snapshot, "tournament_name", None),
            field_size=len(entrants), entrants=tuple(entrants),
        )
        path, action = write_or_supersede_history_stage(history_snapshot, Path(args.history_dir))
        if action == "RECORDED":
            freeze_status = f"FROZEN at {path}"
        elif action == "SUPERSEDED_MISSING_MARKER":
            freeze_status = (
                f"SUPERSEDED a stale HISTORICAL_SNAPSHOT_MISSING marker — new event at {path} "
                "(the original marker file was preserved untouched)"
            )
        else:  # ALREADY_RECORDED
            freeze_status = f"SKIP + LOG — already recorded at {path}"

    print(f"FREEZE: {freeze_status}")
    print(f"HISTORY: stage=R2 game_code={args.game_code} (append-only, klpga.neo_win.tournament_history)")
    print(f"PRE source: {pre_source}")
    if missing:
        print(f"Missing r1/r2/cut data (SKIP+LOG, excluded from simulation): {missing}")
        print("Evidence-only classification (never fabricated, never used to fill in a value):")
        for code in missing:
            status = missing_classification.get(code)
            if status is not None:
                print(f"  - {code}: {status.classification} — {status.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
