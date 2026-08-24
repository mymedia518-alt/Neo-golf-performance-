"""One-off diagnostic: dump the raw roundLeaderboard HTML row for
players whose finish_position == '999' (a sentinel value discovered on
the live 5-tournament run — distinct from the normal numeric ranks
given to the 2-round missed-cut group), across every round they might
appear in. The goal is to find any status marker (a class name, title
attribute, different text, etc.) beyond the bare "999" rank that would
let us tell WD apart from DQ, or confirm there isn't one.

Uses the SAME disk cache as the original collection run — pass the same
--cache-dir and this makes ZERO new network requests, since every round
for these tournaments was already fetched.

Usage:
    python scripts/07_inspect_status_markup.py --db data/klpga_small.sqlite --cache-dir data/raw_cache/http
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.leaderboard import fetch_round_leaderboard_html  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def find_row_context(html: str, player_code: str, context_chars: int = 400) -> str | None:
    """Return the HTML surrounding the given player's row (walking back
    to the nearest opening tag, forward to its closing tag), or None if
    that player_code doesn't appear in this HTML at all."""
    marker = f'_playercode="{player_code}"'.lower()
    idx = html.lower().find(marker)
    if idx == -1:
        return None
    start = html.rfind("<", 0, idx)
    if start == -1:
        start = max(0, idx - context_chars)
    close_start = html.find("</", idx)
    end = html.find(">", close_start) + 1 if close_start != -1 else idx + context_chars
    return html[max(0, start - context_chars) : end + 50]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga_small.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    samples = conn.execute(
        "SELECT event_id, player_id, player_name FROM player_event WHERE finish_position='999' LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()

    if not samples:
        print("No finish_position='999' rows found in this DB — nothing to inspect.")
        return 0

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))

    for event_id, player_id, player_name in samples:
        print(f"========== {event_id} / playerCode={player_id} ({player_name}) ==========")
        for rnd in (1, 2, 3, 4):
            try:
                html = fetch_round_leaderboard_html(client, event_id, rnd)
            except Exception as exc:  # noqa: BLE001
                print(f"  [round={rnd}] ERROR fetching (should have been a cache hit): {exc}")
                continue
            context = find_row_context(html, player_id)
            if context is None:
                print(f"  [round={rnd}] playerCode {player_id} NOT present in this round's HTML at all.")
            else:
                print(f"  [round={rnd}] playerCode {player_id} row context:")
                print("  " + context.replace("\n", "\n  "))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
