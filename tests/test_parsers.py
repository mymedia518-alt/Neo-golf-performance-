from pathlib import Path

import pytest

from klpga.parsers import ParseError
from klpga.parsers.leaderboard_parser import parse_leaderboard
from klpga.parsers.tournament_detail_parser import parse_tournament_detail
from klpga.parsers.tournament_list_parser import parse_tournament_list

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_tournament_list():
    items = parse_tournament_list(_read("tournament_list_sample.html"))
    assert len(items) == 2
    first = items[0]
    assert first.tournament_id == "1001"
    assert first.tournament_name == "Fixture Open"
    assert first.status == "완료"
    assert first.tournament_type == "정규투어"


def test_parse_tournament_list_empty_raises():
    with pytest.raises(ParseError):
        parse_tournament_list("<html><body><table></table></body></html>")


def test_parse_tournament_detail():
    detail = parse_tournament_detail(_read("tournament_detail_sample.html"))
    assert detail.course_name == "Fixture Country Club"
    assert detail.par == 72
    assert detail.yardage == 6500
    assert detail.rounds_scheduled == 4


def test_parse_leaderboard():
    rows = parse_leaderboard(_read("leaderboard_sample.html"))
    assert len(rows) == 2

    winner = rows[0]
    assert winner.raw_rank == "1"
    assert winner.player_id == "9001"
    assert winner.total_strokes == 276
    assert winner.round_strokes == [68, 70, 69, 69]

    cut_player = rows[1]
    assert cut_player.raw_rank == "CUT"
    assert cut_player.total_strokes is None
    assert cut_player.round_strokes == [75, 74]


def test_parse_leaderboard_empty_raises():
    with pytest.raises(ParseError):
        parse_leaderboard("<html><body><table></table></body></html>")
