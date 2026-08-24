"""Collect player_master / player_event / player_round rows for every
tournament already in tournament_master, via the confirmed
roundLeaderboard API adapter.

Usage:
    python scripts/02_collect_leaderboards.py --db data/klpga.sqlite

Flow (per project spec sections 4-5):
    for each tournament_master row (by game_code)
        -> discover the final round, fetch it
        -> targeted extra fetch of any earlier round missing scores
        -> merge per-player rows across whatever rounds were fetched
        -> UPSERT player_master / player_event / player_round

Fields with no confirmed source (prize_money, round_to_par for rounds
that weren't directly queried, front9/back9/birdie/eagle/etc. counts,
player birth_year/nationality/team_or_sponsor) are left NULL — see
docs/SITE_STRUCTURE_TODO.md.

ASSUMPTION (not confirmed against a live response, flagged so it can be
corrected once verified): made_cut is derived as status not in {'CUT'};
withdrawn/disqualified are derived from status == 'WD'/'DQ'. This is a
reasonable reading of the confirmed CUT/WD/DQ status strings, not a
verified site rule.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.aggregate import build_rows, merge_player_rows  # noqa: E402
from klpga.collectors.leaderboard import collect_all_rounds_for_game  # noqa: E402
from klpga.db.upsert import (  # noqa: E402
    finish_collection_run,
    start_collection_run,
    upsert_player,
    upsert_player_event,
    upsert_player_round,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist — run db/init_db.py and "
              f"01_collect_tournaments.py first.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tournaments = conn.execute(
        "SELECT event_id, game_code, season FROM tournament_master ORDER BY end_date DESC"
    ).fetchall()

    if not tournaments:
        print("No rows in tournament_master — run 01_collect_tournaments.py first.", file=sys.stderr)
        return 2

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    total_players_written = 0
    blocked = False

    for t in tournaments:
        run_id = start_collection_run(conn, "02_collect_leaderboards", target=t["game_code"], started_at=_now_iso())
        conn.commit()
        try:
            rounds_data = collect_all_rounds_for_game(client, t["game_code"])
        except RateLimitBlockedError as exc:
            finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
            conn.commit()
            print(f"BLOCKED collecting gameCode={t['game_code']}: {exc}", file=sys.stderr)
            blocked = True
            break
        except Exception as exc:  # noqa: BLE001
            finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
            conn.commit()
            print(f"ERROR collecting gameCode={t['game_code']}: {exc}", file=sys.stderr)
            continue

        merged = merge_player_rows(rounds_data)
        player_rows, player_event_rows, player_round_rows = build_rows(
            t["game_code"], t["season"], t["event_id"], merged
        )

        for row in player_rows:
            upsert_player(conn, row)
        for row in player_event_rows:
            upsert_player_event(conn, row)
        for row in player_round_rows:
            upsert_player_round(conn, row)
        conn.commit()

        total_players_written += len(player_rows)
        finish_collection_run(
            conn, run_id, status="success", finished_at=_now_iso(), rows_written=len(player_rows)
        )
        conn.commit()
        print(f"gameCode={t['game_code']}: {len(player_rows)} players, "
              f"{len(player_round_rows)} round rows.")

    conn.close()
    print(f"Total players written across tournaments processed: {total_players_written}")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
