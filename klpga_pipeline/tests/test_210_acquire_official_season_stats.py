"""Tests for scripts/210_acquire_official_season_stats.py's
classification logic -- SOURCE_EXISTS_AND_ACQUIRED vs
SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED vs
SOURCE_EXISTS_BUT_ACCESS_BLOCKED -- using a fake client so no real
network call happens."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "210_acquire_official_season_stats.py"
REAL_FIXTURE = (
    Path(__file__).parent / "fixtures" / "official_detail" / "8436_publicRecordSeasonDetail.html"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_210", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_210"] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeClient:
    """Returns a fixed real-fixture-derived response for the 'last'
    call and the same fixture for the 'full' call (good enough for
    exercising the classification branches without a real network
    call)."""

    def __init__(self, status_code=200, text=None):
        self.status_code = status_code
        self.text = text if text is not None else REAL_FIXTURE.read_text(encoding="utf-8")

    def _throttle(self, host):
        pass

    def _do_request(self, method, url, **kwargs):
        return FakeResponse(self.status_code, self.text)


def test_acquire_player_source_exists_and_acquired_when_rounds_consistent(tmp_path):
    mod = _load_module()
    # the real fixture's own 평균타수 row says 라운드수=8 -- set expected >= 8 so the cross-check passes
    entry = {
        "player_name": "테스트선수", "player_code": "8436", "season": 2026,
        "last_pre_cutoff_game_code": "2026080002", "expected_pre_cutoff_rounds_total": 8,
    }
    client = FakeClient()
    result = mod.acquire_player(client, entry, tmp_path, force=True)
    assert result["status"] == "SOURCE_EXISTS_AND_ACQUIRED"
    assert result["temporal_cross_check_consistent"] is True
    assert result["returned_rounds_for_last_pre_cutoff_gamecode"] == 8
    assert result["metrics"]["average_score"]["value"] == 77.625


def test_acquire_player_temporal_reconstruction_failed_when_rounds_exceed_expected(tmp_path):
    mod = _load_module()
    # expected pre-cutoff rounds is LESS than the 8 the fixture reports -- the
    # gameCode-scoped call returned MORE rounds than this player could have
    # played before her own cutoff, so the scoping hypothesis fails for her.
    entry = {
        "player_name": "테스트선수", "player_code": "8436", "season": 2026,
        "last_pre_cutoff_game_code": "2026080002", "expected_pre_cutoff_rounds_total": 3,
    }
    client = FakeClient()
    result = mod.acquire_player(client, entry, tmp_path, force=True)
    assert result["status"] == "SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED"
    assert result["temporal_cross_check_consistent"] is False


def test_acquire_player_access_blocked_on_non_200():
    mod = _load_module()
    entry = {
        "player_name": "테스트선수", "player_code": "8436", "season": 2026,
        "last_pre_cutoff_game_code": "2026080002", "expected_pre_cutoff_rounds_total": 8,
    }
    import tempfile
    client = FakeClient(status_code=403, text="Forbidden")
    with tempfile.TemporaryDirectory() as d:
        result = mod.acquire_player(client, entry, Path(d), force=True)
    assert result["status"] == "SOURCE_EXISTS_BUT_ACCESS_BLOCKED"


def test_acquire_player_access_blocked_on_garbage_response():
    mod = _load_module()
    entry = {
        "player_name": "테스트선수", "player_code": "8436", "season": 2026,
        "last_pre_cutoff_game_code": "2026080002", "expected_pre_cutoff_rounds_total": 8,
    }
    import tempfile
    client = FakeClient(status_code=200, text="<html><body>not a real fragment</body></html>")
    with tempfile.TemporaryDirectory() as d:
        result = mod.acquire_player(client, entry, Path(d), force=True)
    assert result["status"] == "SOURCE_EXISTS_BUT_ACCESS_BLOCKED"


def test_already_acquired_skips_without_force(tmp_path):
    mod = _load_module()
    entry = {
        "player_name": "테스트선수", "player_code": "9999", "season": 2026,
        "last_pre_cutoff_game_code": "2026080002", "expected_pre_cutoff_rounds_total": 8,
    }
    (tmp_path / "9999_last.html").write_text("x", encoding="utf-8")
    (tmp_path / "9999_full.html").write_text("x", encoding="utf-8")
    client = FakeClient()
    result = mod.acquire_player(client, entry, tmp_path, force=False)
    assert result["acquisition_status"] == "ALREADY_ACQUIRED"
