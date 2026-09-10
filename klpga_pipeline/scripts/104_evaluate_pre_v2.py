from __future__ import annotations

import json
import math
import random
import sqlite3
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.walk_forward import build_walk_forward_dataset
from klpga.models.math_utils import wilcoxon_signed_rank_test
from klpga.models.metrics import brier_norm, log_loss, paired_comparison
from klpga.models.walk_forward_eval import run_multi_model_walk_forward
from klpga.models.candidates import apply_shrinkage_and_standardize, fit_shrinkage

DB = ROOT / "data" / "klpga.sqlite"
OUT = ROOT / "content" / "website_v2" / "NEO_PRE_5PROB_V2_WALK_FORWARD.json"
N_SIMS = 5000
SEED = 20260910
EPS = 1e-6
OUTCOMES = ("CUT", "TOP20", "TOP10", "TOP5")


def plackett_luce_inclusion(weights: dict[str, float], cut_n: int, *, seed: int) -> dict[str, dict[str, float]]:
    codes = sorted(weights)
    rng = random.Random(seed)
    counts = {o: {c: 0 for c in codes} for o in OUTCOMES}
    cut_n = min(len(codes), max(1, cut_n))
    for _ in range(N_SIMS):
        ranking = sorted(codes, key=lambda c: -math.log(max(rng.random(), 1e-300)) / max(weights[c], EPS))
        for outcome, n in (("CUT", cut_n), ("TOP20", 20), ("TOP10", 10), ("TOP5", 5)):
            for c in ranking[: min(n, len(ranking))]:
                counts[outcome][c] += 1
    return {o: {c: counts[o][c] / N_SIMS for c in codes} for o in OUTCOMES}


def uniform_probs(codes: list[str], cut_n: int) -> dict[str, dict[str, float]]:
    n = len(codes)
    return {
        "CUT": {c: cut_n / n for c in codes},
        "TOP20": {c: min(20, n) / n for c in codes},
        "TOP10": {c: min(10, n) / n for c in codes},
        "TOP5": {c: min(5, n) / n for c in codes},
    }


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n=len(vector); a=[row[:] + [vector[i]] for i,row in enumerate(matrix)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda r:abs(a[r][col]))
        a[col],a[pivot]=a[pivot],a[col]
        if abs(a[col][col]) < 1e-12: a[col][col]=1e-12
        div=a[col][col]; a[col]=[v/div for v in a[col]]
        for r in range(n):
            if r==col: continue
            f=a[r][col]
            a[r]=[a[r][c]-f*a[col][c] for c in range(n+1)]
    return [a[i][-1] for i in range(n)]


def fit_binary_logit(training_rows: list[dict], features: tuple[str,...]) -> tuple[list[float],dict]:
    shrink={f:fit_shrinkage(training_rows,f) for f in features}
    xs=[]; ys=[]
    for r in training_rows:
        xs.append([1.0]+[apply_shrinkage_and_standardize(r.get(f),r.get(f+"_n"),shrink[f]) for f in features])
        ys.append(1.0 if r.get("label_made_cut") else 0.0)
    beta=[0.0]*len(xs[0])
    for _ in range(50):
        grad=[0.0]*len(beta); info=[[0.0]*len(beta) for _ in beta]
        for x,y in zip(xs,ys):
            eta=max(-30.0,min(30.0,sum(b*v for b,v in zip(beta,x))))
            p=1.0/(1.0+math.exp(-eta)); w=max(1e-9,p*(1-p))
            for i in range(len(beta)):
                grad[i]+=x[i]*(y-p)
                for j in range(len(beta)): info[i][j]+=w*x[i]*x[j]
        for i in range(1,len(beta)): info[i][i]+=1e-8
        delta=_solve(info,grad)
        beta=[b+d for b,d in zip(beta,delta)]
        if max(abs(d) for d in delta)<1e-9: break
    return beta,shrink


def predict_binary_logit(rows: list[dict], features: tuple[str,...], beta:list[float], shrink:dict) -> dict[str,float]:
    out={}
    for r in rows:
        x=[1.0]+[apply_shrinkage_and_standardize(r.get(f),r.get(f+"_n"),shrink[f]) for f in features]
        eta=max(-30.0,min(30.0,sum(b*v for b,v in zip(beta,x))))
        out[r["player_code"]]=1.0/(1.0+math.exp(-eta))
    return out


