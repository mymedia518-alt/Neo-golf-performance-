"""RED TEAM (2026-09-25): the ONE shared utility for ordering
tournaments chronologically. Every module that orders a player's
tournaments in time -- Player History, Player Intelligence, Tournament
History, Rolling Average, Recent Form, Career Timeline, Season Replay,
DNA -- must sort through sort_tournaments()/tournament_sort_key() here.
No module may write its own (season, game_code) or (game_code,) sort
key inline; that is exactly the bug this module fixes.

Root cause this replaces: game_code is an internal KLPGA tournament id,
not a date, and season is a coarse year bucket -- neither is a reliable
chronology proxy within a season. Confirmed wrong in this repository:
2026090003 (KB금융 골든라이프 챔피언십) really ended 2026-09-13;
2026090002 (하나금융그룹 챔피언십) really ended 2026-09-20 -- later --
but game_code order (090002 < 090003) sorts Hana BEFORE KB. The one
source of REAL per-tournament dates in this repository is
content/website_v2/OFFICIAL_KLPGA_SCHEDULE.json, loaded through
klpga.website_v2.official_schedule (never re-parsed ad hoc here or
anywhere else).

Coverage note (disclosed, not hidden): that schedule artifact currently
covers only the season's most recent tail (dates were captured as
tournaments were actually played) -- most of a career's tournaments
have no real date on file. For those, this utility falls back to the
same (season, game_code) proxy every caller already used -- it never
fabricates a date. The fallback is scoped to WITHIN a season (season
itself is always a real fact, never a proxy), so a real date is only
ever used to correct ordering among tournaments the pipeline already
knows happened in the same year; it can never silently reorder across
season boundaries. Within a season, a real-dated tournament always
sorts after every proxy-only one there -- true for every entry this
repository has ever captured a real date for (all of them are the
recency-biased tail of the season being actively collected), but this
is a real, disclosed limitation, not a proof for all future data: if a
schedule entry is ever added for an OLDER, not-most-recent event in a
season, this module's ordering-within-real-dates still stays correct,
but its placement relative to that season's undated tournaments would
need re-examination.
"""
from __future__ import annotations

from typing import Optional

import json

from klpga.tournament_context import CONTENT_DIR
from klpga.website_v2.official_schedule import load_official_schedule

_SCHEDULE_PATH = CONTENT_DIR / "OFFICIAL_KLPGA_SCHEDULE.json"
_MASTER_DATES_PATH = CONTENT_DIR / "TOURNAMENT_MASTER_DATES_V1.json"


def load_schedule_end_dates() -> dict[str, str]:
    """{game_code: real official end_date (ISO)} for every tournament
    the official schedule artifact currently covers. Missing/unreadable
    file -> empty dict (every caller then falls back to the existing
    (season, game_code) proxy for everything, exactly as before this
    utility existed -- never an error that blocks report generation).
    Unchanged by the 2026-10-01 fix below -- kept exactly as it was so
    any direct caller of this one function keeps its exact behavior."""
    if not _SCHEDULE_PATH.exists():
        return {}
    try:
        entries = load_official_schedule(_SCHEDULE_PATH)
    except Exception:
        return {}
    return {e.game_code: e.end_date for e in entries}


