"""PUBLIC UI Phase 8: a generic last/current/next tournament resolver
for HOME's three tournament cards (지난 대회 / 이번 대회 / 다음 대회).

Never date-guesses a tournament's LIVE STAGE (that stays
klpga.website_v2.tournament_state.home_mode()'s job, driven only by
real validated stage-state artifacts) -- this module only orders
already-scheduled tournaments chronologically by their own real,
officially-sourced start/end dates, to answer "which one just
finished, which one is on now, which one is next", never "what stage
is the current one at".

Red Team FAIL B remediation: calendar identity now comes ONLY from
klpga.website_v2.official_schedule's ScheduleEntry list (the
authoritative KLPGA calendar artifact) -- never from
TOURNAMENT_SITE_REGISTRY.json (route/presentation metadata only, joined
on by game_code for url_base/hub_card display copy) and never from
internal pipeline stage-validation state. A previous version of this
resolver let a real stage-completion signal
(tournament_state.ok_open_tournament_is_complete()) override a stale
scheduled end_date so a still-being-played tournament wouldn't
disappear from 이번 대회 -- that inverted the actual bug: it let
internal pipeline staleness (this sandbox has no live network access
to ever validate OK Open's FINAL stage) keep a tournament pinned to
이번 대회 for days after it had genuinely, officially ended by
calendar date. Pipeline stage freshness must never decide calendar
identity in either direction -- only the official schedule's own
start_date/end_date does now.

A game_code present in the schedule but absent from the site registry
(no public page exists for it yet) still produces a full
TournamentCardFacts -- tournament_name/dates/venue are real, sourced
from the schedule; url_base stays "" so the card renders the facts
with no link, per FAIL B's "known official tournament, no public page
yet" requirement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from klpga.website_v2.official_schedule import ScheduleEntry


@dataclass(frozen=True)
class TournamentCardFacts:
    game_code: str
    tournament_name: str
    date_range_display: str
    url_base: str
    start_date: str
    end_date: str
    venue: str | None = None
    winner: str | None = None
    winning_score: str | None = None
    defending_champion: str | None = None
    defending_champion_score: str | None = None


def _date_range_display(entry: ScheduleEntry, hub: dict) -> str:
    if hub.get("date_range"):
        return hub["date_range"]
    start, end = entry.start_date, entry.end_date
    if start[:7] == end[:7]:
        return f"{start[:4]}.{start[5:7]}.{start[8:]}–{end[8:]}"
    return f"{start} – {end}"


def _facts_from_schedule_entry(entry: ScheduleEntry, registry: dict) -> TournamentCardFacts:
    """Join a schedule entry (the authoritative name/dates/venue) with
    whatever route/presentation metadata the site registry happens to
    have for the same game_code -- url_base/winner/etc are registry-
    only fields with no calendar meaning, so a game_code missing from
    the registry entirely still gets a complete, real facts object
    (url_base "", no result fields), never a skipped/blank card."""
    reg_entry = registry.get(entry.game_code) or {}
    hub = reg_entry.get("hub_card") or {}
    return TournamentCardFacts(
        game_code=entry.game_code,
        tournament_name=entry.tournament_name,
        date_range_display=_date_range_display(entry, hub),
        url_base=str(reg_entry.get("url_base") or ""),
        start_date=entry.start_date,
        end_date=entry.end_date,
        venue=entry.venue or reg_entry.get("venue"),
        winner=hub.get("winner"),
        winning_score=hub.get("winning_score"),
        defending_champion=hub.get("defending_champion"),
        defending_champion_score=hub.get("defending_champion_score"),
    )


def resolve_tournament_chronology(
    schedule: list[ScheduleEntry],
    registry: dict,
    *,
    as_of: date,
) -> dict[str, TournamentCardFacts | None]:
    """Pure resolution (no file I/O) -- see build_home_tournament_chronology()
    below for the real, artifact-backed caller.

    `schedule`: every officially-known tournament (klpga.website_v2.
    official_schedule.load_official_schedule()'s output) -- the ONLY
    source of chronological identity. `registry`: TOURNAMENT_SITE_
    REGISTRY.json's "tournaments" mapping, consulted only for route/
    display metadata once a schedule entry has already been placed
    into last/current/next by real calendar dates.

    Returns {"last": facts|None, "current": facts|None, "next": facts|None}.

    "last" = the schedule entry with the most recent end_date that is
    strictly before as_of.

    "current" = the schedule entry whose [start_date, end_date] window
    contains as_of (this week's/still-being-played event), or, when no
    entry is currently in its window, the nearest upcoming entry --
    never an entry whose window has already closed, purely by date,
    regardless of what any pipeline stage-state artifact says about it.

    "next" = the soonest-starting entry after whichever one is resolved
    as "current" (or the second-nearest upcoming entry when "current"
    itself had to degrade to the nearest one).

    Every comparison uses only the schedule's own real start_date/
    end_date strings (ISO, so lexical order == chronological order)."""
    as_of_iso = as_of.isoformat()

    ongoing = sorted((e for e in schedule if e.start_date <= as_of_iso <= e.end_date), key=lambda e: e.start_date)
    completed = sorted((e for e in schedule if e.end_date < as_of_iso), key=lambda e: e.end_date, reverse=True)
    upcoming = sorted((e for e in schedule if e.start_date > as_of_iso), key=lambda e: e.start_date)

    if ongoing:
        current_entry, next_entry = ongoing[0], (upcoming[0] if upcoming else None)
    else:
        current_entry = upcoming[0] if upcoming else None
        next_entry = upcoming[1] if len(upcoming) > 1 else None

    return {
        "last": _facts_from_schedule_entry(completed[0], registry) if completed else None,
        "current": _facts_from_schedule_entry(current_entry, registry) if current_entry else None,
        "next": _facts_from_schedule_entry(next_entry, registry) if next_entry else None,
    }


def build_home_tournament_chronology(registry: dict, context, *, as_of: date | None = None) -> dict[str, TournamentCardFacts | None]:
    """Real caller: `registry` is TOURNAMENT_SITE_REGISTRY.json's
    "tournaments" mapping (route/display metadata only). `context` is
    accepted for call-site compatibility (scripts/88 already resolves
    the active tournament's own route patch separately once this
    returns) but is no longer consulted for calendar facts -- those
    come exclusively from the official schedule artifact below.
    `as_of` defaults to today (UTC date)."""
    from klpga.tournament_context import CONTENT_DIR
    from klpga.website_v2.official_schedule import load_official_schedule

    schedule = load_official_schedule(CONTENT_DIR / "OFFICIAL_KLPGA_SCHEDULE.json")

    return resolve_tournament_chronology(schedule, registry, as_of=as_of or date.today())
