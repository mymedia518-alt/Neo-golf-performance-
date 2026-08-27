"""OFFICIAL LEADERBOARD VALIDATION GATE — scripts/50_validate_official_round.py

READ-ONLY against the DB (opened `mode=ro`). Cross-checks the real
official KLPGA entry list + round leaderboard against this project's
own DB (tournament_entry / player_event / player_round), for ONE
(game_code, round_number) at a time. This is the SAME reusable gate
for every round transition (PRE->R1, R1->R2, R2->R3, R3->FINAL) — see
klpga.neo_win.round_reconciliation for the actual reconciliation
logic; this script is only I/O plumbing (fetch + DB read + print).

Reuses the existing collector/parser infrastructure verbatim:
  - klpga.collectors.entry_list.fetch_entry_list
  - klpga.parsers.entry_list_parser.parse_entry_list_html
  - klpga.collectors.leaderboard.fetch_round_leaderboard
Both go through klpga.http_client.PoliteHttpClient, which transparently
uses the existing disk cache (data/raw_cache/http by default) — a
repeat run for the same (game_code, round) does not re-fetch.

Never writes to the DB, never modifies any frozen prediction/history
artifact, never fabricates a score/position/probability for an
unresolved or absent player.

Usage:
    python scripts/50_validate_official_round.py --game-code 2026080001 --round 1 \\
        --db data/klpga.sqlite --cache-dir data/raw_cache/http
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.entry_list import fetch_entry_list  # noqa: E402
from klpga.collectors.leaderboard import fetch_round_leaderboard  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402
from klpga.neo_win.round_reconciliation import (  # noqa: E402
    VERDICT_FAIL,
    VERDICT_WARN,
    normalize_db_round,
    normalize_entry_rows,
    normalize_official_round,
    reconcile_round,
)
from klpga.parsers.entry_list_parser import parse_entry_list_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--round", type=int, required=True, dest="round_number")
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    try:
        entry_html = fetch_entry_list(client, args.game_code)
    except RateLimitBlockedError as exc:
        print(f"ERROR: could not fetch official entry list: {exc}")
        return 4
    entry_rows = parse_entry_list_html(entry_html).rows
    entry_normalized = normalize_entry_rows(entry_rows)

    try:
        official_rows = fetch_round_leaderboard(client, args.game_code, args.round_number)
    except RateLimitBlockedError as exc:
        print(f"ERROR: could not fetch official round {args.round_number} leaderboard: {exc}")
        return 5
    official_normalized = normalize_official_round(official_rows, args.round_number)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        db_normalized = normalize_db_round(conn, args.game_code, args.round_number)
    finally:
        conn.close()

    result = reconcile_round(entry_normalized, official_normalized, db_normalized, args.round_number)

    print("=== OFFICIAL LEADERBOARD VALIDATION ===")
    print()
    print(f"ENTRY COUNT: {len(result.entry)}")
    print(f"OFFICIAL ROUND COUNT: {len(result.official)}")
    print(f"DB ROUND COUNT: {len(result.db)}")
    print()
    print(f"MATCHED: {len(result.entry_and_official_and_db)}")
    print(f"ENTRY ONLY: {len(result.entry_only)} {sorted(result.entry_only)}")
    print(f"OFFICIAL ONLY: {len(result.official_only)} {sorted(result.official_only)}")
    print(f"DB ONLY: {len(result.db_only)} {sorted(result.db_only)}")
    print()
    score_mismatches = [a for a in result.anomalies if a["classification"] == "SCORE_MISMATCH"]
    position_mismatches = [a for a in result.anomalies if a["classification"] == "POSITION_MISMATCH"]
    identity_mismatches = [
        a for a in result.anomalies if a["classification"] in ("NAME_MISMATCH", "POSSIBLE_IDENTITY_MISMATCH")
    ]
    print(f"SCORE MISMATCH: {len(score_mismatches)}")
    print(f"POSITION MISMATCH: {len(position_mismatches)}")
    print(f"IDENTITY MISMATCH: {len(identity_mismatches)}")
    print()
    print("=== ANOMALIES ===")
    print()
    if result.anomalies:
        print(f"{'player_code':<14} {'player_name':<12} {'classification':<32} detail")
        for a in result.anomalies:
            code = a["player_code"]
            o = result.official.get(code)
            d = result.db.get(code)
            e = result.entry.get(code)
            name = (o and o.player_name) or (d and d.player_name) or (e and e.player_name) or ""
            print(f"{code:<14} {name:<12} {a['classification']:<32} {a['detail']}")
    else:
        print("(none)")
    print()
    print("=== DATA QUALITY GATE ===")
    print()
    print(f"VERDICT: {result.verdict}")
    print()
    print(f"PREDICTION ELIGIBLE: {len(result.eligible)} {result.eligible}")
    print(f"EXCLUDED: {len(result.excluded)} {result.excluded}")
    print(f"UNRESOLVED: {len(result.unresolved)} {result.unresolved}")
    print()
    if result.verdict == VERDICT_FAIL:
        print("BLOCKED: FAIL verdict — round prediction must NOT be published until every FAIL-class "
              "anomaly above is resolved with real evidence.")
    elif result.verdict == VERDICT_WARN:
        print("PERMITTED WITH WARNINGS: no FAIL-class anomaly, but see WARN items above before publishing.")
    else:
        print("PERMITTED: no anomalies detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
