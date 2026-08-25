"""Tests for scripts/13_discover_entry_list.py's pure logic — no
network access. Covers the keyword-link matcher and the getGameList
candidate-selection logic (find non-"F" entries, sort soonest-first,
print the full raw JSON of the chosen candidate) against a fake client,
the same pattern as tests/test_tournaments_collector.py."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "13_discover_entry_list.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("discover_entry_list_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient.post_json — mirrors
    tests/test_tournaments_collector.py's FakeClient."""

    def __init__(self, responses_by_season: dict[int, dict]):
        self.responses_by_season = responses_by_season

    def post_json(self, url, data=None, **kwargs):
        season = int(data["season"])
        return self.responses_by_season.get(season, {"gameList": []})


def _game(game_code, title, tour_type="RE", start_date="20260301", end_date="20260315", finish="F", game_method="0", **extra):
    row = {
        "gameCode": game_code,
        "gameTitle": title,
        "gameEngTitle": f"{title} (EN)",
        "tourType": tour_type,
        "courseText": "코스",
        "courseEngText": "Course",
        "outCourseText": "아웃",
        "inCourseText": "인",
        "startDate": start_date,
        "endDate": end_date,
        "gameFinish": finish,
        "prizeMoney": None,
        "winnerCode": None,
        "winnerName": None,
        "gameMethod": game_method,
    }
    row.update(extra)
    return row


def test_keyword_links_matches_english_and_korean_entry_terms(module):
    html = """
    <a href="/schedule/list.do">Schedule</a>
    <a href="/tournament/entrylist.do?gameCode=X">Entry List</a>
    <a href="/tournament/참가선수.do?gameCode=X">참가선수</a>
    <a href="/about/company.do">About</a>
    <script src="/js/analytics.js"></script>
    """
    links = module._keyword_links("https://www.klpga.co.kr", html)
    assert any("entrylist" in link for link in links)
    assert any("참가선수" in link for link in links)
    assert any("schedule" in link for link in links)
    assert not any("company" in link for link in links)
    assert not any("analytics" in link for link in links)


def test_keyword_links_resolves_relative_urls_against_base(module):
    html = '<a href="entry/list.do">Entry</a>'
    links = module._keyword_links("https://www.klpga.co.kr/tournament/", html)
    assert links == {"https://www.klpga.co.kr/tournament/entry/list.do"}


def test_discover_game_list_finds_soonest_non_completed_candidate(module, capsys):
    responses = {
        2026: {
            "gameList": [
                _game("A", "완료된 대회", finish="F", start_date="20260101", end_date="20260104"),
                _game("B", "다음 대회", finish="P", start_date="20260901", end_date="20260904", entryCnt=90),
                _game("C", "그 다음 대회", finish="P", start_date="20260815", end_date="20260818"),
            ]
        }
    }
    client = FakeClient(responses)

    module.discover_game_list(client, 2026)
    out = capsys.readouterr().out

    assert "gameFinish breakdown: {'F': 1, 'P': 2}" in out
    # Soonest by startDate among non-F entries is C (20260815), not B.
    assert "FULL raw getGameList entry for the soonest candidate (gameCode=C)" in out
    assert '"gameCode": "C"' in out


def test_discover_game_list_reports_when_no_candidates_exist(module, capsys):
    responses = {2026: {"gameList": [_game("A", "완료된 대회", finish="F")]}}
    client = FakeClient(responses)

    module.discover_game_list(client, 2026)
    out = capsys.readouterr().out

    assert "No non-'F'" in out


def test_discover_game_list_prints_full_raw_json_for_manual_inspection(module, capsys):
    """The whole point of dumping the raw entry is to let a human spot
    an unparsed entry-count/entry-list hint field — confirm a field
    this project has never parsed before survives into the printed
    output verbatim."""
    responses = {
        2026: {
            "gameList": [
                _game("B", "다음 대회", finish="P", start_date="20260901", someNeverBeforeSeenField="hello"),
            ]
        }
    }
    client = FakeClient(responses)

    module.discover_game_list(client, 2026)
    out = capsys.readouterr().out

    assert '"someNeverBeforeSeenField": "hello"' in out
