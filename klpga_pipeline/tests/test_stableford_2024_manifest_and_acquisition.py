"""Tests for the 2024 replication's manifest + acquisition script
identity check -- mirrors
test_stableford_prior_tournament_manifest.py and
test_207_acquire_2025_prior_tournaments.py for the 2025 run."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

from klpga.website_v2.stableford_historical_dates import HISTORICAL_EVENT_DATES
from klpga.website_v2.stableford_prior_tournament_manifest import build_manifest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "208_acquire_2024_prior_tournaments.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("acquire_208", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_208"] = module
    spec.loader.exec_module(module)
    return module


def test_2024_manifest_has_23_bounded_prior_tournaments_all_before_target():
    target = HISTORICAL_EVENT_DATES["2024100009"].event_start_date
    assert target == date(2024, 10, 10)
    manifest = build_manifest("2024100009", target)
    assert len(manifest) == 23
    for e in manifest:
        y, m, d = map(int, e.start_date.split("-"))
        assert date(y, m, d) < target
    assert "2024100009" not in {e.game_code for e in manifest}


def test_manifest_file_is_valid_and_matches_live_build():
    import json
    manifest_path = Path(__file__).parent.parent / "content" / "website_v2" / "STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["target_game_code"] == "2024100009"
    assert len(data["entries"]) == 23
    for e in data["entries"]:
        assert e["acquisition_status"] == "NOT_YET_ACQUIRED"
        assert e["before_target_event_start"] is True


def test_208_identity_check_true_for_real_2024100009_capture():
    mod = _load_script_module()
    html = (
        Path(__file__).parent.parent
        / "evidence" / "stableford_source_probe_2024100009" / "scoreRecord_2024100009.html"
    ).read_text(encoding="utf-8")
    assert mod._identity_ok(html, "2024100009") is True


def test_208_identity_check_false_for_wrong_game_code():
    mod = _load_script_module()
    html = (
        Path(__file__).parent.parent
        / "evidence" / "stableford_source_probe_2024100009" / "scoreRecord_2024100009.html"
    ).read_text(encoding="utf-8")
    assert mod._identity_ok(html, "2025100001") is False
