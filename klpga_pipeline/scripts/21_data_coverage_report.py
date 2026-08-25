"""Read-only feature coverage report against the real production DB —
no DB writes, does not touch tournament_master/player_master/
player_event/player_round/tournament_entry.

POPULATION REPORTED: every USABLE target tournament (a tournament_master
row with a resolvable date and a non-empty field — see
klpga.backtest.walk_forward's module docstring for the canonical
definition), UNCONDITIONALLY — this script applies NO minimum-prior-
history filter. This is the SAME population as
scripts/17_eligibility_report.py's threshold=0 row (proven identical in
tests/test_population_definitions.py); any threshold>0 row in that
script reports a strictly smaller, ELIGIBLE-AT-THRESHOLD-k subset — do
not expect this script's totals to match that script's non-zero
thresholds, they answer different questions on purpose.

For the real walk-forward dataset (klpga.backtest.walk_forward), reports
actual coverage of the sparser/derived point-in-time features:
  - prior_avg_round_score_to_par
  - prior_avg_round_to_par
  - prior_avg_field_relative_round_score
  - prior_recent_form_5
  - prior_recent_form_10
  - prior_recent_form_20

For each: non-NULL coverage (count and %) across every (target, player)
row, plus the distribution (min/median/mean/max) of its companion `_n`
sample-size column — including the zeros, since a `_n` of 0 IS part of
the real coverage picture, not an outlier to discard.

Usage (on a machine with the real production data/klpga.sqlite):
    python scripts/21_data_coverage_report.py --db data/klpga.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.backtest.walk_forward import build_walk_forward_dataset  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# (value column, companion _n column, human label)
COVERAGE_FEATURES = (
    ("prior_avg_round_score_to_par", "prior_avg_round_score_to_par_n", "career round-score-to-par rate"),
    ("prior_avg_round_to_par", "prior_avg_round_to_par_n", "sparse real round_to_par average"),
    ("prior_avg_field_relative_round_score", "prior_avg_field_relative_round_score_n", "field-relative round score"),
    ("prior_recent_form_5", "prior_recent_form_5_n", "recent form (5-event window)"),
    ("prior_recent_form_10", "prior_recent_form_10_n", "recent form (10-event window)"),
    ("prior_recent_form_20", "prior_recent_form_20_n", "recent form (20-event window)"),
)


def _pct(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


def compute_coverage(rows: list[dict]) -> dict:
    total = len(rows)
    report = {}
    for value_col, n_col, label in COVERAGE_FEATURES:
        non_null = sum(1 for row in rows if row.get(value_col) is not None)
        n_values = [row.get(n_col) for row in rows if row.get(n_col) is not None]
        report[value_col] = {
            "label": label,
            "n_column": n_col,
            "total_rows": total,
            "non_null_count": non_null,
            "non_null_pct": _pct(non_null, total),
            "n_min": min(n_values) if n_values else None,
            "n_median": statistics.median(n_values) if n_values else None,
            "n_mean": round(statistics.mean(n_values), 2) if n_values else None,
            "n_max": max(n_values) if n_values else None,
        }
    return report


def run(conn: sqlite3.Connection) -> dict:
    result = build_walk_forward_dataset(conn)
    total = len(result.rows)
    print(
        f"USABLE population (unconditional — NO minimum-prior-history filter applied; "
        f"same population scripts/17_eligibility_report.py's threshold=0 row reports): "
        f"{total} (target, player) row(s) across {len(result.target_order)} usable target tournament(s)."
    )

    coverage = compute_coverage(result.rows)

    print()
    for value_col, entry in coverage.items():
        print(f"{value_col}  ({entry['label']})")
        print(f"  non-NULL: {entry['non_null_count']}/{entry['total_rows']} ({entry['non_null_pct']}%)")
        print(f"  companion {entry['n_column']} distribution (incl. zeros): "
              f"min={entry['n_min']}  median={entry['n_median']}  mean={entry['n_mean']}  max={entry['n_max']}")
        print()

    return {"total_rows": total, "coverage": coverage}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        run(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
