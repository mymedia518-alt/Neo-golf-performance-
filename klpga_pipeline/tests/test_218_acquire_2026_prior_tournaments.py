"""Tests for scripts/218_acquire_2026_prior_tournaments.py -- the
identity check against real already-captured scoreRecord pages (same
pattern as test_207_acquire_2025_prior_tournaments.py), plus the
acquire_one orchestration logic against a fake client (no real
network)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "218_acquire_2026_prior_tournaments.py"
EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_218", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_218"] = module
    spec.loader.exec_module(module)
    return module


def test_identity_ok_true_for_a_real_already_captured_2025_page():
    # reuses the same already-real, already-SOURCE_PASS-verified capture
    # from the 2025 acquisition -- _identity_ok's regex logic is
    # identical across scripts 207/208/209/218, so this is a real check
    # of the actual function, not a copy-pasted assumption.
    mod = _load_module()
    html = (EVIDENCE_ROOT / "stableford_source_probe_2025100001" / "scoreRecord_2025100001.html").read_text(encoding="utf-8")
    assert mod._identity_ok(html, "2025100001") is True
    assert mod._identity_ok(html, "2024100009") is False


def test_identity_ok_false_for_garbage_html():
    mod = _load_module()
    assert mod._identity_ok("<html><body>not a real page</body></html>", "2026030001") is False


def test_manifest_file_is_valid_and_has_24_entries():
    manifest_path = Path(__file__).parent.parent / "content" / "website_v2" / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["target_game_code"] == "2026100004"
    assert data["target_start_date"] == "2026-10-08"
    assert len(data["entries"]) == 24


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeClient:
    def __init__(self, html_by_code: dict[str, str]):
        self.html_by_code = html_by_code
        self.calls: list[str] = []

    def get_text_with_status(self, url, params=None):
        code = params["gameCode"]
        self.calls.append(code)
        if code not in self.html_by_code:
            raise ConnectionError(f"simulated fetch failure for {code}")
        return (200, self.html_by_code[code])


REAL_2025100001_HTML = (
    EVIDENCE_ROOT / "stableford_source_probe_2025100001" / "scoreRecord_2025100001.html"
).read_text(encoding="utf-8")


def test_acquire_one_source_pass_on_real_matching_capture(tmp_path):
    mod = _load_module()
    mod.OUT_DIR = tmp_path  # redirect output for this test
    client = FakeClient({"2025100001": REAL_2025100001_HTML})
    entry = {"game_code": "2025100001", "tournament_name": "test", "start_date": "2025-01-01"}
    result = mod.acquire_one(client, entry, force=False)
    assert result["acquisition_status"] == "ACQUIRED"
    assert result["source_pass_fail"] == "SOURCE_PASS"
    assert (tmp_path / "2025100001_scoreRecord.html").exists()


def test_acquire_one_source_fail_on_wrong_game_code_response(tmp_path):
    mod = _load_module()
    mod.OUT_DIR = tmp_path
    client = FakeClient({"2026030001": REAL_2025100001_HTML})  # real HTML but for the WRONG gameCode
    entry = {"game_code": "2026030001", "tournament_name": "test", "start_date": "2026-03-12"}
    result = mod.acquire_one(client, entry, force=False)
    assert result["acquisition_status"] == "ACQUISITION_FAILED"
    assert result["source_pass_fail"] == "SOURCE_FAIL"


def test_acquire_one_skips_when_already_valid(tmp_path):
    mod = _load_module()
    mod.OUT_DIR = tmp_path
    out_path = tmp_path / "2025100001_scoreRecord.html"
    out_path.write_text(REAL_2025100001_HTML, encoding="utf-8")
    client = FakeClient({})  # would raise if actually called
    entry = {"game_code": "2025100001", "tournament_name": "test", "start_date": "2025-01-01"}
    result = mod.acquire_one(client, entry, force=False)
    assert result["acquisition_status"] == "ALREADY_ACQUIRED"
    assert client.calls == []


def test_acquire_one_fetch_failure_recorded_not_raised(tmp_path):
    mod = _load_module()
    mod.OUT_DIR = tmp_path
    client = FakeClient({})
    entry = {"game_code": "2026030001", "tournament_name": "test", "start_date": "2026-03-12"}
    result = mod.acquire_one(client, entry, force=False)
    assert result["acquisition_status"] == "ACQUISITION_FAILED"
    assert "error" in result
