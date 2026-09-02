"""Leakage-safe historical evaluation of frozen NEO Ranking V1.

Every feature is computed from SG events whose official tournament start date
is strictly earlier than the target start date.  Target outcomes are joined
only after ranks and scores have been frozen for that target.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values); i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]: j += 1
        rank = (i + 1 + j) / 2.0
        for k in range(i, j): result[order[k]] = rank
        i = j
    return result


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2: return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    dx, dy = [x-mx for x in rx], [y-my for y in ry]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return sum(x*y for x, y in zip(dx, dy)) / den if den else None


def auc(scores: list[float], labels: list[bool]) -> float | None:
    pos = [s for s, y in zip(scores, labels) if y]; neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg: return None
    return sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg) / (len(pos)*len(neg))


def _latest_records(warehouse: dict, start_dates: dict[str, str]) -> dict[str, dict[str, dict]]:
    events: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in warehouse.get("records", ()):
        pid, event = str(row.get("player_id") or ""), str(row.get("game_code") or "")
        if not pid or event not in start_dates or row.get("identity_state") != "RETAINED" or not isinstance(row.get("total"), (int,float)): continue
        old = events[event].get(pid)
        if old is None or int(row.get("rounds") or 0) >= int(old.get("rounds") or 0): events[event][pid] = row
    return events


def _z(values: dict[str, float]) -> dict[str, float]:
    mean=statistics.fmean(values.values()); sd=statistics.pstdev(values.values())
    return {k:(v-mean)/sd if sd else 0.0 for k,v in values.items()}


def run_backtest(warehouse: dict, start_dates: dict[str, str], outcomes: dict[tuple[str,str], dict], config: dict) -> dict:
    events = _latest_records(warehouse, start_dates)
    ordered = sorted(events, key=lambda event:(start_dates[event], event))
    weights={name:float(spec["weight"]) for name,spec in config["features"].items()}; minimum=int(config["eligibility"]["minimum_sg_events"])
    history: dict[str,list[tuple[str,float]]] = defaultdict(list); observations=[]; event_reports=[]
    for event in ordered:
        target_date=start_dates[event]; target=events[event]; eligible={pid:[value for date,value in history[pid] if date < target_date] for pid in target}
        eligible={pid:vals for pid,vals in eligible.items() if len(vals)>=minimum}
        if len(eligible)<2:
            for pid,row in target.items(): history[pid].append((target_date,float(row["total"])))
            continue
        raw={"recent_5_sg":{p:statistics.fmean(v[-5:]) for p,v in eligible.items()},"recent_10_sg":{p:statistics.fmean(v[-10:]) for p,v in eligible.items()},"long_term_sg":{p:statistics.fmean(v) for p,v in eligible.items()},"consistency":{p:-statistics.pstdev(v) if len(v)>1 else 0.0 for p,v in eligible.items()}}
        z={name:_z(vals) for name,vals in raw.items()}; scores={}; contributions={}
        for pid,vals in eligible.items():
            contributions[pid]={name:weights[name]*z[name][pid] for name in z}; contributions[pid]["sample_reliability"]=weights["sample_reliability"]*min(len(vals)/20,1)
            scores[pid]=sum(contributions[pid].values())
        ranked=sorted(scores,key=lambda pid:(-scores[pid],pid)); ranks={pid:i+1 for i,pid in enumerate(ranked)}; event_obs=[]
        for pid in ranked:
            outcome=outcomes.get((event,pid),{}); finish=outcome.get("finish_position_numeric"); sg=float(target[pid]["total"])
            row={"event":event,"target_start_date":target_date,"player_id":pid,"neo_rank":ranks[pid],"neo_score":round(scores[pid],8),"prior_sample_count":len(eligible[pid]),"max_feature_date":max(date for date,_ in history[pid]),"target_sg_total":sg,"outcome_joined":bool(outcome),"finish_position":finish,"made_cut":outcome.get("made_cut"),"withdrawn":outcome.get("withdrawn"),"disqualified":outcome.get("disqualified"),"feature_contributions":{k:round(v,8) for k,v in contributions[pid].items()}}
            if not row["max_feature_date"] < target_date: raise AssertionError("future leakage")
            observations.append(row); event_obs.append(row)
        valid_finish=[r for r in event_obs if r["finish_position"] is not None and not r["withdrawn"] and not r["disqualified"]]
        top10=set(r["player_id"] for r in sorted(valid_finish,key=lambda r:r["finish_position"])[:10]); pick10=set(ranked[:10])
        top20=set(r["player_id"] for r in sorted(valid_finish,key=lambda r:r["finish_position"])[:20]); pick20=set(ranked[:20])
        event_reports.append({"event":event,"start_date":target_date,"ranked_players":len(ranked),"finish_observations":len(valid_finish),"spearman_neo_rank_vs_finish":spearman([r["neo_rank"] for r in valid_finish],[r["finish_position"] for r in valid_finish]),"spearman_neo_score_vs_subsequent_sg":spearman([r["neo_score"] for r in event_obs],[r["target_sg_total"] for r in event_obs]),"top10_precision":len(pick10&top10)/len(pick10) if pick10 else None,"top10_recall":len(pick10&top10)/len(top10) if top10 else None,"top20_precision":len(pick20&top20)/len(pick20) if pick20 else None,"top20_recall":len(pick20&top20)/len(top20) if top20 else None,"made_cut_auc":auc([r["neo_score"] for r in event_obs if r["made_cut"] is not None],[bool(r["made_cut"]) for r in event_obs if r["made_cut"] is not None])})
        for pid,row in target.items(): history[pid].append((target_date,float(row["total"])))
    def avg(key):
        vals=[e[key] for e in event_reports if e[key] is not None]
        return statistics.fmean(vals) if vals else None
    metrics={key:avg(key) for key in ("spearman_neo_rank_vs_finish","spearman_neo_score_vs_subsequent_sg","top10_precision","top10_recall","top20_precision","top20_recall","made_cut_auc")}
    payload={"model_id":config["model_id"],"model_config_sha256":hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest(),"tournament_count":len(event_reports),"observation_count":len(observations),"unique_players":len({r["player_id"] for r in observations}),"metrics":metrics,"k_ranking_comparison":{"status":"NOT_EVALUABLE","reason":"no point-in-time historical official K-Ranking snapshots in repository; current 2026-W35 ranks are future data for historical targets"},"incremental_predictive_value":{"status":"NOT_EVALUABLE","reason":"historical K-Ranking baseline unavailable"},"validation":{"future_leakage_count":sum(not r["max_feature_date"]<r["target_start_date"] for r in observations),"duplicate_event_player_count":len(observations)-len({(r["event"],r["player_id"]) for r in observations}),"invalid_player_mapping_count":sum(not r["outcome_joined"] for r in observations),"insufficient_sample_ranked_count":sum(r["prior_sample_count"]<minimum for r in observations)},"events":event_reports,"observations":observations}
    payload["deterministic_fingerprint"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return payload
