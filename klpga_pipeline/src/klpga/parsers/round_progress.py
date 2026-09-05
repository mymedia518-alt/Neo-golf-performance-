"""Resolve each player's TRUE completed-hole count for the CURRENT round.

This exists because neither of KLPGA's two real, confirmed data sources
alone can answer "how many holes has this player actually played?":

  - roundLeaderboard's `data-inghole` (see leaderboard_parser.py) is the
    REAL COURSE HOLE NUMBER of the last hole the player has played, not
    a count of holes played. Confirmed real values seen so far are only
    "18" (round finished) or "" (no data) -- no live mid-round capture
    with a non-1 starting tee exists anywhere in this repo, so the
    exact mid-round semantics of this attribute have never been
    directly observed. This module's formula below is the only
    interpretation consistent with (a) the attribute's own name
    ("in-progress hole"), (b) it confirmed reading "18" at the real
    course hole where an OUT-starter's round ends, and (c) the site's
    own real, confirmed starting-tee data (see below) -- but it should
    be reconfirmed the moment a real mid-round, non-1-tee capture is
    obtained.
  - the group/tee-time page's `td.fixed-start` (see
    group_page_parser.parse_round_grouping -> GroupingRow.starting_tee)
    gives the real, confirmed starting tee for the round ("1" for an
    OUT start, "10" for an IN start).

Naive use of data-inghole alone is exactly the bug this module fixes:
a player who started hole 10 and has played holes 10-16 (7 holes) has
data-inghole="16" -- displaying that raw value directly ("16H") is
wrong. The real completed-hole count only comes from combining it with
the player's real starting tee.

Formula (18-hole rounds only -- KLPGA rounds are always 18 holes):
    completed = ((current_hole - starting_tee) mod 18) + 1
This holds for any starting tee 1-18, and naturally yields 18 for a
finished round regardless of starting tee (e.g. start=10, last hole
played=9 (wrapped) -> completed=18).

Never fabricates a positive count from missing/invalid data: a player
with no parseable current-hole value is reported as 0 (holes completed
so far in evidence = 0 -- covers "hasn't teed off yet").

WD/DQ/CUT/INCOMPLETE status does NOT blank this value: scripts/84's own
row renderer (see its module docstring and
tests/test_ok_open_r1_unresolved_status_rendering.py) deliberately keeps
완료홀 (holes completed) untouched even on an unresolved-status row --
"they are real, officially collected facts, not part of the [999]
sentinel". Only rank/score fields are known to reset to a placeholder
for that sentinel (see leaderboard_parser.py) -- data-inghole itself is
not documented as doing so, so this module runs the same real-hole ->
completed-count arithmetic regardless of status; status is not a
parameter here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_HOLES_PER_ROUND = 18


@dataclass(frozen=True)
class HolesCompletedResult:
    """completed is 0 only when there is no real current-hole evidence
    at all (pre-round / missing data) -- never a guess otherwise.
    display is the ready-to-render UI string ("0H".."18H").
    assumed_default_start is True only when a real starting_tee was not
    available and tee=1 (OUT) was assumed as a documented, non-silent
    fallback -- callers/UI should treat such a result as less certain
    than one with a real starting_tee."""

    completed: int
    display: str
    assumed_default_start: bool


def _parse_hole_number(value: Optional[str]) -> Optional[int]:
    """Plain 1-18 integer parse. Never guesses: anything else (empty,
    non-numeric, out of range) is treated as no real hole-number data."""
    if value is None:
        return None
    text = str(value).strip()
    if not text.isdigit():
        return None
    parsed = int(text)
    return parsed if 1 <= parsed <= _HOLES_PER_ROUND else None


def resolve_completed_holes(
    raw_inghole: Optional[str],
    starting_tee: Optional[str],
) -> HolesCompletedResult:
    """Pure calculation -- no I/O, no site knowledge beyond the two
    confirmed attributes described in the module docstring. Status is
    deliberately not a parameter here: see the module docstring for why
    this value is computed the same way regardless of WD/DQ/CUT/
    INCOMPLETE."""
    current_hole = _parse_hole_number(raw_inghole)
    if current_hole is None:
        # No real evidence of any hole played yet -- pre-round / not
        # yet teed off. Never fabricated as anything but 0.
        return HolesCompletedResult(completed=0, display="0H", assumed_default_start=False)

    tee = _parse_hole_number(starting_tee)
    assumed_default_start = tee is None
    if tee is None:
        tee = 1  # documented fallback: majority-case OUT start, flagged via assumed_default_start

    completed = ((current_hole - tee) % _HOLES_PER_ROUND) + 1
    return HolesCompletedResult(completed=completed, display=f"{completed}H", assumed_default_start=assumed_default_start)


def resolve_round_progress(
    round_rows,
    groupings,
) -> dict[str, HolesCompletedResult]:
    """Join roundLeaderboard rows (klpga.parsers.leaderboard_parser.
    PlayerRoundRow, for one round) with that same round's real grouping
    (klpga.parsers.group_page_parser.GroupingRow, from
    parse_round_grouping) by player_code, and resolve each player's
    real completed-hole count.

    A player with no matching grouping row (e.g. the group page hasn't
    been collected, or a real gap in the data) is not dropped or
    guessed at -- resolve_completed_holes still runs with
    starting_tee=None, which falls back to the documented OUT-start
    assumption and reports assumed_default_start=True so callers can
    surface that reduced confidence rather than silently trusting it."""
    starting_tee_by_player = {
        g.player_code: g.starting_tee for g in groupings if g.player_code is not None
    }

    result: dict[str, HolesCompletedResult] = {}
    for row in round_rows:
        if row.player_code is None:
            continue
        starting_tee = starting_tee_by_player.get(row.player_code)
        result[row.player_code] = resolve_completed_holes(row.holes_completed, starting_tee)
    return result
