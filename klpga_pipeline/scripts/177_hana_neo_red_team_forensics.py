"""NEO RED TEAM -- FULL TOURNAMENT FORENSICS (Hana 2026090002).

Operator instruction (2026-09-19): a full forensic audit of every real,
evidence-backed prediction transition this tournament has produced so
far (PRE->R1, R1->R2, R2->R3). Read-only analysis over EXISTING frozen/
evidence artifacts only -- NO new predictions, NO Monte Carlo
re-execution, NO freeze modification.

R3->FINAL is deliberately NOT computed here: no official FINAL/FR
evidence exists for this game_code (2026090002_POST_R4_FINAL_PREVIEW.json
is a forecast preview, not a real result -- its own `status` field says
so explicitly). Treating it as ground truth would be fabrication.

Outputs:
  - HANA_2026090002_RED_TEAM_FORENSICS_COMPUTED_V1.json (this script's
    full computed dataset -- confusion matrices, movers, calibration,
    SG correlation, cross-stage player deltas)
  - HANA_2026090002_NEO_RED_TEAM_FORENSICS_V1.md (the narrative report,
    built from this dataset by build_red_team_report.py-equivalent
    logic -- kept as a companion evidence artifact, never published to
    docs/).
"""
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "content" / "website_v2"

def load(name):
    return json.loads((D / name).read_text(encoding="utf-8"))

pre_r1 = load("HANA_2026090002_R1_PRE_COMPARISON_V1.json")
r1_analysis = load("HANA_2026090002_R1_ANALYSIS_V1.json")
r2_freeze = load("2026090002_R2_FROZEN_EVIDENCE.json")
post_r2_forecast = load("2026090002_POST_R2_FINAL_FORECAST.json")
candidate_freeze = load("2026090002_POST_R3_CANDIDATE_FREEZE_V1.json")
r3_freeze = load("2026090002_R3_FROZEN_EVIDENCE.json")
final_preview = load("2026090002_POST_R4_FINAL_PREVIEW.json")
r1_sg = load("HANA_2026090002_R1_SG_V1.json")
r2_sg = load("HANA_2026090002_R2_SG_V1.json")
r3_sg = load("HANA_2026090002_R3_SG_V1.json")

def pct(s):
    return float(str(s).replace("%", ""))

def standard_rank(items, score_key, reverse=False):
    ordered = sorted(items, key=lambda r: (r[score_key], r.get("player_id","")), reverse=reverse)
    rank = {}
    prev_score, prev_rank = None, 0
    for i, r in enumerate(ordered, 1):
        s = r[score_key]
        if s != prev_score:
            prev_rank = i
            prev_score = s
        rank[r["player_id"]] = prev_rank
    return rank

def predicted_topn(records, n, primary_key, tie_keys, id_key="player_id"):
    def keyf(r):
        return tuple([-r[primary_key]] + [-r[k] for k in tie_keys] + [r[id_key]])
    ordered = sorted(records, key=keyf)
    return [r[id_key] for r in ordered[:n]], ordered

def confusion(pred_ids, actual_ids):
    pred, act = set(pred_ids), set(actual_ids)
    tp, fp, fn = pred & act, pred - act, act - pred
    precision = len(tp)/len(pred) if pred else float("nan")
    recall = len(tp)/len(act) if act else float("nan")
    f1 = 2*precision*recall/(precision+recall) if (precision+recall) else float("nan")
    return dict(tp=len(tp), fp=len(fp), fn=len(fn), precision=precision, recall=recall, f1=f1,
                fp_ids=sorted(fp), fn_ids=sorted(fn))

