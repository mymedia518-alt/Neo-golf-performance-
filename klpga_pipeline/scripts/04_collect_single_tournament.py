"""Collect ONE known KLPGA tournament end-to-end — the real-data
validation checkpoint before attempting the full 100-tournament run.

Current project goal: prove real collection works for one gameCode
(e.g. gameCode=2026080002) rather than scaling up to 100 tournaments
first. This script does exactly that:

    season -> POST /ajax/tourInfo/getGameList -> find the matching
              gameCode entry (fills tournament_master fields that ARE
              confirmed; everything else stays NULL)
           -> POST /load/leaderboard/roundLeaderboard -> parse -> UPSERT
              player_master / player_event / player_round

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts/04_collect_single_tournament.py --season 2026 --game-code 2026080002

Requires the DB to already be initialized:
    python src/klpga/db/init_db.py --db data/klpga.sqlite

Prints a structured, copy-pasteable summary to stdout: the raw
getGameList entry that matched, how many rounds/requests were fetched,
row counts written, a few sample player rows, and a short raw-HTML
snippet — so the still-open items in docs/SITE_STRUCTURE_TODO.md (CUT
player round-history behavior, real markup around the confirmed
attributes, any extra confirmed fields) can be checked against a real
response instead of guessed.

If the site blocks access (401/403/429) or the gameCode isn't found,
this exits non-zero and does NOT write fabricated data.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.leaderboard import fetch_round_leaderboard_html  # noqa: E402
from klpga.collectors.single_tournament import (  # noqa: E402
    STATUS_GAME_CODE_NOT_FOUND,
    STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND,
    collect_and_persist_tournament,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True, help="season to look this gameCode up under")
    parser.add_argument("--game-code", required=True, dest="game_code")
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument(
        "--force-refresh-round", type=int, action="append", dest="force_refresh_round",
        help="Round number to bypass the HTTP cache for and always fetch live (repeatable). Use this "
             "for a round that may have been cached empty before it was actually played — see "
             "klpga.collectors.leaderboard.collect_all_rounds_for_game's force_refresh_rounds docstring. "
             "Not tied to any specific tournament/round number; pass whichever round you need refreshed.",
    )
    parser.add_argument(
        "--expected-final-round", type=int, default=None,
        help="If given, HARD STOP (no 'collected successfully' message, non-zero exit) when the round "
             "actually discovered falls short of this — e.g. a round-close run that must reach round 4 "
             "but silently stopped at round 3 due to a stale cache. Real rounds that WERE found are "
             "still persisted; only the success framing is withheld. Omit for the original, unconditional "
             "behavior (whatever round is discovered is accepted).",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist. Run:", file=sys.stderr)
        print(f"  python src/klpga/db/init_db.py --db {args.db}", file=sys.stderr)
        return 2

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    conn = sqlite3.connect(db_path)

    try:
        result = collect_and_persist_tournament(
            conn, client, args.season, args.game_code,
            force_refresh_rounds=frozenset(args.force_refresh_round or []),
            expected_final_round=args.expected_final_round,
            collection_run_source="04_collect_single_tournament",
        )
    except RateLimitBlockedError as exc:
        conn.close()
        print(f"BLOCKED by site access restriction: {exc}", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as exc:
        conn.close()
        print(f"NETWORK ERROR: {exc}", file=sys.stderr)
        print("Not fabricating data — whatever had already been written stays as-is.", file=sys.stderr)
        return 1

    if result.status == STATUS_GAME_CODE_NOT_FOUND:
        conn.close()
        print(f"ERROR: {result.reason}", file=sys.stderr)
        print("Check --season, or this gameCode may belong to a different tour type.", file=sys.stderr)
        return 2

    match = result.match
    print("=== STEP 1: getGameList match (raw entry, exactly as returned) ===")
    print(json.dumps(match.raw, ensure_ascii=False, indent=2))
    print()
    if not match.is_regular_tour:
        print(f"NOTE: tourType={match.tour_type!r} != 'RE' — confirm this is really the intended tournament.")
    if not match.is_completed:
        print(f"NOTE: gameFinish={match.game_finish!r} != 'F' — tournament may not be finished yet.")
    print()

    if match.prize_money is not None or match.out_course_text is not None or match.in_course_text is not None:
        print("=== NOTE: confirmed getGameList fields with no tournament_master column yet ===")
        print(f"  prizeMoney (total purse, KRW): {match.prize_money!r}")
        print(f"  outCourseText: {match.out_course_text!r}")
        print(f"  inCourseText: {match.in_course_text!r}")
        print("  (not written to the DB — the spec's 16-column tournament_master")
        print("   schema has no slot for these; see docs/SITE_STRUCTURE_TODO.md)")
        print()

    print("=== STEP 2: roundLeaderboard rounds fetched ===")
    for rnd, rows in sorted(result.rounds_data.items()):
        print(f"  round={rnd}: {len(rows)} player rows")
    print()

    if result.status == STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND:
        conn.close()
        print("=== HARD STOP ===")
        print(f"STATUS: HARD_STOP_BELOW_EXPECTED_FINAL_ROUND")
        print(f"REASON: {result.reason}")
        print()
        print(f"  players (player_master) persisted:  {len(result.player_rows)}")
        print(f"  player_event rows persisted:         {len(result.player_event_rows)}")
        print(f"  player_round rows persisted:         {len(result.player_round_rows)}")
        print(f"  rounds reached: {sorted(result.rounds_data.keys())} (expected to reach round "
              f"{result.expected_final_round})")
        return 6

    print("=== STEP 3: rows written to DB ===")
    print(f"  players (player_master):        {len(result.player_rows)}")
    print(f"  player_event rows:               {len(result.player_event_rows)}")
    print(f"  player_round rows:               {len(result.player_round_rows)}")
    print(f"  winner (from getGameList):       {match.winner_name!r} (playerCode={match.winner_code!r})")
    print(f"  winner_score (from collected round data): {result.winner_score!r}")
    print()

    print("=== STEP 4: sample player_event rows (top 5 by finish rank) ===")
    sample = sorted(
        result.player_event_rows,
        key=lambda r: (r["finish_position_numeric"] is None, r["finish_position_numeric"] or 0),
    )[:5]
    for r in sample:
        print(
            f"  rank={r['finish_position']!r} player_id={r['player_id']} name={r['player_name']!r} "
            f"total_score={r['total_score']} score_to_par={r['score_to_par']} "
            f"r1={r['r1_score']} r2={r['r2_score']} r3={r['r3_score']} r4={r['r4_score']} "
            f"made_cut={r['made_cut']} withdrawn={r['withdrawn']} disqualified={r['disqualified']}"
        )
    print()

    print("=== STEP 5: raw HTML snippet (first ~1200 chars of one fetched round) ===")
    first_round = min(result.rounds_data.keys())
    raw_html = fetch_round_leaderboard_html(client, args.game_code, first_round)  # cached, no extra request
    print(f"[round={first_round}]")
    print(raw_html[:1200])
    print("... (truncated)" if len(raw_html) > 1200 else "")
    print()

    conn.close()
    print("=== DONE ===")
    print(f"gameCode={args.game_code} collected successfully. Copy this ENTIRE output and send it back for review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
