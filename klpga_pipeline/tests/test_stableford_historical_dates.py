"""The 3 historical event dates must match the real captured HTML
verbatim -- re-derived from the raw evidence file by this test, not
just asserted against the hardcoded module in isolation, so a future
edit to stableford_historical_dates.py that drifts from the real page
is caught."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from klpga.website_v2.stableford_historical_dates import HISTORICAL_EVENT_DATES

EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"


@pytest.mark.parametrize("game_code", list(HISTORICAL_EVENT_DATES.keys()))
def test_round_close_timestamps_match_real_captured_html_verbatim(game_code):
    path = EVIDENCE_ROOT / f"stableford_source_probe_{game_code}" / f"scoreRecord_{game_code}.html"
    html = path.read_text(encoding="utf-8")
    real_timestamps = tuple(re.findall(r"라운드 마감 : (20\d\d-\d\d-\d\d \d\d:\d\d:\d\d)", html))
    assert real_timestamps == HISTORICAL_EVENT_DATES[game_code].round_close_timestamps


def test_event_start_dates_are_the_r1_date():
    assert HISTORICAL_EVENT_DATES["2023100002"].event_start_date == date(2023, 10, 12)
    assert HISTORICAL_EVENT_DATES["2024100009"].event_start_date == date(2024, 10, 10)
    assert HISTORICAL_EVENT_DATES["2025100001"].event_start_date == date(2025, 10, 1)


def test_events_are_four_consecutive_days():
    """Sanity check against the real timestamps -- all 3 events run
    R1-R4 on 4 consecutive calendar days, matching the known 4-round/
    72-hole structure already recorded for this tournament."""
    for dates in HISTORICAL_EVENT_DATES.values():
        days = [int(ts.split(" ")[0].split("-")[2]) for ts in dates.round_close_timestamps]
        assert days == [days[0], days[0] + 1, days[0] + 2, days[0] + 3]
