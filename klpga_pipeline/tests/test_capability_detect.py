"""Tests for klpga.neo_reader.capability_detect -- classification by
PARSER CAPABILITY (read the real content, try the real parser), never
by filename. Covers the two real bugs found 2026-09-30:

1. A file named "leaderboard.html" (not the archive_raw convention
   "round_leaderboard_r<n>.html") was reported parser_missing even
   though leaderboard_parser.parse_round_leaderboard_html can parse
   it -- classification must go by content, not the exact filename.
2. Offline sync hard-required the exact filename "game_list.json" for
   tournament_info even when a real getGameList JSON entry existed
   under a different name -- fixed via find_capture_by_capability.

Also covers a bug found WHILE fixing #1: parse_round_leaderboard_html's
row selector ([data-rank]) is broader than "this is a leaderboard
page" -- it false-positive-matched the K-Ranking full-table page
(which also uses data-rank on its own rows), so the leaderboard probe
now requires at least one row to carry a real player identity
(player_code AND player_name), the same distinction the parser's own
PlayerRoundRow contract already draws."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.neo_reader.capability_detect import classify_file_by_content, find_capture_by_capability, probe_tournament_info

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
KRANKING_EVIDENCE = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026090003"


def test_a_file_literally_named_leaderboard_html_classifies_as_parser_exists(tmp_path):
    """Bug #1, reproduced exactly: the filename does NOT follow
    archive_raw's round_leaderboard_r<n>.html convention, but the
    content is real, parseable leaderboard HTML."""
    p = tmp_path / "leaderboard.html"
    p.write_text((FIXTURES / "round_leaderboard_sample.html").read_text(encoding="utf-8"), encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "parser_exists"
    assert result["stage_name"] == "leaderboard"


def test_kranking_full_table_is_never_misclassified_as_leaderboard(tmp_path):
    """Bug found while fixing #1: K-Ranking's own table also carries
    data-rank attributes, which used to false-positive-match the
    leaderboard probe before it required a real player identity too."""
    p = tmp_path / "some_ranking_page.html"
    p.write_text((KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_RAW.html").read_text(encoding="utf-8"), encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "parser_exists"
    assert result["stage_name"] == "kranking"  # must NOT be "leaderboard"


def test_kranking_period_page_classifies_correctly_regardless_of_filename(tmp_path):
    p = tmp_path / "weird_name_123.html"
    p.write_text((KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_PERIOD_EVIDENCE_RAW.html").read_text(encoding="utf-8"), encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "parser_exists"
    assert result["stage_name"] == "kranking"


def test_entry_list_html_classifies_correctly_regardless_of_filename(tmp_path):
    p = tmp_path / "not_the_usual_name.html"
    p.write_text((FIXTURES / "entry_list_sample.html").read_text(encoding="utf-8"), encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "parser_exists"
    assert result["stage_name"] == "entry_list"


def test_group_page_html_classifies_correctly_regardless_of_filename(tmp_path):
    p = tmp_path / "tee_times_dump.html"
    p.write_text((FIXTURES / "group_page_sample.html").read_text(encoding="utf-8"), encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "adapter_exists"
    assert result["stage_name"] == "grouping"


def test_tournament_info_json_classifies_correctly_regardless_of_filename(tmp_path):
    """Bug #2's content: a real getGameList JSON entry under a
    filename that isn't game_list.json -- e.g. a mislabeled
    .html extension on genuinely JSON content."""
    p = tmp_path / "tournament_info.html"
    p.write_text('{"gameCode": "2026100005", "gameTitle": "Test"}', encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "parser_exists"
    assert result["stage_name"] == "tournament_info"


def test_genuinely_unparseable_content_is_still_honestly_parser_missing(tmp_path):
    """Not every "bug" is a classification bug: real rendered HTML that
    doesn't match ANY existing parser's contract must still report
    parser_missing -- this is the honest, correct answer, not a gap to
    paper over."""
    p = tmp_path / "course.html"
    p.write_text("<html><body><h1>코스 안내</h1><p>Some real page, no confirmed parser exists for this shape.</p></body></html>", encoding="utf-8")

    result = classify_file_by_content(p)
    assert result["status"] == "parser_missing"
    assert result["stage_name"] is None


def test_find_capture_by_capability_locates_tournament_info_under_any_filename(tmp_path):
    """The offline-sync side of bug #2: find_capture_by_capability must
    find a real getGameList JSON entry even when it isn't named
    game_list.json."""
    game_dir = tmp_path / "raw" / "2026100005"
    game_dir.mkdir(parents=True)
    (game_dir / "tournament_info.html").write_text('{"gameCode": "2026100005", "gameTitle": "Test"}', encoding="utf-8")
    (game_dir / "unrelated.txt").write_text("not json, not html we care about", encoding="utf-8")

    found = find_capture_by_capability(tmp_path / "raw", "2026100005", probe_tournament_info)
    assert found is not None
    assert found.name == "tournament_info.html"


def test_find_capture_by_capability_returns_none_when_nothing_matches(tmp_path):
    game_dir = tmp_path / "raw" / "2026100005"
    game_dir.mkdir(parents=True)
    (game_dir / "course.html").write_text("<html>not tournament info</html>", encoding="utf-8")

    found = find_capture_by_capability(tmp_path / "raw", "2026100005", probe_tournament_info)
    assert found is None
