"""BETA #001-C Phase 11 — TOP20 red-team audit on an already-frozen
#001-C snapshot. Read-only DB connection for independent cross-checks
(identity crosswalk, field membership) only — never re-fits, never
re-derives the prediction, never writes to the DB.

Usage:
    python scripts/40_redteam_beta001c_top20.py --db data/klpga.sqlite \\
        --c-json neo_win_c_predictions/2026/neo_win_c_001-C_2026080001.json
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.redteam import red_team_top20  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001_c"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--c-json", required=True)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3
    c_path = Path(args.c_json)
    if not c_path.exists():
        print(f"ERROR: {c_path} does not exist.")
        return 3

    c_snapshot = read_neo_win_c_snapshot(c_path)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        reports = red_team_top20(c_snapshot, conn, top_n=args.top_n)
    finally:
        conn.close()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "BETA001C_TOP20_REDTEAM.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "player_code", "player_name", "status", "flags"])
        writer.writeheader()
        for r in reports:
            writer.writerow({**r, "flags": "; ".join(r["flags"])})

    print(f"=== BETA #001-C — TOP {args.top_n} RED-TEAM ===")
    print()
    counts: dict[str, int] = {}
    for r in reports:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"{r['rank']}. {r['player_name']} ({r['player_code']}) — {r['status']}")
        for flag in r["flags"]:
            print(f"     - {flag}")
    print()
    print("=== SUMMARY ===")
    print()
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    print()
    print(f"Wrote: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
