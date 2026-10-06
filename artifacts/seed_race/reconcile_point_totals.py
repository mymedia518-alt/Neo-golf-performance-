"""Reconcile a full-season mainRecord against the known official cumulative
point totals -- NOT RUNNABLE YET.

Status: blocked. See SEED_POINT_SYSTEM_GAP.md section 13.

This does exactly what the user asked for: sum each player's official
target_points across every 2026 tournament in mainrecord.csv, then compare
the sum against the already-confirmed cumulative point values (from
point_table_PARTIAL_2026-10-06.csv and point_values_bubble_55_80_2026-10-06.csv).
If a player's summed total does not match their known official cumulative
value, that's a real discrepancy to investigate (wrong tournament included,
missing row, wrong tie handling, etc.) -- NOT something to silently paper
over.

It refuses to run against mainrecord_TEMPLATE.csv as shipped (0 rows) --
there is no official 2026 KLPGA mainRecord data available in this session
(klpga.co.kr's record/mainRecord and tourInfo/record endpoints are both
blocked, same as every other klpga.co.kr path tried this session). Reverse-
engineering a fake set of per-tournament results that happens to sum to the
19 known totals would not be "reconstruction" -- it would be inventing
results that never happened, which this project does not do.

To actually run this:
  1. Fill mainrecord.csv (copy of mainrecord_TEMPLATE.csv) with real rows:
     one per (player, tournament) they played in 2026, with the *official*
     target_points shown for that finish (not estimated from money).
  2. Re-run with --confirm-real-data (required but not sufficient -- the
     guard also requires a minimum row count, since a handful of rows is
     not "the full season").
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MIN_ROWS = 500  # ~121 players x several events each; a handful of rows isn't a season


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def guard_real_data(mainrecord_path, confirmed: bool):
    problems = []
    rows = read_csv(mainrecord_path)
    if len(rows) == 0:
        problems.append(f"{mainrecord_path.name} has 0 data rows (still just the template header)")
    elif len(rows) < MIN_ROWS:
        problems.append(
            f"{mainrecord_path.name} has only {len(rows)} rows -- a full 2026 season across "
            f"~121 players is expected to be {MIN_ROWS}+; this looks partial"
        )
    if not confirmed:
        problems.append("--confirm-real-data flag not passed")
    if problems:
        raise RuntimeError(
            "REFUSING TO RUN -- mainRecord dataset is not yet complete enough to reconcile. "
            "See SEED_POINT_SYSTEM_GAP.md section 13 for what's needed. Problems: "
            + "; ".join(problems)
        )
    return rows


def known_official_totals(root: Path):
    """Pull the already-confirmed cumulative point totals we're reconciling against."""
    totals = {}
    for r in read_csv(root / "point_table_PARTIAL_2026-10-06.csv"):
        totals[r["player"]] = int(r["points"])
    for r in read_csv(root / "point_values_bubble_55_80_2026-10-06.csv"):
        if r["points_status"] == "CONFIRMED_VALUE":
            totals[r["player"]] = int(r["points"])
    return totals


def reconcile(mainrecord_rows, known_totals):
    summed = defaultdict(int)
    for row in mainrecord_rows:
        summed[row["player"]] += int(row["official_target_points"])

    report = []
    for player, known in known_totals.items():
        got = summed.get(player)
        if got is None:
            report.append((player, known, None, "NO_MAINRECORD_ROWS_FOUND"))
        elif got != known:
            report.append((player, known, got, "MISMATCH -- investigate, do not silently accept"))
        else:
            report.append((player, known, got, "MATCH"))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mainrecord", default=str(ROOT / "mainrecord_TEMPLATE.csv"))
    ap.add_argument("--confirm-real-data", action="store_true")
    a = ap.parse_args()

    rows = guard_real_data(Path(a.mainrecord), a.confirm_real_data)
    known = known_official_totals(ROOT)
    report = reconcile(rows, known)
    for player, known_total, summed_total, status in report:
        print(f"{player}: known={known_total} summed={summed_total} -> {status}")


if __name__ == "__main__":
    main()
