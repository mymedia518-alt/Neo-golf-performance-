"""Single source of truth for "which tournament is currently active, and
which of its stages have real, validated data behind them" -- HOME's
tournament-day hero, OK Open's own stage nav (script 84), the tournament
hub's CTA, and the R1 active-collection cycle (script 96) all need the
identical answer, so there is exactly one place this is decided.

TOURNAMENT-DAY MODE (NEO GOLF DATA hotfix, 2026-09-04): never infer a
stage (R1/R2/R3/FINAL) from today's calendar date -- a tournament
"starting today" says nothing about whether R1's data has actually been
collected and validated yet. Only ok_open_available_stages() below
decides that, and it never guesses: PRE is always available (the public
participant/pre-analysis master ships with the repo); every later
stage is available ONLY once OK_OPEN_STAGE_STATE_PATH records it, which
only the R1 active-cycle (script 96, run with real klpga.co.kr access)
ever writes, and only after a real official collection passed its
safety gate (see klpga.neo_win.r1_active_cycle). home_mode() likewise
never guesses "in progress" from a date range; it reacts only to
whether any stage is actually available.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from klpga.tournament_context import load_active_tournament_context

_KST = datetime.timezone(datetime.timedelta(hours=9))

# NEO TOURNAMENT PIPELINE: these five names used to be this module's own
# hardcoded constants (one specific tournament's name/path/date/game_code
# baked directly into Python). They are now resolved once, at import
# time, from the shared TournamentContext (config/active_tournament.json
# + content/website_v2/TOURNAMENT_SITE_REGISTRY.json) -- pointing
# active_tournament.json at a new game_code and adding one registry
# entry is now enough to operate on a different tournament; nothing here
# needs to change. Kept as plain module attributes (not functions) since
# existing callers (scripts 84/88/94) import them by name and
# tests/test_tournament_state_r1_active.py monkeypatches
# STAGE_STATE_PATH directly.
_CONTEXT = load_active_tournament_context()

OK_DISPLAY_NAME = _CONTEXT.tournament_name
OK_BASE = _CONTEXT.url_base
OK_DATE_RANGE = _CONTEXT.display_date_range
OK_GAME_CODE = _CONTEXT.game_code
OK_END_DATE = _CONTEXT.end_date

STAGE_ORDER = _CONTEXT.stage_order
STAGE_LABELS = _CONTEXT.stage_labels

# Written only by scripts/96_ok_open_r1_active_cycle.py (--live, run
# somewhere with real network access), after a real official collection
# passes its per-cycle safety gate. Absent (the committed, default
# state) means nothing but PRE is real yet -- see
# ok_open_available_stages() below, which is the only reader of this
# file's stage/url/timestamp fields.
STAGE_STATE_PATH = Path(__file__).resolve().parents[3] / "content" / "website_v2" / _CONTEXT.stage_state_filename


def _read_stage_state() -> dict:
    try:
        return json.loads(STAGE_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ok_open_available_stages() -> dict[str, str]:
    """The ONLY place that decides which OK Open stage pages have real,
    collected-and-validated data behind them. PRE always qualifies (its
    master ships with the repo, no live collection needed). Any later
    stage qualifies ONLY if OK_OPEN_STAGE_STATE_PATH says so -- never
    derived from today's date."""
    stages = {"pre": f"{OK_BASE}pre/"}
    state = _read_stage_state()
    for key, entry in (state.get("stages") or {}).items():
        if key in STAGE_ORDER and isinstance(entry, dict) and entry.get("validated"):
            stages[key] = f"{OK_BASE}{key}/"
    return stages


def ok_open_latest_stage_update() -> dict | None:
    """{'stage', 'retrieved_at' (raw ISO), 'retrieved_at_hhmm_kst'
    (what HOME's "마지막 업데이트 HH:MM" line actually shows)} for the
    most-advanced validated stage's real collection timestamp. None
    while only PRE (no live timestamp) is available. Never build time
    -- always the actual official-data retrieval time recorded by
    script 96."""
    stage_key, _ = ok_open_latest_available_stage()
    if stage_key == "pre":
        return None
    state = _read_stage_state()
    entry = (state.get("stages") or {}).get(stage_key)
    if not entry or not entry.get("retrieved_at"):
        return None
    retrieved_at = entry["retrieved_at"]
    dt = datetime.datetime.fromisoformat(retrieved_at.replace("Z", "+00:00")).astimezone(_KST)
    return {"stage": stage_key, "retrieved_at": retrieved_at, "retrieved_at_hhmm_kst": dt.strftime("%H:%M")}


def ok_open_r1_status() -> str | None:
    """'IN_PROGRESS' while R1 has a validated in-round snapshot but has
    not been confirmed officially complete; 'COMPLETE' once script 96's
    R1-close workflow has run (state['r1_complete']); None while R1
    itself has no validated data yet. Never inferred from a date or
    clock -- reacts only to what script 96 actually recorded."""
    state = _read_stage_state()
    r1_entry = (state.get("stages") or {}).get("r1")
    if not r1_entry or not (isinstance(r1_entry, dict) and r1_entry.get("validated")):
        return None
    return "COMPLETE" if state.get("r1_complete") else "IN_PROGRESS"


def ok_open_latest_available_stage() -> tuple[str, str]:
    """(stage_key, url) for the most-advanced validated stage -- what
    HOME's tournament-day CTA and any other "go straight to the useful
    page" link should point at. Raises if somehow nothing is available
    yet (should never happen once a tournament's PRE master exists)."""
    available = ok_open_available_stages()
    for key in reversed(STAGE_ORDER):
        if key in available:
            return key, available[key]
    raise RuntimeError("no OK Open stage has validated data yet")


def ok_open_tournament_is_complete() -> bool:
    """True only once the LAST stage in STAGE_ORDER (the tournament's
    own real, curated stage list -- "final" for OK Open, also "final"
    for KG Ladies Open) has validated data behind it. This is the one
    authoritative "has this tournament actually ended" signal --
    PUBLIC UI correction: a tournament's own SCHEDULED end_date can go
    stale (a real-world delay, a postponed final round) while it is
    still genuinely being played; only real stage-validation evidence,
    never a calendar date, may retire it from "이번 대회" into "지난 대회"
    (see klpga.website_v2.tournament_chronology, which consumes this)."""
    return STAGE_ORDER[-1] in ok_open_available_stages()


def home_mode() -> str:
    """TOURNAMENT_ACTIVE while a real tournament has at least one
    validated stage available AND today (KST) has not yet passed that
    same tournament's own official end_date; RANKING_DEFAULT otherwise
    (no active tournament, a future one with nothing validated yet, or
    the active-tournament pointer's calendar window has already
    closed).

    The end_date check does not "guess a stage from a date" (the thing
    this module's own docstring forbids) -- it only stops treating a
    tournament as ROOT HOME content once its own real, officially-
    sourced end_date (the same field klpga.website_v2.
    tournament_chronology already uses to move a tournament from 이번
    대회 into 지난 대회) has passed, matching that same calendar-only
    discipline. Without this, a stale active_tournament.json left
    pointing at a tournament for days after it genuinely finished
    (config/active_tournament.json is only ever advanced by a separate,
    DB-driven process) would keep rendering that tournament's last
    validated stage page at "/" indefinitely, even once chronology's
    own cards correctly show it under 지난 대회 and a new tournament is
    now 이번 대회."""
    if not ok_open_available_stages():
        return "RANKING_DEFAULT"
    today_kst = datetime.datetime.now(_KST).date().isoformat()
    if today_kst > OK_END_DATE:
        return "RANKING_DEFAULT"
    return "TOURNAMENT_ACTIVE"
