import json
from pathlib import Path
from klpga.analytics.sg_performance import (normalize_sg_records, validate_sg_records,
    sg_window_summary, compute_sg_windows, sg_trend, build_player_performance_profile)

def rows():
    return [{"player_id":"p","season":2026,"game_code":f"g{i}","date":f"2026-0{i+1}-01","scope":"tournament_cumulative","total":i+1,"tee_to_green":None,"off_the_tee":0.1*i,"approach":0.2*i,"around_green":None,"putting":0.3*i} for i in range(5)]

def test_missing_components_remain_null_and_identity_validates():
    r=normalize_sg_records(rows()); assert r[0]["tee_to_green"] is None; assert validate_sg_records(r)["valid"]

def test_duplicate_identity_is_rejected():
    r=normalize_sg_records(rows()+[rows()[0]]); assert not validate_sg_records(r)["valid"]

def test_recent_windows_and_season_are_distinct():
    r=normalize_sg_records(rows()); assert sg_window_summary(r,"p",window=5)["event_count"]==5; assert compute_sg_windows(r,"p")["recent5"]["event_count"]==5

def test_trend_threshold_and_sample_sufficiency_are_deterministic():
    r=compute_sg_windows(normalize_sg_records(rows()),"p"); t=sg_trend(r["recent5"],r["season"]); assert t["total"]["state"] in {"비슷한 흐름","최근 상승","최근 하락","표본 부족"}
    assert sg_trend({"components":{"total":{"mean":1,"sample_count":1}}},{"components":{"total":{"mean":0,"sample_count":5}}})["total"]["state"]=="표본 부족"

def test_profile_keeps_model_separate():
    p=build_player_performance_profile(player_id="p",player_name="P",sg_records=normalize_sg_records(rows()),recent_form={"recent5":-1},consistency={"value":0.4})
    assert p["sg"]["season"]["components"]["total"]["sample_count"]==5; assert p["forecast_model_inputs"]==[]

def test_canonical_historical_series_has_official_scope_and_coverage():
    root=Path(__file__).resolve().parents[1]; d=json.loads((root/"content/website_v2/historical_sg_series.json").read_text(encoding="utf-8"))
    assert d["validation"]["valid"] and len(d["records"])==467
    assert {r["scope"] for r in d["records"]}=={"tournament_cumulative","single_round"}
    assert all(r["source"].startswith("https://klpga.co.kr/") for r in d["records"])

def test_multi_event_warehouse_has_real_multi_season_coverage():
    root=Path(__file__).resolve().parents[1]; p=root/"content/website_v2/historical_sg_warehouse.json"
    assert p.exists(); d=json.loads(p.read_text(encoding="utf-8")); rows=d["records"]
    assert d["events"] >= 10 and len(set(r["season"] for r in rows)) >= 2
    assert len(set(r["game_code"] for r in rows)) == d["events"]
    assert all(r.get("player_id") and r.get("source","").startswith("https://klpga.co.kr/") for r in rows)
    assert any(r["scope"]=="single_round" and r["round"] in (1,2,3,4) for r in rows)

def test_warehouse_audit_does_not_equate_no_rows_with_parser_failure():
    root=Path(__file__).resolve().parents[1]; d=json.loads((root/"content/website_v2/sg_warehouse_audit.json").read_text(encoding="utf-8"))
    assert d["events_attempted"]==49 and d["events_with_sg"]==48 and d["events_without_sg"]==1
    assert d["no_row_reason_breakdown"].get("OFFICIAL_SG_NOT_AVAILABLE")==1
