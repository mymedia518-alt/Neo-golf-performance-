"""NEO KB MODEL VALIDATION -- SG FORENSIC / PRE PROBABILITY PUBLICATION
GATE V1.

Regression coverage for the invariants this audit discovered and the
durable evidence artifacts it produced. This is a validation-only
task: no SG/model/ranking formula or weight was changed, and none of
these tests assert a formula should change either -- they lock in the
CURRENT, evidence-backed BLOCKED state so a future change to any of
these contracts is deliberate (a test update), never silent.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def test_kb_pre_input_freeze_artifact_exists_and_references_real_files():
    doc = _load("KB_2026090003_PRE_INPUT_FREEZE_V1.json")
    assert doc["game_code"] == "2026090003"
    assert doc["hard_fail_check"]["result"].startswith("PASS")
    for name in doc["frozen_input_artifacts"]:
        assert (CONTENT / name).is_file(), f"freeze references a missing artifact: {name}"


def test_kb_pre_input_freeze_confirms_no_r1_artifact_exists_for_kb():
    """The freeze's own r1-absence evidence must stay internally
    consistent with the real filesystem: KB's registered stage-state
    filename must not (yet) exist, and no r1/live/snapshot-named file
    for game_code 2026090003 may exist -- once a real R1 IS collected
    this test is EXPECTED to start failing, which is the correct
    signal that a new R1 checkpoint (never overwriting this PRE
    freeze) is due, per NEO_FUTURE_ROUND_CONTRACT_V1.json."""
    doc = _load("KB_2026090003_PRE_INPUT_FREEZE_V1.json")
    assert doc["r1_result_absence_evidence"]["claim"].startswith("No KB R1")
    stage_state = CONTENT / "2026090003_STAGE_STATE.json"
    assert not stage_state.is_file(), (
        "2026090003_STAGE_STATE.json now exists -- KB_2026090003_PRE_INPUT_FREEZE_V1.json's "
        "r1-absence evidence is stale. Do not silently update the freeze file: create a new, "
        "separate R1 checkpoint artifact per NEO_FUTURE_ROUND_CONTRACT_V1.json instead."
    )


def test_sg_warehouse_total_is_a_per_round_average_not_a_sum():
    """Locks in the NEO_SG_FORENSIC_AUDIT_V1.json Section 1a finding:
    tournament_cumulative's `total` is the MEAN of the per-round
    single_round totals, not their sum. A future change to the
    warehouse-building pipeline that turns `total` into a true summed
    cumulative value would silently invalidate every recent_5_sg/
    recent_10_sg figure this project publishes -- this test spot-checks
    one real, already-verified example so such a change cannot land
    unnoticed."""
    warehouse = json.loads((CONTENT / "historical_sg_warehouse_corrected.json").read_text(encoding="utf-8"))
    singles = {}
    cumulative = None
    for row in warehouse["records"]:
        if row.get("player_id") != "9784" or row.get("game_code") != "2025040001":
            continue
        if row.get("scope") == "single_round":
            singles[row["round"]] = row["total"]
        elif row.get("scope") == "tournament_cumulative":
            cumulative = row["total"]
    assert cumulative is not None and len(singles) == 4, "fixture example not found in warehouse -- audit sample may be stale"
    mean_of_singles = sum(singles[r] for r in (1, 2, 3, 4)) / 4
    assert abs(mean_of_singles - cumulative) < 0.02, (
        f"tournament_cumulative total ({cumulative}) no longer matches the mean of this "
        f"player's 4 single-round totals ({mean_of_singles}) -- the SG_TOTAL_DEFINITION "
        "conclusion in NEO_SG_FORENSIC_AUDIT_V1.json (Section 1a) needs re-auditing."
    )


def test_neo_ranking_v1_config_still_matches_its_own_redteam_reject_verdict():
    config = _load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    assert config["publication_class"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    assert config["weight_status"] == "HEURISTIC_FOR_EVALUATION_NOT_FITTED_OR_APPROVED"
    # Weights are recorded here only to prove this test does not silently
    # tolerate a retune -- NOT to assert they are correct or approved.
    weights = {k: v["weight"] for k, v in config["features"].items()}
    assert weights == {
        "recent_5_sg": 0.35, "recent_10_sg": 0.25, "long_term_sg": 0.25,
        "consistency": 0.10, "sample_reliability": 0.05,
    }


def test_pre_probability_fields_beyond_win_remain_unimplemented_for_every_registered_tournament():
    """CUT/TOP20/TOP10/TOP5 have no implementation anywhere in this
    codebase (NEO_PRE_PROBABILITY_MODEL_AUDIT_V1.json, Section 5). This
    guards against one silently appearing in a *_PRE_PUBLIC_MASTER.json
    record without a corresponding publication-gate decision being
    updated in NEO_PUBLICATION_GATES_V1.json first."""
    checked_any = False
    for path in CONTENT.glob("*_PRE_PUBLIC_MASTER.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for record in doc.get("records", []):
            checked_any = True
            for field in ("cut_probability", "top20_probability", "top10_probability", "top5_probability"):
                assert record.get(field) is None, (
                    f"{path.name} record for player_id={record.get('player_id')} has a non-null "
                    f"{field} -- NEO_PUBLICATION_GATES_V1.json's corresponding gate must be "
                    "re-evaluated with real evidence before this can ship, per this task's "
                    "'No PASS by convenience' rule."
                )
    assert checked_any, "no *_PRE_PUBLIC_MASTER.json files found to check"


def test_publication_gates_artifact_has_all_seven_gates_blocked_with_evidence():
    doc = _load("NEO_PUBLICATION_GATES_V1.json")
    expected = {"A_NEO_PERFORMANCE", "B_NEO_RANKING", "C_PRE_CUT_PROBABILITY", "D_PRE_TOP20", "E_PRE_TOP10", "F_PRE_TOP5", "G_PRE_WIN"}
    assert set(doc["gates"]) == expected
    for key, gate in doc["gates"].items():
        assert gate["status"] == "BLOCKED", f"{key} is not BLOCKED"
        assert gate["evidence_artifact"], f"{key} has no evidence_artifact recorded"
        assert gate["reason"], f"{key} has no reason recorded"
    assert doc["global_verdict"].startswith("NO PASS")


def test_kb_pre_forecast_is_blocked_and_no_frozen_forecast_was_created():
    doc = _load("KB_2026090003_PRE_FORECAST_STATUS.json")
    assert doc["KB_PRE_FORECAST_STATUS"] == "BLOCKED_MODEL_NOT_APPROVED"
    assert doc["no_frozen_forecast_created"] is True
    assert not (CONTENT / "KB_2026090003_PRE_FORECAST_FROZEN_V1.json").is_file(), (
        "a frozen KB PRE forecast exists despite every probability publication gate being BLOCKED"
    )


def test_neo_performance_band_confirmed_independent_of_neo_ranking_v1_formula():
    """Locks in the NEO_PERFORMANCE_LINEAGE_AUDIT_V1.json Section 3
    finding that NEO 경기력 (the public band) does not read
    validation_score/neo_validation_rank from top120_validation.py --
    if a future change wires them together, this test's own source
    reference should be re-audited before assuming the two metrics can
    share a publication decision."""
    doc = _load("NEO_PERFORMANCE_LINEAGE_AUDIT_V1.json")
    assert doc["dependency_on_neo_ranking_v1"]["verdict"] == "INDEPENDENT -- confirmed no code-level dependency."
    source = (ROOT / "scripts" / "79_rebuild_corrected_sg_downstream.py").read_text(encoding="utf-8")
    assert "neo_validation_rank" not in source
    assert "validation_score" not in source
