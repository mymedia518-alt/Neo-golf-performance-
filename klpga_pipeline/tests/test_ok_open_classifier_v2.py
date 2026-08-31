import hashlib
import json
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "69_build_ok_open_classifier_v2.py"
spec = importlib.util.spec_from_file_location("classifier_v2", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_v2_preserves_original_and_all_entrants():
    source = ROOT / "content/website_v2/OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"
    raw = source.read_bytes()
    original = json.loads(raw)
    v2, diff = mod.build()
    assert len(v2["profiles"]) == 120
    assert len(diff["profiles"]) == 120
    assert v2["original_artifact_sha256"] == hashlib.sha256(raw).hexdigest()
    assert v2["PRE_TOURNAMENT_CORRECTION"] is True
    assert source.read_bytes() == raw


def test_direction_conflict_cannot_be_supported():
    p = {"player_id":"x","player_name":"x","coverage":"ENTRY + SUFFICIENT SG","windows":{
        "recent3":{"event_count":3,"components":{"total":{"mean":1.0}}},
        "recent5":{"event_count":5,"components":{"total":{"mean":1.0}}},
        "recent10":{"event_count":10,"components":{"total":{"mean":-1.0}}},
        "season2026":{"event_count":10,"components":{"total":{"mean":0.0}}},
        "multi_season":{"event_count":10,"components":{"total":{"mean":0.0,"sample_sd":1.0,"population_sd":0.95}}}}}
    q = mod.corrected_profile(p)
    assert q["direction"]["window_agreement"] == "WINDOW_CONFLICT"
    assert q["direction"]["dimension_confidence"] != "SUPPORTED"


def test_composition_confidence_is_independent_from_level():
    p = {"player_id":"x","player_name":"x","coverage":"ENTRY + SUFFICIENT SG","windows":{
        "recent3":{"event_count":3,"components":{}},
        "recent5":{"event_count":5,"components":{"total":{"mean":1.0},"approach":{"mean":2.0},"putting":{"mean":0.1}}},
        "recent10":{"event_count":10,"components":{"total":{"mean":1.0},"approach":{"mean":2.0},"putting":{"mean":0.1}}},
        "season2026":{"event_count":10,"components":{"total":{"mean":0.0},"approach":{"mean":2.0},"putting":{"mean":0.1}}},
        "multi_season":{"event_count":10,"components":{"total":{"mean":0.0,"sample_sd":1.0,"population_sd":0.95}}}}}
    q = mod.corrected_profile(p)
    assert q["level"]["dimension_confidence"] == "SUPPORTED"
    assert q["composition"]["dimension_confidence"] == "SUPPORTED"
    assert "sample_sufficiency" in q["composition"]


def test_small_sample_is_not_high_variance_label():
    p = {"player_id":"x","player_name":"x","coverage":"ENTRY + LIMITED SG","windows":{"recent3":{"event_count":1,"components":{}},"recent5":{"event_count":1,"components":{"total":{"mean":1.0}}},"recent10":{"event_count":1,"components":{"total":{"mean":1.0}}},"season2026":{"event_count":1,"components":{"total":{"mean":1.0}}},"multi_season":{"event_count":1,"components":{"total":{"mean":1.0,"sample_sd":None,"population_sd":None}}}}}
    q = mod.corrected_profile(p)
    assert q["consistency"]["materiality_evidence"] == "INSUFFICIENT"
