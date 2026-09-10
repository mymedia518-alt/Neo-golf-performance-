"""LOCAL EXTRACTION (real sqlite corpus required): dump ONLY
tournament_master(game_code, start_date) -- the one missing input
needed to exactly reproduce NEO Ranking V1's NEO_V1_score for a new
target cohort.

WHY THIS IS NEEDED: reproducing NEO_V1_score for KB requires ordering
each player's prior Strokes-Gained events chronologically (to pick the
correct "last 5" / "last 10" windows) using the EXACT same
game_code -> start_date values scripts/89_redteam_neo_ranking_v1.py
originally read from this table. Two candidate JSON substitutes were
tried and BOTH proven wrong by direct reproduction against real
historical NEO_V1_score rows (see KB_2026090003_NEO_V1_SCORE_
REPRODUCTION_BLOCKER_V1.json):
  - historical_sg_warehouse.json's own 'date' field: consistently
    2-3 days LATER than the true start_date for every one of 82
    directly-compared tournaments (it is some other date, not
    tournament_master.start_date).
  - NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json's tournament_start_date:
    the correct VALUE where present, but only covers 82 of the 97
    game_codes in historical_sg_warehouse_corrected.json -- the
    missing 15 silently drop real prior events from some players'
    history and change their computed score.

This script changes NOTHING else: no weights, no normalization, no
model logic. It is read-only against the database and writes exactly
one JSON file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "content" / "website_v2" / "TOURNAMENT_MASTER_DATES_V1.json"


def extract(db_path: Path) -> dict:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT game_code, start_date FROM tournament_master WHERE start_date IS NOT NULL"
        ).fetchall()

    game_codes = [str(g) for g, _ in rows]
    if len(game_codes) != len(set(game_codes)):
        raise ValueError("tournament_master has a duplicate game_code with a non-null start_date -- refusing to write an ambiguous mapping")

    dates = {str(g): str(d) for g, d in rows}
    return {
        "schema_version": "tournament_master_dates_v1",
        "purpose": "game_code -> official start_date, extracted verbatim from tournament_master. The only input NEO_V1_score reproduction was missing.",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_query": "SELECT game_code, start_date FROM tournament_master WHERE start_date IS NOT NULL",
        "record_count": len(dates),
        "dates": dates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()

    result = extract(args.db)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sha256 = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
    print(json.dumps({"output": str(OUTPUT_PATH), "record_count": result["record_count"], "sha256": sha256}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
