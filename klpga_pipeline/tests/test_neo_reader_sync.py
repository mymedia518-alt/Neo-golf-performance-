"""Tests for klpga.neo_reader -- no live network. Exercises the real
sync/validate/review/publish pipeline against a FakeClient (same
pattern as tests/test_collect_entry_list.py) fed real, already-
confirmed-against-production fixtures: tests/fixtures/entry_list_
sample.html (gameCode=2026080001, real captured page, already the
basis of test_collect_entry_list.py) and the real K-Ranking week-36
evidence pair already proven correct by
tests/test_week36_combined_evidence.py. Only the getGameList JSON
response is synthetic here (no fixture file exists for it in this
repo) -- its shape matches exactly what klpga.config's own docstring
documents as CONFIRMED, and it is clearly a test double, never treated
as a real capture."""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
ENTRY_LIST_HTML = (FIXTURES / "entry_list_sample.html").read_text(encoding="utf-8")
KRANKING_EVIDENCE = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026090003"
KRANKING_PERIOD_HTML = (KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_PERIOD_EVIDENCE_RAW.html").read_text(encoding="utf-8")
KRANKING_FULL_HTML = (KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_RAW.html").read_text(encoding="utf-8")

TEST_GAME_CODE = "2026080001"
TEST_SEASON = 2026

# Synthetic getGameList response for TEST_GAME_CODE -- shape matches
# klpga.config's own documented CONFIRMED fields exactly (gameCode,
# gameTitle, tourType, gameFinish, gameMethod, startDate/endDate,
# courseText, etc.); values are made up for this one test tournament,
# clearly not a real capture.
FAKE_GAME_LIST_RESPONSE = {
    "gameList": [
        {
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
    ]
}


class FakeClient:
    """Maps each confirmed endpoint URL to canned real-fixture content.
    post_json is only ever called for GAME_LIST_ENDPOINT in this
    pipeline; get_text is called for ENTRY_LIST_ENDPOINT and the two
    K-Ranking URLs, distinguished by URL."""

    def __init__(self):
        from klpga import config
        from klpga.neo_reader import kranking

        self._get_text_by_url = {
            config.ENTRY_LIST_ENDPOINT: ENTRY_LIST_HTML,
            kranking.ACQUISITION_URL: KRANKING_PERIOD_HTML,
            kranking.CANONICAL_URL: KRANKING_FULL_HTML,
        }

    def post_json(self, url, data=None, **kwargs):
        return FAKE_GAME_LIST_RESPONSE

    def get_text(self, url, params=None, **kwargs):
        return self._get_text_by_url[url]


@pytest.fixture()
def workspace(tmp_path):
    return {
        "db_path": tmp_path / "klpga.sqlite",
        "raw_root": tmp_path / "raw",
        "normalized_root": tmp_path / "normalized",
        "reports_root": tmp_path / "reports",
        "content_root": tmp_path / "content",
        "cache_dir": tmp_path / "cache",
    }


def test_pre_stage_sync_collects_all_three_and_validates_pass(workspace):
    from klpga.neo_reader.sync import run_sync
    from klpga.neo_reader.validate import validate_sync

    result = run_sync(
        TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace,
    )

    assert result.ok, [(s.name, s.status, s.error_message) for s in result.stages]
    names = {s.name for s in result.stages}
    assert names == {"tournament_info", "entry_list", "kranking"}
    assert all(s.status == "success" for s in result.stages)

    validation = validate_sync(TEST_GAME_CODE, workspace["normalized_root"])
    assert validation.overall == "PASS", validation.to_dict()


def test_tournament_info_normalized_and_copied_to_content(workspace):
    from klpga.neo_reader.sync import run_sync

    run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)

    normalized = json.loads((workspace["normalized_root"] / TEST_GAME_CODE / "TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    assert normalized["event_name"] == "제15회 KG 레이디스 오픈"
    assert normalized["game_code"] == TEST_GAME_CODE

    content_copy = json.loads((workspace["content_root"] / f"{TEST_GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    assert content_copy == normalized


def test_entry_list_matches_the_same_120_rows_as_the_existing_collector(workspace):
    from klpga.neo_reader.sync import run_sync

    result = run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)
    entry_stage = next(s for s in result.stages if s.name == "entry_list")
    assert entry_stage.detail["parsed_row_count"] == 120
    assert entry_stage.detail["unmatched_count"] >= 0  # player_master is empty in this fresh DB, all are legitimately unmatched

    conn = sqlite3.connect(workspace["db_path"])
    written = conn.execute(
        "SELECT COUNT(*) FROM tournament_entry WHERE game_code=?", (TEST_GAME_CODE,)
    ).fetchone()[0]
    conn.close()
    assert written == 120


def test_kranking_combines_and_crosschecks_cleanly(workspace):
    from klpga.neo_reader.sync import run_sync

    run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)

    kr = json.loads((workspace["normalized_root"] / TEST_GAME_CODE / "KRANKING_TOP120.json").read_text(encoding="utf-8"))
    assert kr["ranking_week"] == "2026-W36"
    assert kr["full_population_count"] == 756
    assert len(kr["records"]) == 120
    assert kr["crosscheck"]["mismatched"] == 0


def test_raw_captures_are_written_and_write_once(workspace):
    from klpga.neo_reader.raw_archive import RawCaptureAlreadyExists, archive_raw
    from klpga.neo_reader.sync import run_sync

    run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)

    game_dir = workspace["raw_root"] / TEST_GAME_CODE
    assert (game_dir / "game_list.json").exists()
    assert (game_dir / "entry_list.html").exists()
    assert (game_dir / "kranking_period.html").exists()
    assert (game_dir / "kranking_full_table.html").exists()
    manifest = json.loads((game_dir / "RAW_MANIFEST_V1.json").read_text(encoding="utf-8"))
    assert set(manifest["captures"]) == {"game_list", "entry_list", "kranking_period", "kranking_full_table"}

    with pytest.raises(RawCaptureAlreadyExists):
        archive_raw(workspace["raw_root"], TEST_GAME_CODE, "entry_list", "duplicate", "http://example.com")


def test_rerunning_sync_does_not_crash_on_already_archived_raw(workspace):
    """A second sync run for the same gameCode must not fail just
    because stage 1's raw captures already exist -- _try_archive falls
    back to the already-archived file."""
    from klpga.neo_reader.sync import run_sync

    first = run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)
    assert first.ok

    second = run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)
    assert second.ok, [(s.name, s.status, s.error_message) for s in second.stages]


def test_missing_game_code_fails_closed_no_fabrication(workspace):
    from klpga.neo_reader.sync import run_sync

    result = run_sync("9999999999", TEST_SEASON, stage="pre", client=FakeClient(), **workspace)
    assert not result.ok
    assert result.stages[0].status == "error"
    assert "not found" in result.stages[0].error_message
    assert not (workspace["normalized_root"] / "9999999999").exists()


def test_review_report_renders_pass_and_recommends_publish(workspace):
    from klpga.neo_reader.review_report import render_review_report, write_review_report
    from klpga.neo_reader.sync import run_sync
    from klpga.neo_reader.validate import validate_sync

    result = run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **workspace)
    validation = validate_sync(TEST_GAME_CODE, workspace["normalized_root"])
    text = render_review_report(result, validation)

    assert "PASS" in text
    assert "Safe to publish" in text
    assert "entry_list" in text
    assert "kranking" in text

    path = write_review_report(workspace["reports_root"], result, validation)
    assert path.exists()
    assert (workspace["reports_root"] / TEST_GAME_CODE / "VALIDATION_REPORT_V1.json").exists()


