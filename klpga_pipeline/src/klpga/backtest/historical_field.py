"""Reconstruct the evaluation field for a HISTORICAL target tournament —
i.e. "which players does this backtest row need a prediction for."

======================================================================
LIMITATION — read before using this for anything (per explicit
red-team requirement #2)
======================================================================
`tournament_entry` (see docs/SITE_STRUCTURE_TODO.md section 7) only
exists going FORWARD from 2026-08-25 — it was never collected for any
of the 100 validated historical tournaments, and there is no confirmed
way to retroactively reconstruct a historical ENTRY list (who was
scheduled/eligible to play before the tournament started).

The only confirmed historical data this project has is `player_event`
— built from the roundLeaderboard endpoint, i.e. it reflects who
actually appears in the site's own collected RESULTS for that
tournament (including missed-cut/incomplete-round players — see
docs/SITE_STRUCTURE_TODO.md section 5 for the CUT/999-sentinel
collection fix that makes this membership set as complete as this
project's collection can make it). This is therefore a RESULT field,
not a true pre-tournament ENTRY field, and the two are not guaranteed
identical:
  - A player who withdrew before ever appearing in any collected round
    response (e.g. withdrew the morning of round 1, before a single
    score was posted) would NOT appear in player_event at all, and so
    would NOT appear in this reconstructed field, even though she may
    have been a real, confirmed entrant.
  - Conversely there is no known case of the reverse (a player in
    player_event who was never actually entered) — player_event is
    built strictly from the site's own round-by-round leaderboard, so
    every row it contains reflects a player who genuinely appeared in
    a real collected round.

This is disclosed here, not hidden: `HistoricalFieldResult.source`
names this limitation explicitly, and every caller (walk_forward.py,
the diagnostic script) surfaces it rather than presenting the
reconstructed field as if it were a true historical entry list.

Field MEMBERSHIP (player_code/player_name) and the tournament's OUTCOME
(finish position, made_cut, win) both come from the same player_event
row here, but are kept in clearly separate dataclass fields —
`FieldMember`'s outcome fields are LABELS ONLY and must never be read
by anything computing point-in-time FEATURES (see
klpga.backtest.point_in_time_features, which never imports this
module's outcome fields as inputs).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

HISTORICAL_FIELD_SOURCE = (
    "player_event (site-collected RESULT field for this event, not a confirmed "
    "pre-tournament ENTRY list — tournament_entry was never collected for "
    "historical tournaments; see this module's docstring for the exact "
    "limitation)"
)


@dataclass(frozen=True)
class FieldMember:
    player_code: str
    player_name: str

    # ---- LABEL fields (outcome of the target tournament) ----
    # Never pass these into a feature computation — they describe WHAT
    # HAPPENED at the target tournament, which is exactly what a
    # point-in-time feature must never see.
    label_finish_position: Optional[str]
    label_finish_position_numeric: Optional[int]
    label_made_cut: bool
    label_is_winner: bool


@dataclass(frozen=True)
class HistoricalFieldResult:
    target_event_id: str
    members: tuple[FieldMember, ...]
    source: str = HISTORICAL_FIELD_SOURCE


def reconstruct_historical_field(conn: sqlite3.Connection, target_event_id: str) -> HistoricalFieldResult:
    """Every player_event row for target_event_id becomes one
    FieldMember — see module docstring for exactly what this does and
    does not confirm. Returns an empty member tuple (not an error) if
    the event_id has no player_event rows at all."""
    rows = conn.execute(
        """
        SELECT player_id, player_name, finish_position, finish_position_numeric, made_cut
        FROM player_event
        WHERE event_id = ?
        """,
        (target_event_id,),
    ).fetchall()

    members = tuple(
        FieldMember(
            player_code=row[0],
            player_name=row[1],
            label_finish_position=row[2],
            label_finish_position_numeric=row[3],
            label_made_cut=bool(row[4]),
            label_is_winner=(row[3] == 1),
        )
        for row in rows
    )
    return HistoricalFieldResult(target_event_id=target_event_id, members=members)
