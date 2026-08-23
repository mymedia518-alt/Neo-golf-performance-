"""python -m klpga.export

Dumps every core table to CSV under data/export/, UTF-8 with a BOM so
Korean player names display correctly in Excel on Windows.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys

from . import config, db

TABLES = ["tournaments", "players", "player_events", "rounds"]


def export_table(conn: sqlite3.Connection, table: str, out_dir) -> int:
    cur = conn.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    columns = [d[0] for d in cur.description]
    out_path = out_dir / f"{table}.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[c] for c in columns])
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m klpga.export",
        description="Export the KLPGA historical DB to CSV (UTF-8 with BOM).",
    )
    parser.parse_args(argv)

    conn = db.get_connection()
    db.init_db(conn)
    try:
        for table in TABLES:
            n = export_table(conn, table, config.EXPORT_DIR)
            print(f"{table}: {n} rows -> {config.EXPORT_DIR / (table + '.csv')}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
