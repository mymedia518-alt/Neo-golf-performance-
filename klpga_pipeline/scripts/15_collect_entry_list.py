"""Collect ONE tournament's entry list into tournament_entry — real,
idempotent storage against the confirmed entry-list HTML source.

    GET https://klpga.co.kr/web/tourInfo/entry?gameCode=<code>
        -> parse (klpga.parsers.entry_list_parser)
        -> UPSERT tournament_entry, keyed on (game_code, player_code)

Re-running this script for the same gameCode is safe: every write is an
UPSERT keyed on (game_code, player_code), so a repeated collection
overwrites each row in place rather than duplicating it (see
klpga.db.upsert.upsert_tournament_entry).

This script NEVER writes to tournament_master, player_master,
player_event, or player_round — it only SELECTs from player_master
(read-only) to report matched/unmatched counts against the confirmed
entrant list. A player_code with no player_master row is a legitimate
unmatched entrant (e.g. a rookie not yet in player_master, confirmed
live 2026-08-25: player_code=13355, 배윤철) and is still stored — never
dropped.

Only fields genuinely confirmed on the live page are written:
game_code, player_code, player_name_display, nationality,
qualification_category, qualification_reason, source, collected_at. No
entry_status/WD/DNS/SG/GIR/course-par or any other unconfirmed field is
invented here.

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts/15_collect_entry_list.py --game-code 2026080001 --db data/klpga.sqlite

Requires the DB to already be initialized (this also safely adds the
tournament_entry table to an already-populated DB, since schema.sql
uses CREATE TABLE IF NOT EXISTS throughout):
    python src/klpga/db/init_db.py --db data/klpga.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.entry_list import (  # noqa: E402
    build_tournament_entry_rows,
    fetch_entry_list,
    match_entries_to_player_master,
)
from klpga.db.migrate import ensure_tournament_entry_schema  # noqa: E402
from klpga.db.upsert import finish_collection_run, start_collection_run, upsert_tournament_entry  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402
from klpga.parsers.entry_list_parser import parse_entry_list_html, parse_entry_summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "src" / "klpga" / "db" / "schema.sql"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_entry_list(conn: sqlite3.Connection, client, game_code: str, schema_path: Path = SCHEMA_PATH) -> dict:
    """All the actual fetch/parse/store/report logic, factored out of
    main() so it can be exercised in tests against a FakeClient and an
    in-memory DB, the same pattern as scripts/14_inspect_entry_list.py's
    inspect_entry_list(). Returns a summary dict for the caller/tests to
    assert on.

    Additively creates tournament_entry (if this DB predates it) via
    ensure_tournament_entry_schema before writing anything — safe even
    against an already-populated production DB, see that function's
    docstring."""
    ensure_tournament_entry_schema(conn, schema_path)
    collected_at = _now_iso()
    run_id = start_collection_run(conn, "15_collect_entry_list", target=game_code, started_at=collected_at)
    conn.commit()

    try:
        html = fetch_entry_list(client, game_code)
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        print(f"BLOCKED: {exc}")
        return {"status": "blocked", "error": str(exc)}

    summary = parse_entry_summary(html)
    result = parse_entry_list_html(html)

    total_entrants_label = summary.counts.get("총 참가자")
    print(f"gameCode={game_code}")
    print(f"Page summary counts: {summary.counts}")
    print(f"Parsed entrant rows: {len(result.rows)}")
    if total_entrants_label is not None and total_entrants_label != len(result.rows):
        print(
            f"  MISMATCH: page reports 총 참가자={total_entrants_label} but "
            f"{len(result.rows)} rows were parsed."
        )
    print(f"Unparseable rows: {result.unparsed_row_count}")

    match = match_entries_to_player_master(conn, result.rows)
    print(f"Duplicate player_codes: {len(match.duplicate_player_codes)}")
    print(f"Matched against player_master: {match.matched_count}")
    print(f"Unmatched against player_master: {match.unmatched_count}")
    for row in match.unmatched:
        print(f"  - UNMATCHED (stored anyway): player_code={row.player_code} name={row.player_name!r}")

    entry_rows = build_tournament_entry_rows(
        game_code=game_code,
        entry_rows=result.rows,
        source=config.ENTRY_LIST_ENDPOINT,
        collected_at=collected_at,
    )
    for row in entry_rows:
        upsert_tournament_entry(conn, row)
    conn.commit()

    finish_collection_run(
        conn, run_id, status="success", finished_at=_now_iso(), rows_written=len(entry_rows)
    )
    conn.commit()

    print(f"Wrote {len(entry_rows)} tournament_entry row(s) for gameCode={game_code}.")

    return {
        "status": "success",
        "parsed_rows": len(result.rows),
        "unparsed_row_count": result.unparsed_row_count,
        "duplicate_player_codes": match.duplicate_player_codes,
        "matched_count": match.matched_count,
        "unmatched_count": match.unmatched_count,
        "rows_written": len(entry_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True, dest="game_code")
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist. Run:", file=sys.stderr)
        print(f"  python src/klpga/db/init_db.py --db {args.db}", file=sys.stderr)
        return 2

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    conn = sqlite3.connect(db_path)
    try:
        outcome = collect_entry_list(conn, client, args.game_code)
    finally:
        conn.close()

    return 0 if outcome["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
