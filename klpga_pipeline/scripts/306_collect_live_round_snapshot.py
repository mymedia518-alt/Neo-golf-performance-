"""Generic, tournament-agnostic live round snapshot collector.

Generalizes the OK Open-specific scripts/96_ok_open_r1_active_cycle.py
collection step (same confirmed primitives: klpga.collectors.leaderboard
.fetch_round_leaderboard with use_cache=False, klpga.collectors
.group_page.fetch_group_page_html, klpga.parsers.round_progress
.resolve_round_progress) into a plain --game-code/--round CLI so it is
not tied to one tournament. Collection only -- this script never
computes or publishes any probability; see
scripts/307_build_live_probability.py for that, which consumes this
script's output.

Safe by default: with no --live flag, makes ZERO HTTP requests (prints
what it WOULD do and exits 0) -- same convention every real-collection
script in this project follows (see run_klpga_collector.py's own module
docstring, scripts/96's own header).

Output: content/website_v2/<GAME_CODE>_LIVE_R<round>_SNAPSHOT.json --
collected_at (real UTC timestamp of this fetch), and one row per player
carrying ONLY real, parsed facts (today_under_par, holes_completed,
status, total_under_par, rank_display) -- no estimate, no fabrication.
A player this round's leaderboard does not mention at all is simply
absent from `players` (the honest "not yet teed off" state is resolved
downstream by klpga.neo_win.sg_live_v1.build_live_states, not guessed
here).

This file OVERWRITES its own output on every run (it is a live,
mutable, re-collected snapshot, not an immutable archive) -- callers
that need an immutable record of a specific moment should copy it
elsewhere before the next cycle overwrites it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.collectors.group_page import fetch_group_page_html  # noqa: E402
from klpga.collectors.leaderboard import fetch_round_leaderboard_html  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.parsers.group_page_parser import parse_round_grouping  # noqa: E402
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402
from klpga.parsers.round_progress import resolve_round_progress  # noqa: E402

CONTENT = ROOT / "content" / "website_v2"


def collect(game_code: str, round_number: int, *, client: PoliteHttpClient) -> dict:
    leaderboard_html = fetch_round_leaderboard_html(client, game_code, round_number, use_cache=False)
    round_rows = parse_round_leaderboard_html(leaderboard_html, game_code=game_code, round_number=round_number)

    group_status, group_html = fetch_group_page_html(client, game_code)
    if group_status != 200:
        raise RuntimeError(f"group page fetch returned status {group_status}")
    try:
        groupings = parse_round_grouping(group_html, round_number)
        assumed_default_start_overall = False
    except ValueError:
        # Real, confirmed absence of this round's grouping tab (e.g. not
        # yet published) -- never fabricated; every player's starting
        # tee falls back to the documented OUT-start assumption and is
        # flagged, rather than failing the whole collection closed.
        groupings = []
        assumed_default_start_overall = True

    progress = resolve_round_progress(round_rows, groupings)

    players = []
    for row in round_rows:
        if row.player_code is None:
            continue
        hc = progress.get(row.player_code)
        players.append({
            "player_code": row.player_code,
            "player_name": row.player_name,
            "rank_display": row.rank_display,
            "status": row.status,
            "total_under_par": row.total_under_par,
            "today_under_par": row.today_under_par,
            "holes_completed": hc.completed if hc is not None else 0,
            "holes_completed_display": hc.display if hc is not None else "0H",
            "assumed_default_start": hc.assumed_default_start if hc is not None else assumed_default_start_overall,
        })

    return {
        "schema_version": 1,
        "game_code": game_code,
        "round": round_number,
        "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "player_count": len(players),
        "group_page_status": group_status,
        "group_page_round_found": bool(groupings) or not assumed_default_start_overall,
        "players": players,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--round", required=True, type=int)
    parser.add_argument("--live", action="store_true", help="Make real HTTP requests. Without this flag: dry run, zero network calls.")
    args = parser.parse_args()

    out_path = CONTENT / f"{args.game_code}_LIVE_R{args.round}_SNAPSHOT.json"

    if not args.live:
        print(f"DRY RUN (no --live): would fetch round {args.round} leaderboard + group page for "
              f"game_code={args.game_code} and write {out_path}. Zero HTTP requests made.")
        return

    client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "live_round_snapshot")
    snapshot = collect(args.game_code, args.round, client=client)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}: {snapshot['player_count']} player rows, collected_at={snapshot['collected_at']}")


if __name__ == "__main__":
    main()
