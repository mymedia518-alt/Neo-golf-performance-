"""Create (or reset) the klpga.sqlite database from schema.sql."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def init_db(db_path: Path, reset: bool = False) -> None:
    if reset and db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    print(f"Initialized {db_path} from {SCHEMA_PATH.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/klpga.sqlite")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    init_db(Path(args.db), reset=args.reset)
