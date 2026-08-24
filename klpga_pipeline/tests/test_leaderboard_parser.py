"""Tests for klpga.parsers.leaderboard_parser against the synthetic
round_leaderboard_sample.html fixture (see that file's header comment:
it is NOT real captured KLPGA data, and must never be written into
data/klpga.sqlite)."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.parsers.leaderboard_parser import parse_rank, parse_round_leaderboard_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "round_leaderboard_sample.html"


@pytest.fixture()
def sample_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def rows(sample_html: str):
    return parse_round_leaderboard_html(sample_html, game_code="2026080002", round_number=2)


def test_parses_three_rows(rows):
    assert len(rows) == 3


def test_seo_gyorim_row_matches_confirmed_spec(rows):
    """Exact field values from the task spec's confirmed capture."""
    row = next(r for r in rows if r.player_code == "11134")

    assert row.game_code == "2026080002"
    assert row.player_code == "11134"
    assert row.player_name == "서교림"
    assert row.player_eng_name == "SEO Kyorim"
    assert row.round_number == 2

    assert row.rank == 1
    assert row.rank_display == "1"
    assert row.tie_flag is False
    assert row.status is None

    assert row.total_under_par == -7
    assert row.total_strokes == 137
    assert row.today_under_par == -5
    assert row.holes_completed == "18"

    assert row.round1_score == 70
    assert row.round2_score == 67
    assert row.round3_score is None
    assert row.round4_score is None


def test_empty_strings_become_none_not_zero_or_guessed(rows):
    cut_row = next(r for r in rows if r.player_code == "30055")
    # data-inghole="" / data-todayunderpar="" / data-score="" -> None, never 0
    assert cut_row.holes_completed is None
    assert cut_row.today_under_par is None
    assert cut_row.today_under_par_display is None
    assert cut_row.total_strokes is None
    # rounds not played stay None
    assert cut_row.round3_score is None
    assert cut_row.round4_score is None
    # rounds actually played are preserved
    assert cut_row.round1_score == 75
    assert cut_row.round2_score == 79


def test_cut_status_preserves_raw_string_and_has_no_numeric_rank(rows):
    cut_row = next(r for r in rows if r.player_code == "30055")
    assert cut_row.rank_display == "CUT"
    assert cut_row.rank is None
    assert cut_row.status == "CUT"
    assert cut_row.tie_flag is False
    # to-par with a '+' sign is still parsed correctly
    assert cut_row.total_under_par == 2
    assert cut_row.total_under_par_display == "+2"


def test_tied_rank_parses_number_and_sets_tie_flag(rows):
    tied_row = next(r for r in rows if r.player_code == "20099")
    assert tied_row.rank_display == "T2"
    assert tied_row.rank == 2
    assert tied_row.tie_flag is True
    assert tied_row.status is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", ("1", 1, False, None)),
        ("T1", ("T1", 1, True, None)),
        ("t3", ("t3", 3, True, None)),
        ("CUT", ("CUT", None, False, "CUT")),
        ("WD", ("WD", None, False, "WD")),
        ("DQ", ("DQ", None, False, "DQ")),
        ("", (None, None, False, None)),
        (None, (None, None, False, None)),
    ],
)
def test_parse_rank_matrix(raw, expected):
    assert parse_rank(raw) == expected


def test_parser_does_not_persist_anything(rows, tmp_path):
    """Sanity check that parsing is pure / has no side effects that could
    accidentally write fixture data into a real database file."""
    import klpga.parsers.leaderboard_parser as mod

    assert not hasattr(mod, "conn")
    assert not hasattr(mod, "sqlite3")