def brier_logloss_calibration(pairs, bins=((0,0.1),(0.1,0.2),(0.2,0.3),(0.3,0.4),(0.4,0.5),(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.01))):
    # pairs: list of (predicted_prob_0_1, actual_binary_0_1)
    n = len(pairs)
    brier = sum((p-a)**2 for p,a in pairs)/n
    eps=1e-9
    logloss = -sum(a*math.log(max(p,eps)) + (1-a)*math.log(max(1-p,eps)) for p,a in pairs)/n
    bucket_stats=[]
    ece=0.0
    for lo,hi in bins:
        in_bin=[(p,a) for p,a in pairs if lo<=p<hi]
        if not in_bin: continue
        mp = mean(p for p,_ in in_bin)
        ap = mean(a for _,a in in_bin)
        bucket_stats.append(dict(bucket=f"[{lo:.1f},{min(hi,1.0):.1f})", n=len(in_bin), mean_predicted=round(mp,4), actual_rate=round(ap,4)))
        ece += (len(in_bin)/n)*abs(mp-ap)
    sharpness = pstdev([p for p,_ in pairs])
    return dict(n=n, brier=round(brier,5), logloss=round(logloss,5), ece=round(ece,5), sharpness=round(sharpness,5), buckets=bucket_stats)

RESULT = {}

# ============ STAGE 1: PRE -> R1 ============
pre_recs_all = pre_r1["records"]  # 107, has pre.* and r1.*
r1_wd_players = [r for r in pre_recs_all if r["r1"].get("rank") is None]
pre_recs = [r for r in pre_recs_all if r["r1"].get("rank") is not None]  # exclude real R1 WDs (3), never fabricate their rank
r1_actual_rank = standard_rank(
    [{"player_id": r["player_id"], "rank": r["r1"]["rank"]} for r in pre_recs],
    "rank"
)
pre_flat = [dict(player_id=r["player_id"], name=r["official_display_name"],
                  win=r["pre"]["win_probability"]*100, top5=r["pre"]["top5_probability"]*100,
                  top10=r["pre"]["top10_probability"]*100, top20=r["pre"]["top20_probability"]*100)
            for r in pre_recs]
name_lookup_all = {r["player_id"]: r["official_display_name"] for r in pre_recs_all}
pred20, _ = predicted_topn(pre_flat, 20, "top20", ["top10","top5","win"])
pred10, _ = predicted_topn(pre_flat, 10, "top10", ["top5","win"])
pred5, _  = predicted_topn(pre_flat, 5, "top5", ["win"])
act20 = {pid for pid,rk in r1_actual_rank.items() if rk<=20}
act10 = {pid for pid,rk in r1_actual_rank.items() if rk<=10}
act5  = {pid for pid,rk in r1_actual_rank.items() if rk<=5}
pred_winner = max(pre_flat, key=lambda r: r["win"])["player_id"]
actual_winner = min(r1_actual_rank, key=lambda k: r1_actual_rank[k])

name_lookup = {r["player_id"]: r["official_display_name"] for r in pre_recs}
def enrich(ids): return [(pid, name_lookup.get(pid,pid), r1_actual_rank.get(pid)) for pid in ids]

stage1 = dict(
    n_population=len(pre_flat),
    r1_wd_players=[(r["player_id"], r["official_display_name"]) for r in r1_wd_players],
    top20=confusion(pred20, act20), top10=confusion(pred10, act10), top5=confusion(pred5, act5),
    predicted_winner=(pred_winner, name_lookup.get(pred_winner)),
    actual_winner=(actual_winner, name_lookup.get(actual_winner), r1_actual_rank[actual_winner]),
    winner_hit = pred_winner == actual_winner,
)
stage1["top20"]["fp_named"]=enrich(stage1["top20"]["fp_ids"]); stage1["top20"]["fn_named"]=enrich(stage1["top20"]["fn_ids"])
stage1["top10"]["fp_named"]=enrich(stage1["top10"]["fp_ids"]); stage1["top10"]["fn_named"]=enrich(stage1["top10"]["fn_ids"])
stage1["top5"]["fp_named"]=enrich(stage1["top5"]["fp_ids"]); stage1["top5"]["fn_named"]=enrich(stage1["top5"]["fn_ids"])

