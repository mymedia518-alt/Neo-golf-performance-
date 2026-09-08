"""PUBLIC UI Phase 8: a generic last/current/next tournament resolver
for HOME's three tournament cards (지난 대회 / 이번 대회 / 다음 대회).

Never date-guesses a tournament's LIVE STAGE (that stays
klpga.website_v2.tournament_state.home_mode()'s job, driven only by
real validated stage-state artifacts) -- this module only orders
already-registered tournaments chronologically by their own real,
curated start/end dates, to answer "which one just finished, which one
is on now, which one is next", never "what stage is the current one
at".

Zero game_code-specific branching: every fact this module surfaces
comes from TOURNAMENT_SITE_REGISTRY.json's own per-tournament fields
(plus the live TournamentContext for whichever game_code is currently
active) -- a tournament this module has never seen before needs a
registry entry (real start_date/end_date, and hub_card facts once it
finishes), never a source edit here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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


def _registry_entry_facts(game_code: str, entry: dict) -> TournamentCardFacts | None:
    """Build TournamentCardFacts for a non-active registry entry. None
    when the entry carries no real, curated start_date/end_date --
    such an entry cannot be chronologically ordered against others, so
    it is excluded rather than guessed into a position."""
    start = entry.get("start_date")
    end = entry.get("end_date")
    if not start or not end:
        return None
    hub = entry.get("hub_card") or {}
    return TournamentCardFacts(
        game_code=game_code,
        tournament_name=hub.get("display_name") or "",
        date_range_display=hub.get("date_range") or "",
        url_base=str(entry.get("url_base") or ""),
        start_date=start,
        end_date=end,
        venue=entry.get("venue"),
        winner=hub.get("winner"),
        winning_score=hub.get("winning_score"),
        defending_champion=hub.get("defending_champion"),
        defending_champion_score=hub.get("defending_champion_score"),
    )


def resolve_tournament_chronology(
    registry: dict,
    *,
    active_game_code: str | None,
    active_tournament_name: str | None = None,
    active_date_range_display: str | None = None,
    active_start_date: str | None = None,
    active_end_date: str | None = None,
    as_of: date,
) -> dict[str, TournamentCardFacts | None]:
    """Pure resolution (no file I/O) -- see build_home_tournament_chronology()
    below for the real, registry+TournamentContext-backed caller.

    registry: the "tournaments" mapping from TOURNAMENT_SITE_REGISTRY.json.
    active_game_code/active_tournament_name/active_date_range_display/
    active_start_date/active_end_date: the currently active tournament's
    OWN real facts (from TournamentContext / load_active_tournament_context()),
    never re-derived from the registry's own possibly-stale copy -- the
    live context is the one authoritative source for "what tournament
    is active right now and what are its real dates."

    Returns {"last": facts|None, "current": facts|None, "next": facts|None}.

    "last" = the most recently ENDED tournament as of as_of -- either a
    registered (non-active) entry, or the active one itself once its
    own end_date has passed (see "current" below).

    "current" = the active tournament ONLY while it has not already
    ended (its own end_date is unknown, or >= as_of). PUBLIC UI Phase 8
    correction (FAIL 3): an active context whose end_date is < as_of is
    a completed tournament, not "이번 대회", regardless of whether the
    pipeline still points at it -- date evidence always overrides
    which game_code happens to be "active". When that happens (or when
    no active tournament is tracked at all is NOT this case -- see
    below), "current" degrades to the nearest known upcoming
    tournament so the card never shows a stale, already-over event.

    "next" = the soonest-starting tournament after whichever one is
    resolved as "current" -- i.e. the second-nearest upcoming entry
    when "current" itself had to degrade to the nearest one.

    Every date comparison uses only real, curated start_date/end_date
    values -- never inferred, never fabricated. A candidate lacking
    either date is excluded from consideration entirely."""
    as_of_iso = as_of.isoformat()

    active_facts = None
    active_is_stale = False
    if active_game_code:
        active_entry = registry.get(active_game_code) or {}
        hub = active_entry.get("hub_card") or {}
        end = active_end_date or active_entry.get("end_date") or ""
        active_facts = TournamentCardFacts(
            game_code=active_game_code,
            tournament_name=active_tournament_name or hub.get("display_name") or "",
            date_range_display=active_date_range_display or hub.get("date_range") or "",
            url_base=str(active_entry.get("url_base") or ""),
            start_date=active_start_date or active_entry.get("start_date") or "",
            end_date=end,
            venue=active_entry.get("venue"),
            winner=hub.get("winner"),
            winning_score=hub.get("winning_score"),
            defending_champion=hub.get("defending_champion"),
            defending_champion_score=hub.get("defending_champion_score"),
        )
        active_is_stale = bool(end) and end < as_of_iso

    others = [
        facts for game_code, entry in registry.items()
        if game_code != active_game_code
        for facts in (_registry_entry_facts(game_code, entry),)
        if facts is not None
    ]
    completed_pool = list(others) + ([active_facts] if active_is_stale else [])
    completed = sorted((f for f in completed_pool if f.end_date < as_of_iso), key=lambda f: f.end_date, reverse=True)
    upcoming = sorted((f for f in others if f.start_date > as_of_iso), key=lambda f: f.start_date)

    if active_facts is not None and not active_is_stale:
        # A live-or-not-yet-started active tournament genuinely is
        # "이번 대회" -- unchanged from before this correction.
        current, next_ = active_facts, (upcoming[0] if upcoming else None)
    elif active_game_code:
        # The tracked tournament has already ended: "이번 대회" degrades
        # to the nearest known upcoming event (never the stale one),
        # and "다음 대회" becomes whatever comes after that.
        current = upcoming[0] if upcoming else None
        next_ = upcoming[1] if len(upcoming) > 1 else None
    else:
        # No active tournament tracked at all -- pure-resolver use
        # only (real callers always have an active_game_code); behavior
        # unchanged from before this correction.
        current, next_ = None, (upcoming[0] if upcoming else None)

    return {
        "last": completed[0] if completed else None,
        "current": current,
        "next": next_,
    }


def build_home_tournament_chronology(registry: dict, context, *, as_of: date | None = None) -> dict[str, TournamentCardFacts | None]:
    """Real caller: `registry` is TOURNAMENT_SITE_REGISTRY.json's
    "tournaments" mapping, `context` is a TournamentContext (or any
    object with the same game_code/tournament_name/display_date_range/
    start_date/end_date attributes) for whichever tournament is
    currently active. `as_of` defaults to today (UTC date)."""
    return resolve_tournament_chronology(
        registry,
        active_game_code=context.game_code,
        active_tournament_name=context.tournament_name,
        active_date_range_display=context.display_date_range,
        active_start_date=context.start_date,
        active_end_date=context.end_date,
        as_of=as_of or date.today(),
    )
