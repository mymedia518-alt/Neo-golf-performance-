"""Read-only entry-list diagnostic — no DB writes.

Fetches the confirmed entry-list page for one gameCode
(GET https://klpga.co.kr/web/tourInfo/entry?gameCode=<code>), parses it,
and prints:
  - tournament name/gameCode
  - total entrants (parsed row count, cross-checked against the page's
    own "총 참가자" summary figure — any mismatch is flagged, not hidden)
  - matched vs. unmatched players against player_master (optional --db;
    read-only SELECT only, never writes)
  - duplicate player_code detection
  - any row that looked like an entrant but had no extractable
    player_code (explicitly reported, never silently dropped)
  - 10 sample entrants

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts/14_inspect_entry_list.py --game-code 2026080001
    python scripts/14_inspect_entry_list.py --game-code 2026080001 --db data/klpga.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.entry_list import fetch_entry_list, match_entries_to_player_master  # noqa: E402
from klpga.parsers.entry_list_parser import parse_entry_list_html, parse_entry_summary  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def inspect_entry_list(client, game_code: str, db_path: str | None = None) -> int:
    """All the actual print/report logic, factored out of main() so it
    can be exercised in tests against a FakeClient (same pattern as
    scripts/13_discover_entry_list.py's helper functions) without any
    network access."""
    print(f"Fetching entry list for gameCode={game_code} ...")
    try:
        html = fetch_entry_list(client, game_code)
    except RateLimitBlockedError as exc:
        print(f"BLOCKED: {exc}")
        return 1

    summary = parse_entry_summary(html)
    result = parse_entry_list_html(html)

    print("\n" + "=" * 80)
    print(f"gameCode = {game_code}")
    print(f"Summary box counts (parsed from the page itself): {summary.counts}")
    print(f"Parsed entrant rows: {len(result.rows)}")

    total_entrants_label = summary.counts.get("총 참가자")
    if total_entrants_label is None:
        print("  NOTE: could not find a '총 참가자' figure in the summary box to cross-check against.")
    elif total_entrants_label != len(result.rows):
        print(
            f"  MISMATCH: page reports 총 참가자={total_entrants_label} but "
            f"{len(result.rows)} entrant rows were parsed — investigate before trusting this run."
        )
    else:
        print(f"  OK: parsed row count matches the page's own 총 참가자 figure ({total_entrants_label}).")

    print(f"\nUnparseable rows (looked like an entrant, no extractable player_code): {result.unparsed_row_count}")
    for sample in result.unparsed_samples:
        print(f"  - {sample}")

    codes_seen: dict[str, int] = {}
    for row in result.rows:
        codes_seen[row.player_code] = codes_seen.get(row.player_code, 0) + 1
    duplicates = sorted(code for code, count in codes_seen.items() if count > 1)
    print(f"\nDuplicate player_codes within this entry list: {len(duplicates)}")
    for code in duplicates:
        print(f"  - {code} (x{codes_seen[code]})")

    if db_path:
        resolved_db_path = Path(db_path)
        if not resolved_db_path.exists():
            print(f"\n--db {resolved_db_path} does not exist — skipping player_master matching.")
        else:
            conn = sqlite3.connect(f"file:{resolved_db_path}?mode=ro", uri=True)
            try:
                match = match_entries_to_player_master(conn, result.rows)
                print(f"\nMatched against player_master ({resolved_db_path}): {match.matched_count}")
                print(f"Unmatched against player_master: {match.unmatched_count}")
                for row in match.unmatched:
                    print(f"  - UNMATCHED: player_code={row.player_code} name={row.player_name!r}")
            finally:
                conn.close()
    else:
        print("\n--db not provided — skipping player_master matching.")

    print("\nSample entrants (up to 10):")
    for row in result.rows[:10]:
        print(
            f"  player_code={row.player_code}  name={row.player_name!r}  "
            f"nationality={row.nationality}  category={row.qualification_category!r}  "
            f"reason={row.qualification_reason!r}"
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--db", default=None, help="Optional path to klpga.sqlite for read-only player_master matching")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    return inspect_entry_list(client, args.game_code, db_path=args.db)


if __name__ == "__main__":
    raise SystemExit(main())