# movers PRE->R1_analysis (win_probability, using common ids with r1_analysis)
r1a_by_id = {r["player_id"]: r for r in r1_analysis["records"] if r.get("status") is None}  # exclude WD
pre_by_id = {r["player_id"]: r for r in pre_flat}
common_ids = sorted(set(pre_by_id) & set(r1a_by_id))
movers1 = []
for pid in common_ids:
    before = pre_by_id[pid]["win"]
    after = pct(r1a_by_id[pid]["win_probability"])
    movers1.append((pid, name_lookup.get(pid, pid), before, after, after-before))
movers1_up = sorted(movers1, key=lambda x: -x[4])[:10]
movers1_down = sorted(movers1, key=lambda x: x[4])[:10]
stage1["movers_win_prob"] = dict(up=movers1_up, down=movers1_down)

# calibration PRE.top20_prob vs actual R1 top20
pairs1 = [(r["top20"]/100.0, 1.0 if pid in act20 else 0.0) for pid,r in pre_by_id.items()]
stage1["calibration_top20"] = brier_logloss_calibration(pairs1)

RESULT["stage1_pre_to_r1"] = stage1

# ============ STAGE 2: R1 -> R2 ============
r1a_flat = [dict(player_id=r["player_id"], name=r["official_display_name"],
                  win=pct(r["win_probability"]), top5=pct(r["top5_probability"]),
                  top10=pct(r["top10_probability"]), top20=pct(r["top20_probability"]),
                  cut=pct(r["cut_probability"]))
            for r in r1_analysis["records"] if r.get("status") is None]  # exclude 3 WD
r2_non_wd = [r for r in r2_freeze["records"] if r["status"] != "WD"]
r2_actual_rank = standard_rank(
    [{"player_id": r["player_id"], "score": r["r2_total_under_par"]} for r in r2_non_wd], "score"
)
name2 = {r["player_id"]: r["player_name"] for r in r2_freeze["records"]}
pred20b, _ = predicted_topn(r1a_flat, 20, "top20", ["top10","top5","win"])
pred10b, _ = predicted_topn(r1a_flat, 10, "top10", ["top5","win"])
pred5b, _  = predicted_topn(r1a_flat, 5, "top5", ["win"])
act20b = {pid for pid,rk in r2_actual_rank.items() if rk<=20}
act10b = {pid for pid,rk in r2_actual_rank.items() if rk<=10}
act5b  = {pid for pid,rk in r2_actual_rank.items() if rk<=5}
pred_winner2 = max(r1a_flat, key=lambda r: r["win"])["player_id"]
actual_leader2 = min(r2_actual_rank, key=lambda k: r2_actual_rank[k])

def enrich2(ids): return [(pid, name2.get(pid,pid), r2_actual_rank.get(pid, "WD/N-A")) for pid in ids]

stage2 = dict(
    n_population=len(r1a_flat), n_actual_ranked=len(r2_non_wd),
    top20=confusion(pred20b, act20b), top10=confusion(pred10b, act10b), top5=confusion(pred5b, act5b),
    predicted_winner=(pred_winner2, name2.get(pred_winner2)),
    actual_leader=(actual_leader2, name2.get(actual_leader2), r2_actual_rank[actual_leader2]),
    winner_hit = pred_winner2 == actual_leader2,
    made_cut_check = dict(
        cut_survivors = sum(1 for r in r2_freeze["records"] if r["status"]=="ACTIVE"),
        cut_missed = sum(1 for r in r2_freeze["records"] if r["status"]=="CUT"),
    )
)
stage2["top20"]["fp_named"]=enrich2(stage2["top20"]["fp_ids"]); stage2["top20"]["fn_named"]=enrich2(stage2["top20"]["fn_ids"])
stage2["top10"]["fp_named"]=enrich2(stage2["top10"]["fp_ids"]); stage2["top10"]["fn_named"]=enrich2(stage2["top10"]["fn_ids"])
stage2["top5"]["fp_named"]=enrich2(stage2["top5"]["fp_ids"]); stage2["top5"]["fn_named"]=enrich2(stage2["top5"]["fn_ids"])

