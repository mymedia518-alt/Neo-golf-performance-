"""Tests for scripts/207_acquire_2025_prior_tournaments.py's identity
check against the real, already-captured scoreRecord pages -- confirms
the `value="<gameCode>" selected` marker this script relies on to
verify a response actually corresponds to the requested tournament."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "207_acquire_2025_prior_tournaments.py"
EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_207", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_207"] = module
    spec.loader.exec_module(module)
    return module


def test_identity_ok_true_for_all_three_real_already_captured_pages():
    mod = _load_module()
    for code in ["2023100002", "2024100009", "2025100001"]:
        html = (EVIDENCE_ROOT / f"stableford_source_probe_{code}" / f"scoreRecord_{code}.html").read_text(encoding="utf-8")
        assert mod._identity_ok(html, code) is True


def test_identity_ok_false_for_wrong_game_code():
    mod = _load_module()
    html = (EVIDENCE_ROOT / "stableford_source_probe_2025100001" / "scoreRecord_2025100001.html").read_text(encoding="utf-8")
    assert mod._identity_ok(html, "2024100009") is False


def test_identity_ok_false_for_garbage_html():
    mod = _load_module()
    assert mod._identity_ok("<html><body>not a real page</body></html>", "2025100001") is False


def test_manifest_file_is_valid_and_has_23_entries():
    import json
    manifest_path = Path(__file__).parent.parent / "content" / "website_v2" / "STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["target_game_code"] == "2025100001"
    assert len(data["entries"]) == 23
    for e in data["entries"]:
        assert e["acquisition_status"] == "NOT_YET_ACQUIRED"
        assert e["before_target_event_start"] is True
