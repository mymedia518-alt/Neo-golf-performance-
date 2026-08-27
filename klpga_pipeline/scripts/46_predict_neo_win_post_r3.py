"""Roadmap next-step — BETA post-Round-3 snapshot. Combines the frozen
PRE prediction with the real, already-collected Round-1, Round-2, AND
Round-3 leaderboard (`player_round`, round_number 1/2/3) via
`klpga.neo_win.round_update_r3` (a NEW, parallel module — never touches
`klpga.neo_win.round_update` / `round_update_r2.py`, BETA #001-R1/R2's
own pipelines).

The cut is READ as a real fact from `player_event.made_cut` (settled
after Round 2 — see round_update_r2.py), never re-simulated. By Round 3
there is no cut/advancement probability left to report at all — see
round_update_r3.py's module docstring and docs/NEO_TOURNAMENT_DASHBOARD_
SPEC.md Section 3a ("R3 | WIN %, final-round outcome probabilities where
a real one is defined, CHANGE vs R2 | any recomputed cut/R3-qualification
number | round 3 has already been played; nothing left to forecast about
reaching it"). This script therefore never writes a cut/make-cut/R3/FINAL
-qualification column — only WIN %, TOP5/TOP10/TOP20 % (real, distinct
final-round outcome probabilities round_update_r3.py now computes), and
CHANGE vs the frozen R2 stage (read from tournament_history, NOT from
PRE — R2 is the correct movement baseline at this stage).

======================================================================
STATUS-AWARE READINESS (NOT a numeric coverage gate)
======================================================================
Readiness is decided by `klpga.neo_win.player_status.assess_field_
readiness` at round_number=3 — same status-aware GO/WARN/HARD_STOP rule
as scripts/44, reused without any round-specific duplication:
  - HARD_STOP: any player shows POSITIVE evidence of participation
    (rounds_played>=3, no CUT/WD/DQ explanation) with no round_number=3
    row (a real ingestion gap), or zero real round_number=3 rows exist
    at all (official R3 data hasn't arrived). Writes/freezes NOTHING.
  - WARN: no ingestion failure, but at least one player is UNKNOWN —
    still generates, but reports every UNKNOWN player explicitly.
  - GO: every entry-field player is accounted for by a legitimate,
    evidence-backed state (COMPLETED/WD/DQ/DNS/CUT) — generates.
Also HARD STOPS if any round_number=4 data already exists (future-data
leakage guard, same discipline as scripts/44's round_number=3 check).

Freezing = recording klpga.neo_win.tournament_history's STAGE_R3 stage
via write_or_supersede_history_stage (append-only; a real duplicate is
a SKIP+LOG no-op, never an overwrite; a stale HISTORICAL_SNAPSHOT_MISSING
marker is preserved untouched and corrected via a superseding event —
see tournament_history.py's module docstring). Never touches the
PRE/R1/R2 frozen artifacts.

Usage:
    python scripts/46_predict_neo_win_post_r3.py --db data/klpga.sqlite --game-code 2026080001 \\
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
from klpga.neo_win.player_status import (  # noqa: E402
    READINESS_HARD_STOP,
    READINESS_WARN,
    STATUS_COMPLETED,
    assess_field_readiness,
)
from klpga.neo_win.round_update_r3 import (  # noqa: E402
    DEFAULT_N_SIMULATIONS,
    build_r3_sim_inputs_from_frozen_snapshot,
    simulate_post_round3,
)
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_R2,
    STAGE_R3,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    read_effective_history_stage,
    write_or_supersede_history_stage,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_DIR = ROOT / "neo_win_predictions"
DEFAULT_C_PREDICTIONS_DIR = ROOT / "neo_win_c_predictions"
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta_r3"


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


def _r4_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 4", (game_code,)
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
            print("STATUS: READY_FOR_R3")
            print(f"R3 DATA: no tournament_entry field found for game_code={args.game_code!r} — nothing to check.")
            return 0

        r4_count = _r4_row_count(conn, args.game_code)
        if r4_count > 0:
            print("STATUS: HARD_STOP")
            print(f"REASON: {r4_count} round_number=4 row(s) already exist for game_code={args.game_code!r} — "
                  "this script only ever uses R1/R2/R3-confirmed data. Generating a POST-R3 snapshot now would "
                  "leak Round-4 information. Nothing written.")
            return 0

        readiness = assess_field_readiness(conn, args.game_code, round_number=3)
        status_by_code = {s.player_code: s for s in readiness.statuses}
        if readiness.verdict == READINESS_HARD_STOP:
            print("STATUS: HARD_STOP")
            print(f"REASON: {readiness.reason}")
            return 0

        r3_scores = _read_round_scores(conn, args.game_code, 3)
        r2_scores = _read_round_scores(conn, args.game_code, 2)
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

        sim_inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(
            pre_snapshot, r1_scores, r2_scores, r3_scores, made_cut
        )
    finally:
        conn.close()

    rng = __import__("random").Random(args.seed) if args.seed is not None else None
    sim_result = simulate_post_round3(sim_inputs, n_simulations=args.n_simulations, rng=rng)

    # R2->R3 movement baseline: the FROZEN R2 stage, not PRE — R2's WIN % is
    # the correct "where we stood before this round" reference at this stage.
    r2_history = read_effective_history_stage(Path(args.history_dir), args.game_code, STAGE_R2)
    r2_win_by_code = {e.player_code: e.win_pct for e in r2_history.entrants} if r2_history is not None else {}

    positions_ordered = sorted(
        (
            (r1_scores.get(c, 0) + r2_scores.get(c, 0) + r3_scores.get(c, 0), c)
            for c in r3_scores if c in r1_scores and c in r2_scores
        ),
        key=lambda t: t[0],
    )
    position_by_code = {c: i + 1 for i, (_score, c) in enumerate(positions_ordered)}

    entrants = []
    for inp in sim_inputs:
        code = inp.player_code
        sim = sim_result.get(code)
        win_pct = sim["win_pct"] if sim else None
        top5_pct = sim["top5_pct"] if sim else None
        top10_pct = sim["top10_pct"] if sim else None
        top20_pct = sim["top20_pct"] if sim else None
        has_full_score = code in r1_scores and code in r2_scores and code in r3_scores
        entrants.append(
            HistoryEntrant(
                player_code=code, player_name=inp.player_name, win_pct=win_pct,
                top5_pct=top5_pct, top10_pct=top10_pct, top20_pct=top20_pct,
                position=position_by_code.get(code),
                score_to_par=(r1_scores[code] + r2_scores[code] + r3_scores[code]) if has_full_score else None,
            )
        )

    duplicate_count = len(entrants) - len({e.player_code for e in entrants})
    win_values = [e.win_pct for e in entrants if e.win_pct is not None]
    win_sum = sum(win_values)
    null_count = sum(1 for e in entrants if e.win_pct is None)
    non_field_count = 0  # entrants are built 1:1 from pre_snapshot.predictions, already the frozen field

    print("=== BETA POST-R3 ===")
    print()
    print(f"STATUS: DATA_COMPLETE (readiness verdict: {readiness.verdict})")
    print(f"R3 DATA: {len(r3_scores)}/{field_size} entry-field players have a real round_number=3 score "
          f"(field size != completed-round size — see klpga.neo_win.player_status)")
    print(f"PLAYERS: {len(entrants)}")
    print(f"WIN SUM: {win_sum:.4f}%  (over {len(win_values)} players with a real simulated value)")
    print(f"VALIDATION: duplicates={duplicate_count} nulls={null_count} non_field={non_field_count} "
          f"missing_r1_r2_r3_or_cut={len(missing)}")
    if r2_history is None:
        print("WARN: no frozen R2 stage found in tournament_history — R2->R3 CHANGE will be 'unavailable' for every player.")
    if readiness.verdict == READINESS_WARN:
        print(f"WARN: {readiness.reason}")
    print()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "BETA_R3_FULL.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "player_code", "player_name", "player_status", "position", "score_to_par",
            "neo_win_pct", "neo_top5_pct", "neo_top10_pct", "neo_top20_pct",
            "r2_win_pct", "r2_to_r3_win_change_pct",
        ])
        writer.writeheader()
        for e in entrants:
            r2_pct = r2_win_by_code.get(e.player_code)
            change = (e.win_pct - r2_pct) if (e.win_pct is not None and r2_pct is not None) else None
            player_status_entry = status_by_code.get(e.player_code)
            # ACTIVE is the display label for STATUS_COMPLETED here (a player with a real R3 score) —
            # every other value (WD/DQ/DNS/CUT/UNKNOWN/COLLECTION_MISSING) is the classification as-is.
            # Never fabricated: unresolved/terminal players simply carry "unavailable" probability fields.
            if player_status_entry is None:
                player_status_label = "unavailable"
            elif player_status_entry.classification == STATUS_COMPLETED:
                player_status_label = "ACTIVE"
            else:
                player_status_label = player_status_entry.classification
            writer.writerow({
                "player_code": e.player_code, "player_name": e.player_name, "player_status": player_status_label,
                "position": e.position if e.position is not None else "unavailable",
                "score_to_par": e.score_to_par if e.score_to_par is not None else "unavailable",
                "neo_win_pct": e.win_pct if e.win_pct is not None else "unavailable",
                "neo_top5_pct": e.top5_pct if e.top5_pct is not None else "unavailable",
                "neo_top10_pct": e.top10_pct if e.top10_pct is not None else "unavailable",
                "neo_top20_pct": e.top20_pct if e.top20_pct is not None else "unavailable",
                "r2_win_pct": r2_pct if r2_pct is not None else "unavailable",
                "r2_to_r3_win_change_pct": change if change is not None else "unavailable",
            })
    print(f"Wrote: {csv_path}")

    freeze_status = "NOT FROZEN (pass --freeze to freeze + record history)"
    if args.freeze:
        history_snapshot = HistoryStageSnapshot(
            game_code=args.game_code, stage=STAGE_R3, record_kind=RECORD_KIND,
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
    print(f"HISTORY: stage=R3 game_code={args.game_code} (append-only, klpga.neo_win.tournament_history)")
    print(f"PRE source: {pre_source}")
    if missing:
        print(f"Missing r1/r2/r3/cut data (SKIP+LOG, excluded from simulation): {missing}")
        print("Evidence-only classification (never fabricated, never used to fill in a value):")
        for code in missing:
            status = status_by_code.get(code)
            if status is not None:
                print(f"  - {code}: {status.classification} — {status.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