# cut-probability calibration (this mirrors 172's own item 7/8/9 methodology -- reused, not recomputed differently)
r2_status_by_id = {r["player_id"]: r["status"] for r in r2_freeze["records"]}
pairs_cut = [(r["cut"]/100.0, 1.0 if r2_status_by_id.get(r["player_id"])=="ACTIVE" else 0.0)
             for r in r1a_flat if r["player_id"] in r2_status_by_id]
stage2["calibration_cut"] = brier_logloss_calibration(pairs_cut)

# movers R1-based -> R2-based (post_r2_forecast, cut survivors only; cut-missed collapse to 0, real fact not a guess)
post2_by_id = {r["player_id"]: r for r in post_r2_forecast["records"]}
movers2 = []
for pid, r in {r["player_id"]: r for r in r1a_flat}.items():
    before = r["win"]
    after = post2_by_id[pid]["win_pct"] if pid in post2_by_id else 0.0
    movers2.append((pid, name2.get(pid,pid), before, after, after-before,
                     "CUT (eliminated)" if pid not in post2_by_id and r2_status_by_id.get(pid)=="CUT" else ""))
movers2_up = sorted(movers2, key=lambda x: -x[4])[:10]
movers2_down = sorted(movers2, key=lambda x: x[4])[:10]
stage2["movers_win_prob"] = dict(up=movers2_up, down=movers2_down)

# top20 calibration for stage2 (post-R1 top20_prob vs actual R2 top20)
pairs2 = [(r["top20"]/100.0, 1.0 if pid in act20b else 0.0) for pid,r in {r["player_id"]:r for r in r1a_flat}.items()]
stage2["calibration_top20"] = brier_logloss_calibration(pairs2)

RESULT["stage2_r1_to_r2"] = stage2

# ============ STAGE 3: R2 -> R3 (reuse/re-derive) ============
cand_by_id = {r["player_id"]: r for r in candidate_freeze["records"]}
r3_by_id = {r["player_id"]: r for r in r3_freeze["records"]}
r3_rank = standard_rank([{"player_id": pid, "score": r["r3_total_under_par"]} for pid,r in r3_by_id.items()], "score")
name3 = {r["player_id"]: r["player_name"] for r in r3_freeze["records"]}

def predicted_topn3(n, pct_field, tiebreaks):
    def keyf(r): return tuple([-r[pct_field]] + [-r[k] for k in tiebreaks] + [r["player_id"]])
    ordered = sorted(cand_by_id.values(), key=keyf)
    return [r["player_id"] for r in ordered[:n]]

pred20c = predicted_topn3(20, "top20_pct", ["top10_pct","top5_pct","win_pct"])
pred10c = predicted_topn3(10, "top10_pct", ["top5_pct","win_pct"])
pred5c  = predicted_topn3(5, "top5_pct", ["win_pct"])
act20c = {pid for pid,rk in r3_rank.items() if rk<=20}
act10c = {pid for pid,rk in r3_rank.items() if rk<=10}
act5c  = {pid for pid,rk in r3_rank.items() if rk<=5}
pred_winner3 = max(cand_by_id.values(), key=lambda r: r["win_pct"])["player_id"]
actual_leader3 = min(r3_rank, key=lambda k: r3_rank[k])

def enrich3(ids): return [(pid, name3.get(pid,pid), r3_rank.get(pid)) for pid in ids]
stage3 = dict(
    n_population=len(cand_by_id),
    top20=confusion(pred20c, act20c), top10=confusion(pred10c, act10c), top5=confusion(pred5c, act5c),
    predicted_winner=(pred_winner3, name3.get(pred_winner3)),
    actual_leader=(actual_leader3, name3.get(actual_leader3), r3_rank[actual_leader3]),
    winner_hit = pred_winner3 == actual_leader3,
)
stage3["top20"]["fp_named"]=enrich3(stage3["top20"]["fp_ids"]); stage3["top20"]["fn_named"]=enrich3(stage3["top20"]["fn_ids"])
stage3["top10"]["fp_named"]=enrich3(stage3["top10"]["fp_ids"]); stage3["top10"]["fn_named"]=enrich3(stage3["top10"]["fn_ids"])
stage3["top5"]["fp_named"]=enrich3(stage3["top5"]["fp_ids"]); stage3["top5"]["fn_named"]=enrich3(stage3["top5"]["fn_ids"])

