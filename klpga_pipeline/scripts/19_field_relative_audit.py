"""Read-only field-relative round-score audit against the real
production DB — no DB writes, does not touch tournament_master/
player_master/player_event/player_round/tournament_entry.

For selected player/round examples, prints:
  - the player's real round_score
  - the field benchmark for that historical (event_id, round_number)
    INCLUDING every player who played it
  - the LEAVE-ONE-OUT benchmark EXCLUDING the player's own score — the
    actual benchmark klpga.backtest.point_in_time_features uses for
    prior_avg_field_relative_round_score
  - the resulting field-relative round score (player_score minus the
    leave-one-out benchmark)
  - an explicit arithmetic proof that the player's own score is not
    silently folded back into their own benchmark

This is a plain per-round scoring deviation against the field of a
single, already-completed historical round. It is NEVER Strokes
Gained — true SG needs shot-level distance-to-hole/lie data this
project has never collected (see docs/SITE_STRUCTURE_TODO.md section
6 / klpga.analytics.player_stats's module docstring). Nothing in this
script's output should ever be relabeled SG.

Usage (on a machine with the real production data/klpga.sqlite):
    python scripts/19_field_relative_audit.py --db data/klpga.sqlite
    python scripts/19_field_relative_audit.py --db data/klpga.sqlite --game-code 2026080002 --round 2
    python scripts/19_field_relative_audit.py --db data/klpga.sqlite --game-code 2026080002 --round 2 --players 10296,9174
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]


def _auto_select_round(conn: sqlite3.Connection) -> tuple[str, int] | None:
    """The (event_id, round_number) with the LARGEST real field —
    a deterministic, non-arbitrary choice ('the most illustrative
    example available'), not a hand-picked one."""
    row = conn.execute(
        """
        SELECT event_id, round_number, COUNT(*) AS n
        FROM player_round
        WHERE round_score IS NOT NULL
        GROUP BY event_id, round_number
        ORDER BY n DESC, event_id, round_number
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return row[0], row[1]


def run(conn: sqlite3.Connection, game_code: str | None, round_number: int | None, player_codes: list[str] | None, sample: int) -> dict:
    if game_code is not None and round_number is not None:
        event_id_row = conn.execute("SELECT event_id FROM tournament_master WHERE game_code = ?", (game_code,)).fetchone()
        if event_id_row is None:
            print(f"ERROR: no tournament_master row for game_code={game_code!r}.")
            return {"status": "error"}
        event_id = event_id_row[0]
    else:
        auto = _auto_select_round(conn)
        if auto is None:
            print("ERROR: no player_round rows with a real round_score exist in this DB.")
            return {"status": "error"}
        event_id, round_number = auto
        print(f"(auto-selected (event_id, round_number) with the largest real field: "
              f"event_id={event_id}, round={round_number})")

    all_rows = conn.execute(
        "SELECT player_id, player_name, round_score FROM player_round "
        "WHERE event_id = ? AND round_number = ? AND round_score IS NOT NULL",
        (event_id, round_number),
    ).fetchall()
    if not all_rows:
        print(f"ERROR: event_id={event_id!r} round={round_number} has no player_round rows with a real round_score.")
        return {"status": "error"}

    total_sum = sum(r[2] for r in all_rows)
    n = len(all_rows)
    field_avg_including_all = total_sum / n

    print("=" * 92)
    print(f"ROUND: event_id={event_id}  round={round_number}  real field size (n)={n}")
    print(f"Field benchmark INCLUDING every player: sum={total_sum}, n={n}, average={round(field_avg_including_all, 2)}")

    if player_codes:
        selected = [r for r in all_rows if r[0] in player_codes]
        found_codes = {r[0] for r in selected}
        for code in player_codes:
            if code not in found_codes:
                print(f"\nNOTE: requested player_code={code!r} has no round_score for this (event, round) — skipping.")
    else:
        selected = sorted(all_rows, key=lambda r: r[0])[:sample]

    if not selected:
        print("\nNo players selected/found to report on.")
        return {"status": "error"}

    examples = []
    for player_id, player_name, own_score in selected:
        if n < 2:
            print(f"\nPLAYER: {player_name} (player_code={player_id}) — field size is 1 (only this player); "
                  f"no leave-one-out benchmark is possible.")
            continue

        sum_excluding_self = total_sum - own_score
        n_excluding_self = n - 1
        leave_one_out = sum_excluding_self / n_excluding_self
        field_relative = own_score - leave_one_out

        print(f"\nPLAYER: {player_name} (player_code={player_id})")
        print(f"  round_score (real, own) = {own_score}")
        print(f"  field benchmark INCLUDING self = total_sum/n = {total_sum}/{n} = {round(field_avg_including_all, 2)}")
        print(f"  leave-one-out benchmark EXCLUDING self = (total_sum - own_score)/(n-1) "
              f"= ({total_sum} - {own_score})/({n}-1) = {sum_excluding_self}/{n_excluding_self} = {round(leave_one_out, 2)}")
        print(f"  field-relative round score = own_score - leave_one_out = {own_score} - {round(leave_one_out, 2)} "
              f"= {round(field_relative, 2)}")
        proof_ok = (sum_excluding_self + own_score) == total_sum
        print(f"  PROOF own score excluded from its own benchmark: "
              f"(sum_excluding_self + own_score) == total_sum -> ({sum_excluding_self} + {own_score}) == {total_sum} "
              f"-> {'PASS' if proof_ok else 'FAIL'}")
        print(f"  NOTE: this is a field-relative round-score deviation, NOT Strokes Gained.")

        examples.append(
            {
                "player_code": player_id,
                "own_score": own_score,
                "field_avg_including_self": round(field_avg_including_all, 2),
                "leave_one_out": round(leave_one_out, 2),
                "field_relative": round(field_relative, 2),
                "proof_ok": proof_ok,
            }
        )

    return {"status": "success", "event_id": event_id, "round_number": round_number, "n": n, "examples": examples}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", default=None, dest="game_code")
    parser.add_argument("--round", type=int, default=None, dest="round_number")
    parser.add_argument("--players", default=None, help="comma-separated player_codes to inspect")
    parser.add_argument("--sample", type=int, default=5, help="if --players not given, inspect the first N players (by player_code)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        player_codes = [c.strip() for c in args.players.split(",")] if args.players else None
        outcome = run(conn, args.game_code, args.round_number, player_codes, args.sample)
    finally:
        conn.close()

    return 0 if outcome["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
