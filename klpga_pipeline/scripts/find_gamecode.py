"""One-off diagnostic: print every gameCode/title in a season's
getGameList response whose title contains a given substring. Used to
resolve the real gameCode for a tournament name when it doesn't match
what a --game-code guess actually returns."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.tournaments import fetch_game_list  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402

if __name__ == "__main__":
    season = int(sys.argv[1])
    needle = sys.argv[2]
    client = PoliteHttpClient(cache_dir=Path("data/raw_cache/http"))
    listings = fetch_game_list(client, season=season)
    print(f"season={season} total={len(listings)}")
    for l in listings:
        if needle in (l.game_title or ""):
            print(f"MATCH gameCode={l.game_code} title={l.game_title!r} start={l.start_date_raw} end={l.end_date_raw} finish={l.game_finish!r}")
    print("--- all titles (for context) ---")
    for l in listings:
        print(f"{l.game_code} {l.game_title} {l.start_date_raw}-{l.end_date_raw} finish={l.game_finish}")
