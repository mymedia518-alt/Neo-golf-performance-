"""Collect the N most-recently-completed KLPGA regular tour events into
tournament_master, via the confirmed getGameList API adapter.

Usage:
    python scripts/01_collect_tournaments.py --season 2026 --target 100

Flow (per project spec section 4):
    season -> POST /ajax/tourInfo/getGameList -> gameList
           -> filter tourType=RE and gameFinish=F
           -> walk backward through seasons until `target` events collected
           -> UPSERT into tournament_master

Only fields confirmed from a live response are written. Fields with no
confirmed source (start_date, course_location, par, course_yards,
rounds_scheduled, rounds_completed, field_size, winner, winner_score,
official_url) are left NULL — see docs/SITE_STRUCTURE_TODO.md for what's
still open.

If the site blocks access (401/403/429), this exits non-zero with the
collection_runs row marked 'blocked' rather than pretending to succeed.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.tournaments import collect_most_recent_completed  # noqa: E402
from klpga.db.upsert import (  # noqa: E402
    finish_collection_run,
    start_collection_run,
    upsert_tournament,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_tournament_row(listing) -> dict:
    return {
        "event_id": listing.game_code,
        "game_code": listing.game_code,
        "event_name": listing.game_title,
        "season": listing.season,
        "start_date": None,  # not confirmed from getGameList — see docs/SITE_STRUCTURE_TODO.md
        "end_date": listing.end_date.isoformat() if listing.end_date else listing.end_date_raw,
        "course_name": listing.course_text,
        "course_location": None,
        "par": None,
        "course_yards": None,
        "rounds_scheduled": None,
        "rounds_completed": None,
        "field_size": None,
        "winner": None,
        "winner_score": None,
        "official_url": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True, help="most recent season to start walking back from")
    parser.add_argument("--target", type=int, default=config.TARGET_COMPLETED_TOURNAMENTS)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist — run db/init_db.py first.", file=sys.stderr)
        return 2

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    conn = sqlite3.connect(db_path)
    run_id = start_collection_run(conn, "01_collect_tournaments", target=f"season<={args.season}", started_at=_now_iso())
    conn.commit()

    try:
        listings = collect_most_recent_completed(client, start_season=args.season, target_count=args.target)
    except RateLimitBlockedError as exc:
        finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        print(f"BLOCKED by site access restriction: {exc}", file=sys.stderr)
        print("Not retrying or fabricating data — see error above.", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
        conn.commit()
        conn.close()
        raise

    for listing in listings:
        upsert_tournament(conn, to_tournament_row(listing))
    conn.commit()

    finish_collection_run(
        conn, run_id, status="success", finished_at=_now_iso(), rows_written=len(listings)
    )
    conn.commit()
    conn.close()

    print(f"Collected {len(listings)} completed regular-tour events (target={args.target}).")
    if len(listings) != args.target:
        print(
            f"WARNING: collected {len(listings)} != target {args.target}. "
            "Check season range / min_season floor / tourType filter.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
