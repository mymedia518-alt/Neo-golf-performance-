"""Roadmap next-step — FINAL stage recording. A thin CLI wrapper around
`klpga.neo_win.tournament_history.build_final_stage_entry`, which
already exists (built in an earlier round) and needs no changes: it
reads the REAL, already-collected actual result straight from
`tournament_master.winner` joined to `player_event` (finish_position_
numeric, score_to_par, made_cut/withdrawn/disqualified) — the same
"confirmed win requires BOTH finish_position_numeric==1 AND the winner
NAME field agreeing" convention `klpga.neo_win.audit.audit_2026_season`
already established. This script performs NO simulation, NO probability
computation, and NO model logic of any kind — FINAL is a pure, already-
decided RESULT (see docs/NEO_TOURNAMENT_DASHBOARD_SPEC.md Section 3a /
the "already decided = RESULT, not yet decided = PROBABILITY" rule).

======================================================================
READ-ONLY GUARD — a real winner must actually be determined
======================================================================
Before calling build_final_stage_entry, this script checks that
`tournament_master.winner` is non-NULL/non-empty for game_code. If not,
it reports STATUS: NOT_YET_FINAL and writes/freezes NOTHING — never
fabricates a winner, never guesses the tournament is over from a score
alone.

Freezing = recording klpga.neo_win.tournament_history's STAGE_FINAL
stage via write_or_supersede_history_stage (append-only; a real
duplicate is a SKIP+LOG no-op, never an overwrite; a stale HISTORICAL_
SNAPSHOT_MISSING marker is preserved untouched and corrected via a
superseding event). Never touches the PRE/R1/R2/R3 frozen artifacts.

Usage:
    python scripts/47_record_final_result.py --db data/klpga.sqlite --game-code 2026080001 --freeze
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_FINAL,
    build_final_stage_entry,
    write_or_supersede_history_stage,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"


def _real_winner(conn: sqlite3.Connection, game_code: str):
    row = conn.execute(
        "SELECT winner FROM tournament_master WHERE game_code = ?", (game_code,)
    ).fetchone()
    if row is None:
        return None
    winner = row[0]
    return winner if winner else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--source-prediction-id", default="001-C")
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        winner = _real_winner(conn, args.game_code)
        if winner is None:
            print("STATUS: NOT_YET_FINAL")
            print(f"REASON: tournament_master.winner is NULL/empty for game_code={args.game_code!r} — "
                  "the tournament is not yet confirmed complete. Nothing written.")
            return 0

        recorded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = build_final_stage_entry(
            conn, args.game_code, source_prediction_id=args.source_prediction_id, recorded_at_utc=recorded_at
        )
    finally:
        conn.close()

    confirmed_winners = [e for e in entry.entrants if e.actual_confirmed_winner]
    unconfirmed_note = ""
    if not confirmed_winners:
        unconfirmed_note = (
            " (tournament_master.winner is set, but no player_event row's finish_position_numeric==1 AND "
            "name matched it — real, disclosed discrepancy, not fabricated)"
        )

    print("=== BETA FINAL RESULT ===")
    print()
    print("STATUS: FINAL_CONFIRMED")
    print(f"TOURNAMENT: {entry.tournament_name}")
    print(f"WINNER (tournament_master.winner): {winner}")
    print(f"CONFIRMED WINNER PLAYER(S) (finish_position_numeric==1 AND name match): "
          f"{[e.player_code for e in confirmed_winners] or 'NONE'}{unconfirmed_note}")
    print(f"FIELD SIZE: {entry.field_size}")
    print(f"ENTRANTS RECORDED: {len(entry.entrants)}")
    print()

    freeze_status = "NOT FROZEN (pass --freeze to freeze + record history)"
    if args.freeze:
        path, action = write_or_supersede_history_stage(entry, Path(args.history_dir))
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
    print(f"HISTORY: stage=FINAL game_code={args.game_code} (append-only, klpga.neo_win.tournament_history)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
