"""One-off diagnostic: for tournament_master rows that ended up with
ZERO player_event rows (leaderboard collection found no round data at
all — discover_final_round exhausted rounds 1..config.PROBE_MAX_ROUNDS
with nothing), this:

  1. Prints the raw getGameList entry for each failed tournament AND
     for one successfully-collected tournament (a baseline) — every
     field the site returned, not just the ones we normally parse —
     so the two can be diffed by eye for a distinguishing field (a
     game-type/score-type flag, etc). The getGameList calls this makes
     are cache hits against the original 01_collect_tournaments.py run
     (same --cache-dir), so this part makes ZERO new network requests.

  2. Probes round=1..N (default N=8, beyond the normal 1..4) against
     the REAL roundLeaderboard endpoint for each failed gameCode. This
     DOES make new network requests (rate-limited, same as any other
     collection step) — testing whether e.g. a match-play bracket
     ("7Round Match Play" per the tournament name) actually has data at
     higher round numbers that the normal 1..4 probe never reaches.

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
from klpga.collectors.leaderboard import fetch_round_leaderboard  # noqa: E402
from klpga.collectors.tournaments import fetch_game_list  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument(
        "--probe-rounds", type=int, default=8,
        help="try round=1..N for each failed gameCode (default 8) — makes new network requests",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    failed = conn.execute(
        "SELECT tm.game_code, tm.event_name, tm.season FROM tournament_master tm "
        "LEFT JOIN player_event pe ON tm.event_id = pe.event_id "
        "WHERE pe.event_id IS NULL "
        "ORDER BY tm.season, tm.game_code"
    ).fetchall()
    baseline = conn.execute(
        "SELECT DISTINCT tm.game_code, tm.event_name, tm.season FROM tournament_master tm "
        "INNER JOIN player_event pe ON tm.event_id = pe.event_id "
        "LIMIT 1"
    ).fetchone()
    conn.close()

    if not failed:
        print("No tournament_master rows with zero player_event rows — nothing to inspect.")
        return 0

    print(f"{len(failed)} tournament(s) with zero player_event rows:\n")

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    seasons_needed = sorted({season for _, _, season in failed} | ({baseline[2]} if baseline else set()))
    raw_by_code = {}
    for season in seasons_needed:
        for listing in fetch_game_list(client, season=season, tour_type=config.TOUR_TYPE_REGULAR):
            raw_by_code[listing.game_code] = listing.raw

    if baseline:
        base_code, base_name, base_season = baseline
        print(f"===== BASELINE (successfully collected): {base_code} ({base_name}, season={base_season}) =====")
        raw = raw_by_code.get(base_code)
        print(json.dumps(raw, ensure_ascii=False, indent=2) if raw else "  NOT FOUND")
        print()

    for game_code, event_name, season in failed:
        print(f"========== {game_code} ({event_name}, season={season}) ==========")
        raw = raw_by_code.get(game_code)
        if raw is None:
            print("  NOT FOUND in the cached getGameList response for that season.")
        else:
            print(json.dumps(raw, ensure_ascii=False, indent=2))

        print(f"  Probing round=1..{args.probe_rounds} against the real roundLeaderboard endpoint...")
        for rnd in range(1, args.probe_rounds + 1):
            rows = fetch_round_leaderboard(client, game_code, rnd)
            detail = f" -- e.g. rank={rows[0].rank_display!r} name={rows[0].player_name!r}" if rows else ""
            print(f"    round={rnd}: {len(rows)} player row(s){detail}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
