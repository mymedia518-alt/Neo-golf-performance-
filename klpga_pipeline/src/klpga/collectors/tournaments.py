"""Tournament list collector — real getGameList API adapter.

Confirmed via browser Network capture AND a live run against the real
site (see docs/SITE_STRUCTURE_TODO.md, gameCode=2026080002 / season=2026,
Windows validation run):

  POST https://klpga.co.kr/ajax/tourInfo/getGameList
  Content-Type: application/x-www-form-urlencoded
  form: season=<year>, tourType=RE, year=
  response: application/json, {"gameList": [...]}

Fields confirmed and parsed into named TournamentListing fields:
  gameCode, gameTitle, gameEngTitle, tourType, courseText, courseEngText,
  outCourseText, inCourseText, startDate/endDate (YYYYMMDD),
  gameFinish ("F" == confirmed "completed"), prizeMoney (total purse,
  integer KRW), winnerCode, winnerName.

Every other key present in a live response is kept verbatim in `.raw`
for later inspection, but nothing is invented for keys that were never
observed in a confirmed capture/run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from klpga import config
from klpga.http_client import PoliteHttpClient


@dataclass
class TournamentListing:
    game_code: Optional[str]
    game_title: Optional[str]
    game_eng_title: Optional[str]
    tour_type: Optional[str]
    course_text: Optional[str]
    course_eng_text: Optional[str]
    out_course_text: Optional[str]  # outCourseText, e.g. nine-hole course name
    in_course_text: Optional[str]   # inCourseText, e.g. nine-hole course name
    start_date: Optional[date]      # parsed from startDate (YYYYMMDD)
    start_date_raw: Optional[str]   # startDate exactly as returned
    end_date: Optional[date]        # parsed from endDate (YYYYMMDD)
    end_date_raw: Optional[str]     # endDate exactly as returned
    game_finish: Optional[str]      # raw gameFinish flag
    prize_money: Optional[int]      # total tournament purse (KRW), as returned
    winner_code: Optional[str]      # official playerCode of the winner
    winner_name: Optional[str]      # winner's name as returned
    # The season this listing was requested under (i.e. the `season` form
    # value sent to getGameList) — this is request metadata, not a value
    # read from the response body, so it's always populated.
    season: int
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        return self.game_finish == config.GAME_FINISH_DONE

    @property
    def is_regular_tour(self) -> bool:
        return self.tour_type == config.TOUR_TYPE_REGULAR


def _clean(text: Any) -> Optional[str]:
    if text is None:
        return None
    text = str(text).strip()
    return text if text != "" else None


def _parse_yyyymmdd(text: Optional[str]) -> Optional[date]:
    text = _clean(text)
    if text is None or len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def fetch_game_list(
    client: PoliteHttpClient,
    season: int,
    tour_type: str = config.TOUR_TYPE_REGULAR,
) -> list[TournamentListing]:
    """Fetch one season's game list for a given tourType. No filtering —
    callers decide what to keep, so this adapter never silently drops
    entries returned by the site."""
    payload = {"season": str(season), "tourType": tour_type, "year": ""}
    data = client.post_json(config.GAME_LIST_ENDPOINT, data=payload)

    if not isinstance(data, dict) or "gameList" not in data:
        got = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        raise ValueError(
            "Unexpected getGameList response shape for "
            f"season={season} tourType={tour_type}: missing top-level "
            f"'gameList' key. Got: {got}"
        )

    game_list = data["gameList"]
    if not isinstance(game_list, list):
        raise ValueError(
            f"Unexpected 'gameList' type for season={season} tourType={tour_type}: "
            f"expected a list, got {type(game_list).__name__}"
        )

    listings: list[TournamentListing] = []
    for entry in game_list:
        listings.append(
            TournamentListing(
                game_code=_clean(entry.get("gameCode")),
                game_title=_clean(entry.get("gameTitle")),
                game_eng_title=_clean(entry.get("gameEngTitle")),
                tour_type=_clean(entry.get("tourType")),
                course_text=_clean(entry.get("courseText")),
                course_eng_text=_clean(entry.get("courseEngText")),
                out_course_text=_clean(entry.get("outCourseText")),
                in_course_text=_clean(entry.get("inCourseText")),
                start_date=_parse_yyyymmdd(entry.get("startDate")),
                start_date_raw=_clean(entry.get("startDate")),
                end_date=_parse_yyyymmdd(entry.get("endDate")),
                end_date_raw=_clean(entry.get("endDate")),
                game_finish=_clean(entry.get("gameFinish")),
                prize_money=_to_int(entry.get("prizeMoney")),
                winner_code=_clean(entry.get("winnerCode")),
                winner_name=_clean(entry.get("winnerName")),
                season=season,
                raw=entry,
            )
        )
    return listings


def filter_completed_regular_tour(listings: list[TournamentListing]) -> list[TournamentListing]:
    """Keep only tourType=RE (confirmed 'regular tour') AND
    gameFinish=F (confirmed 'completed') entries."""
    return [l for l in listings if l.is_regular_tour and l.is_completed]


def collect_most_recent_completed(
    client: PoliteHttpClient,
    start_season: int,
    target_count: int = config.TARGET_COMPLETED_TOURNAMENTS,
    min_season: int = config.MIN_SEASON_FLOOR,
) -> list[TournamentListing]:
    """Walk backwards season by season (per spec section 4: "과거 시즌을
    season 값으로 순차 요청"), accumulating completed regular-tour events
    until target_count is reached or min_season is passed.

    An empty gameList for a season is recorded as-is (0 events that
    season, e.g. the tour didn't exist yet) and the walk simply continues
    to the prior season — never fabricated.
    """
    collected: list[TournamentListing] = []
    season = start_season
    while season >= min_season:
        listings = fetch_game_list(client, season=season, tour_type=config.TOUR_TYPE_REGULAR)
        collected.extend(filter_completed_regular_tour(listings))
        if len(collected) >= target_count:
            break
        season -= 1

    # endDate is the only confirmed date field to sort on. Entries with no
    # parseable end_date sort last rather than crashing the comparison.
    collected.sort(key=lambda l: l.end_date or date.min, reverse=True)
    return collected[:target_count]
