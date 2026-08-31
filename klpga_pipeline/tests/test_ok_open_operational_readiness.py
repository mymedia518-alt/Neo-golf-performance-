import json
from pathlib import Path
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "70_ok_open_operational_readiness.py"
spec = importlib.util.spec_from_file_location("readiness", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_readiness_artifact_is_54_hole_and_zero_manual_changes():
    mod.main()
    doc = json.loads((ROOT / "content/website_v2/OK_OPEN_2026_OPERATIONAL_READINESS.json").read_text(encoding="utf-8"))
    assert doc["tournament"]["game_code"] == "2026120001"
    assert doc["tournament"]["holes"] == 54
    assert doc["lifecycle"]["public_stages"] == ["PRE", "R1", "R2", "FINAL"]
    assert doc["lifecycle"]["no_r4"] is True
    assert doc["dry_run"]["tournament_specific_code_changes"] == 0
    assert doc["dry_run"]["manual_intervention_count"] == 0
    assert doc["pre_forecast_readiness"]["ready"] is True


def test_failure_recovery_never_advances_incomplete_core_data():
    doc = json.loads((ROOT / "content/website_v2/OK_OPEN_2026_OPERATIONAL_READINESS.json").read_text(encoding="utf-8"))
    recovery = doc["failure_recovery"]
    assert recovery["partial_leaderboard"] == "WAIT"
    assert recovery["missing_player_identity"] == "HARD STOP"
    assert recovery["round_incomplete"] == "WAIT"
    assert recovery["format_mismatch"] == "HARD STOP"
    assert recovery["sg_unavailable"].startswith("SAFE CONTINUE")
