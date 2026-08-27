"""BETA #001-C Phase 10 — full BETA #001 vs BETA #001-C comparison.
Read-only: reads the two already-frozen snapshot files (never a live
DB connection, never re-derives either prediction) and reports
PRE_001_WIN_PCT / CORRECTED_001C_WIN_PCT / DELTA / OLD_RANK / NEW_RANK
/ RANK_CHANGE for every player in either snapshot, plus biggest
risers/fallers/rank-changes.

Per the release's explicit instruction, this script reports numbers
ONLY — it never characterizes a probability increase as evidence the
correction "worked." Pass --highlight with the exact real player_name
string(s) from your own database (this script never guesses or
hardcodes a Korean name spelling) to get full before/after detail for
specific players (e.g. --highlight 서교림 박현경).

Usage:
    python scripts/39_compare_beta001_vs_c.py \\
        --pre-001-json neo_win_predictions/2026/neo_win_001_2026080001.json \\
        --c-json neo_win_c_predictions/2026/neo_win_c_001-C_2026080001.json \\
        --highlight 서교림 박현경
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.beta001c_archive import read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.comparison import compare_beta001_to_beta001c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001_c"


def _fmt(value) -> str:
    return "—" if value is None else f"{value:.4f}"


def print_report(comparison: dict, highlight_names) -> None:
    print("=== BETA #001 vs BETA #001-C ===")
    print()
    print(f"Players compared: {len(comparison['rows'])}")
    print()
    print("=== BIGGEST WIN % RISERS ===")
    print()
    for r in comparison["biggest_risers"]:
        print(f"{r.player_name} ({r.player_code}): {_fmt(r.pre_001_win_pct)}% -> {_fmt(r.corrected_001c_win_pct)}% "
              f"(delta {_fmt(r.delta_pct)}) rank {r.old_rank}->{r.new_rank}")
    print()
    print("=== BIGGEST WIN % FALLERS ===")
    print()
    for r in comparison["biggest_fallers"]:
        print(f"{r.player_name} ({r.player_code}): {_fmt(r.pre_001_win_pct)}% -> {_fmt(r.corrected_001c_win_pct)}% "
              f"(delta {_fmt(r.delta_pct)}) rank {r.old_rank}->{r.new_rank}")
    print()
    print("=== BIGGEST RANK CHANGES ===")
    print()
    for r in comparison["biggest_rank_changes"]:
        print(f"{r.player_name} ({r.player_code}): rank {r.old_rank} -> {r.new_rank} (change {r.rank_change:+d})")
    print()
    if highlight_names:
        print("=== HIGHLIGHTED PLAYERS ===")
        print()
        for name in highlight_names:
            r = comparison["highlighted"].get(name)
            if r is None:
                print(f"{name}: NOT FOUND in either snapshot")
                continue
            print(f"{name} ({r.player_code}): PRE_001={_fmt(r.pre_001_win_pct)}% "
                  f"CORRECTED_001C={_fmt(r.corrected_001c_win_pct)}% DELTA={_fmt(r.delta_pct)} "
                  f"OLD_RANK={r.old_rank} NEW_RANK={r.new_rank} RANK_CHANGE={r.rank_change}")
        print()
    print("Note: a higher or lower probability alone is not evidence the correction worked. "
          "See BETA001C_MODEL_REPORT.md / MODEL_BACKTEST.md for whether the selected model actually "
          "passed historical out-of-sample validation.")


def _write_csv(comparison: dict, output_path: Path) -> None:
    fieldnames = [
        "player_code", "player_name", "pre_001_win_pct", "corrected_001c_win_pct", "delta_pct",
        "old_rank", "new_rank", "rank_change", "in_pre_001_only", "in_001c_only",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(comparison["rows"], key=lambda row: (row.new_rank is None, row.new_rank or 0)):
            writer.writerow({
                "player_code": r.player_code, "player_name": r.player_name,
                "pre_001_win_pct": "" if r.pre_001_win_pct is None else r.pre_001_win_pct,
                "corrected_001c_win_pct": "" if r.corrected_001c_win_pct is None else r.corrected_001c_win_pct,
                "delta_pct": "" if r.delta_pct is None else r.delta_pct,
                "old_rank": "" if r.old_rank is None else r.old_rank,
                "new_rank": "" if r.new_rank is None else r.new_rank,
                "rank_change": "" if r.rank_change is None else r.rank_change,
                "in_pre_001_only": r.in_pre_001_only, "in_001c_only": r.in_001c_only,
            })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pre-001-json", required=True, help="Path to the frozen BETA #001 PRE snapshot JSON.")
    parser.add_argument("--c-json", required=True, help="Path to the frozen BETA #001-C snapshot JSON.")
    parser.add_argument("--highlight", nargs="*", default=[], help="Exact real player_name string(s) to detail.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    pre_path = Path(args.pre_001_json)
    c_path = Path(args.c_json)
    if not pre_path.exists():
        print(f"ERROR: {pre_path} does not exist.")
        return 3
    if not c_path.exists():
        print(f"ERROR: {c_path} does not exist.")
        return 3

    pre_snapshot = read_neo_win_snapshot(pre_path)
    c_snapshot = read_neo_win_c_snapshot(c_path)
    if pre_snapshot.game_code != c_snapshot.game_code:
        print(f"ERROR: game_code mismatch — PRE 001 is {pre_snapshot.game_code!r}, "
              f"001-C is {c_snapshot.game_code!r}. Refusing to compare different tournaments.")
        return 5

    comparison = compare_beta001_to_beta001c(pre_snapshot, c_snapshot, highlighted_names=tuple(args.highlight))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "BETA001_VS_001C_COMPARISON.csv"
    _write_csv(comparison, csv_path)

    print_report(comparison, args.highlight)
    print()
    print(f"Wrote: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
