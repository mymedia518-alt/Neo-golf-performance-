"""Tests for scripts/224_build_hj_2026_sg_profile.py -- real 2026
season-to-date SG Total/Tee-to-Green for the HJ field, reusing the
already-validated simple-mean-across-tournaments rule, against the
real already-committed SG warehouse."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "224_build_hj_2026_sg_profile.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sg_224", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sg_224"] = module
    spec.loader.exec_module(module)
    return module


def test_field_scoped_to_108_real_entrants():
    mod = _load_module()
    data = mod.build()
    assert data["field_n"] == 108
    assert len(data["players"]) == 108


def test_exactly_two_tournaments_missing_from_warehouse():
    mod = _load_module()
    data = mod.build()
    assert data["game_codes_missing_from_warehouse"] == ["2026090002", "2026120001"]
    assert data["eligible_game_codes_count"] == 24
    assert len(data["game_codes_covered_in_warehouse"]) == 22


def test_target_event_never_in_warehouse_coverage():
    mod = _load_module()
    data = mod.build()
    assert "2026100004" not in data["game_codes_covered_in_warehouse"]


def test_no_sg_data_players_get_none_never_a_fabricated_zero():
    mod = _load_module()
    data = mod.build()
    for p in data["players"].values():
        if p["data_status"] == "DATA_LIMITED_NO_SG_DATA":
            assert p["sg_total_mean"] is None
            assert p["sg_tee_to_green_mean"] is None
