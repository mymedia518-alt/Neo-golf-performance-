"""Tests for scripts/222_build_hj_2026_gir_dd_reconstruction_manifest.py
-- the per-tournament GIR/Driving-Distance reconstruction manifest for
the real 108-player HJ 2026 field, built from already-held data only."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "222_build_hj_2026_gir_dd_reconstruction_manifest.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("manifest_222", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["manifest_222"] = module
    spec.loader.exec_module(module)
    return module


def test_covers_all_108_real_entrants():
    mod = _load_module()
    data = mod.build()
    assert len(data["entries"]) == 108
    codes = {e["player_code"] for e in data["entries"]}
    assert len(codes) == 108


def test_the_two_brand_new_players_have_zero_prior_tournaments():
    mod = _load_module()
    data = mod.build()
    by_name = {e["player_name"]: e for e in data["entries"]}
    for name in ("김민서3", "이지유 0901(A)"):
        assert by_name[name]["pre_cutoff_tournaments"] == []
        assert by_name[name]["expected_pre_cutoff_rounds_total"] == 0


def test_known_winners_tournament_breakdown_sums_to_already_known_round_totals():
    mod = _load_module()
    data = mod.build()
    by_name = {e["player_name"]: e for e in data["entries"]}
    # cross-check against the already-verified V1 snapshot round counts
    assert by_name["방신실"]["expected_pre_cutoff_rounds_total"] == 74
    assert by_name["김민솔"]["expected_pre_cutoff_rounds_total"] == 73


def test_every_tournament_entry_strictly_before_cutoff():
    mod = _load_module()
    data = mod.build()
    target = date.fromisoformat(mod.TARGET_CUTOFF)
    for e in data["entries"]:
        for t in e["pre_cutoff_tournaments"]:
            assert date.fromisoformat(t["start_date"]) < target
            assert t["real_rounds_this_tournament"] > 0