def load_master_start_dates() -> dict[str, str]:
    """{game_code: real official start_date (ISO)}, read from
    content/website_v2/TOURNAMENT_MASTER_DATES_V1.json -- a real,
    committed snapshot of tournament_master.start_date (102 game_codes,
    generated 2026-09-10; see that file's own "source_query"). Missing/
    unreadable file or a null date value -> simply absent from the
    returned dict, never fabricated."""
    if not _MASTER_DATES_PATH.exists():
        return {}
    try:
        doc = json.loads(_MASTER_DATES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {gc: d for gc, d in doc.get("dates", {}).items() if d}


def load_real_tournament_dates() -> dict[str, str]:
    """RED TEAM BUG FIX (2026-10-01): the single merged real-date source
    sort_tournaments() now falls back to by default, replacing the old
    "game_code string order approximates calendar order" assumption,
    which real dates disprove (confirmed: within a single month, the
    trailing game_code sequence number does NOT track real start_date --
    e.g. July 2026: 2026070003 is the OLDEST of that month's three
    events by real date, not the newest; August 2026: 2026080004 is the
    EARLIEST of that month's four, 2026080001 the LATEST -- exactly
    backwards from naive ascending-game_code order).

    Merges load_master_start_dates() (102 game_codes, start_date) with
    load_schedule_end_dates() (5 game_codes, end_date) -- the schedule
    entries take priority on overlap (none of the 2 game_codes the two
    sources both cover ever disagree in practice, confirmed by direct
    comparison), since that was this module's original, narrower,
    already-tested real-date source. Every OTHER caller behavior
    (season-boundary protection, tiebreak-only semantics, proxy
    fallback on a still-missing date) is completely unchanged -- only
    the real-date dictionary sort_tournaments() consults by default is
    wider now."""
    merged = dict(load_master_start_dates())
    merged.update(load_schedule_end_dates())
    return merged


def tournament_sort_key(
    game_code: str,
    season: int,
    schedule_end_dates: dict[str, str],
    *,
    tiebreak: Optional[str] = None,
) -> tuple:
    """The one sort key every tournament-ordering site must use.
    `tiebreak` (e.g. a round number) breaks ties among rows that share
    one tournament -- appended last so it never affects tournament-vs-
    tournament order, only intra-tournament order."""
    season = season or 0
    game_code = game_code or ""
    real_end_date = schedule_end_dates.get(game_code)
    if real_end_date:
        key = (season, 1, real_end_date, game_code)
    else:
        key = (season, 0, game_code, game_code)
    return key if tiebreak is None else key + (tiebreak,)


def sort_tournaments(
    events: list,
    *,
    game_code_key: str = "game_code",
    season_key: str = "season",
    tiebreak_key: Optional[str] = None,
    schedule_end_dates: Optional[dict[str, str]] = None,
) -> list:
    """Sort a list of dicts (or objects, via getattr fallback) that
    each represent one tournament (or one row belonging to one
    tournament) into real chronological order. `schedule_end_dates`
    may be passed in (e.g. loaded once per build() call) to avoid
    re-reading the date files per call, and an explicit value --
    including {} -- is always honored verbatim (every existing test
    that pins exact proxy-fallback behavior passes one). Omit it to
    load the merged real-date dictionary fresh: load_real_tournament_
    dates(), not load_schedule_end_dates() alone (2026-10-01 RED TEAM
    fix -- see that function's own docstring for why)."""
    end_dates = schedule_end_dates if schedule_end_dates is not None else load_real_tournament_dates()

    def _get(item, key):
        return item.get(key) if isinstance(item, dict) else getattr(item, key)

    def _key(item):
        tiebreak = _get(item, tiebreak_key) if tiebreak_key else None
        return tournament_sort_key(_get(item, game_code_key), _get(item, season_key), end_dates, tiebreak=tiebreak)

    return sorted(events, key=_key)


def sort_by_official_date(items: list, date_key: str, *, reverse: bool = False) -> list:
    """MISSION V9 (2026-09-25) governance audit: the one caller that
    never needed the (season, game_code) proxy at all -- every item it
    sorts (an official schedule entry) already carries its own real
    ISO date, so there is nothing to fall back from. Still routed
    through this module rather than reimplemented locally, so no
    tournament-adjacent chronology sort exists anywhere else in the
    repository, proxy-based or not. Accepts dicts or objects (getattr
    fallback), matching sort_tournaments()'s own convention above."""
    def _get(item):
        return item.get(date_key) if isinstance(item, dict) else getattr(item, date_key)

    return sorted(items, key=_get, reverse=reverse)
