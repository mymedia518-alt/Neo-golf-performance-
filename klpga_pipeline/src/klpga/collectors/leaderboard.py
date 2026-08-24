"""Round leaderboard collector — real roundLeaderboard API adapter.

Confirmed via browser Network capture (see docs/SITE_STRUCTURE_TODO.md):

  POST https://klpga.co.kr/load/leaderboard/roundLeaderboard
  Content-Type: application/x-www-form-urlencoded
  form: gameCode=<code>, round=<n>
  response: HTML fragment (NOT JSON), parsed by
  klpga.parsers.leaderboard_parser.parse_round_leaderboard_html.

Request-count optimization (spec section 5): for a completed tournament,
fetch only the final round's leaderboard first. If every player who
actually finished the tournament already has round1..round4 scores in
that single response, no further requests are needed. Only players
missing an earlier round's score (typically CUT/WD/DQ players who never
reached the final round) trigger a *targeted* extra fetch of that
specific earlier round — never a blind refetch of every round.

How many rounds a given tournament was scheduled for is NOT confirmed
from any getGameList field, so `discover_final_round` probes downward
from config.PROBE_MAX_ROUNDS until it finds a round with player rows.
This is a discovery *strategy*, not fabricated tournament data.
"""
from __future__ import annotations

from typing import Optional

from klpga import config
from klpga.http_client import PoliteHttpClient
from klpga.parsers.leaderboard_parser import PlayerRoundRow, parse_round_leaderboard_html


def fetch_round_leaderboard_html(client: PoliteHttpClient, game_code: str, round_number: int) -> str:
    payload = {"gameCode": game_code, "round": str(round_number)}
    return client.post_text(config.ROUND_LEADERBOARD_ENDPOINT, data=payload)


def fetch_round_leaderboard(
    client: PoliteHttpClient, game_code: str, round_number: int
) -> list[PlayerRoundRow]:
    html = fetch_round_leaderboard_html(client, game_code, round_number)
    return parse_round_leaderboard_html(html, game_code=game_code, round_number=round_number)


def discover_final_round(
    client: PoliteHttpClient,
    game_code: str,
    max_round: int = config.PROBE_MAX_ROUNDS,
) -> tuple[int, list[PlayerRoundRow]]:
    """Probe downward from max_round to find the actual final round with
    player data. Returns (round_number, rows) for the first non-empty
    round found. Raises if no round in [1, max_round] has any rows —
    that's a real "couldn't determine the final round" failure, not
    something to guess past."""
    for rnd in range(max_round, 0, -1):
        rows = fetch_round_leaderboard(client, game_code, rnd)
        if rows:
            return rnd, rows
    raise ValueError(
        f"No player rows found for gameCode={game_code} in any round "
        f"1..{max_round} — cannot determine the final round."
    )


def collect_all_rounds_for_game(
    client: PoliteHttpClient,
    game_code: str,
    final_round: Optional[int] = None,
) -> dict[int, list[PlayerRoundRow]]:
    """Collect per-round rows for a completed tournament with minimal
    requests.

    1. Fetch the final round's leaderboard (discovering it first if not
       given).
    2. Check every row for missing round1..(final_round-1) scores.
    3. Only fetch an earlier round if at least one row is missing a
       score for it — and even then, only that specific round.
    """
    if final_round is None:
        final_round, final_rows = discover_final_round(client, game_code)
    else:
        final_rows = fetch_round_leaderboard(client, game_code, final_round)

    results: dict[int, list[PlayerRoundRow]] = {final_round: final_rows}

    round_score_getters = {
        1: lambda r: r.round1_score,
        2: lambda r: r.round2_score,
        3: lambda r: r.round3_score,
        4: lambda r: r.round4_score,
    }

    missing_rounds = {
        rnd
        for rnd in range(1, final_round)
        if rnd in round_score_getters
        and any(round_score_getters[rnd](row) is None for row in final_rows)
    }

    for rnd in sorted(missing_rounds):
        results[rnd] = fetch_round_leaderboard(client, game_code, rnd)

    return results
