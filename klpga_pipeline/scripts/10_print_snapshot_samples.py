"""Print sample rows from player_stats_snapshot's derived_trailing100
metrics (see scripts/09_build_player_stats_snapshot.py /
src/klpga/analytics/player_stats.py) for a quick eyeball check — e.g.
after building the snapshot on the validated 100-tournament production
DB, to confirm the numbers look sane and to pull real sample rows for
review.

Read-only: only SELECTs from player_stats_snapshot/player_master, never
writes anything and never touches tournament_master/player_event/
player_round.

Usage:
    python scripts/10_print_snapshot_samples.py --db data/klpga.sqlite
    python scripts/10_print_snapshot_samples.py --db data/klpga.sqlite --limit 20
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_COLUMNS = [
    "derived_tournaments_played",
    "derived_wins",
    "derived_top5",
    "derived_top10",
    "derived_best_finish",
    "derived_cut_rate",
    "derived_avg_round_score",
    "derived_round_scoring_stddev",
    "derived_avg_event_score_to_par",
    "derived_avg_round_score_to_par",
    "derived_recent_event_form_10",
    "derived_recent_event_form_10_n",
    "derived_weighted_recent_event_form",
]


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_samples(db_path: Path, limit: int) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM player_stats_snapshot WHERE snapshot_type = 'derived_trailing100'"
        ).fetchone()[0]
        if count == 0:
            print(
                "No derived_trailing100 rows in player_stats_snapshot yet — "
                "run scripts/09_build_player_stats_snapshot.py first.",
                file=sys.stderr,
            )
            return 1

        rows = conn.execute(
            f"""
            SELECT p.player_name, {', '.join('s.' + c for c in _COLUMNS)}
            FROM player_stats_snapshot s
            JOIN player_master p ON s.player_id = p.player_id
            WHERE s.snapshot_type = 'derived_trailing100'
            ORDER BY s.derived_wins DESC, s.derived_avg_event_score_to_par ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    header = ["player_name"] + _COLUMNS
    print(f"{count} player(s) total in player_stats_snapshot (snapshot_type='derived_trailing100')\n")
    print(" | ".join(header))
    for row in rows:
        print(" | ".join([row["player_name"]] + [_fmt(row[c]) for c in _COLUMNS]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    return print_samples(db_path, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
