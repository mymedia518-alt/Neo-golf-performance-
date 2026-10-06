"""Real event dates for the 3 historical Modified Stableford events
(2023100002 / 2024100009 / 2025100001), needed as the leakage cutoff
for the pre-event blind backtest dataset (HJ 2026100004 gap, continued
2026-10-06).

SOURCE (not guessed from the gameCode's month digits, not estimated
from 2026's calendar slot): each event's own real captured scoreRecord
page literally prints "* 라운드 마감 : <timestamp>" ("Round closed at")
once per round table -- direct quote, confirmed by grep against the
real committed evidence files:

    klpga_pipeline/evidence/stableford_source_probe_2023100002/scoreRecord_2023100002.html
    klpga_pipeline/evidence/stableford_source_probe_2024100009/scoreRecord_2024100009.html
    klpga_pipeline/evidence/stableford_source_probe_2025100001/scoreRecord_2025100001.html

event_start_date is the date of the R1 "라운드 마감" timestamp (the
tournament's own first playing day) -- this is the leakage cutoff: any
record with record_date >= event_start_date must never be used as a
pre-event feature input for that event."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HistoricalEventDates:
    game_code: str
    round_close_timestamps: tuple[str, str, str, str]  # as literally printed on the real page, R1..R4

    @property
    def event_start_date(self) -> date:
        """R1's own date -- the earliest moment any real outcome from
        this event could exist. The leakage cutoff for feature
        construction is this date (record_date must be strictly
        before it)."""
        r1 = self.round_close_timestamps[0]
        y, m, d = r1.split(" ")[0].split("-")
        return date(int(y), int(m), int(d))


HISTORICAL_EVENT_DATES: dict[str, HistoricalEventDates] = {
    "2023100002": HistoricalEventDates(
        "2023100002",
        ("2023-10-12 17:13:58", "2023-10-13 17:04:28", "2023-10-14 15:48:29", "2023-10-15 15:17:23"),
    ),
    "2024100009": HistoricalEventDates(
        "2024100009",
        ("2024-10-10 17:09:47", "2024-10-11 17:07:43", "2024-10-12 16:37:22", "2024-10-13 16:20:44"),
    ),
    "2025100001": HistoricalEventDates(
        "2025100001",
        ("2025-10-01 16:54:37", "2025-10-02 16:43:40", "2025-10-03 16:07:29", "2025-10-04 15:58:26"),
    ),
}
