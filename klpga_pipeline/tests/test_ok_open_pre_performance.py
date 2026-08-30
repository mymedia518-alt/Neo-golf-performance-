import json
from datetime import date
from pathlib import Path

def test_ok_open_pre_snapshot_is_complete_and_pre_cutoff():
    root = Path(__file__).resolve().parents[1]
    entry = json.loads((root / "content/website_v2/OK_OPEN_2026_ENTRY_SNAPSHOT.json").read_text(encoding="utf-8"))
    snap = json.loads((root / "content/website_v2/OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json").read_text(encoding="utf-8"))
    plan = json.loads((root / "content/website_v2/OK_OPEN_2026_VALIDATION_PLAN.json").read_text(encoding="utf-8"))
    assert entry["game_code"] == snap["game_code"] == plan["game_code"] == "2026120001"
    assert entry["player_count"] == len(snap["profiles"]) == 120
    assert entry["duplicate_player_ids"] == []
    assert entry["unresolved_player_ids"] == []
    assert snap["future_data_excluded"] is True
    assert snap["cutoff"].startswith("2026-09-04")
    assert plan["no_composite_performance_index"] is True

def test_pre_snapshot_profiles_have_explicit_coverage_and_confidence():
    root = Path(__file__).resolve().parents[1]
    snap = json.loads((root / "content/website_v2/OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json").read_text(encoding="utf-8"))
    allowed = {"SUPPORTED", "PARTIALLY_SUPPORTED", "INSUFFICIENT", "CONTRADICTED", "UNKNOWN"}
    assert all(p["coverage"].startswith("ENTRY + ") for p in snap["profiles"])
    assert all(p["dimensions"]["level"]["confidence"] in allowed for p in snap["profiles"])
