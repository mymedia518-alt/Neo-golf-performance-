"""Export the SQLite tables to the exact CSV column layout the project
spec requires (booleans as TRUE/FALSE, one file per table).

Stdlib-only (sqlite3 + csv) — no pandas/numpy. This used to go through
pandas, but a real run on Windows exited with no error and no output
directory at all: `out_dir.mkdir(...)` is the very first line of
`export_all`, so for the directory to never appear, execution must have
stopped before `export_all` even ran — i.e. at module import time. The
only import that could plausibly fail silently there was `import pandas
as pd` (a C-extension package, unlike the stdlib modules every other
script in this project already depends on and which have run
successfully on the same machine). Rather than keep guessing at exactly
what failed in an environment this dev sandbox can't reach, the pandas
dependency is removed for this script entirely — a straight
SQLite-rows-to-CSV export doesn't need it — which also eliminates that
whole failure class. See docs/SITE_STRUCTURE_TODO.md section 5.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Optional

BOOL_COLUMNS = {
    "player_event": ["tie_flag", "made_cut", "withdrawn", "disqualified"],
}

TABLE_TO_COLUMNS = {
    "tournament_master": [
        "event_id", "game_code", "event_name", "season", "start_date", "end_date",
        "course_name", "course_location", "par", "course_yards",
        "rounds_scheduled", "rounds_completed", "field_size",
        "winner", "winner_score", "official_url",
    ],
    "player_master": [
        "player_id", "player_name", "birth_year", "nationality",
        "team_or_sponsor", "official_player_url",
    ],
    "player_event": [
        "event_id", "game_code", "season", "player_id", "player_name",
        "finish_position", "finish_position_numeric", "tie_flag",
        "made_cut", "withdrawn", "disqualified", "rounds_played",
        "r1_score", "r2_score", "r3_score", "r4_score",
        "total_score", "score_to_par", "prize_money", "avg_score_event",
        "official_url",
    ],
    "player_round": [
        "event_id", "game_code", "season", "round_number",
        "player_id", "player_name",
        "round_score", "round_to_par", "finish_position_after_round",
        "course_name", "course_par",
        "front9_score", "back9_score", "birdies", "eagles", "pars",
        "bogeys", "double_bogey_plus", "official_url",
    ],
    "player_stats_snapshot": [
        "snapshot_id", "player_id", "season", "as_of_date", "snapshot_type",
        "related_event_id",
        "scoring_average", "scoring_average_rank",
        "sg_total", "sg_total_rank",
        "sg_off_the_tee", "sg_off_the_tee_rank",
        "sg_approach", "sg_approach_rank",
        "sg_around_green", "sg_around_green_rank",
        "sg_putting", "sg_putting_rank",
        "gir", "gir_rank",
        "driving_distance", "driving_distance_rank",
        "driving_accuracy", "driving_accuracy_rank",
        "putting_average", "putting_average_rank",
        "sixties_rate", "sixties_rate_rank",
        "top10_rate", "top10_rate_rank",
        "birdie_average", "birdie_average_rank",
        "par_breakers", "par_breakers_rank",
        "sand_save", "sand_save_rank",
        "scrambling", "scrambling_rank",
        "official_url", "collected_at",
    ],
}


def _cell(row: sqlite3.Row, column: str, is_bool: bool) -> str:
    value = row[column] if column in row.keys() else None
    if is_bool:
        if value == 1:
            return "TRUE"
        if value == 0:
            return "FALSE"
        return ""
    return "" if value is None else value


def export_all(db_path: Path, out_dir: Path) -> dict[str, int]:
    """Write one CSV per table in TABLE_TO_COLUMNS. Returns a
    {table_name: row_count} dict of what was actually written, so a
    caller (or the CLI below) can print/verify it rather than just
    trusting the export ran. Raises FileNotFoundError if db_path
    doesn't exist, rather than letting sqlite3 silently create a new
    empty database at that path."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path} does not exist — run the collection scripts first "
            "(see README.md 'Running the full pipeline')."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row_counts: dict[str, int] = {}
    try:
        for table, columns in TABLE_TO_COLUMNS.items():
            bool_columns = set(BOOL_COLUMNS.get(table, []))
            out_path = out_dir / f"{table}.csv"
            count = 0
            with out_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for row in conn.execute(f"SELECT * FROM {table}"):
                    writer.writerow(_cell(row, col, col in bool_columns) for col in columns)
                    count += 1
            row_counts[table] = count
            print(f"{table}: {count} rows -> {out_path.resolve()}")
    finally:
        conn.close()
    return row_counts


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/klpga.sqlite")
    parser.add_argument("--out", default="data/csv")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    out_dir = Path(args.out)

    try:
        row_counts = export_all(db_path, out_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("ERROR: export_csv.py failed unexpectedly:", file=sys.stderr)
        traceback.print_exc()
        return 1

    total_rows = sum(row_counts.values())
    print(f"\nExported {len(row_counts)} table(s), {total_rows} row(s) total -> {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
