"""Best-effort, generic derivation of the "ranking week" REQUEST
parameters the legacy k-rankings.klpga.co.kr JSP endpoints require on
every request (Rank_week POST field, last_week query param).

PHASE 2 (K-RANK PROVENANCE / WEEK SAFETY): this module's output is a
REQUEST CANDIDATE only -- never proof of which week the official site
actually returned. Requesting "Rank_week=202635" does not by itself
confirm the response the server sent back reflects that same week; the
official response itself must be parsed for its own returned/selected
week and that value compared against the request before anything here
is trusted (see klpga.neo_win.tier2_publication_gate's K_RANKING domain
and scripts/72's collect_rankings(), which records both the requested
and returned week plus a week_match state rather than assuming they
agree).

Confirmed against the real, already-committed OK Open PRE build
(tournament start 2026-09-04, ISO week 36): the site's published
ranking week at build time was 2026-W35 -- the ISO week immediately
BEFORE the tournament's own start-date week, consistent with a
"most recently completed week" publish cadence. This has NOT been
independently re-verified against the live site for any other
week/tournament (this environment has no live network access), so it
is a documented best-effort default, not a confirmed site contract --
override it with the NEO_KRANKING_WEEK environment variable
(format "YYYY-WNN") if a real run finds the site's actual cadence
differs for a given tournament.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import date, timedelta


def resolve_ranking_week(start_date: str) -> tuple[str, str, str]:
    """-> (rank_week_param "YYYYWW", label "YYYY-WNN", korean "YYYY년 N주")"""
    override = os.environ.get("NEO_KRANKING_WEEK")
    if override:
        year_str, week_str = override.split("-W")
        year, week = int(year_str), int(week_str)
    else:
        anchor = date.fromisoformat(start_date) - timedelta(days=7)
        year, week, _ = anchor.isocalendar()
    return f"{year}{week:02d}", f"{year}-W{week:02d}", f"{year}년 {week}주"


_WEEK_LABEL_RE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*주")


def extract_returned_week(html: str) -> str | None:
    """Best-effort extraction of the officially-returned/selected
    ranking week label ("YYYY-WNN") from the raw K-Rankings response
    HTML -- never a guess, never inferred from the request. Looks for
    a selected <option> inside a week-select control first (the
    common pattern for this kind of legacy JSP filter form), then
    falls back to any "YYYY년 N주" label text appearing anywhere in
    the page. Returns None when no such evidence is found: this
    parser has not been independently verified against a real live
    response (this environment has no live network access -- see this
    module's own docstring), so None is the honest, expected outcome
    until it has been, and callers must treat None as "unproven",
    never as "assume it matched the request"."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None
    soup = BeautifulSoup(html, "html.parser")
    selected = soup.select_one("select option[selected]")
    if selected is not None:
        match = _WEEK_LABEL_RE.search(selected.get_text(" ", strip=True))
        if match:
            year, week = int(match.group(1)), int(match.group(2))
            return f"{year}-W{week:02d}"
    match = _WEEK_LABEL_RE.search(html)
    if match:
        year, week = int(match.group(1)), int(match.group(2))
        return f"{year}-W{week:02d}"
    return None


def response_sha256(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()
