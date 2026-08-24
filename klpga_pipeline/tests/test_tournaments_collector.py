"""Tests for klpga.collectors.tournaments against synthetic getGameList
JSON shaped like the confirmed capture. No network access — a fake
client stands in for PoliteHttpClient."""
from __future__ import annotations

import pytest

from klpga.collectors.tournaments import (
    collect_most_recent_completed,
    fetch_game_list,
    filter_completed_regular_tour,
)


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient.post_json — returns
    canned per-season responses, records every call made."""

    def __init__(self, responses_by_season: dict[int, dict]):
        self.responses_by_season = responses_by_season
        self.calls: list[dict] = []

    def post_json(self, url, data=None, **kwargs):
        self.calls.append({"url": url, "data": dict(data or {})})
        season = int(data["season"])
        return self.responses_by_season.get(season, {"gameList": []})


def _game(
    game_code,
    title,
    tour_type="RE",
    start_date="20260301",
    end_date="20260315",
    finish="F",
    prize_money=None,
    winner_code=None,
    winner_name=None,
):
    return {
        "gameCode": game_code,
        "gameTitle": title,
        "gameEngTitle": f"{title} (EN)",
        "tourType": tour_type,
        "courseText": "아마타스프링",
        "courseEngText": "AMATA SPRING Country Club",
        "outCourseText": "아웃코스",
        "inCourseText": "인코스",
        "startDate": start_date,
        "endDate": end_date,
        "gameFinish": finish,
        "prizeMoney": prize_money,
        "winnerCode": winner_code,
        "winnerName": winner_name,
    }


def test_fetch_game_list_parses_confirmed_fields_only():
    """Field values mirror the real live-confirmed capture for
    gameCode=2026080002 (BC카드·한경 제48회 KLPGA 챔피언십, winner
    서교림 / playerCode=11134) — see docs/SITE_STRUCTURE_TODO.md."""
    client = FakeClient(
        {
            2026: {
                "gameList": [
                    _game(
                        "2026080002",
                        "BC카드 · 한경 제48회 KLPGA 챔피언십",
                        start_date="20260820",
                        end_date="20260823",
                        prize_money=1500000000,
                        winner_code="11134",
                        winner_name="서교림",
                    )
                ]
            }
        }
    )
    listings = fetch_game_list(client, season=2026, tour_type="RE")

    assert len(listings) == 1
    listing = listings[0]
    assert listing.game_code == "2026080002"
    assert listing.game_title == "BC카드 · 한경 제48회 KLPGA 챔피언십"
    assert listing.game_eng_title == "BC카드 · 한경 제48회 KLPGA 챔피언십 (EN)"
    assert listing.tour_type == "RE"
    assert listing.course_text == "아마타스프링"
    assert listing.course_eng_text == "AMATA SPRING Country Club"
    assert listing.out_course_text == "아웃코스"
    assert listing.in_course_text == "인코스"
    assert listing.start_date_raw == "20260820"
    assert listing.start_date.isoformat() == "2026-08-20"
    assert listing.end_date_raw == "20260823"
    assert listing.end_date.isoformat() == "2026-08-23"
    assert listing.game_finish == "F"
    assert listing.prize_money == 1500000000
    assert listing.winner_code == "11134"
    assert listing.winner_name == "서교림"
    assert listing.season == 2026
    assert listing.is_completed is True
    assert listing.is_regular_tour is True


def test_fetch_game_list_leaves_unconfirmed_optional_fields_none_when_absent():
    """A game list entry with no prizeMoney/winner fields (e.g. an
    upcoming/in-progress tournament) parses without fabricating values."""
    client = FakeClient({2026: {"gameList": [_game("X", "미완료 대회", finish="P")]}})
    listing = fetch_game_list(client, season=2026)[0]
    assert listing.prize_money is None
    assert listing.winner_code is None
    assert listing.winner_name is None


def test_fetch_game_list_raises_on_unexpected_shape():
    client = FakeClient({2026: {"notGameList": []}})
    with pytest.raises(ValueError, match="gameList"):
        fetch_game_list(client, season=2026)


def test_filter_completed_regular_tour_excludes_other_tour_types_and_unfinished():
    client = FakeClient(
        {
            2026: {
                "gameList": [
                    _game("A", "완료된 정규투어", tour_type="RE", finish="F"),
                    _game("B", "진행중 정규투어", tour_type="RE", finish="P"),
                    _game("C", "완료된 드림투어", tour_type="DR", finish="F"),
                ]
            }
        }
    )
    listings = fetch_game_list(client, season=2026)
    kept = filter_completed_regular_tour(listings)
    assert [l.game_code for l in kept] == ["A"]


def test_collect_most_recent_completed_walks_back_seasons_until_target_reached():
    responses = {
        2026: {"gameList": [_game("2026-1", "A", end_date="20260315")]},
        2025: {"gameList": [_game("2025-1", "B", end_date="20251110"), _game("2025-2", "C", end_date="20250801")]},
        2024: {"gameList": [_game("2024-1", "D", end_date="20241005")]},
    }
    client = FakeClient(responses)
    result = collect_most_recent_completed(client, start_season=2026, target_count=3, min_season=2000)

    assert [l.game_code for l in result] == ["2026-1", "2025-1", "2025-2"]
    # stops walking back once target reached — season 2024 never requested
    seasons_requested = {call["data"]["season"] for call in client.calls}
    assert seasons_requested == {"2026", "2025"}


def test_collect_most_recent_completed_records_empty_seasons_without_fabricating():
    responses = {
        2026: {"gameList": []},
        2025: {"gameList": [_game("2025-1", "B")]},
    }
    client = FakeClient(responses)
    result = collect_most_recent_completed(client, start_season=2026, target_count=1, min_season=2025)
    assert [l.game_code for l in result] == ["2025-1"]
