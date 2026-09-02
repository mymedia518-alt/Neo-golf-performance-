from __future__ import annotations

import copy

from klpga.website_v2.neo_ranking_backtest import run_backtest

CONFIG={"model_id":"neo-ranking-validation-v1","eligibility":{"minimum_sg_events":2},"features":{"recent_5_sg":{"weight":.35},"recent_10_sg":{"weight":.25},"long_term_sg":{"weight":.25},"consistency":{"weight":.10},"sample_reliability":{"weight":.05}}}

def corpus():
    dates={f"E{i}":f"2026-{i:02d}-01" for i in range(1,5)}; records=[]; outcomes={}
    for i,event in enumerate(dates,1):
        for p in ("P1","P2","P3"):
            records.append({"game_code":event,"player_id":p,"identity_state":"RETAINED","rounds":4,"total":float(i if p=="P1" else -i if p=="P2" else 0)})
            outcomes[(event,p)]={"finish_position_numeric":{"P1":1,"P2":3,"P3":2}[p],"made_cut":p!="P2","withdrawn":False,"disqualified":False}
    return {"records":records},dates,outcomes

def test_no_future_or_target_data_enters_features_and_hard_contracts_pass():
    warehouse,dates,outcomes=corpus(); result=run_backtest(warehouse,dates,outcomes,CONFIG)
    assert result["validation"]=={"future_leakage_count":0,"duplicate_event_player_count":0,"invalid_player_mapping_count":0,"insufficient_sample_ranked_count":0}
    assert all(row["max_feature_date"] < row["target_start_date"] for row in result["observations"])

def test_future_canary_does_not_change_earlier_target_scores():
    warehouse,dates,outcomes=corpus(); baseline=run_backtest(warehouse,dates,outcomes,CONFIG)
    changed=copy.deepcopy(warehouse); changed["records"].append({"game_code":"E4","player_id":"P1","identity_state":"RETAINED","rounds":4,"total":999999.0})
    replay=run_backtest(changed,dates,outcomes,CONFIG)
    before=lambda r:[(x["event"],x["player_id"],x["neo_score"]) for x in r["observations"] if x["event"]=="E3"]
    assert before(baseline)==before(replay)

def test_deterministic_reproducibility_and_no_forced_insufficient_rank():
    args=corpus(); first=run_backtest(*args,CONFIG); second=run_backtest(*args,CONFIG)
    assert first["deterministic_fingerprint"]==second["deterministic_fingerprint"]
    assert all(row["prior_sample_count"]>=2 for row in first["observations"])
