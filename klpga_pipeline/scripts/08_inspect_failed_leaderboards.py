"""One-off diagnostic: for tournament_master rows that ended up with
ZERO player_event rows (leaderboard collection found no round data at
all — discover_final_round exhausted rounds 1..config.PROBE_MAX_ROUNDS
with nothing), print the raw getGameList entry for each. Looking for
any confirmed field (not just the tournament name) indicating a
different format — e.g. match play vs. stroke play — that would explain
why the roundLeaderboard endpoint (round=1..4) returned nothing.

Uses the SAME disk cache as the original 01_collect_tournaments.py run
— the getGameList calls this makes are cache hits (one per distinct
season involved), so this makes ZERO new network requests.

Usage:
    python scripts/08_inspect_failed_leaderboards.py --db data/klpga.sqlite --cache-dir data/raw_cache/http
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.tournaments import fetch_game_list  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    failed = conn.execute(
        "SELECT tm.game_code, tm.event_name, tm.season FROM tournament_master tm "
        "LEFT JOIN player_event pe ON tm.event_id = pe.event_id "
        "WHERE pe.event_id IS NULL "
        "ORDER BY tm.season, tm.game_code"
    ).fetchall()
    conn.close()

    if not failed:
        print("No tournament_master rows with zero player_event rows — nothing to inspect.")
        return 0

    print(f"{len(failed)} tournament(s) with zero player_event rows:\n")

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    seasons_needed = sorted({season for _, _, season in failed})
    raw_by_code = {}
    for season in seasons_needed:
        for listing in fetch_game_list(client, season=season, tour_type=config.TOUR_TYPE_REGULAR):
            raw_by_code[listing.game_code] = listing.raw

    for game_code, event_name, season in failed:
        print(f"========== {game_code} ({event_name}, season={season}) ==========")
        raw = raw_by_code.get(game_code)
        if raw is None:
            print("  NOT FOUND in the cached getGameList response for that season.")
        else:
            print(json.dumps(raw, ensure_ascii=False, indent=2))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
