"""Tests for klpga.parsers.entry_list_parser against
tests/fixtures/entry_list_sample.html — the COMPLETE, verbatim real HTML
of https://klpga.co.kr/web/tourInfo/entry?gameCode=2026080001 (제15회 KG
레이디스 오픈), pasted directly by the user from a live browser capture.
This is real captured data, not a synthetic fixture."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.parsers.entry_list_parser import (
    parse_entry_list_html,
    parse_entry_summary,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "entry_list_sample.html"


@pytest.fixture()
def sample_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def summary(sample_html: str):
    return parse_entry_summary(sample_html)


@pytest.fixture()
def result(sample_html: str):
    return parse_entry_list_html(sample_html)


def test_summary_counts_match_confirmed_capture(summary):
    assert summary.counts == {
        "총 참가자": 120,
        "자격자": 115,
        "추천자": 5,
        "초청자": 0,
    }


def test_total_parsed_rows_matches_summary_total_entrants(result, summary):
    assert len(result.rows) == summary.counts["총 참가자"] == 120


def test_no_unparsed_rows_in_real_capture(result):
    assert result.unparsed_row_count == 0
    assert result.unparsed_samples == []


def test_moon_jungmin_cross_check(result):
    """The specific cross-check the user asked for: 문정민 -> playerCode
    10296, confirmed live via her mainRecord?playerCode=10296 profile
    page."""
    matches = [r for r in result.rows if r.player_code == "10296"]
    assert len(matches) == 1
    row = matches[0]
    assert row.player_name == "문정민"
    assert row.qualification_category == "자격자"
    assert row.qualification_reason == "2024 일반대회 우승자"
    assert row.nationality == "KOR"


@pytest.mark.parametrize(
    "player_code,expected_name,expected_category,expected_reason",
    [
        ("9174", "강가율", "자격자", "2025 정규투어 상금순위 60위 이내"),
        ("10623", "강지선", "자격자", "시드순위자"),
        ("10095", "방신실", "자격자", "2025 일반대회 우승자"),
        ("10138", "임진영", "자격자", "2026 일반대회 우승자"),
        ("10143", "정영화", "추천자", None),
    ],
)
def test_additional_real_players_cross_check(
    result, player_code, expected_name, expected_category, expected_reason
):
    matches = [r for r in result.rows if r.player_code == player_code]
    assert len(matches) == 1
    row = matches[0]
    assert row.player_name == expected_name
    assert row.qualification_category == expected_category
    assert row.qualification_reason == expected_reason


def test_category_transitions_from_qualified_to_recommended(result):
    """자격자 (115) then 추천자 (5) — the boundary players on either side
    of the divider must carry the correct category, not the prior one
    leaking across the divider row."""
    by_code = {r.player_code: r for r in result.rows}
    qualified = [r for r in result.rows if r.qualification_category == "자격자"]
    recommended = [r for r in result.rows if r.qualification_category == "추천자"]
    invited = [r for r in result.rows if r.qualification_category == "초청자"]
    assert len(qualified) == 115
    assert len(recommended) == 5
    assert len(invited) == 0
    assert by_code["10143"].qualification_category == "추천자"


def test_favorites_table_never_leaks_into_parsed_result(sample_html, result):
    """The hidden '즐겨찾기 선수' table duplicates the entire entrant list
    under a different DOM structure (individually display:none rows) —
    confirm parsing still yields exactly one EntryRow per real playerCode,
    not two."""
    codes = [r.player_code for r in result.rows]
    assert len(codes) == len(set(codes)), "duplicate playerCode — favorites table may have leaked in"
    assert "즐겨찾기 선수" in sample_html  # sanity: the decoy section really is present in this fixture


def test_missing_all_players_heading_raises():
    with pytest.raises(ValueError, match="전체 선수"):
        parse_entry_list_html("<html><body>no entry table here</body></html>")
