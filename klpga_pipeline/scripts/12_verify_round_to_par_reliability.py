"""Red-team verification for `derived_avg_round_score_to_par` (see
src/klpga/analytics/player_stats.py) and an independent reliability
check of `player_round.round_to_par` (`data-todayunderpar`) against the
REAL production DB — do NOT assume this field is trustworthy just
because it exists; this script checks it.

`derived_avg_round_score_to_par` is computed as sum(player_event.
score_to_par) / sum(player_event.rounds_played) — a per-round RATE
built from tournament-total figures, NOT from averaging the real
per-round `round_to_par` field directly (that field's coverage is real
but partial — see klpga.collectors.leaderboard's docstring: round 1 and
the final round are always queried, other rounds only when a player
dropped out of the field before the final round). This script checks,
using ONLY real production rows, whether that choice is actually
correct — i.e. whether using round_to_par directly WOULD give the same
answer wherever there happens to be enough of it to check.

Two independent checks, neither relying on an additivity assumption
alone:

  CHECK A (no assumption needed): for a player with exactly ONE valid
  round (rounds_played == 1), "today's round" and "the tournament total
  so far" are the SAME thing by definition — round_to_par for that
  single round and score_to_par for the event MUST be identical if both
  fields mean what this project believes they mean. Any mismatch here
  is unambiguous evidence something is misunderstood.

  CHECK B (tests additivity): for a player whose event has round_to_par
  present on EVERY round they played (rounds_played >= 2), if per-round
  to-par values are genuine independent daily deltas, they must sum to
  the tournament's score_to_par. Any systematic mismatch (not just
  isolated rounding noise — both fields are integers, so any real
  disagreement shows up as a clean non-zero difference) is evidence
  round_to_par does NOT mean what a naive reading suggests (e.g. it
  might actually be cumulative-to-that-point, same as total_under_par,
  rather than a true single-round delta).

  CROSS-CHECK: for the CHECK B subset, derived_avg_round_score_to_par's
  rate formula (sum(score_to_par)/sum(rounds_played)) is compared
  against a DIRECT reconstruction from the raw round_to_par values
  (sum(round_to_par)/count(rounds)) — restricted to that subset, these
  two must come out equal (both numerator and denominator are literally
  the same sums when coverage is full), which is the actual proof that
  the rate formula is mathematically consistent with real per-round
  data wherever there's enough of it to check.

Read-only: only SELECTs from player_event/player_round. Never writes
anything.

Usage:
    python scripts/12_verify_round_to_par_reliability.py --db data/klpga.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _coverage_stats(conn: sqlite3.Connection) -> dict:
    total_rounds = conn.execute("SELECT COUNT(*) FROM player_round").fetchone()[0]
    covered_rounds = conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE round_to_par IS NOT NULL"
    ).fetchone()[0]
    return {"total_rounds": total_rounds, "covered_rounds": covered_rounds}


def _check_a_single_round(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT pe.player_id, pe.event_id, pe.score_to_par, pr.round_to_par
        FROM player_event pe
        JOIN player_round pr ON pr.event_id = pe.event_id AND pr.player_id = pe.player_id
        WHERE pe.rounds_played = 1 AND pe.score_to_par IS NOT NULL AND pr.round_to_par IS NOT NULL
        """
    ).fetchall()
    mismatches = [r for r in rows if r["round_to_par"] != r["score_to_par"]]
    return {"checked": len(rows), "exact_matches": len(rows) - len(mismatches), "mismatches": mismatches}


