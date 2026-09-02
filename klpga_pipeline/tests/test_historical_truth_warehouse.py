from __future__ import annotations
import gzip,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];C=ROOT/"content"/"website_v2"
def load(name):return json.loads((C/name).read_text(encoding="utf-8"))
def digest(name):return hashlib.sha256((C/name).read_bytes()).hexdigest()

def test_frozen_baselines_are_byte_identical_to_locked_commits():
    assert digest("NEO_RANKING_VALIDATION_MODEL_V1.json")=="0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643"
    assert digest("HOME_PLAYER_MASTER_TOP120.json")=="1b48705569e1d4ca15835e2f16d965c8465e75f18f7f7be4bf2513cfda065add"
    assert digest("HOME_REGULAR_TOUR_PLAYER_MASTER.json")=="74efaacf604cf24b30c12def16e4ff9a71c12550852743d97c417cc4e96e8d0a"

def test_representative_official_week_probe_distinguishes_history_and_fallback():
    audit=load("HISTORICAL_KRANKING_RECOVERY_AUDIT_V1.json")
    for week in ("202630","202620","202535"):
        verified=[p for p in audit["probes"] if p["requested_week"]==week and p["classification"]=="VERIFIED_HISTORICAL"]
        assert verified and all(p["selected_week"]==week and p["differs_from_current_w35"] for p in verified)
    assert not [p for p in audit["probes"] if p["requested_week"]=="202435" and p["classification"]=="VERIFIED_HISTORICAL"]
    assert any(p["classification"]=="CURRENT_FALLBACK" for p in audit["probes"])

def test_all_preserved_weekly_snapshots_are_selected_complete_and_auditable():
    index=load("HISTORICAL_KRANKING_SNAPSHOT_INDEX_V1.json");raw=ROOT/"evidence"/"historical_kranking_snapshots_v1"
    assert index["verified_week_count"]==53
    for snap in index["snapshots"]:
        assert snap["classification"]=="VERIFIED_HISTORICAL" and snap["returned_week"]==snap["requested_week"]
        assert snap["player_count"]>=120 and snap["response_sha256"]
        ranks=[r["rank"] for r in snap["records"]]
        assert ranks==sorted(ranks) and snap["official_rank_tie_count"]==len(ranks)-len(set(ranks))
        assert snap["duplicate_player_id_count"]==0
        body=gzip.open(raw/snap["raw_evidence"],"rb").read();assert hashlib.sha256(body).hexdigest()==snap["response_sha256"]

def test_tournament_mapping_never_infers_unverified_publication_dates():
    mapping=load("TOURNAMENT_K_WEEK_MAPPING_V1.json");assert len(mapping["records"])==82
    assert all(r["status"]=="K_TEMPORAL_MAPPING_UNVERIFIED" and r["latest_available_pre_event_K_week"] is None and r["K_ranking_publication_date"] is None and r["temporal_gap_days"] is None for r in mapping["records"])

def test_truth_warehouse_hard_invariants_and_missing_values_are_not_fabricated():
    truth=load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json");assert truth["tournament_count"]==82 and truth["record_count"]==7830
    v=truth["validation"]
    assert v=={"future_leakage_count":0,"K_snapshot_after_start_count":0,"silent_current_W35_substitution_count":0,"duplicate_tournament_player_count":0,"duplicate_K_rank_count":0,"invalid_player_mapping_count":0,"fabricated_K_rank_count":0,"fabricated_entry_status_count":0,"frozen_V1_config_changed":False,"insufficient_sample_force_ranked_count":0}
    assert all(r["pre_event_truth"]["K_rank"] is None and r["pre_event_truth"]["K_status"]=="K_TEMPORAL_MAPPING_UNVERIFIED" for r in truth["records"])
    assert all(r["frozen_model"]["V1_max_feature_date"]<r["tournament_start_date"] for r in truth["records"])

def test_field_provenance_and_coverage_are_explicit():
    fields=load("HISTORICAL_FIELD_PROVENANCE_V1.json");coverage=load("HISTORICAL_TRUTH_COVERAGE_V1.json")
    assert len(fields["summaries"])==coverage["total_tournaments"]==82
    assert sum(r["pre_event_field_verified"] for r in fields["summaries"])==1
    assert {r["field_provenance"] for r in fields["summaries"]}<={"VERIFIED_PRE_EVENT_ENTRY","SG_ROW_RECONSTRUCTED"}
    assert all(r["entry_status"] is None and r["entry_status_reason"] for r in fields["records"])
    assert coverage["fully_verified_tournaments"]==0 and coverage["partially_verified_tournaments"]==82

def test_direct_benchmark_and_divergence_are_blocked_not_fabricated():
    benchmark=load("K_VS_NEO_V1_BENCHMARK_V1.json")
    assert benchmark["status"]=="NOT_EVALUABLE" and benchmark["directly_comparable_tournaments"]==0 and benchmark["comparable_player_events"]==0
    assert "rank divergence" in benchmark["inconclusive_metrics"]

def test_truth_artifact_fingerprint_is_reproducible():
    truth=load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json");fingerprint=truth.pop("deterministic_fingerprint")
    canonical=json.dumps(truth,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    assert hashlib.sha256(canonical.encode()).hexdigest()==fingerprint