pairs3 = [(r["top20_pct"]/100.0, 1.0 if pid in act20c else 0.0) for pid,r in cand_by_id.items()]
stage3["calibration_top20"] = brier_logloss_calibration(pairs3)

# movers: candidate freeze (pre-R3) -> final preview (post-R3, both are MODEL outputs, not real outcome)
final_by_id = {r["player_id"]: r for r in final_preview["records"]}
movers3 = []
for pid, r in cand_by_id.items():
    before = r["win_pct"]
    after = final_by_id[pid]["win_pct"] if pid in final_by_id else 0.0
    movers3.append((pid, name3.get(pid,pid), before, after, after-before))
movers3_up = sorted(movers3, key=lambda x: -x[4])[:10]
movers3_down = sorted(movers3, key=lambda x: x[4])[:10]
stage3["movers_win_prob"] = dict(up=movers3_up, down=movers3_down)

RESULT["stage3_r2_to_r3"] = stage3

# ============ SG analysis: correlation of round-N SG with round-(N+1) real score ============
def pearson(xs, ys):
    n=len(xs)
    if n<2: return float("nan")
    mx,my = mean(xs), mean(ys)
    cov = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    sx = math.sqrt(sum((x-mx)**2 for x in xs))
    sy = math.sqrt(sum((y-my)**2 for y in ys))
    return cov/(sx*sy) if sx>0 and sy>0 else float("nan")

r1sg_by_id = {r["player_id"]: r["total"] for r in r1_sg["records"]} if "records" in r1_sg else {}
r2sg_by_id = {r["player_id"]: r["total"] for r in r2_sg["records"]} if "records" in r2_sg else {}
r3sg_by_id = {r["player_id"]: r["total"] for r in r3_sg["records"]} if "records" in r3_sg else {}

# R1 SG (round1, lower score-to-par is better, so SG (higher=better) should correlate negatively with R2 raw score-to-par)
r2_score_by_id = {r["player_id"]: r["r2_score_to_par"] for r in r2_freeze["records"] if r["status"]!="WD"}
common_r1sg_r2 = set(r1sg_by_id) & set(r2_score_by_id)
corr_r1sg_r2score = pearson([r1sg_by_id[p] for p in common_r1sg_r2], [r2_score_by_id[p] for p in common_r1sg_r2])

r3_score_by_id = {r["player_id"]: r["r3_score_to_par"] for r in r3_freeze["records"]}
common_r2sg_r3 = set(r2sg_by_id) & set(r3_score_by_id)
corr_r2sg_r3score = pearson([r2sg_by_id[p] for p in common_r2sg_r3], [r3_score_by_id[p] for p in common_r2sg_r3])

# same-round self-correlation (R1 SG vs R1 score, sanity check -- should be strongly negative since SG derived partly from score)
r1_score_by_id = {r["player_id"]: r["r1_score_to_par"] for r in r2_freeze["records"] if r["status"]!="WD"}
common_r1sg_r1 = set(r1sg_by_id) & set(r1_score_by_id)
corr_r1sg_r1score = pearson([r1sg_by_id[p] for p in common_r1sg_r1], [r1_score_by_id[p] for p in common_r1sg_r1])

r2_score_self_by_id = r2_score_by_id
common_r2sg_r2 = set(r2sg_by_id) & set(r2_score_self_by_id)
corr_r2sg_r2score = pearson([r2sg_by_id[p] for p in common_r2sg_r2], [r2_score_self_by_id[p] for p in common_r2sg_r2])

