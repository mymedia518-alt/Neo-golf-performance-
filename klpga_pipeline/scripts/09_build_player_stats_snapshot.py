"""Build player_stats_snapshot's DERIVED metrics (snapshot_type=
'derived_trailing100') from the validated tournament_master /
player_event / player_round dataset.

See src/klpga/analytics/player_stats.py for exactly which columns get
written, their formulas, sample sizes, and provenance. This does NOT
read data.klpga.co.kr (never reached) and does NOT write any of the
official Data Center columns (sg_*, gir, driving_*, putting_average,
sixties_rate, birdie_average, par_breakers, sand_save, scrambling) —
those stay NULL. See docs/SITE_STRUCTURE_TODO.md section 6 for why true
Strokes Gained / GIR are not computable from this dataset.

Always fully regenerates every derived_trailing100 row from the current
dataset (DELETE + re-INSERT), not an incremental upsert — this snapshot
type's related_event_id is intentionally always NULL (not tied to one
event), and SQLite's UNIQUE constraint never treats two NULLs as
conflicting, so an ON CONFLICT upsert on that natural key would silently
accumulate duplicate rows on every re-run instead of replacing them.

Usage:
    python scripts/09_build_player_stats_snapshot.py --db data/klpga.sqlite
"""
from __future__ import annotations

import argparse
import datetime
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.analytics.player_stats import compute_player_stats  # noqa: E402
from klpga.db.migrate import ensure_player_stats_snapshot_schema  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "src" / "klpga" / "db" / "schema.sql"


def build(db_path: Path, schema_path: Path = SCHEMA_PATH) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        ensure_player_stats_snapshot_schema(conn, schema_path)

        tm_row = conn.execute(
            "SELECT season, end_date FROM tournament_master ORDER BY end_date DESC, season DESC LIMIT 1"
        ).fetchone()
        if tm_row is None:
            raise RuntimeError("tournament_master is empty — run the collection scripts first.")
        season, as_of_date = tm_row

        stats_rows = compute_player_stats(conn)
        collected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn.execute("DELETE FROM player_stats_snapshot WHERE snapshot_type = 'derived_trailing100'")
        for stats_row in stats_rows:
            row = dict(stats_row)
            row.update(
                {
                    "season": season,
                    "as_of_date": as_of_date,
                    "snapshot_type": "derived_trailing100",
                    "related_event_id": None,
                    "collected_at": collected_at,
                }
            )
            cols = list(row.keys())
            placeholders = ", ".join(f":{c}" for c in cols)
            conn.execute(
                f"INSERT INTO player_stats_snapshot ({', '.join(cols)}) VALUES ({placeholders})",
                row,
            )
        conn.commit()
    finally:
        conn.close()
    return stats_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    try:
        rows = build(db_path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"player_stats_snapshot: {len(rows)} player(s) populated (snapshot_type='derived_trailing100')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
