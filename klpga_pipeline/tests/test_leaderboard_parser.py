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
        # CONFIRMED live, 2026-08-24 (gameCode=2026080002): "999" is the
        # real site's sentinel for "did not complete this round" — not
        # a literal numeric rank.
        ("999", ("999", None, False, "INCOMPLETE")),
        ("", (None, None, False, None)),
        (None, (None, None, False, None)),
    ],
)
def test_parse_rank_matrix(raw, expected):
    assert parse_rank(raw) == expected


def _make_row_html(rank, code, name="선수", **fields):
    attrs = " ".join(f'data-{k}="{v}"' for k, v in fields.items())
    return (
        f'<ul class="lb-row" data-rank="{rank}" data-name="{name}" {attrs}>'
        f'<li class="player-detail" _gamecode="G1" _playercode="{code}" _playername="{name}" '
        f'_round="2" _hole="1"></li></ul>'
    )


def test_999_sentinel_row_matches_the_real_confirmed_markup():
    """From the actual live HTML captured for gameCode=2026080002,
    playerCode 9777 (see docs/SITE_STRUCTURE_TODO.md): data-rank="999"
    pairs with data-score/data-totunderpar/data-todayunderpar all reset
    to the placeholder "0", and data-round2score is ALSO the placeholder
    "0" (not a real 0-stroke round) — while data-round1score="75" (a
    real, valid score from a round they did complete) must be kept."""
    html = _make_row_html(
        999, "9777", name="김윤경2",
        totunderpar="0", inghole="1", todayunderpar="0", score="0",
        round1score="75", round2score="0", round3score="", round4score="",
    )
    row = parse_round_leaderboard_html(html, game_code="G1", round_number=2)[0]

    assert row.rank_display == "999"
    assert row.rank is None
    assert row.status == "INCOMPLETE"

    # placeholder totals paired with the 999 sentinel -> None, not 0
    assert row.total_strokes is None
    assert row.total_under_par is None
    assert row.total_under_par_display is None
    assert row.today_under_par is None
    assert row.today_under_par_display is None

    # a literal "0" round score is never a real value in golf
    assert row.round2_score is None
    # but a genuinely completed EARLIER round's real score is preserved
    assert row.round1_score == 75


def test_literal_zero_round_score_is_not_a_real_score_even_without_999():
    """A round score of exactly 0 strokes is never realistic regardless
    of what the row's rank shows — belt-and-suspenders check that this
    isn't only handled via the 999-sentinel special case."""
    html = _make_row_html(
        50, "222", totunderpar="1", inghole="18", todayunderpar="1", score="73",
        round1score="0", round2score="73", round3score="", round4score="",
    )
    row = parse_round_leaderboard_html(html, game_code="G1", round_number=2)[0]
    assert row.round1_score is None
    assert row.round2_score == 73


def test_even_par_zero_is_preserved_for_a_normal_row():
    """A normal (non-999) row's data-totunderpar="0" genuinely means
    'E' (even par) and must NOT be treated as a placeholder/no-data —
    only the confirmed 999-sentinel case suppresses these fields."""
    html = _make_row_html(
        50, "333", totunderpar="0", inghole="18", todayunderpar="0", score="72",
        round1score="72", round2score="", round3score="", round4score="",
    )
    row = parse_round_leaderboard_html(html, game_code="G1", round_number=1)[0]
    assert row.total_under_par == 0
    assert row.today_under_par == 0


def test_parser_does_not_persist_anything(rows, tmp_path):
    """Sanity check that parsing is pure / has no side effects that could
    accidentally write fixture data into a real database file."""
    import klpga.parsers.leaderboard_parser as mod

    assert not hasattr(mod, "conn")
    assert not hasattr(mod, "sqlite3")
