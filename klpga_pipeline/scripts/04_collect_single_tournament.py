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
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.aggregate import build_rows, merge_player_rows, resolve_winner_score  # noqa: E402
from klpga.collectors.leaderboard import (  # noqa: E402
    collect_all_rounds_for_game,
    fetch_round_leaderboard_html,
)
from klpga.collectors.tournaments import fetch_game_list  # noqa: E402
from klpga.db.upsert import (  # noqa: E402
    finish_collection_run,
    start_collection_run,
    update_tournament_winner_score,
    upsert_player,
    upsert_player_event,
    upsert_player_round,
    upsert_tournament,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True, help="season to look this gameCode up under")
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

    run_id = start_collection_run(
        conn, "04_collect_single_tournament", target=args.game_code, started_at=_now_iso()
    )
    conn.commit()

    # --- Step 1: find this gameCode in the season's getGameList response ---
    try:
        listings = fetch_game_list(client, season=args.season, tour_type=config.TOUR_TYPE_REGULAR)
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        print(f"BLOCKED by site access restriction on getGameList: {exc}", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as exc:
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        print(f"NETWORK ERROR reaching {config.GAME_LIST_ENDPOINT}: {exc}", file=sys.stderr)
        print("Not fabricating data — nothing was written.", file=sys.stderr)
        return 1

    match = next((l for l in listings if l.game_code == args.game_code), None)
    if match is None:
        finish_collection_run(
            conn, run_id, status="error", finished_at=_now_iso(),
            error_message=f"gameCode {args.game_code} not found in season={args.season} tourType=RE list",
        )
        conn.commit()
        conn.close()
        print(
            f"ERROR: gameCode={args.game_code} was not found in the season={args.season} "
            f"tourType=RE getGameList response ({len(listings)} entries returned).",
            file=sys.stderr,
        )
        print("Check --season, or this gameCode may belong to a different tour type.", file=sys.stderr)
        return 2

    print("=== STEP 1: getGameList match (raw entry, exactly as returned) ===")
    print(json.dumps(match.raw, ensure_ascii=False, indent=2))
    print()
    if not match.is_regular_tour:
        print(f"NOTE: tourType={match.tour_type!r} != 'RE' — confirm this is really the intended tournament.")
    if not match.is_completed:
        print(f"NOTE: gameFinish={match.game_finish!r} != 'F' — tournament may not be finished yet.")
    print()

    tournament_row = {
        "event_id": match.game_code,
        "game_code": match.game_code,
        "event_name": match.game_title,
        "season": match.season,
        "start_date": match.start_date.isoformat() if match.start_date else match.start_date_raw,
        "end_date": match.end_date.isoformat() if match.end_date else match.end_date_raw,
        "course_name": match.course_text,
        "course_location": None,  # not confirmed — see docs/SITE_STRUCTURE_TODO.md
        "par": None,
        "course_yards": None,
        "rounds_scheduled": None,
        "rounds_completed": None,
        "field_size": None,
        "winner": match.winner_name,
        # winner_score can only come from real collected round data —
        # filled in below, after the leaderboard is collected.
        "winner_score": None,
        "official_url": None,
    }
    upsert_tournament(conn, tournament_row)
    conn.commit()

    if match.prize_money is not None or match.out_course_text is not None or match.in_course_text is not None:
        print("=== NOTE: confirmed getGameList fields with no tournament_master column yet ===")
        print(f"  prizeMoney (total purse, KRW): {match.prize_money!r}")
        print(f"  outCourseText: {match.out_course_text!r}")
        print(f"  inCourseText: {match.in_course_text!r}")
        print("  (not written to the DB — the spec's 16-column tournament_master")
        print("   schema has no slot for these; see docs/SITE_STRUCTURE_TODO.md)")
        print()

    # --- Step 2: leaderboard collection ---
    try:
        rounds_data = collect_all_rounds_for_game(client, args.game_code)
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        print(f"BLOCKED collecting roundLeaderboard: {exc}", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as exc:
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        print(f"NETWORK ERROR reaching {config.ROUND_LEADERBOARD_ENDPOINT}: {exc}", file=sys.stderr)
        print("Not fabricating data — tournament_master row was written, but no player data.", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        raise

    print("=== STEP 2: roundLeaderboard rounds fetched ===")
    for rnd, rows in sorted(rounds_data.items()):
        print(f"  round={rnd}: {len(rows)} player rows")
    print()

    merged = merge_player_rows(rounds_data)
    total_raw_rows = sum(len(rows) for rows in rounds_data.values())
    if total_raw_rows != len(merged):
        print(
            f"NOTE: {total_raw_rows} raw parsed row(s) across all fetched rounds merged down to "
            f"{len(merged)} unique player_code(s) — the site's roundLeaderboard HTML appears to "
            f"contain duplicate/partial DOM entries per player; merge-by-player_code handles this."
        )
        print()

    player_rows, player_event_rows, player_round_rows = build_rows(
        args.game_code, match.season, match.game_code, merged
    )

    for row in player_rows:
        upsert_player(conn, row)
    for row in player_event_rows:
        upsert_player_event(conn, row)
    for row in player_round_rows:
        upsert_player_round(conn, row)
    conn.commit()

    winner_score = resolve_winner_score(player_event_rows, match.winner_code)
    if winner_score is not None:
        # A plain UPDATE on the already-existing row, NOT an upsert —
        # a partial-column upsert here previously failed with a
        # NOT NULL constraint error on other tournament_master columns.
        update_tournament_winner_score(conn, match.game_code, winner_score)
        conn.commit()

    finish_collection_run(conn, run_id, status="success", finished_at=_now_iso(), rows_written=len(player_rows))
    conn.commit()

    print("=== STEP 3: rows written to DB ===")
    print(f"  players (player_master):        {len(player_rows)}")
    print(f"  player_event rows:               {len(player_event_rows)}")
    print(f"  player_round rows:               {len(player_round_rows)}")
    print(f"  winner (from getGameList):       {match.winner_name!r} (playerCode={match.winner_code!r})")
    print(f"  winner_score (from collected round data): {winner_score!r}")
    print()

    print("=== STEP 4: sample player_event rows (top 5 by finish rank) ===")
    sample = sorted(
        player_event_rows,
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
    first_round = min(rounds_data.keys())
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