def labels(rows: list[dict]) -> dict[str, dict[str, int]]:
    out = {o: {} for o in (*OUTCOMES, "WIN")}
    for r in rows:
        c = r["player_code"]
        pos = r.get("label_finish_position_numeric")
        out["CUT"][c] = int(bool(r.get("label_made_cut")))
        out["TOP20"][c] = int(pos is not None and pos <= 20)
        out["TOP10"][c] = int(pos is not None and pos <= 10)
        out["TOP5"][c] = int(pos is not None and pos <= 5)
        out["WIN"][c] = int(bool(r.get("label_is_winner")))
    return out


def binary_metrics(prob: dict[str, float], truth: dict[str, int]) -> dict[str, float]:
    codes = sorted(truth)
    ps = [min(1 - EPS, max(EPS, prob[c])) for c in codes]
    ys = [truth[c] for c in codes]
    return {
        "log_loss": sum(-(y * math.log(p) + (1 - y) * math.log(1 - p)) for p, y in zip(ps, ys)) / len(codes),
        "brier": sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(codes),
        "auc": auc(prob, truth),
    }


def auc(prob: dict[str, float], truth: dict[str, int]) -> float:
    positives = [prob[c] for c, y in truth.items() if y]
    negatives = [prob[c] for c, y in truth.items() if not y]
    if not positives or not negatives:
        return float("nan")
    wins = 0.0
    for p in positives:
        for n in negatives:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(positives) * len(negatives))


def calibration(items: list[tuple[float, int]]) -> list[dict]:
    bins = ((0,.1),(.1,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.0000001))
    out=[]
    for lo,hi in bins:
        selected=[(p,y) for p,y in items if lo <= p < hi]
        if selected:
            out.append({"lo":lo,"hi":min(hi,1.0),"n":len(selected),"mean_predicted":statistics.mean(p for p,_ in selected),"actual_rate":statistics.mean(y for _,y in selected)})
    return out


def aggregate(per_event: dict[str, dict], outcome: str, model: str, allowed: set[str]) -> dict:
    rows=[per_event[e][outcome][model] for e in sorted(allowed) if e in per_event]
    return {"n_tournaments":len(rows),"mean_log_loss":statistics.mean(r["log_loss"] for r in rows),"mean_brier":statistics.mean(r["brier"] for r in rows),"mean_auc":statistics.mean(r["auc"] for r in rows if not math.isnan(r["auc"]))}


def paired_binary(per_event: dict[str, dict], outcome: str, a: str, b: str, metric: str, allowed: set[str]) -> dict:
    diffs=[per_event[e][outcome][a][metric]-per_event[e][outcome][b][metric] for e in sorted(allowed) if e in per_event]
    return wilcoxon_signed_rank_test(diffs)


