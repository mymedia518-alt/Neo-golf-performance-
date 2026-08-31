import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"


def test_corrected_warehouse_retains_explicit_identity_states_and_exceeds_legacy():
    legacy = json.loads((CONTENT / "historical_sg_warehouse.json").read_text(encoding="utf-8"))
    corrected = json.loads((CONTENT / "historical_sg_warehouse_corrected_v2.json").read_text(encoding="utf-8"))
    assert len(corrected["records"]) > len(legacy["records"])
    assert all(r.get("identity_state") in {"RETAINED", "UNRESOLVED_IDENTITY"} for r in corrected["records"])
    assert any(r.get("identity_state") == "UNRESOLVED_IDENTITY" for r in corrected["records"])


def test_corrected_round_rows_are_not_keyed_only_to_final_survivors():
    corrected = json.loads((CONTENT / "historical_sg_warehouse_corrected_v2.json").read_text(encoding="utf-8"))
    rounds = [r for r in corrected["records"] if r.get("scope") == "single_round"]
    cumulative = [r for r in corrected["records"] if r.get("scope") == "tournament_cumulative"]
    assert len(rounds) > 23_203
    assert len(cumulative) > 6_609
    assert all("identity_state" in r for r in rounds + cumulative)


def test_corrected_sg_arithmetic_identity_holds():
    corrected = json.loads((CONTENT / "historical_sg_warehouse_corrected_v2.json").read_text(encoding="utf-8"))
    checked = [r for r in corrected["records"] if all(r.get(k) is not None for k in ("total", "off_the_tee", "approach", "around_green", "putting"))]
    assert checked
    assert all(abs(float(r["total"]) - sum(float(r[k]) for k in ("off_the_tee", "approach", "around_green", "putting"))) <= 0.03 for r in checked)
