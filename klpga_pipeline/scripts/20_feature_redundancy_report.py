"""Read-only feature redundancy report against the real production DB —
no DB writes, does not touch tournament_master/player_master/
player_event/player_round/tournament_entry.

`prior_wins`/`prior_top5`/`prior_top10`/`prior_cut_rate`/the career
scoring feature (`prior_avg_round_score_to_par`)/the recent-form
features may encode overlapping performance signal (a player who wins
often also tends to make more cuts and post better recent form, by
construction). This script reports PAIRWISE PEARSON CORRELATION across
the point-in-time performance features on the real walk-forward
dataset, so that overlap is visible as EVIDENCE — not resolved.

This script does NOT remove any feature and does NOT pick model
weights — see klpga.backtest's package docstring: no probability
model, feature weight, or calibration constant is introduced anywhere
in this project yet. The "notable redundancy" section below only
highlights pairs for readability (an arbitrary DISPLAY threshold,
`|r| >= 0.7` with `n >= 30` pairs) — it is not a selection or
elimination decision.

Correlation is computed with a plain hand-rolled Pearson implementation
(no numpy/scipy/pandas dependency, consistent with the rest of this
project — see docs/SITE_STRUCTURE_TODO.md section 5 for the export_csv
"no pandas" precedent) using pairwise deletion: for each pair of
features, only rows where BOTH values are non-NULL are used, and the
resulting sample size n is always printed alongside r — a correlation
computed from a small n is exactly as unreliable as any other small-n
statistic and is never hidden.

Usage (on a machine with the real production data/klpga.sqlite):
    python scripts/20_feature_redundancy_report.py --db data/klpga.sqlite
    python scripts/20_feature_redundancy_report.py --db data/klpga.sqlite --min-n 50 --notable-threshold 0.6
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.backtest.walk_forward import build_walk_forward_dataset  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# The performance-signal columns to cross-correlate. Deliberately
# excludes every `_n` sample-size companion (those are coverage
# metadata, not a performance signal) and every non-numeric/label
# column.
CORRELATION_COLUMNS = (
    "prior_events_n",
    "prior_wins",
    "prior_top5",
    "prior_top10",
    "prior_cut_rate",
    "prior_avg_round_score_to_par",
    "prior_recent_form_5",
    "prior_recent_form_10",
    "prior_recent_form_20",
    "prior_avg_round_to_par",
    "prior_avg_field_relative_round_score",
)

# Short display codes for the matrix header (full names are long enough
# to break fixed-width alignment) — a legend is always printed with them.
_SHORT_CODE = {
    "prior_events_n": "exp",
    "prior_wins": "win",
    "prior_top5": "top5",
    "prior_top10": "top10",
    "prior_cut_rate": "cutr",
    "prior_avg_round_score_to_par": "career",
    "prior_recent_form_5": "rf5",
    "prior_recent_form_10": "rf10",
    "prior_recent_form_20": "rf20",
    "prior_avg_round_to_par": "rtp",
    "prior_avg_field_relative_round_score": "frel",
}


def _pearson_r(pairs: list[tuple[float, float]]) -> float | None:
    n = len(pairs)
    if n < 2:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return None
    return cov / denom


def compute_pairwise_correlations(rows: list[dict], columns: tuple[str, ...] = CORRELATION_COLUMNS) -> dict:
    """Returns {(col_a, col_b): {"r": float|None, "n": int}} for every
    unordered pair of columns, using pairwise deletion (only rows where
    BOTH values are non-NULL contribute to that pair)."""
    result = {}
    for i, col_a in enumerate(columns):
        for col_b in columns[i + 1:]:
            pairs = [
                (row[col_a], row[col_b])
                for row in rows
                if row.get(col_a) is not None and row.get(col_b) is not None
            ]
            result[(col_a, col_b)] = {"r": _pearson_r(pairs), "n": len(pairs)}
    return result


def run(conn: sqlite3.Connection, min_n: int, notable_threshold: float) -> dict:
    result = build_walk_forward_dataset(conn)
    print(f"Walk-forward dataset: {len(result.rows)} (target, player) row(s) across "
          f"{len(result.target_order)} usable target tournament(s).")

    correlations = compute_pairwise_correlations(result.rows)

    print("\nLegend:")
    for col in CORRELATION_COLUMNS:
        print(f"  {_SHORT_CODE[col]:<8} = {col}")

    col_width = 8
    print("\nPairwise Pearson correlation (pairwise deletion — n shown per pair below):")
    header = "".ljust(8) + "".join(_SHORT_CODE[c].ljust(col_width) for c in CORRELATION_COLUMNS)
    print(header)
    for col_a in CORRELATION_COLUMNS:
        line = _SHORT_CODE[col_a].ljust(8)
        for col_b in CORRELATION_COLUMNS:
            if col_a == col_b:
                line += "1.00".ljust(col_width)
                continue
            key = (col_a, col_b) if (col_a, col_b) in correlations else (col_b, col_a)
            entry = correlations.get(key)
            r = entry["r"] if entry else None
            line += (f"{r:.2f}" if r is not None else "-").ljust(col_width)
        print(line)

    notable = [
        (cols, entry) for cols, entry in correlations.items()
        if entry["r"] is not None and entry["n"] >= min_n and abs(entry["r"]) >= notable_threshold
    ]
    notable.sort(key=lambda item: abs(item[1]["r"]), reverse=True)

    print(f"\nNotable pairs (|r| >= {notable_threshold}, n >= {min_n}) — DISPLAY threshold only, "
          f"not a feature-selection decision:")
    if notable:
        for (col_a, col_b), entry in notable:
            print(f"  r={entry['r']:.2f}  n={entry['n']:>5}  {col_a}  <->  {col_b}")
    else:
        print("  (none at this threshold)")

    print(
        "\nNo feature is removed and no weight is chosen by this script — this is diagnostic "
        "evidence for the model-design gate, not a decision."
    )

    return {"row_count": len(result.rows), "correlations": correlations, "notable": notable}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--min-n", type=int, default=30, dest="min_n",
                         help="minimum pairwise sample size to consider a pair for the 'notable' list (display only)")
    parser.add_argument("--notable-threshold", type=float, default=0.7, dest="notable_threshold",
                         help="|r| threshold for the 'notable' list (display only)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        run(conn, args.min_n, args.notable_threshold)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