r3_score_self = r3_score_by_id
common_r3sg_r3 = set(r3sg_by_id) & set(r3_score_self)
corr_r3sg_r3score = pearson([r3sg_by_id[p] for p in common_r3sg_r3], [r3_score_self[p] for p in common_r3sg_r3])

RESULT["sg_analysis"] = dict(
    same_round_correlation=dict(
        r1_sg_vs_r1_score=dict(n=len(common_r1sg_r1), pearson_r=round(corr_r1sg_r1score,4)),
        r2_sg_vs_r2_score=dict(n=len(common_r2sg_r2), pearson_r=round(corr_r2sg_r2score,4)),
        r3_sg_vs_r3_score=dict(n=len(common_r3sg_r3), pearson_r=round(corr_r3sg_r3score,4)),
    ),
    predictive_correlation_next_round=dict(
        r1_sg_vs_r2_score=dict(n=len(common_r1sg_r2), pearson_r=round(corr_r1sg_r2score,4)),
        r2_sg_vs_r3_score=dict(n=len(common_r2sg_r3), pearson_r=round(corr_r2sg_r3score,4)),
    ),
)

# ============ Player-level cross-stage rank tracking (closest / overvalued / undervalued) ============
# rank by win_prob at each of the 3 forecast points, vs actual rank at the corresponding next checkpoint
def rankmap(records, key, id_key="player_id"):
    ordered = sorted(records, key=lambda r: (-r[key], r[id_key]))
    return {r[id_key]: i+1 for i,r in enumerate(ordered)}

pre_rank_map = rankmap(pre_flat, "win")
r1a_rank_map = rankmap(r1a_flat, "win")
cand_rank_map = rankmap(list(cand_by_id.values()), "win_pct")

deltas = []
for pid in sorted(set(pre_rank_map) & set(r1_actual_rank)):
    deltas.append(("PRE->R1", pid, name_lookup.get(pid,pid), pre_rank_map[pid], r1_actual_rank[pid], pre_rank_map[pid]-r1_actual_rank[pid]))
for pid in sorted(set(r1a_rank_map) & set(r2_actual_rank)):
    deltas.append(("R1->R2", pid, name2.get(pid,pid), r1a_rank_map[pid], r2_actual_rank[pid], r1a_rank_map[pid]-r2_actual_rank[pid]))
for pid in sorted(set(cand_rank_map) & set(r3_rank)):
    deltas.append(("R2->R3", pid, name3.get(pid,pid), cand_rank_map[pid], r3_rank[pid], cand_rank_map[pid]-r3_rank[pid]))

closest10 = sorted(deltas, key=lambda x: abs(x[5]))[:10]
overvalued10 = sorted(deltas, key=lambda x: x[5])[:10]   # predicted rank << actual rank (model too optimistic)
undervalued10 = sorted(deltas, key=lambda x: -x[5])[:10] # predicted rank >> actual rank (model too pessimistic)
surprise10 = sorted(deltas, key=lambda x: -abs(x[5]))[:10]

RESULT["player_cross_stage"] = dict(
    closest_to_neo=closest10, most_overvalued=overvalued10, most_undervalued=undervalued10, biggest_surprises=surprise10,
    all_deltas=deltas,
)

out_path = D / "HANA_2026090002_RED_TEAM_FORENSICS_COMPUTED_V1.json"
out_path.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
print("WROTE", out_path)
print(json.dumps({k: {kk: (vv if not isinstance(vv, dict) else {k3: v3 for k3,v3 in vv.items() if k3 not in ('fp_named','fn_named','buckets')}) for kk,vv in v.items()} if isinstance(v, dict) else v for k,v in RESULT.items() if k in ("stage1_pre_to_r1","stage2_r1_to_r2","stage3_r2_to_r3")}, ensure_ascii=False, indent=2, default=str)[:6000])
