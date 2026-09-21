"""Kim Minsun7 multi-event observed-only replication + Decision Map readiness.
No Expected Strokes, no SG, no causal claim.
"""
from __future__ import annotations
import argparse,json,sqlite3,sys
from collections import defaultdict
from pathlib import Path
SRC_ROOT=Path(__file__).resolve().parents[1]/"src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from klpga.collectors.score_record import parse_score_record_hole_par
from klpga.expected_strokes.transitions import build_transition_dataset

ROUND_TABS={1:"round-one",2:"round-two",3:"round-three",4:"round-four"}
ROUGH="러프"; GREEN="그린"; HOLED="홀인"

def load_pars(path,rounds):
    html=path.read_text(encoding="utf-8"); out={}
    for rnd in rounds:
        pars=parse_score_record_hole_par(html,round_tab_id=ROUND_TABS[rnd])
        if len(pars)!=18: raise SystemExit(f"BLOCKED: R{rnd} par count={len(pars)}")
        out.update({(rnd,h):p for h,p in pars.items()})
    if len(out)!=18*len(rounds): raise SystemExit("BLOCKED: verified par total mismatch")
    return out

def db_rounds(con,game):
    return [r[0] for r in con.execute("SELECT DISTINCT round_number FROM hole_audit WHERE game_code=? AND qa_status='PASS' ORDER BY round_number",(game,))]

def reconstruct(rows):
    g=defaultdict(list)
    for r in rows:g[(r.player_code,r.round_number,r.hole)].append(r)
    holes=[]; states=[]
    for (_,rnd,hole),hs in g.items():
        hs.sort(key=lambda x:x.shot_no)
        if not hs or hs[-1].end_lie!=HOLED: continue
        for s in hs:
            if s.shot_no>=2 and s.start_distance_yd is not None:
                states.append({"round":rnd,"hole":hole,"par":s.par,"shot_no":s.shot_no,"start_lie":s.start_lie or "UNKNOWN","start_distance_yd":s.start_distance_yd,"end_lie":s.end_lie or "UNKNOWN","end_distance_yd":s.end_distance_yd,"final_to_par":len(hs)-s.par})
        if hs[0].par!=4 or hs[0].end_lie!=ROUGH: continue
        second=next((x for x in hs if x.shot_no==2),None)
        third=next((x for x in hs if x.shot_no==3),None)
        holes.append({"round":rnd,"hole":hole,"to_par":len(hs)-4,"second_start_distance_yd":second.start_distance_yd if second else None,"second_reached_green":bool(second and second.end_lie==GREEN),"second_end_distance_yd":second.end_distance_yd if second else None,"second_end_lie":second.end_lie or "UNKNOWN" if second else None,"third_start_distance_yd":third.start_distance_yd if third else None,"third_end_distance_yd":third.end_distance_yd if third else None,"third_end_lie":third.end_lie or "UNKNOWN" if third else None})
    return holes,states

def outcome(xs):
    n=len(xs); pb=sum(x["to_par"]<=0 for x in xs); b=sum(x["to_par"]==1 for x in xs); d=sum(x["to_par"]>=2 for x in xs)
    return {"n":n,"par_or_better":pb,"par_or_better_rate":pb/n if n else None,"bogey":b,"double_or_worse":d}

def distband(d):
    if d<100:return "<100"
    if d<120:return "100-120"
    if d<130:return "120-130"
    if d<140:return "130-140"
    if d<150:return "140-150"
    if d<175:return "150-175"
    if d<200:return "175-200"
    return "200+"

def decision_summary(states):
    bins={}
    for lie in ("페어웨이","러프","벙커","UNKNOWN"):
        for band in ("<100","100-120","120-130","130-140","140-150","150-175","175-200","200+"):
            xs=[x for x in states if x["start_lie"]==lie and distband(x["start_distance_yd"])==band]
            if not xs: continue
            green=sum(x["end_lie"]==GREEN for x in xs)
            rem=[x["end_distance_yd"] for x in xs if x["end_lie"]==GREEN]
            bins[f"{lie}|{band}"]={"n":len(xs),"green_reach":green,"green_reach_rate":green/len(xs),"avg_remaining_on_green_yd":sum(rem)/len(rem) if rem else None,"par_or_better_final":sum(x["final_to_par"]<=0 for x in xs),"par_or_better_final_rate":sum(x["final_to_par"]<=0 for x in xs)/len(xs)}
    return bins

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(".")); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    games=[
      ("2026040004",a.root/"data/player_cmpro/cmpro_2026040004_player_10097.sqlite",a.root/"data/raw_cache/score_record_sample_2026040004.html"),
      ("2026060003",a.root/"data/player_cmpro/cmpro_2026060003_player_10097.sqlite",a.root/"data/raw_cache/score_record_sample_2026060003.html"),
      ("2026080002",a.root/"data/player_cmpro/cmpro_2026080002_player_10097.sqlite",a.root/"data/raw_cache/score_record_sample_2026080002.html"),
      ("2026090003",a.root/"data/player_cmpro/cmpro_2026090003_player_10097.sqlite",a.root/"data/raw_cache/score_record_sample_2026090003.html")]
    result={"experiment":"kim_multi_event_error_chain_decision_map_01","methodology":{"observed_only":True,"expected_strokes":False,"strokes_gained":False,"causality_claimed":False},"baseline_note":"2026090002 Hana is intentionally excluded from this local run because its validated full DB lives in a separate worktree; compare against the already validated Hana metrics separately.","events":{}}
    all_states=[]; total_holes=0
    for game,db,score in games:
        if not db.is_file(): raise SystemExit(f"BLOCKED: missing DB {db}")
        if not score.is_file(): raise SystemExit(f"BLOCKED: missing scoreRecord {score}")
        con=sqlite3.connect(f"file:{db.resolve()}?mode=ro",uri=True)
        try:
            rounds=db_rounds(con,game)
            if not rounds: raise SystemExit(f"BLOCKED: no PASS rounds {game}")
            pars=load_pars(score,rounds)
            trans=build_transition_dataset(con,game,par_by_round_hole=pars)
        finally: con.close()
        player=[x for x in trans if x.player_code=="10097"]
        holes,states=reconstruct(player); all_states+=states
        played=len({(x.round_number,x.hole) for x in player}); total_holes+=played
        misses=[x for x in holes if not x["second_reached_green"]]
        rem=[x["second_end_distance_yd"] for x in misses if x["second_end_distance_yd"] is not None]
        result["events"][game]={"qa":{"rounds":rounds,"verified_par_holes":len(pars),"transition_rows":len(player),"played_holes":played},"par4_tee_rough":outcome(holes),"second_green_reach":{"count":sum(x["second_reached_green"] for x in holes),"rate":sum(x["second_reached_green"] for x in holes)/len(holes) if holes else None},"second_miss":{"n":len(misses),"avg_remaining_yd":sum(rem)/len(rem) if rem else None,"outcome":outcome(misses)},"decision_map_bins":decision_summary(states)}
    result["qa"]={"event_count":len(result["events"]),"total_played_holes":total_holes,"decision_state_rows":len(all_states)}
    result["combined_decision_map_bins"]=decision_summary(all_states)
    txt=json.dumps(result,ensure_ascii=False,indent=2); print(txt); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(txt,encoding="utf-8")
if __name__=="__main__":main()
