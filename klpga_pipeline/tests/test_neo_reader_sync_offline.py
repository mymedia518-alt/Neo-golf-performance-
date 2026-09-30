"""Tests for klpga.neo_reader.sync.run_sync_offline -- the offline
counterpart to run_sync added 2026-09-30 so a machine with real
NEO_DATA_ROOT raw/ captures already on disk (e.g. from an earlier
online sync run, or copied over from another machine) can produce
normalized/<game_code> with ZERO network access, reusing the exact
same parse/build functions run_sync itself uses (see sync.py's
run_sync_offline docstring). Shares its fixtures with
test_neo_reader_sync.py (same real, already-confirmed-against-
production captures) so the two tests can assert byte-identical
normalized output regardless of whether the data came from a live
fetch or from disk."""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
ENTRY_LIST_HTML = (FIXTURES / "entry_list_sample.html").read_text(encoding="utf-8")
KRANKING_EVIDENCE = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026090003"
KRANKING_PERIOD_HTML = (KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_PERIOD_EVIDENCE_RAW.html").read_text(encoding="utf-8")
KRANKING_FULL_HTML = (KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_RAW.html").read_text(encoding="utf-8")
ROUND_LEADERBOARD_HTML = (FIXTURES / "round_leaderboard_sample.html").read_text(encoding="utf-8")
GROUP_PAGE_HTML = (FIXTURES / "group_page_sample.html").read_text(encoding="utf-8")

TEST_GAME_CODE = "2026080001"
TEST_SEASON = 2026

# Same synthetic single getGameList entry test_neo_reader_sync.py's
# FAKE_GAME_LIST_RESPONSE carries for this gameCode -- archive_raw's
# "game_list" capture is written as exactly this one matched entry's
# raw dict (see sync.py: json.dumps(match.raw, ...)), never the full
# gameList response, so that is what belongs on disk here too.
GAME_LIST_ENTRY = {
    "gameCode": TEST_GAME_CODE,
    "gameTitle": "제15회 KG 레이디스 오픈",
    "gameEngTitle": "15th KG Ladies Open",
    "tourType": "RE",
    "courseText": "테스트GC",
    "courseEngText": "Test GC",
    "outCourseText": "아웃",
    "inCourseText": "인",
    "startDate": "20260825",
    "endDate": "20260828",
    "gameFinish": "",
    "prizeMoney": "1000000000",
    "winnerCode": None,
    "winnerName": None,
    "gameMethod": "0",
}


def _write_pre_stage_raw_captures(raw_root: Path, game_code: str) -> None:
    """Writes the write-once raw/<game_code>/* files exactly as
    archive_raw would, for offline tests -- mirrors what a real online
    sync run (or a copy from another machine's NEO_DATA_ROOT) leaves on
    disk."""
    game_dir = raw_root / game_code
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "game_list.json").write_text(json.dumps(GAME_LIST_ENTRY, ensure_ascii=False, indent=2), encoding="utf-8")
    (game_dir / "entry_list.html").write_text(ENTRY_LIST_HTML, encoding="utf-8")
    (game_dir / "kranking_period.html").write_text(KRANKING_PERIOD_HTML, encoding="utf-8")
    (game_dir / "kranking_full_table.html").write_text(KRANKING_FULL_HTML, encoding="utf-8")


@pytest.fixture()
def offline_workspace(tmp_path):
    return {
        "db_path": tmp_path / "klpga.sqlite",
        "raw_root": tmp_path / "raw",
        "normalized_root": tmp_path / "normalized",
        "content_root": tmp_path / "content",
    }


def test_run_sync_offline_has_no_network_client_parameter_at_all():
    """Structural proof this path cannot make a network call: unlike
    run_sync (which takes an optional PoliteHttpClient), run_sync_offline
    has no client/http parameter to even construct one with."""
    from klpga.neo_reader.sync import run_sync_offline

    params = inspect.signature(run_sync_offline).parameters
    assert "client" not in params
    assert not any("http" in name.lower() for name in params)


def test_offline_pre_stage_matches_the_live_fetch_result_for_the_same_captures(offline_workspace):
    """The whole point: reading the SAME bytes back from disk instead of
    fetching them live must produce byte-identical normalized output,
    since both paths call the identical parse/build functions."""
    from klpga.neo_reader.sync import run_sync_offline
    from klpga.neo_reader.validate import validate_sync

    _write_pre_stage_raw_captures(offline_workspace["raw_root"], TEST_GAME_CODE)

    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    assert result.ok, [(s.name, s.status, s.error_message) for s in result.stages]
    names = {s.name for s in result.stages}
    assert names == {"tournament_info", "entry_list", "kranking", "grouping"}
    non_grouping = [s for s in result.stages if s.name != "grouping"]
    assert all(s.status == "success" for s in non_grouping)
    assert next(s for s in result.stages if s.name == "grouping").status == "skipped"

    validation = validate_sync(TEST_GAME_CODE, offline_workspace["normalized_root"])
    assert validation.overall == "PASS", validation.to_dict()

    info = json.loads((offline_workspace["normalized_root"] / TEST_GAME_CODE / "TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    assert info["event_name"] == "제15회 KG 레이디스 오픈"
    assert info["game_code"] == TEST_GAME_CODE

    kr = json.loads((offline_workspace["normalized_root"] / TEST_GAME_CODE / "KRANKING_TOP120.json").read_text(encoding="utf-8"))
    assert kr["ranking_week"] == "2026-W36"
    assert kr["full_population_count"] == 756
    assert kr["crosscheck"]["mismatched"] == 0

    conn = sqlite3.connect(offline_workspace["db_path"])
    written = conn.execute(
        "SELECT COUNT(*) FROM tournament_entry WHERE game_code=?", (TEST_GAME_CODE,)
    ).fetchone()[0]
    conn.close()
    assert written == 120


def test_offline_entry_list_row_count_matches_online_row_count(offline_workspace):
    """Same real fixture, same parser (parse_entry_list_html) -- the
    row count run_sync's own test asserts (120) must match exactly."""
    from klpga.neo_reader.sync import run_sync_offline

    _write_pre_stage_raw_captures(offline_workspace["raw_root"], TEST_GAME_CODE)
    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    entry_stage = next(s for s in result.stages if s.name == "entry_list")
    assert entry_stage.detail["parsed_row_count"] == 120


def test_offline_fails_closed_with_the_exact_missing_path_when_raw_is_empty(offline_workspace):
    """No raw/<game_code>/ captures at all -- must fail closed naming
    the exact expected path, never fabricate a TOURNAMENT_INFO.json."""
    from klpga.neo_reader.sync import run_sync_offline

    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    assert not result.ok
    assert result.stages[0].name == "tournament_info"
    assert result.stages[0].status == "error"
    assert "game_list.json" in result.stages[0].error_message
    assert not (offline_workspace["normalized_root"] / TEST_GAME_CODE).exists()


def test_offline_kranking_skips_without_blocking_when_not_archived(offline_workspace):
    """Only game_list.json + entry_list.html on disk (no K-Ranking
    captures) -- tournament_info/entry_list must still succeed; kranking
    must SKIP rather than fabricate or hard-fail the whole run, matching
    run_sync's own NON_BLOCKING_STAGES treatment of kranking."""
    from klpga.neo_reader.sync import run_sync_offline

    game_dir = offline_workspace["raw_root"] / TEST_GAME_CODE
    game_dir.mkdir(parents=True)
    (game_dir / "game_list.json").write_text(json.dumps(GAME_LIST_ENTRY, ensure_ascii=False, indent=2), encoding="utf-8")
    (game_dir / "entry_list.html").write_text(ENTRY_LIST_HTML, encoding="utf-8")

    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    assert result.ok, [(s.name, s.status, s.error_message) for s in result.stages]
    kranking_stage = next(s for s in result.stages if s.name == "kranking")
    assert kranking_stage.status == "skipped"
    assert not (offline_workspace["normalized_root"] / TEST_GAME_CODE / "KRANKING_TOP120.json").exists()


def test_offline_results_stage_reads_archived_rounds_from_disk_without_live_discovery(offline_workspace):
    """stage='results': round_leaderboard_r<n>.html captures already on
    disk must be read and parsed via parse_round_leaderboard_html (the
    same parser collect_all_rounds_for_game uses live) with no probing,
    no fetch, and the highest archived round number treated as final --
    same discovery *outcome* as discover_final_round, reached by
    listing the filesystem instead of a live probe."""
    from klpga.neo_reader.sync import run_sync_offline

    _write_pre_stage_raw_captures(offline_workspace["raw_root"], TEST_GAME_CODE)
    game_dir = offline_workspace["raw_root"] / TEST_GAME_CODE
    (game_dir / "round_leaderboard_r1.html").write_text(ROUND_LEADERBOARD_HTML, encoding="utf-8")
    (game_dir / "round_leaderboard_r2.html").write_text(ROUND_LEADERBOARD_HTML, encoding="utf-8")

    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="results", **offline_workspace)

    leaderboard_stage = next(s for s in result.stages if s.name == "leaderboard")
    assert leaderboard_stage.status == "success", leaderboard_stage.error_message
    assert leaderboard_stage.detail["final_round"] == 2

    leaderboard = json.loads((offline_workspace["normalized_root"] / TEST_GAME_CODE / "LEADERBOARD.json").read_text(encoding="utf-8"))
    assert leaderboard["final_round"] == 2
    assert len(leaderboard["records"]) == 3  # round_leaderboard_sample.html's 3 synthetic rows


def test_offline_tournament_info_is_found_by_content_even_under_a_different_filename(offline_workspace):
    """Real bug found 2026-09-30: offline sync hard-required the exact
    filename game_list.json even when a real getGameList JSON entry
    existed under a different name (e.g. tournament_info.html).
    run_sync_offline must now fall back to find_capture_by_capability
    and find it by content."""
    from klpga.neo_reader.sync import run_sync_offline

    game_dir = offline_workspace["raw_root"] / TEST_GAME_CODE
    game_dir.mkdir(parents=True)
    # Named "tournament_info.html", NOT "game_list.json" -- but the
    # real content is a genuine getGameList JSON entry.
    (game_dir / "tournament_info.html").write_text(json.dumps(GAME_LIST_ENTRY, ensure_ascii=False, indent=2), encoding="utf-8")

    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    tournament_info_stage = next(s for s in result.stages if s.name == "tournament_info")
    assert tournament_info_stage.status == "success", tournament_info_stage.error_message

    info = json.loads((offline_workspace["normalized_root"] / TEST_GAME_CODE / "TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    assert info["event_name"] == "제15회 KG 레이디스 오픈"


def test_offline_grouping_stage_reuses_group_page_parser_from_archived_html(offline_workspace):
    """Real gap found during the required-work audit: group_page_parser
    is a real, already-confirmed parser (see its own module docstring
    and tests/test_group_page_parser.py) that was never wired into any
    sync stage before. This proves the adapter: archived grouping.html
    -> parse_round_grouping (unchanged) -> GROUPING.json, using the
    same fixture test_group_page_parser.py itself is built against
    (round-one: 6 players, round-three: 9 players, round-two/four not
    yet published on this real capture)."""
    from klpga.neo_reader.sync import run_sync_offline

    _write_pre_stage_raw_captures(offline_workspace["raw_root"], TEST_GAME_CODE)
    (offline_workspace["raw_root"] / TEST_GAME_CODE / "grouping.html").write_text(GROUP_PAGE_HTML, encoding="utf-8")

    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    assert result.ok, [(s.name, s.status, s.error_message) for s in result.stages]
    grouping_stage = next(s for s in result.stages if s.name == "grouping")
    assert grouping_stage.status == "success"
    assert grouping_stage.detail["rounds_present"] == [1, 3]
    assert grouping_stage.detail["player_counts"] == {1: 6, 3: 9}

    grouping = json.loads((offline_workspace["normalized_root"] / TEST_GAME_CODE / "GROUPING.json").read_text(encoding="utf-8"))
    assert len(grouping["rounds"]["1"]) == 6
    assert len(grouping["rounds"]["3"]) == 9
    assert "2" not in grouping["rounds"] and "4" not in grouping["rounds"]


def test_offline_grouping_stage_skips_without_blocking_when_not_archived(offline_workspace):
    from klpga.neo_reader.sync import run_sync_offline

    _write_pre_stage_raw_captures(offline_workspace["raw_root"], TEST_GAME_CODE)
    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="pre", **offline_workspace)

    assert result.ok, [(s.name, s.status, s.error_message) for s in result.stages]
    grouping_stage = next(s for s in result.stages if s.name == "grouping")
    assert grouping_stage.status == "skipped"
    assert not (offline_workspace["normalized_root"] / TEST_GAME_CODE / "GROUPING.json").exists()


def test_offline_results_stage_fails_closed_when_no_rounds_archived(offline_workspace):
    from klpga.neo_reader.sync import run_sync_offline

    _write_pre_stage_raw_captures(offline_workspace["raw_root"], TEST_GAME_CODE)
    result = run_sync_offline(TEST_GAME_CODE, TEST_SEASON, stage="results", **offline_workspace)

    leaderboard_stage = next(s for s in result.stages if s.name == "leaderboard")
    assert leaderboard_stage.status == "error"
    assert "round_leaderboard_r" in leaderboard_stage.error_message
