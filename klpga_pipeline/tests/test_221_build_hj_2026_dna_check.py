"""Tests for scripts/221_build_hj_2026_dna_check.py -- the separate
Three-Winner DNA explanatory layer, confirming it never touches V1's
own net_expected_value ranking and is scoped to the real HJ 2026 field
only (never a broader multi-tournament player pool)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "221_build_hj_2026_dna_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dna_221", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dna_221"] = module
    spec.loader.exec_module(module)
    return module


def test_field_scoped_to_real_hj_entrants_only():
    mod = _load_module()
    data = mod.build()
    import json
    identity = json.loads(mod.IDENTITY_PATH.read_text(encoding="utf-8"))
    hj_names = {r["player_name"] for r in identity["records"]}
    assert set(data["players"].keys()) <= hj_names
    assert data["field_n"] == len(data["players"])


def test_missing_metrics_explicitly_disclosed_not_silently_dropped():
    mod = _load_module()
    data = mod.build()
    assert set(data["missing_metrics_not_computed"]) == {
        "official_gir", "driving_distance", "sg_total", "sg_tee_to_green",
    }


def test_known_strong_players_clear_most_available_core_criteria():
    mod = _load_module()
    data = mod.build()
    for name in ("방신실", "김민솔"):
        assert name in data["players"]
        r = data["players"][name]
        assert r["core_criteria_met_count"] >= 1


def test_core_criteria_count_never_exceeds_available_metric_count():
    mod = _load_module()
    data = mod.build()
    for r in data["players"].values():
        assert r["core_criteria_met_count"] <= r["core_criteria_available_count"]
        assert r["core_criteria_available_count"] == len(mod.AVAILABLE_METRICS)