def main() -> None:
    conn=sqlite3.connect(DB)
    dataset=build_walk_forward_dataset(conn)
    targets={t.event_id:t for t in dataset.target_order}
    rows_by={}
    for r in dataset.rows: rows_by.setdefault(r["target_event_id"],[]).append(r)
    print("fit M0/M1/M4 strict walk-forward", flush=True)
    wf=run_multi_model_walk_forward(conn,("M0","M1","M4"),5)
    preds={m:{p.target_event_id:p for p in ps} for m,ps in wf.predictions_by_model.items()}
    per_event={}
    all_cal={o:{m:[] for m in ("M0","M1","V2_M4_PL")} for o in OUTCOMES}
    eligible=[t for t in dataset.target_order if t.prior_tournament_count>=5]
    for idx,t in enumerate(eligible,1):
        if t.event_id not in preds["M4"]: continue
        rows=rows_by[t.event_id]; truth=labels(rows); codes=sorted(truth["WIN"])
        prior_rows=[]
        for pt in dataset.target_order:
            if pt.effective_date < t.effective_date: prior_rows.extend(rows_by.get(pt.event_id,[]))
        cut_rate=(sum(bool(r.get("label_made_cut")) for r in prior_rows)/len(prior_rows))
        cut_n=max(1,round(len(codes)*cut_rate))
        probs={"M0":uniform_probs(codes,cut_n)}
        probs["M1"]=plackett_luce_inclusion(preds["M1"][t.event_id].probabilities,cut_n,seed=SEED+t.rank*10+1)
        probs["V2_M4_PL"]=plackett_luce_inclusion(preds["M4"][t.event_id].probabilities,cut_n,seed=SEED+t.rank*10+4)
        m1_beta,m1_shrink=fit_binary_logit(prior_rows,("prior_avg_round_score_to_par",))
        m4_beta,m4_shrink=fit_binary_logit(prior_rows,("prior_avg_round_score_to_par","prior_recent_form_10"))
        probs["M1"]["CUT"]=predict_binary_logit(rows,("prior_avg_round_score_to_par",),m1_beta,m1_shrink)
        probs["V2_M4_PL"]["CUT"]=predict_binary_logit(rows,("prior_avg_round_score_to_par","prior_recent_form_10"),m4_beta,m4_shrink)
        per_event[t.event_id]={o:{} for o in OUTCOMES}
        for o in OUTCOMES:
            for m in probs:
                per_event[t.event_id][o][m]=binary_metrics(probs[m][o],truth[o])
                all_cal[o][m].extend((probs[m][o][c],truth[o][c]) for c in codes)
        if idx%10==0 or idx==len(eligible): print(f"tier simulation {idx}/{len(eligible)}",flush=True)
    thresholds={}
    for th in (5,8,10):
        allowed={t.event_id for t in dataset.target_order if t.prior_tournament_count>=th and t.event_id in preds["M4"]}
        win={}
        for m in ("M0","M1","M4"):
            pp=[preds[m][e] for e in sorted(allowed)]
            win[m]={"mean_log_loss":statistics.mean(log_loss(p) for p in pp),"mean_brier":statistics.mean(brier_norm(p) for p in pp)}
        win["V2_vs_M0_log_loss"]=paired_comparison([preds["M4"][e] for e in sorted(allowed)],[preds["M0"][e] for e in sorted(allowed)],log_loss)
        win["V2_vs_M1_log_loss"]=paired_comparison([preds["M4"][e] for e in sorted(allowed)],[preds["M1"][e] for e in sorted(allowed)],log_loss)
        win["V2_vs_M1_brier"]=paired_comparison([preds["M4"][e] for e in sorted(allowed)],[preds["M1"][e] for e in sorted(allowed)],brier_norm)
        win["primary_gate_pass"]=(win["V2_vs_M0_log_loss"]["mean_diff"]<0 and win["V2_vs_M0_log_loss"]["p_value"]<.05 and win["V2_vs_M1_log_loss"]["mean_diff"]<0 and win["V2_vs_M1_log_loss"]["p_value"]<.05)
        tiers={}
        for o in OUTCOMES:
            tiers[o]={m:aggregate(per_event,o,m,allowed) for m in ("M0","M1","V2_M4_PL")}
            tiers[o]["V2_vs_M0_log_loss"]=paired_binary(per_event,o,"V2_M4_PL","M0","log_loss",allowed)
            tiers[o]["V2_vs_M1_log_loss"]=paired_binary(per_event,o,"V2_M4_PL","M1","log_loss",allowed)
            tiers[o]["V2_vs_M1_brier"]=paired_binary(per_event,o,"V2_M4_PL","M1","brier",allowed)
        thresholds[str(th)]={"n":len(allowed),"WIN":win,"tiers":tiers}
    report={
      "schema_version":"NEO_PRE_5PROB_V2_WALK_FORWARD_V1",
      "model":"V2B_M4_PL_PLUS_CUT_LOGIT",
      "candidate_registry":[
        {"id":"V1_SCORE_NORMAL","status":"REJECTED","evidence":"neo_kb_pre_full_validation.json","reason":"failed frozen paired WIN log-loss gate vs M1 at thresholds 5/8/10"},
        {"id":"V2A_M4_PL_ALL_OUTCOMES","status":"REJECTED","reason":"CUT log loss materially worse than uniform baseline","structure":"frozen M4 pre-event win weights extended to all rank outcomes"},
        {"id":"V2B_M4_PL_PLUS_CUT_LOGIT","status":"SELECTED_IF_GATE_PASS","structure":"frozen M4 pre-event win weights extended to TOP/WIN finish order; CUT uses fold-fitted binary logistic MLE on explicit player_event.made_cut with frozen M4 features; no hand-set coefficient"}
      ],
      "kb_excluded": "2026090003 not present in tournament_master/player_event/player_round; cutoff remains 2026-09-10",
      "cut_truth":"player_event.made_cut only",
      "simulation":{"n_per_event":N_SIMS,"seed_base":SEED},
      "thresholds":thresholds,
      "calibration_threshold5":{o:{m:calibration(all_cal[o][m]) for m in all_cal[o]} for o in OUTCOMES},
      "overall_frozen_win_gate_pass":all(v["WIN"]["primary_gate_pass"] for v in thresholds.values()),
    }
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    brief={"out":str(OUT),"overall":report["overall_frozen_win_gate_pass"],"thresholds":{k:{"WIN":v["WIN"],"tiers":v["tiers"]} for k,v in thresholds.items()}}
    print(json.dumps(brief,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__": main()
