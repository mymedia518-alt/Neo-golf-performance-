"""Read-only walk-forward eligibility report against the real production
DB — no DB writes, does not touch tournament_master/player_master/
player_event/player_round/tournament_entry.

POPULATION REPORTED: this script's rows are the ELIGIBLE-AT-THRESHOLD-k
population (see klpga.backtest.walk_forward's module docstring for the
canonical definitions) — a THRESHOLD-FILTERED SUBSET of every USABLE
target tournament (a tournament_master row with a resolvable date and a
non-empty field). scripts/21_data_coverage_report.py reports that full
USABLE population UNCONDITIONALLY (no threshold filter at all) — this
script's threshold=0 row is DEFINITIONALLY identical to it (proven in
tests/test_population_definitions.py), but any threshold>0 row is, BY
DESIGN, a strictly smaller number. Do not compare a threshold>0 row here
against script 21's total and expect them to match — that difference is
the trade-off this script exists to show, not a bug.

For a range of candidate "minimum prior tournaments required" values,
prints:
  - number of target tournaments ELIGIBLE at that threshold
  - percentage of the corpus (every USABLE target tournament) retained
  - number of player-target rows ELIGIBLE at that threshold
  - earliest eligible target tournament / date at that threshold
  - median (and mean) prior_events_n among eligible player-target rows
  - % of eligible rows with zero prior events, and with <5/<10/<20

This script does NOT choose a threshold — see
klpga.backtest.walk_forward's module docstring. It only surfaces the
empirical trade-off (more history required -> fewer eligible target
tournaments, but higher-quality features on the ones that remain) for
a human to decide on later, at the model-design gate.

Usage (on a machine with the real production data/klpga.sqlite):
    python scripts/17_eligibility_report.py --db data/klpga.sqlite
    python scripts/17_eligibility_report.py --db data/klpga.sqlite --thresholds 0,1,2,3,5,10,20,30
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.backtest.walk_forward import (  # noqa: E402
    DEFAULT_ELIGIBILITY_THRESHOLDS,
    build_walk_forward_dataset,
    eligibility_sweep,
)

ROOT = Path(__file__).resolve().parents[1]

_COLUMNS = [
    ("threshold", "min prior\ntournaments", 12),
    ("eligible_tournament_count", "eligible\ntargets", 10),
    ("pct_of_corpus_retained", "% of\nusable", 8),
    ("eligible_field_row_count", "eligible\nrows", 13),
    ("earliest_eligible_target_start_date", "earliest\neligible date", 14),
    ("earliest_eligible_target_game_code", "earliest\ngame_code", 12),
    ("median_prior_events_n", "median\nprior_n", 9),
    ("mean_prior_events_n", "mean\nprior_n", 9),
    ("pct_zero_prior_events", "% zero\nprior", 8),
    ("pct_lt_5_prior_events", "% <5\nprior", 8),
    ("pct_lt_10_prior_events", "% <10\nprior", 8),
    ("pct_lt_20_prior_events", "% <20\nprior", 8),
]


def format_report(sweep: list[dict], total_tournament_count: int) -> str:
    lines = [
        f"USABLE population (unconditional — every tournament_master row with a resolvable date "
        f"and a non-empty field; same population scripts/21_data_coverage_report.py reports): "
        f"{total_tournament_count} tournament(s).",
        "Rows below are the ELIGIBLE-AT-THRESHOLD-k SUBSET of that population — 'eligible targets' "
        "at threshold=0 equals the usable count above exactly; any threshold>0 row is, by design, "
        "smaller (see klpga.backtest.walk_forward's module docstring).",
    ]
    header_lines = [""] * 2
    for _, label, width in _COLUMNS:
        parts = label.split("\n")
        header_lines[0] += parts[0].rjust(width) + " "
        header_lines[1] += parts[1].rjust(width) + " "
    lines.append(header_lines[0])
    lines.append(header_lines[1])
    lines.append("-" * len(header_lines[1]))

    for row in sweep:
        line = ""
        for key, _, width in _COLUMNS:
            value = row.get(key)
            line += (str(value) if value is not None else "-").rjust(width) + " "
        lines.append(line)
    return "\n".join(lines)


def run(conn: sqlite3.Connection, thresholds: tuple[int, ...]) -> str:
    result = build_walk_forward_dataset(conn)
    if result.skipped_no_date_event_ids:
        print(
            f"NOTE: {len(result.skipped_no_date_event_ids)} tournament(s) skipped entirely "
            f"(no resolvable effective date): {result.skipped_no_date_event_ids}"
        )
    if result.skipped_empty_field_event_ids:
        print(
            f"NOTE: {len(result.skipped_empty_field_event_ids)} tournament(s) skipped "
            f"(empty reconstructed field): {result.skipped_empty_field_event_ids}"
        )

    sweep = eligibility_sweep(result, thresholds=thresholds)
    report = format_report(sweep, result.total_tournament_count)
    print(report)
    print(
        "\nNo threshold is chosen by this script — pick one (or several, for an ensemble/"
        "sensitivity check) at the model-design gate, informed by this trade-off."
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument(
        "--thresholds",
        default=None,
        help="comma-separated list of minimum-prior-tournament thresholds to report "
        f"(default: {DEFAULT_ELIGIBILITY_THRESHOLDS})",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    thresholds = (
        tuple(int(t.strip()) for t in args.thresholds.split(","))
        if args.thresholds
        else DEFAULT_ELIGIBILITY_THRESHOLDS
    )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        run(conn, thresholds)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
