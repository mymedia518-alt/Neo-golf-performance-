"""Round-agnostic "현재 스코어" cell formatter for HOME's TOP120 table.

Takes a real tournament-total-to-par score plus the CURRENT round's raw
holes-completed/status text and produces one compact display string
("-4 · 12H", "-5 · F", "—") plus the structured sort fields the page's
own JS sort reads (never re-parses the display string -- see
top120.js). Deliberately round-agnostic: this never hardcodes "R1" --
it always reads "the tournament's current total to par" and "the
current round's progress", so the identical formatter keeps working
once R2/R3/FINAL snapshots exist, with zero changes here.

Normalizes only the DISPLAY state (raw KLPGA holes-completed/status
text varies -- "18", "F", "Finished", "종료" have all been observed or
are plausible) -- the raw source fields themselves are never altered,
only read.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_COMPLETE_TOKENS = {"18", "F", "FINAL", "FINISHED", "COMPLETE", "COMPLETED", "종료"}
_ROUND_HOLE_COUNT = 18


@dataclass(frozen=True)
class CurrentScoreCell:
    display: str
    sort_score: Optional[int]
    """Tournament total to par, or None when there is nothing to sort
    by (no live data)."""
    sort_holes: Optional[int]
    """Holes completed in the current round (COMPLETE normalizes to
    18, matching a finished round's real hole count), or None."""
    sort_status: str
    """'IN_PROGRESS' | 'COMPLETE' | 'NO_DATA'."""


def normalize_hole_state(holes_completed, status) -> tuple[str, Optional[int]]:
    """(state, holes) where state is 'NOT_STARTED' | 'IN_PROGRESS' |
    'COMPLETE'. Checks `status` first (some sources report completion
    there, e.g. "Finished"/"종료"), then `holes_completed`. Any value
    that cannot be confidently classified is treated as NOT_STARTED --
    never guessed into IN_PROGRESS or COMPLETE."""
    if status is not None and str(status).strip().upper() in _COMPLETE_TOKENS:
        return "COMPLETE", _ROUND_HOLE_COUNT
    if holes_completed is None:
        return "NOT_STARTED", None
    raw = str(holes_completed).strip()
    if not raw or raw == "0":
        return "NOT_STARTED", None
    if raw.upper() in _COMPLETE_TOKENS:
        return "COMPLETE", _ROUND_HOLE_COUNT
    try:
        holes = int(raw)
    except ValueError:
        return "NOT_STARTED", None
    if holes <= 0:
        return "NOT_STARTED", None
    if holes >= _ROUND_HOLE_COUNT:
        return "COMPLETE", _ROUND_HOLE_COUNT
    return "IN_PROGRESS", holes


def _format_score(score_to_par: int) -> str:
    return "E" if score_to_par == 0 else f"{score_to_par:+d}"


def format_current_score(score_to_par: Optional[int], holes_completed, status) -> CurrentScoreCell:
    """`score_to_par`: real tournament-cumulative-total-to-par (e.g.
    R1's running total, or R2's running total once R2 is live) --
    never "today's round score" alone (see module docstring). None
    means this player has no live data at all (not in the field, or no
    validated snapshot exists) -- renders "—", never a guess."""
    if score_to_par is None:
        return CurrentScoreCell("—", None, None, "NO_DATA")
    state, holes = normalize_hole_state(holes_completed, status)
    if state == "NOT_STARTED":
        return CurrentScoreCell("—", None, None, "NO_DATA")
    score_str = _format_score(score_to_par)
    if state == "COMPLETE":
        return CurrentScoreCell(f"{score_str} · F", score_to_par, _ROUND_HOLE_COUNT, "COMPLETE")
    return CurrentScoreCell(f"{score_str} · {holes}H", score_to_par, holes, "IN_PROGRESS")
