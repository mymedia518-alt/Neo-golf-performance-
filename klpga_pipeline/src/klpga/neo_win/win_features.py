"""BETA #001-C Phase 6 — win/recent-success feature CANDIDATES, built to
investigate NEO WIN v0.1's WIN_FEATURE=NONE gap found by the Seo Gyo-rim
diagnostic (docs/discovery evidence: her 4 confirmed 2026 wins had no
corresponding feature in BASE_FEATURES at all).

This module only COMPUTES the candidates, point-in-time safe, from the
same `klpga.backtest.point_in_time_features.Corpus` every other feature
in this project already uses (`compute_point_in_time_features`'s own
`prior_events` filtering/ordering — never a separate, unaudited date
check). Whether any candidate actually IMPROVES the model is decided by
Phase 7's out-of-sample backtest (klpga.neo_win.backtest_eval), never
here — no hindsight tuning to make any one player's number look
"right." A player is never manually inspected during this module's
design; every formula is fixed BEFORE Phase 7's backtest runs.

======================================================================
FIVE CANDIDATES
======================================================================
wins_last_52_weeks   — win count among prior events with effective_date
                        within 364 days before the target date.
wins_current_season   — win count among prior events in the SAME season
                        as the target tournament (season_by_event map,
                        the same lookup dataset.py's augment_rows_with_
                        neo_features already uses for target_season).
wins_last_10_starts   — win count among the 10 MOST RECENT prior events
                        (prior_events is already date-descending sorted
                        by compute_point_in_time_features's own
                        convention; this module sorts independently the
                        same way, never assumes the caller's order).
top3_rate             — count(finish_position_numeric <= 3) / prior_events_n
                        over ALL prior events (no windowing) — an
                        explicit gap in point_in_time_features.py, which
                        has prior_top5/prior_top10 counts but no top3 or
                        rate form.
top10_rate            — prior_top10-equivalent count / prior_events_n
                        (a rate, not the existing raw count feature).

Each candidate reports its own `_n` (the real, non-fabricated sample
size behind it — "0 starts in window" is None/0, distinguished from
"some starts in window, literally zero wins," which is a real,
informative 0.0) so `klpga.models.candidates.apply_shrinkage_and_
standardize` can shrink it exactly like every other optional feature."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Optional

from klpga.backtest.point_in_time_features import Corpus
from klpga.backtest.temporal import is_strictly_before

WIN_FEATURE_CANDIDATE_NAMES: tuple[str, ...] = (
    "wins_last_52_weeks",
    "wins_current_season",
    "wins_last_10_starts",
    "top3_rate",
    "top10_rate",
)

_WEEKS_52 = timedelta(days=364)


def season_by_event(conn: sqlite3.Connection) -> dict[str, int]:
    return {event_id: season for event_id, season in conn.execute("SELECT event_id, season FROM tournament_master")}


def compute_win_feature_candidates(
    corpus: Corpus,
    target_event_id: str,
    target_effective_date: Optional[date],
    target_season: Optional[int],
    player_id: str,
    season_by_event_map: dict[str, int],
) -> dict:
    """Returns one dict with every candidate's `<name>` and `<name>_n`
    key — always the full, fixed key set, regardless of data
    availability (missing data is None/0, never an absent key)."""
    all_events = corpus.events_by_player.get(player_id, [])
    prior_events = [
        e for e in all_events
        if e.event_id != target_event_id and is_strictly_before(e.effective_date, target_effective_date)
    ]
    prior_events.sort(key=lambda e: e.effective_date, reverse=True)
    prior_events_n = len(prior_events)

    out: dict = {}

    # wins_last_52_weeks
    if target_effective_date is not None:
        windowed = [e for e in prior_events if target_effective_date - e.effective_date <= _WEEKS_52]
        out["wins_last_52_weeks_n"] = len(windowed)
        out["wins_last_52_weeks"] = (
            float(sum(1 for e in windowed if e.finish_position_numeric == 1)) if windowed else None
        )
    else:
        out["wins_last_52_weeks"] = None
        out["wins_last_52_weeks_n"] = 0

    # wins_current_season
    if target_season is not None:
        season_events = [e for e in prior_events if season_by_event_map.get(e.event_id) == target_season]
        out["wins_current_season_n"] = len(season_events)
        out["wins_current_season"] = (
            float(sum(1 for e in season_events if e.finish_position_numeric == 1)) if season_events else None
        )
    else:
        out["wins_current_season"] = None
        out["wins_current_season_n"] = 0

    # wins_last_10_starts
    last_10 = prior_events[:10]
    out["wins_last_10_starts_n"] = len(last_10)
    out["wins_last_10_starts"] = (
        float(sum(1 for e in last_10 if e.finish_position_numeric == 1)) if last_10 else None
    )

    # top3_rate / top10_rate
    out["top3_rate_n"] = prior_events_n
    out["top10_rate_n"] = prior_events_n
    if prior_events_n:
        top3 = sum(1 for e in prior_events if e.finish_position_numeric is not None and e.finish_position_numeric <= 3)
        top10 = sum(1 for e in prior_events if e.finish_position_numeric is not None and e.finish_position_numeric <= 10)
        out["top3_rate"] = round(top3 / prior_events_n, 4)
        out["top10_rate"] = round(top10 / prior_events_n, 4)
    else:
        out["top3_rate"] = None
        out["top10_rate"] = None

    return out
