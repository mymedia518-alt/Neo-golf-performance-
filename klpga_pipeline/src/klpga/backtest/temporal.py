"""Temporal-cutoff helpers shared by every point-in-time computation in
this package — the single place that decides "is tournament A strictly
before tournament B."

CONFIRMED (docs/SITE_STRUCTURE_TODO.md section 1): `tournament_master.
start_date` is a real, confirmed getGameList field (`startDate`,
`YYYYMMDD`), stored as ISO-8601 TEXT. It is still schema-nullable,
because it was added to this project's collectors after `end_date` and
older already-collected rows (or any future collection bug) could in
principle lack it — this module does not assume 100% coverage.

Per the explicit red-team requirement to "use tournament start_date/
end_date ordering explicitly" and to "fail safely rather than leak" on
same-day/date ambiguity:

  - `effective_tournament_date` prefers `start_date`; only falls back to
    `end_date` when `start_date` is NULL, and always reports which one
    it used (`is_exact`) so callers/diagnostics can disclose the
    fallback rather than hide it.
  - `is_strictly_before` requires BOTH dates to be present and the
    candidate's effective date to be STRICTLY earlier than the target's
    — a tie (same calendar day) or either date missing returns False
    (exclude), never True (include). This is the one function every
    other module in this package calls to decide "is this row allowed
    into a target tournament's point-in-time features" — getting it
    wrong in the permissive direction would be a real leak, so it never
    guesses.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class EffectiveDate:
    value: Optional[date]
    is_exact: bool  # True if start_date was used; False if end_date fallback (or no date at all)


def _parse_iso_date(text: Optional[str]) -> Optional[date]:
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def effective_tournament_date(start_date: Optional[str], end_date: Optional[str]) -> EffectiveDate:
    """start_date (confirmed real getGameList field) is preferred.
    Falls back to end_date only when start_date is NULL/unparseable,
    with is_exact=False so callers can disclose the fallback. Returns
    (None, False) if neither is usable — callers must treat that as
    "no safe cutoff can be drawn," never as "no history exists.\""""
    parsed_start = _parse_iso_date(start_date)
    if parsed_start is not None:
        return EffectiveDate(parsed_start, is_exact=True)
    parsed_end = _parse_iso_date(end_date)
    if parsed_end is not None:
        return EffectiveDate(parsed_end, is_exact=False)
    return EffectiveDate(None, is_exact=False)


def is_strictly_before(candidate: Optional[date], target: Optional[date]) -> bool:
    """Fail-safe temporal ordering: True only if both dates are present
    AND candidate < target. A same-day tie or a missing date on either
    side returns False (exclude) — never a guess in the permissive
    direction."""
    if candidate is None or target is None:
        return False
    return candidate < target
