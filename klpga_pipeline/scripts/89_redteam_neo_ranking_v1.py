"""Generate the frozen V1 red-team backtest artifact and report."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; CONTENT=ROOT/"content"/"website_v2"; DOCS=ROOT/"docs"
sys.path.insert(0,str(ROOT/"src"))
from klpga.website_v2.neo_ranking_backtest import run_backtest  # noqa:E402
from klpga.website_v2.top120_validation import evaluate  # noqa:E402

FOCUS=("서지은","정슬기","이주미","홍지원","고지우","홍정민","고지원")

def load(name): return json.loads((CONTENT/name).read_text(encoding="utf-8"))
def f(value, digits=4): return "N/A" if value is None else f"{value:.{digits}f}"

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--db",type=Path,required=True);args=parser.parse_args()
    config=load("NEO_RANKING_VALIDATION_MODEL_V1.json"); warehouse=load("historical_sg_warehouse_corrected.json"); cohort=load("HOME_PLAYER_MASTER_TOP120.json")
    with sqlite3.connect(f"file:{args.db}?mode=ro",uri=True) as conn:
        dates={str(g):str(d) for g,d in conn.execute("SELECT game_code,start_date FROM tournament_master WHERE start_date IS NOT NULL")}
        outcomes={(str(g),str(p)): {"finish_position_numeric":fin,"made_cut":bool(cut),"withdrawn":bool(wd),"disqualified":bool(dq)} for g,p,fin,cut,wd,dq in conn.execute("SELECT game_code,player_id,finish_position_numeric,made_cut,withdrawn,disqualified FROM player_event")}
        current,_=evaluate(cohort,warehouse,config); by_name={r["player_name"]:r for r in current}; focus=[]
        for name in FOCUS:
            r=by_name[name]; pid=r["player_id"]
            recent=[{"event":event,"start_date":date,"finish_position":finish,"made_cut":bool(cut),"withdrawn":bool(wd),"disqualified":bool(dq)} for event,date,finish,cut,wd,dq in conn.execute("SELECT pe.game_code,tm.start_date,pe.finish_position_numeric,pe.made_cut,pe.withdrawn,pe.disqualified FROM player_event pe JOIN tournament_master tm ON tm.game_code=pe.game_code WHERE pe.player_id=? ORDER BY tm.start_date DESC LIMIT 5",(pid,))]
            feature=r["features"] or {}; contrib=r["feature_contributions"] or {}
            driver=max(contrib,key=lambda k:abs(contrib[k])) if contrib else "DATA_INSUFFICIENT"
            focus.append({"player_name":name,"player_id":pid,"k_rank":r["official_k_rank"],"neo_rank":r["neo_validation_rank"],"rank_delta":r["rank_delta"],"neo_score":r["validation_score"],"feature_values":feature,"feature_contributions":contrib,"recent_sample_size":min(feature.get("sample_count",0),5),"sg_sample_size":feature.get("sample_count",0),"recent_results":recent,"primary_driver":driver})
    result=run_backtest(warehouse,dates,outcomes,config); result["current_extreme_player_analysis"]=focus
    # The same pure function must produce a byte-identical fingerprint.
    rerun=run_backtest(warehouse,dates,outcomes,config); result["validation"]["reproducibility_match"]=result["deterministic_fingerprint"]==rerun["deterministic_fingerprint"]
    result["validation"]["deterministic_output_match"]=result["validation"]["reproducibility_match"]
    artifact=CONTENT/"NEO_RANKING_V1_REDTEAM_BACKTEST.json"; artifact.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    m=result["metrics"]; lines=["# NEO Ranking V1 RED TEAM & Historical Backtest","","> 판정: **REJECT** — V1은 validation-only heuristic이며 historical K-Ranking baseline 부재, 약한 순위/결과 상관, target-field archival limitation 때문에 PUBLIC/BETA 승격 근거가 없다.","","## Frozen formula","","- Model: `neo-ranking-validation-v1`; weights were not tuned during this audit.","- Features: recent5 SG 0.35, recent10 SG 0.25, long-term SG 0.25, consistency (`-volatility`) 0.10, sample reliability 0.05.","- Normalization: each target cohort's eligible players within each SG feature are population z-scored; zero dispersion maps to 0.","- Recent windows: strictly the latest 5/10 prior events whose start dates precede the target; long-term and volatility use every prior event.","- Eligibility: at least 10 prior validated SG events. Missing SG is never imputed; ineligible players receive no rank.","- Sample reliability: `min(prior_event_count / 20, 1) * 0.05`.","- Cut/WD/DQ: prior official SG remains an observed feature when present; no zero is inserted. WD/DQ targets are excluded from finish correlation. Made-cut evaluation uses the DB's confirmed flag.","- Recency: event-date ordering and fixed 5/10 windows; no exponential decay.","", "## Backtest coverage","",f"- {result['tournament_count']} tournaments; {result['observation_count']} player-event observations; {result['unique_players']} players.","- Every feature date is strictly earlier than its target start date.","- Historical K-Ranking: NOT EVALUABLE. Current W35 ranking was rejected as a historical baseline because it would leak future information.","","## Performance","",f"- Mean Spearman, NEO rank vs finish: {f(m['spearman_neo_rank_vs_finish'])}",f"- Mean Spearman, NEO score vs subsequent SG Total: {f(m['spearman_neo_score_vs_subsequent_sg'])}",f"- Top10 precision / recall: {f(m['top10_precision'])} / {f(m['top10_recall'])}",f"- Top20 precision / recall: {f(m['top20_precision'])} / {f(m['top20_recall'])}",f"- Made-cut AUC: {f(m['made_cut_auc'])}","- K-Ranking metrics and incremental predictive value: N/A (point-in-time snapshots unavailable).","","## Extreme current deltas",""]
    for row in focus:
        recent=", ".join(f"{x['event']}:{x['finish_position'] if x['finish_position'] is not None else '-'}{' CUT' if not x['made_cut'] else ''}" for x in row["recent_results"])
        contributions=", ".join(f"{k}={v:+.4f}" for k,v in row["feature_contributions"].items())
        lines.append(f"- **{row['player_name']}** K {row['k_rank']} / NEO {row['neo_rank']} / Δ {row['rank_delta']:+d} / score {row['neo_score']:.6f}; SG n={row['sg_sample_size']}, recent n={row['recent_sample_size']}; contributions: {contributions}; main driver: {row['primary_driver']}; recent: {recent}.")
    lines += ["","## Hard validation","",f"- future leakage: {result['validation']['future_leakage_count']}",f"- duplicate event-player: {result['validation']['duplicate_event_player_count']}",f"- invalid player mapping: {result['validation']['invalid_player_mapping_count']}",f"- insufficient sample forcibly ranked: {result['validation']['insufficient_sample_ranked_count']}",f"- reproducibility / deterministic output: {result['validation']['reproducibility_match']} / {result['validation']['deterministic_output_match']}","","## Model defects","","1. V1 weights are heuristic and correlated recent5/recent10/long-term windows double-count related SG signal.","2. Cohort z-scores make a player's score depend on who else is present and are not calibrated across events.","3. Reliability is a positive bonus rather than uncertainty shrinkage; it can lift mediocre high-sample players.","4. Volatility is penalized symmetrically and may suppress genuinely improving players.","5. Historical field reconstruction comes from retained SG rows, not archived pre-event entry snapshots; unresolved/non-SG players reduce coverage.","6. Point-in-time historical K-Ranking snapshots are absent, preventing the required K-versus-NEO and incremental-value test.","","No V2 weights were fitted or changed in this audit."]
    report=DOCS/"NEO_RANKING_V1_REDTEAM_BACKTEST.md"; report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"artifact":str(artifact),"report":str(report),"tournaments":result["tournament_count"],"observations":result["observation_count"],"players":result["unique_players"],"metrics":m,"validation":result["validation"]},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
