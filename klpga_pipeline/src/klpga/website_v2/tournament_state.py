"""Single source of truth for "which tournament is currently active, and
which of its stages have real, validated data behind them" -- HOME's
tournament-day hero, OK Open's own stage nav (script 84), and the
tournament hub's CTA all need the identical answer, so there is exactly
one place this is decided.

TOURNAMENT-DAY MODE (NEO GOLF DATA hotfix, 2026-09-04): never infer a
stage (R1/R2/R3/FINAL) from today's calendar date -- a tournament
"starting today" says nothing about whether R1's data has actually been
collected and validated yet. Only ok_open_available_stages() below,
extended by hand the moment a stage's real artifact lands, decides
that. home_mode() likewise never guesses "in progress" from a date
range; it reacts only to whether any stage is actually available.
"""
from __future__ import annotations

OK_DISPLAY_NAME = "OK저축은행 읏맨 오픈"
OK_BASE = "/tournaments/2026/ok-savings-bank-open/"
OK_DATE_RANGE = "2026.09.04 — 09.06"

STAGE_ORDER = ("pre", "r1", "r2", "r3", "final")
STAGE_LABELS = {"pre": "사전 분석 PRE", "r1": "R1", "r2": "R2", "r3": "R3", "final": "FINAL"}


def ok_open_available_stages() -> dict[str, str]:
    """The ONLY place that decides which OK Open stage pages have real,
    collected-and-validated data behind them. Extend this dict by hand
    the moment a stage's real artifact lands -- never derive it from
    today's date. Today only PRE (the public participant/pre-analysis
    master) exists."""
    return {"pre": f"{OK_BASE}pre/"}


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
