"""Tests for scripts/223_acquire_hj_2026_gir_dd.py -- confirms it
correctly reuses scripts/213's pre-flight pilot and per-player
reconstruction functions unchanged, against the real HJ 2026
manifest, using a fake client (no real network)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "223_acquire_hj_2026_gir_dd.py"
REAL_FIXTURE = (
    Path(__file__).parent / "fixtures" / "official_detail" / "8436_publicRecordSeasonDetail.html"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_223", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_223"] = module
    spec.loader.exec_module(module)
    return module


def test_loads_script_213_functions_unchanged():
    mod = _load_module()
    mod213 = mod._load_script_213()
    assert hasattr(mod213, "run_preflight_pilot")
    assert hasattr(mod213, "acquire_and_reconstruct_player")


def test_manifest_file_covers_all_108_real_entrants():
    import json
    manifest_path = Path(__file__).parent.parent / "content" / "website_v2" / "HJ_2026100004_GIR_DD_RECONSTRUCTION_MANIFEST_V1.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["game_code"] == "2026100004"
    assert data["target_cutoff"] == "2026-10-08"
    assert len(data["entries"]) == 108


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeClient:
    """Real-fixture-derived response for every call -- enough to
    exercise the pilot + per-player reconstruction wiring without a
    real network call."""

    def __init__(self):
        self.text = REAL_FIXTURE.read_text(encoding="utf-8")

    def _throttle(self, host):
        pass

    def _do_request(self, method, url, **kwargs):
        return FakeResponse(200, self.text)


def test_acquire_one_player_via_reused_213_function(tmp_path):
    mod = _load_module()
    mod213 = mod._load_script_213()
    entry = {
        "player_name": "테스트선수", "player_code": "8436", "season": 2026,
        "pre_cutoff_tournaments": [
            {"game_code": "2026080002", "start_date": "2026-08-01", "real_rounds_this_tournament": 8},
        ],
        "expected_pre_cutoff_rounds_total": 8,
    }
    client = FakeClient()
    result = mod213.acquire_and_reconstruct_player(client, entry, save_html=False, out_dir=tmp_path)
    assert result["n_tournaments_gate_passed"] == 1
    assert result["reconstructed"]["driving_distance"]["value"] == 238.308
