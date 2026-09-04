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

_KST = datetime.timezone(datetime.timedelta(hours=9))

OK_DISPLAY_NAME = "OK저축은행 읏맨 오픈"
OK_BASE = "/tournaments/2026/ok-savings-bank-open/"
OK_DATE_RANGE = "2026.09.04 — 09.06"
OK_GAME_CODE = "2026120001"

STAGE_ORDER = ("pre", "r1", "r2", "r3", "final")
STAGE_LABELS = {"pre": "사전 분석 PRE", "r1": "R1", "r2": "R2", "r3": "R3", "final": "FINAL"}

# Written only by scripts/96_ok_open_r1_active_cycle.py (--live, run
# somewhere with real network access), after a real official collection
# passes its per-cycle safety gate. Absent (the committed, default
# state) means nothing but PRE is real yet -- see
# ok_open_available_stages() below, which is the only reader of this
# file's stage/url/timestamp fields.
STAGE_STATE_PATH = Path(__file__).resolve().parents[3] / "content" / "website_v2" / "OK_OPEN_STAGE_STATE.json"


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


def home_mode() -> str:
    """TOURNAMENT_ACTIVE while a real tournament has at least one
    validated stage available; RANKING_DEFAULT otherwise (no active
    tournament, or a future one with nothing validated yet). Never
    guesses from a date -- reacts only to ok_open_available_stages()
    actually holding an entry, so this flips back to RANKING_DEFAULT on
    its own once a tournament fully wraps and a new build runs before
    the next one has any validated data."""
    return "TOURNAMENT_ACTIVE" if ok_open_available_stages() else "RANKING_DEFAULT"
