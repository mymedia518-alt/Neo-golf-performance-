"""NEO Intelligence Engine V1 -- PHASE 1: Official Data Warehouse.

Collects every real, already-collected official KLPGA dataset present in
this repository's content/website_v2 tree (current branch:
feature/player-intelligence-v1) into a single permanent, append-only
SQLite warehouse.

This is a COLLECTION step, not an analysis step: every row stored here is
an exact copy of a record that already exists in a JSON file on disk in
this repository. Nothing is computed, derived, or invented. A file is
included only when its name/content matches one of the OFFICIAL data
categories below; pipeline-internal manifests, HTML, Python, tests,
reports, and narrative markdown are explicitly OUT of scope for this
warehouse (they belong to Phase 2, RepositoryIndex).

"Never overwrite": every row is keyed by a content hash of
(source_file, record_index, exact JSON bytes of that record). Re-running
this script is idempotent -- it only ever adds rows for content it has
not seen before; it never updates or deletes an existing row.

Output: content/website_v2/knowledge_engine/engine/OfficialWarehouse.sqlite
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content" / "website_v2"
ENGINE_DIR = CONTENT_DIR / "knowledge_engine" / "engine"
DB_PATH = ENGINE_DIR / "OfficialWarehouse.sqlite"

# ---------------------------------------------------------------------------
# Category classification -- filename-pattern based, applied in order.
# Every rule below is grounded in a real, already-verified naming
# convention used elsewhere in this pipeline (see
# scripts/build_10097_master_player_analysis.py build_master_dataset()).
# ---------------------------------------------------------------------------

CATEGORY_RULES: list[tuple[str, str]] = [
    (r"K_?RANKING|k-rankings|K_RANK|_RANKING|RANK_DIVERGENCE", "KRanking"),
    (r"SCHEDULE", "Season"),
    (r"OFFICIAL_SG_NORMALIZED|_SG_V\d|sg_warehouse|SG_WAREHOUSE|SG_VALIDATION|SG_CROSS_VALIDATION|_SG_CORRECTED", "SG"),
    (r"PROFILE_NORMALIZED|OFFICIAL_PROFILE|PLAYER_UNIFIED_SNAPSHOT|IDENTITY_AUDIT", "Profile"),
    (r"ENTRY_LIST|ENTRY_SNAPSHOT", "Tournament"),
    (r"LEADERBOARD|FINAL_TRUTH|_FINAL_|R1_|R2_|R3_|R4_|_RESULT_|LIVE_SNAPSHOT|r1_final_snapshots", "Round"),
    (r"SCORECARD", "Scorecard"),
    (r"PIN_POSITION|PIN_POS", "PinPosition"),
    (r"HOLE_DIFFICULTY|HOLE_DIFF", "HoleDifficulty"),
    (r"COURSE_SERIES|COURSE_HISTORY|COURSE_ANALYSIS", "Course"),
    (r"MONEY|PRIZE|EARNINGS", "Money"),
    (r"HOME_REGULAR_TOUR_PLAYER_MASTER|PLAYER_MASTER|ACTIVE_KLPGA_TOUR_PLAYER_MASTER", "Player"),
    (r"empirical_sg_corrected_v2", "SG"),
    (r"RECORD_REPORT_WAREHOUSE|HISTORICAL_TRUTH_WAREHOUSE", "Tournament"),
    (r"RANK_DIVERGENCE", "KRanking"),
]

# A file is considered "official" only if it also carries one of these
# broad markers somewhere in its path -- this keeps out pipeline manifests,
# QA notes, and unrelated JSON that happens to share a narrower keyword.
OFFICIAL_MARKERS = re.compile(
    r"OFFICIAL|historical_sg_warehouse|empirical_sg_corrected_v2|HOME_REGULAR_TOUR_PLAYER_MASTER|"
    r"ACTIVE_KLPGA_TOUR_PLAYER_MASTER|r1_final_snapshots|_FINAL_TRUTH|K_?RANKING|k-rankings|SCHEDULE|"
    r"ENTRY_LIST|ENTRY_SNAPSHOT|sg_warehouse|SG_WAREHOUSE|RECORD_REPORT_WAREHOUSE|RANK_DIVERGENCE|"
    r"IDENTITY_AUDIT|PLAYER_UNIFIED_SNAPSHOT",
    re.IGNORECASE,
)

EXCLUDE_DIR_MARKERS = ("knowledge_engine/player_intelligence", "knowledge_engine/tournament_dna", "knowledge_engine/engine")


def classify(rel_path: str) -> str:
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, rel_path, re.IGNORECASE):
            return category
    return "Other"


def is_official(rel_path: str) -> bool:
    if not rel_path.endswith(".json"):
        return False
    if any(marker in rel_path for marker in EXCLUDE_DIR_MARKERS):
        return False
    return bool(OFFICIAL_MARKERS.search(rel_path))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_records(doc) -> list:
    """Return the list of row-dicts inside a warehouse-style JSON document.

    Real, already-established container keys used across this pipeline's
    official JSON files: "records", "rows", "entries", "players",
    "candidates". If none match, the whole document is stored as one row
    (record_index = -1) rather than guessed apart.
    """
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for key in ("records", "rows", "entries", "players", "candidates", "player_table"):
            val = doc.get(key)
            if isinstance(val, list):
                return val
    return None


def infer_player_id(record) -> str | None:
    if not isinstance(record, dict):
        return None
    for key in ("player_id", "playerCode", "player_code"):
        if key in record and record[key] is not None:
            return str(record[key])
    return None


def infer_game_code(rel_path: str, record) -> str | None:
    if isinstance(record, dict):
        for key in ("game_code", "gameCode", "gameCd"):
            if key in record and record[key] is not None:
                return str(record[key])
    m = re.search(r"(20\d{7})", rel_path)
    return m.group(1) if m else None


def build() -> dict:
    ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS official_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row_hash TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            player_id TEXT,
            game_code TEXT,
            record_json TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            ingested_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_official_player ON official_records(player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_official_category ON official_records(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_official_source ON official_records(source_file)")

    ingested_at = datetime.now(timezone.utc).isoformat()
    all_json = sorted((CONTENT_DIR).rglob("*.json"))
    files_scanned = 0
    files_ingested = 0
    files_skipped_not_official = 0
    files_skipped_parse_error = 0
    rows_inserted = 0
    rows_deduped = 0
    category_counts: dict[str, int] = {}
    skipped_files: list[str] = []

    for path in all_json:
        rel = str(path.relative_to(CONTENT_DIR))
        files_scanned += 1
        if not is_official(rel):
            files_skipped_not_official += 1
            continue

        raw_bytes = path.read_bytes()
        file_sha = sha256_bytes(raw_bytes)
        try:
            doc = json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            files_skipped_parse_error += 1
            skipped_files.append(rel)
            continue

        category = classify(rel)
        collected_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

        records = extract_records(doc)
        if records is None:
            records = [doc]
            indices = [-1]
        else:
            indices = list(range(len(records)))

        file_had_row = False
        for idx, record in zip(indices, records):
            record_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
            row_hash = sha256_bytes(f"{rel}|{idx}|{record_json}".encode("utf-8"))
            player_id = infer_player_id(record)
            game_code = infer_game_code(rel, record)
            try:
                conn.execute(
                    """
                    INSERT INTO official_records
                        (row_hash, category, source_file, source_sha256, record_index,
                         player_id, game_code, record_json, collected_at, ingested_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (row_hash, category, rel, file_sha, idx, player_id, game_code, record_json, collected_at, ingested_at),
                )
                rows_inserted += 1
                category_counts[category] = category_counts.get(category, 0) + 1
                file_had_row = True
            except sqlite3.IntegrityError:
                rows_deduped += 1

        if file_had_row or records:
            files_ingested += 1

    conn.commit()

    total_rows = conn.execute("SELECT COUNT(*) FROM official_records").fetchone()[0]
    distinct_player_ids = conn.execute(
        "SELECT COUNT(DISTINCT player_id) FROM official_records WHERE player_id IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    return {
        "db_path": str(DB_PATH.relative_to(ROOT)),
        "json_files_scanned": files_scanned,
        "json_files_classified_official": files_ingested,
        "json_files_skipped_not_official": files_skipped_not_official,
        "json_files_skipped_parse_error": files_skipped_parse_error,
        "skipped_parse_error_files": skipped_files,
        "rows_inserted_this_run": rows_inserted,
        "rows_deduped_this_run": rows_deduped,
        "total_rows_in_warehouse": total_rows,
        "distinct_player_ids": distinct_player_ids,
        "category_counts": category_counts,
        "scope_note": (
            "Scope: content/website_v2/ on the current branch "
            "(feature/player-intelligence-v1) only -- this is where the pipeline's "
            "collected official KLPGA data physically lives. Historical official-data "
            "snapshots on other branches are indexed by Phase 2 (RepositoryIndex), not "
            "duplicated into this warehouse."
        ),
    }


if __name__ == "__main__":
    result = build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
