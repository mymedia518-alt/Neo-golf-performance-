"""Best-effort, generic derivation of the "ranking week" parameters the
legacy k-rankings.klpga.co.kr JSP endpoints require on every request
(Rank_week POST field, last_week query param, and the ranking_date/
ranking_week label recorded in our own output artifacts).

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

import os
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