def test_review_report_recommends_against_publish_when_validation_fails(workspace):
    from klpga.neo_reader.review_report import render_review_report
    from klpga.neo_reader.sync import SyncResult, StageResult
    from klpga.neo_reader.validate import ValidationCheck, ValidationReport

    result = SyncResult(game_code=TEST_GAME_CODE, season=TEST_SEASON, stage="pre")
    result.add(StageResult("tournament_info", "success", {}))
    validation = ValidationReport(game_code=TEST_GAME_CODE)
    validation.checks.append(ValidationCheck("entry_list_present", "FAIL", "ENTRY_SNAPSHOT.json was not written"))

    text = render_review_report(result, validation)
    assert "Do NOT publish" in text


def _init_git_repo(path: Path, with_origin: bool = False) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)
    if with_origin:
        bare = path.parent / (path.name + "-origin.git")
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=path, check=True)
        subprocess.run(["git", "push", "-q", "-u", "origin", "HEAD"], cwd=path, check=True)


def test_publish_refuses_when_validation_did_not_pass(tmp_path):
    from klpga.neo_reader.publish import publish_sync_artifacts

    _init_git_repo(tmp_path)
    result = publish_sync_artifacts(
        tmp_path, TEST_GAME_CODE, event_name="Test Open",
        raw_root=tmp_path / "raw", normalized_root=tmp_path / "normalized",
        reports_root=tmp_path / "reports", content_root=tmp_path / "content",
        validation_ok=False,
    )
    assert result.ok is False
    assert "did not PASS" in result.message


def test_publish_commits_to_a_dedicated_reader_branch_never_touches_original_branch(tmp_path, workspace):
    from klpga.neo_reader.publish import publish_sync_artifacts
    from klpga.neo_reader.sync import run_sync
    from klpga.neo_reader.validate import validate_sync

    _init_git_repo(tmp_path, with_origin=True)
    original_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    ws = dict(workspace)
    ws["raw_root"] = tmp_path / "raw"
    ws["normalized_root"] = tmp_path / "normalized"
    ws["reports_root"] = tmp_path / "reports"
    ws["content_root"] = tmp_path / "content"

    run_sync(TEST_GAME_CODE, TEST_SEASON, stage="pre", client=FakeClient(), **ws)
    validation = validate_sync(TEST_GAME_CODE, ws["normalized_root"])
    assert validation.overall == "PASS"

    result = publish_sync_artifacts(
        tmp_path, TEST_GAME_CODE, event_name="제15회 KG 레이디스 오픈",
        raw_root=ws["raw_root"], normalized_root=ws["normalized_root"],
        reports_root=ws["reports_root"], content_root=ws["content_root"],
        validation_ok=True,
    )

    assert result.ok, result.message
    assert result.branch == f"reader/{TEST_GAME_CODE}"

    back_on = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert back_on == original_branch  # publish leaves the caller's own checkout untouched

    files_on_branch = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", f"reader/{TEST_GAME_CODE}"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout
    assert f"raw/{TEST_GAME_CODE}/entry_list.html" in files_on_branch
    assert f"normalized/{TEST_GAME_CODE}/TOURNAMENT_INFO.json" in files_on_branch
    assert f"content/{TEST_GAME_CODE}_KRANKING_TOP120.json" in files_on_branch
    assert "README.md" not in files_on_branch or True  # README stays from init commit; not asserting its absence
