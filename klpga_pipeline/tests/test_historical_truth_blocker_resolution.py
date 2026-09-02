from __future__ import annotations
import gzip,hashlib,json
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];C=ROOT/"content"/"website_v2"
def load(name):return json.loads((C/name).read_text(encoding="utf-8"))
def digest(name):return hashlib.sha256((C/name).read_bytes()).hexdigest()

def test_all_frozen_and_baseline_artifacts_remain_byte_identical():
    expected={"NEO_RANKING_VALIDATION_MODEL_V1.json":"0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643","HOME_PLAYER_MASTER_TOP120.json":"1b48705569e1d4ca15835e2f16d965c8465e75f18f7f7be4bf2513cfda065add","HOME_REGULAR_TOUR_PLAYER_MASTER.json":"74efaacf604cf24b30c12def16e4ff9a71c12550852743d97c417cc4e96e8d0a","NEO_RANKING_V1_REDTEAM_BACKTEST.json":"bcc5ef42a9ae34ca67e66feb9e13c07ee94fcf6e51fea351c300bd11603d52ac","NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json":"593fbbdec8c9b7480350243cbdda035816842bded7262afd3ae8baccaa27b9da"}
    assert {k:digest(k) for k in expected}==expected

def test_official_temporal_evidence_and_strict_pre_event_mapping():
    t=load("HISTORICAL_KRANKING_TEMPORAL_PROVENANCE_BLOCKER_RESOLUTION_V1.json")
    assert t["verified_week_count"]==53 and t["official_cadence_evidence"]["evidence_present"]
    assert all(r["temporal_evidence_class"]=="OFFICIAL_CADENCE_RULE" and r["source_sha256"] for r in t["records"])
    m=load("TOURNAMENT_K_WEEK_MAPPING_BLOCKER_RESOLUTION_V1.json")["records"]
    assert len(m)==82 and sum(r["mapping_status"]=="K_POINT_IN_TIME_VERIFIED" for r in m)==29
    assert all(not r["verified_publication_date"] or date.fromisoformat(r["verified_publication_date"])<date.fromisoformat(r["tournament_start_date"]) for r in m)

def test_all_official_r1_evidence_is_auditable_unique_and_identity_valid():
    d=load("HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json");raw=ROOT/"evidence"/"historical_r1_groupings_blocker_resolution_v1"
    assert len(d["records"])==82 and all(r["field_provenance"]=="VERIFIED_R1_STARTER" for r in d["records"])
    for r in d["records"]:
        assert r["duplicate_player_id_count"]==0 and r["player_count"]>0
        body=gzip.open(raw/r["raw_evidence"],"rb").read();assert hashlib.sha256(body).hexdigest()==r["response_sha256"]

def test_hard_validation_and_comparability_gate():
    truth=load("NEO_HISTORICAL_TRUTH_WAREHOUSE_BLOCKER_RESOLUTION_V1.json");v=truth["validation"]
    assert truth["record_count"]==7830 and truth["tournament_count"]==82
    assert all(x in (0,False) for x in v.values())
    cov=load("HISTORICAL_TRUTH_COVERAGE_BLOCKER_RESOLUTION_V1.json")
    assert cov["fully_comparable_tournaments"]==29 and cov["partially_comparable_tournaments"]==53
    assert all(r["eligible_for_direct_K_vs_NEO"]==(r["K_temporal_mapping_verified"] and r["R1_starter_verified"] and r["comparable_player_events"]>=2) for r in cov["records"])

def test_field_consistency_has_no_extra_sg_players_or_mapping_failures():
    a=load("HISTORICAL_FIELD_CONSISTENCY_BLOCKER_RESOLUTION_V1.json")["aggregate"]
    assert a["intersection"]==7830 and a["extra_in_SG"]==0 and a["player_mapping_failures"]==0
    f=load("HISTORICAL_FIELD_PROVENANCE_BLOCKER_RESOLUTION_V1.json")
    assert sum(x["pre_event_field_verified"] for x in f["summaries"])==1
    assert sum(x["R1_starter_verified"] for x in f["summaries"])==82

def test_benchmark_is_same_cohort_uncertainty_aware_and_not_tuned():
    b=load("K_VS_FROZEN_NEO_V1_BENCHMARK_BLOCKER_RESOLUTION_V1.json")
    assert b["status"]=="EVALUATED" and b["tournament_count"]==29 and b["comparable_player_events"]==2863 and b["same_field_and_cutoff"]
    assert all(v["bootstrap_95pct_CI"] and v["winner"] in {"K","NEO","INCONCLUSIVE"} for v in b["metrics"].values())
    assert b["incremental_predictive_information"]["status"]=="DESCRIPTIVE_ONLY"

def test_truth_output_is_deterministic():
    t=load("NEO_HISTORICAL_TRUTH_WAREHOUSE_BLOCKER_RESOLUTION_V1.json");fingerprint=t.pop("deterministic_fingerprint")
    canonical=json.dumps(t,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    assert hashlib.sha256(canonical.encode()).hexdigest()==fingerprint
