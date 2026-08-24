"""Round leaderboard collector — real roundLeaderboard API adapter.

Confirmed via browser Network capture (see docs/SITE_STRUCTURE_TODO.md):

  POST https://klpga.co.kr/load/leaderboard/roundLeaderboard
  Content-Type: application/x-www-form-urlencoded
  form: gameCode=<code>, round=<n>
  response: HTML fragment (NOT JSON), parsed by
  klpga.parsers.leaderboard_parser.parse_round_leaderboard_html.

Request-count optimization (spec section 5), corrected after a real bug
found on live data: a 5-tournament run showed player_round == 4 *
player_event EXACTLY across all 336 collected player_event rows — i.e.
every single collected player had all 4 rounds, with zero made_cut=0 /
withdrawn / disqualified rows anywhere. That's not plausible as "none of
5 real tournaments had a cut" — the actual cause was that the original
strategy only checked players ALREADY PRESENT in the final round's
response for missing individual round scores. A player who is cut and
therefore absent from the final round's row list ENTIRELY (not just
missing some fields on a present row) was never detected at all, so
CUT/WD/DQ players were being silently dropped from collection rather
than recorded with the correct status.

Fixed strategy:
  1. Fetch the final round's leaderboard (discovering it first if not
     given).
  2. ALSO fetch round 1 unconditionally (unless round 1 IS the final
     round) — round 1 is the one round the full starting field is
     guaranteed to appear on, so comparing its player_code set against
     the final round's reveals anyone who dropped out.
  3. If the two rounds' player_code sets differ, fetch every
     intermediate round too, to find each dropped player's actual
     last-played round (and whatever status the site shows there) —
     since we can't know in advance which round a given player was cut
     after. This costs more requests than the single-round-only
     strategy, but data completeness/correctness takes priority over
     request-count minimization per the project's own requirements.
  4. If the two rounds' player_code sets are IDENTICAL (a real
     confirmed no-cut/small-field event), fall back to the narrower
     per-score missing check across just those two rounds.

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


_ROUND_SCORE_GETTERS = {
    1: lambda r: r.round1_score,
    2: lambda r: r.round2_score,
    3: lambda r: r.round3_score,
    4: lambda r: r.round4_score,
}


def _player_codes(rows: list[PlayerRoundRow]) -> set[str]:
    return {r.player_code for r in rows if r.player_code is not None}


def collect_all_rounds_for_game(
    client: PoliteHttpClient,
    game_code: str,
    final_round: Optional[int] = None,
) -> dict[int, list[PlayerRoundRow]]:
    """Collect per-round rows for a completed tournament. See the module
    docstring for why this fetches round 1 unconditionally and expands
    to every intermediate round when the field doesn't match — this is
    a correctness fix for CUT/WD/DQ players being silently dropped, not
    just a request-count optimization anymore."""
    if final_round is None:
        final_round, final_rows = discover_final_round(client, game_code)
    else:
        final_rows = fetch_round_leaderboard(client, game_code, final_round)

    results: dict[int, list[PlayerRoundRow]] = {final_round: final_rows}

    if final_round != 1:
        results[1] = fetch_round_leaderboard(client, game_code, 1)

    round1_players = _player_codes(results.get(1, []))
    final_players = _player_codes(final_rows)
    dropped_players = round1_players - final_players

    rounds_to_fetch: set[int] = set()
    if dropped_players:
        # Some players on round 1 never appear on the final round at
        # all — fetch every remaining round to find where each one's
        # real last-played data (and CUT/WD/DQ marker, if the site
        # shows one there) actually is.
        rounds_to_fetch.update(range(2, final_round))
    else:
        # Identical field on round 1 and the final round: a real
        # confirmed no-cut/no-dropout case for this tournament. Still
        # check the FINAL round's own rows for a player missing an
        # individual round's SCORE. Round 1's response is deliberately
        # excluded from this check — it can never meaningfully carry
        # round2..round(final) scores, since those rounds hadn't been
        # played yet at the time round 1 was the current round, so
        # those fields being blank there is normal, not "missing."
        for rnd in range(2, final_round):
            getter = _ROUND_SCORE_GETTERS.get(rnd)
            if getter is not None and any(getter(row) is None for row in final_rows):
                rounds_to_fetch.add(rnd)

    for rnd in sorted(rounds_to_fetch):
        if rnd not in results:
            results[rnd] = fetch_round_leaderboard(client, game_code, rnd)

    return results