def _check_b_full_coverage(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT pe.player_id, pe.event_id, pe.score_to_par, pe.rounds_played,
               COUNT(pr.round_to_par) AS covered_rounds,
               SUM(pr.round_to_par) AS sum_round_to_par
        FROM player_event pe
        JOIN player_round pr ON pr.event_id = pe.event_id AND pr.player_id = pe.player_id
        WHERE pe.rounds_played >= 2 AND pe.score_to_par IS NOT NULL
        GROUP BY pe.player_id, pe.event_id
        HAVING covered_rounds = pe.rounds_played
        """
    ).fetchall()
    total_multi_round_events = conn.execute(
        "SELECT COUNT(*) FROM player_event WHERE rounds_played >= 2 AND score_to_par IS NOT NULL"
    ).fetchone()[0]

    mismatches = [r for r in rows if r["sum_round_to_par"] != r["score_to_par"]]
    diffs = [r["sum_round_to_par"] - r["score_to_par"] for r in rows]

    rate_from_totals_num = sum(r["score_to_par"] for r in rows)
    rate_from_totals_den = sum(r["rounds_played"] for r in rows)
    rate_from_raw_num = sum(r["sum_round_to_par"] for r in rows)
    rate_from_raw_den = sum(r["covered_rounds"] for r in rows)

    return {
        "total_multi_round_events": total_multi_round_events,
        "fully_covered_events": len(rows),
        "exact_matches": len(rows) - len(mismatches),
        "mismatches": mismatches,
        "diffs": diffs,
        "rate_from_totals": rate_from_totals_num / rate_from_totals_den if rate_from_totals_den else None,
        "rate_from_raw_rounds": rate_from_raw_num / rate_from_raw_den if rate_from_raw_den else None,
    }


def verify(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        coverage = _coverage_stats(conn)
        check_a = _check_a_single_round(conn)
        check_b = _check_b_full_coverage(conn)
    finally:
        conn.close()

    print("=" * 100)
    print("round_to_par (data-todayunderpar) COVERAGE across all collected player_round rows")
    print("=" * 100)
    pct = (coverage["covered_rounds"] / coverage["total_rounds"] * 100) if coverage["total_rounds"] else 0.0
    print(
        f"{coverage['covered_rounds']} / {coverage['total_rounds']} player_round rows have a "
        f"non-NULL round_to_par ({pct:.1f}%)"
    )
    print(
        "Partial coverage is EXPECTED (round 1 and the final round are always queried; "
        "other rounds only when the field had a dropout) — not itself a defect.\n"
    )

    print("=" * 100)
    print("CHECK A: rounds_played == 1 -> round_to_par MUST equal score_to_par (no assumption needed)")
    print("=" * 100)
    print(f"checked: {check_a['checked']}   exact matches: {check_a['exact_matches']}")
    if check_a["mismatches"]:
        print(f"⚠ {len(check_a['mismatches'])} MISMATCH(ES):")
        for r in check_a["mismatches"][:10]:
            print(
                f"    player_id={r['player_id']} event_id={r['event_id']} "
                f"round_to_par={_fmt(r['round_to_par'])} score_to_par={_fmt(r['score_to_par'])}"
            )
    else:
        print("no mismatches — round_to_par and score_to_par agree exactly for every single-round player checked.\n")

    print("=" * 100)
    print("CHECK B: rounds_played >= 2 with FULL round_to_par coverage -> sum(round_to_par) MUST equal score_to_par")
    print("=" * 100)
    print(
        f"multi-round events with a real score_to_par: {check_b['total_multi_round_events']}   "
        f"fully covered (every round has round_to_par): {check_b['fully_covered_events']}"
    )
    print(f"exact matches: {check_b['exact_matches']} / {check_b['fully_covered_events']}")
    if check_b["diffs"]:
        mean_abs_diff = sum(abs(d) for d in check_b["diffs"]) / len(check_b["diffs"])
        max_abs_diff = max(abs(d) for d in check_b["diffs"])
        print(f"mean(|sum(round_to_par) - score_to_par|) = {mean_abs_diff:.2f}   max = {max_abs_diff}")
    if check_b["mismatches"]:
        print(f"⚠ {len(check_b['mismatches'])} MISMATCH(ES), first 10:")
        for r in check_b["mismatches"][:10]:
            print(
                f"    player_id={r['player_id']} event_id={r['event_id']} rounds_played={r['rounds_played']} "
                f"sum(round_to_par)={_fmt(r['sum_round_to_par'])} score_to_par={_fmt(r['score_to_par'])}"
            )
    else:
        print("no mismatches — round_to_par values sum exactly to score_to_par for every fully-covered event checked.")
    print()

    print("=" * 100)
    print("CROSS-CHECK: derived_avg_round_score_to_par's rate formula vs. a direct round_to_par reconstruction")
    print("(restricted to the CHECK B fully-covered subset)")
    print("=" * 100)
    print(f"sum(score_to_par)/sum(rounds_played)        = {_fmt(check_b['rate_from_totals'])}")
    print(f"sum(round_to_par)/count(rounds), raw field   = {_fmt(check_b['rate_from_raw_rounds'])}")
    if check_b["rate_from_totals"] is not None and check_b["rate_from_raw_rounds"] is not None:
        agree = round(check_b["rate_from_totals"], 2) == round(check_b["rate_from_raw_rounds"], 2)
        print("=> AGREE" if agree else "=> DISAGREE — investigate before trusting derived_avg_round_score_to_par")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    return verify(db_path)


if __name__ == "__main__":
    raise SystemExit(main())
