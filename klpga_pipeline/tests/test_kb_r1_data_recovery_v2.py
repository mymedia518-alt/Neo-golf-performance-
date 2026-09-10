"""NEO GOLF DATA -- KB R1 DATA RECOVERY -> MODEL -> PRODUCTION DEPLOYMENT,
Phase 1-3.

Locks in the real, verified finding: HISTORICAL_R1_GROUPING_EVIDENCE_
BLOCKER_RESOLUTION_V1.json (backed by 82 archived official KLPGA
grouping/tee-time HTML captures) gives genuine, unbiased full-field R1
PARTICIPATION for all 82 historical tournaments -- but carries no score
field, so it cannot resolve the actual R1-model blocker (missing R1
PERFORMANCE for cut-missers). historical_sg_warehouse.json's survivor
bias is proven unchanged. Live re-collection from klpga.co.kr is
proven still network-blocked at the time of this task. Final status:
DATA_RECOVERY_BLOCKED. These tests guard against a future change
silently fabricating scores into the participation data, silently
modifying historical_sg_warehouse.json, or claiming a live
recollection/deployment that did not happen.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026090003"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _recovery() -> dict:
    return _load(f"KB_{GAME_CODE}_R1_DATA_RECOVERY_V2.json")


def test_final_status_is_data_recovery_blocked():
    assert _recovery()["final_status"] == "DATA_RECOVERY_BLOCKED"


def test_grouping_evidence_covers_all_82_historical_tournaments():
    tw = _load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    grp = _load("HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json")
    tw_gc = {r["game_code"] for r in tw["records"]}
    grp_gc = {r["game_code"] for r in grp["records"]}
    assert len(grp["records"]) == 82
    assert tw_gc == grp_gc


def test_grouping_records_have_no_score_field():
    """Direct proof the participation source cannot substitute for R1
    performance -- not merely asserted."""
    grp = _load("HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json")
    for record in grp["records"][:5]:
        for player in record["players"]:
            for forbidden in ("score", "to_par", "rank", "r1_score", "r1_to_par", "r1_rank"):
                assert forbidden not in player, f"unexpected score-like field {forbidden!r} in grouping player row"
            assert set(player.keys()) == {"player_id", "player_name", "starting_tee", "tee_time"}


def test_grouping_field_provenance_is_verified_r1_starter_not_sg_reconstructed():
    grp = _load("HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json")
    for record in grp["records"]:
        assert record["field_provenance"] == "VERIFIED_R1_STARTER"


def test_archived_grouping_html_captures_exist_for_every_record():
    grp = _load("HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json")
    evidence_dir = ROOT / "evidence" / "historical_r1_groupings_blocker_resolution_v1"
    for record in grp["records"]:
        path = evidence_dir / record["raw_evidence"]
        assert path.exists(), f"missing archived capture for {record['game_code']}"


def test_survivor_bias_in_sg_warehouse_is_unchanged():
    """Re-derive the exact contingency numbers from
    KB_2026090003_R1_MODEL_V1_RESEARCH_V1.json to prove
    historical_sg_warehouse.json was not touched by this task."""
    tw = _load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    wh = _load("historical_sg_warehouse.json")
    r1_index = {
        (r["game_code"], r["player_id"])
        for r in wh["records"]
        if r.get("scope") == "single_round" and r.get("round") == 1
    }
    cut_true = [r for r in tw["records"] if r["outcome"]["made_cut"]]
    cut_false = [r for r in tw["records"] if not r["outcome"]["made_cut"]]
    cut_true_matched = sum(1 for r in cut_true if (r["game_code"], r["player_id"]) in r1_index)
    cut_false_matched = sum(1 for r in cut_false if (r["game_code"], r["player_id"]) in r1_index)
    assert cut_true_matched == len(cut_true) == 4687
    assert cut_false_matched == 68
    assert len(cut_false) == 3143


def test_no_score_was_fabricated_into_the_grouping_or_sg_sources():
    grp_sha = hashlib.sha256(
        (CONTENT / "HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json").read_bytes()
    ).hexdigest()
    wh_sha = hashlib.sha256((CONTENT / "historical_sg_warehouse.json").read_bytes()).hexdigest()
    assert grp_sha == _recovery()["phase1_recovery_attempt"]["source_found"]["sha256"]
    # historical_sg_warehouse.json is not re-hashed inside the recovery
    # artifact (it was never opened for writing) -- git diff proves it.
    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--", "content/website_v2/historical_sg_warehouse.json"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == ""
    assert wh_sha  # sanity: file still readable


def test_no_full_field_r1_score_warehouse_was_created():
    """Phase 2 was deliberately NOT materialized past participation --
    guard against a future change quietly fabricating one."""
    for pattern in ("*R1_FULL_FIELD_WAREHOUSE*.json", "*R1_PERFORMANCE_WAREHOUSE*.json"):
        assert list(CONTENT.glob(pattern)) == []


def test_no_neo_r1_model_v1_was_frozen():
    for pattern in ("NEO_R1_MODEL_V1*.json", "*R1_MODEL_V1_FROZEN*.json"):
        assert list(CONTENT.glob(pattern)) == []


def test_no_kb_r1_predictions_or_page_were_created():
    assert not (CONTENT / f"{GAME_CODE}_R1_5PROB_FROZEN.json").exists()
    assert not (ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1").exists()


def test_pre_frozen_artifact_still_byte_identical():
    actual_sha = hashlib.sha256(
        (CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()
    ).hexdigest()
    expected = "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"
    assert actual_sha == expected
    integrity = _recovery()["pre_frozen_artifact_integrity"]
    assert integrity["sha256_before_this_task"] == integrity["sha256_after_this_task"] == expected


def test_production_reference_unchanged():
    prod = _recovery()["production_untouched"]
    assert prod["branch"] == "neo-website-v2"
    assert prod["commit"] == "15d43a6a5a65f166d38fcf242453cba22f67af1d"
    assert prod["modified_by_this_task"] is False
