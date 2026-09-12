import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "validation_framework_v1"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_alignment_identity_and_distinct_model_universes():
    d = load("NEO_OFFICIAL_SG_EXPOSURE_ALIGNMENT_V1.json")
    assert d["counts"]["official_rows"] == 242
    assert d["counts"]["V1_matched"] == 104
    assert d["counts"]["V2B_matched"] == 105
    assert d["counts"]["duplicates"] == 0


def test_raw_gate_reproduces_frozen_values():
    d = load("NEO_EXPOSURE_CAUSAL_AUDIT_V1.json")
    assert d["raw_association"]["V1"]["rounds_vs_rank"]["spearman"] == -0.3576961802206767
    assert d["raw_association"]["V2B"]["rounds_vs_rank"]["spearman"] == -0.29729564397267816


def test_permutation_configuration_is_deterministic_and_frozen():
    d = load("NEO_EXPOSURE_CAUSAL_AUDIT_V1.json")
    assert d["permutation"]["V1"]["seed"] == 20260912
    assert d["permutation"]["V1"]["permutations"] == 1000
    assert d["permutation"]["V2B"]["seed"] == 20260912


def test_no_material_mechanical_effect_is_not_claimed_as_pass():
    d = load("NEO_EXPOSURE_CAUSAL_AUDIT_V1.json")
    assert d["classification"] == "INSUFFICIENT_EVIDENCE"
    assert d["old_gate_decision"] == "REVISE"


def test_framework_and_ledger_are_validation_only():
    f = load("NEO_VALIDATION_FRAMEWORK_V1.json")
    l = load("NEO_CALIBRATION_LEDGER_V1_SCHEMA.json")
    assert f["status"] == "READY_TO_FREEZE"
    assert l["append_only"] is True
