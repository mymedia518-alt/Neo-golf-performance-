"""Read-only inspection of a roundLeaderboard HTTP cache entry — never
deletes, never modifies, never fetches. Built for
scripts/final_close_preflight.py's stale-cache evidence step: proving
(or ruling out) that a round was silently discovered short of the
real, current site state because an earlier probe cached an EMPTY
response for that round before it had actually been played (see
klpga.collectors.leaderboard.collect_all_rounds_for_game's own
force_refresh_rounds docstring for the full mechanism).

Uses PoliteHttpClient.post_cache_path so the cache-key derivation is
never duplicated/second-guessed here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga import config
from klpga.http_client import PoliteHttpClient
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html


@dataclass
class RoundCacheInspection:
    game_code: str
    round_number: int
    cache_path: Path
    exists: bool
    mtime_utc: Optional[str] = None
    body_length: Optional[int] = None
    player_row_count: Optional[int] = None
    is_empty: Optional[bool] = None
    """True only when the cache entry exists and contains zero parsed
    player rows — the exact signature of a "probed before the round
    was played" stale entry. None if the entry doesn't exist at all
    (nothing to classify as stale vs. fresh)."""


def inspect_round_leaderboard_cache(
    client: PoliteHttpClient, game_code: str, round_number: int
) -> RoundCacheInspection:
    """Read-only. Computes the exact cache path `fetch_round_leaderboard_html`
    would use for this (game_code, round_number) and, if it exists,
    reports its real mtime, body length, and parsed player-row count —
    without ever writing, deleting, or triggering a fetch."""
    payload = {"gameCode": game_code, "round": str(round_number)}
    cache_path = client.post_cache_path(config.ROUND_LEADERBOARD_ENDPOINT, data=payload)

    if not cache_path.exists():
        return RoundCacheInspection(
            game_code=game_code, round_number=round_number, cache_path=cache_path, exists=False,
        )

    stat = cache_path.stat()
    mtime_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    body_text = cached.get("body_text", "")
    rows = parse_round_leaderboard_html(body_text, game_code=game_code, round_number=round_number)

    return RoundCacheInspection(
        game_code=game_code, round_number=round_number, cache_path=cache_path, exists=True,
        mtime_utc=mtime_utc, body_length=len(body_text), player_row_count=len(rows),
        is_empty=(len(rows) == 0),
    )
