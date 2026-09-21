"""NEO Best Next State v1 — Kim Minsun7.
Observed-only. Ranks next-shot states only within the same par + shot number.
No Expected Strokes, no SG, no target/club recommendation, no causal claim.
"""
from __future__ import annotations
import argparse,json,sqlite3,sys,math
from collections import defaultdict
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from klpga.collectors.score_record import parse_score_record_hole_par
from klpga.expected_strokes.transitions import build_transition_dataset

TABS={1:"round-one",2:"round-two",3:"round-three",4:"round-four"}
LIES={"페어웨이","러프","벙커"}
HOLED="홀인"; GREEN="그린"

def band(d):
    if d is None:return None
    if d<100:return "<100"
    if d<120:return "100-120"
    if d<130:return "120-130"
    if d<140:return "130-140"
    if d<150:return "140-150"
    if d<175:return "150-175"
    if d<200:return "175-200"
    return "200+"

def load_pars(path,rounds):
    html=path.read_text(encoding="utf-8"); out={}
    for r in rounds:
        p=parse_score_record_hole_par(html,round_tab_id=TABS[r])
        if len(p)!=18: raise SystemExit(f"BLOCKED: {path} R{r} par count={len(p)}")
        out.update({(r,h):v for h,v in p.items()})
    return out

def wilson_lower(k,n,z=1.0):
    if not n:return None
    p=k/n; den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(".")); ap.add_argument("--min-n",type=int,default=8); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    games=["2026040004","2026060003","2026080002","2026090003"]
    states=[]
    for game in games:
        db=a.root/f"data/player_cmpro/cmpro_{game}_player_10097.sqlite"
        sr=a.root/f"data/raw_cache/score_record_sample_{game}.html"
        if not db.is_file() or not sr.is_file(): raise SystemExit(f"BLOCKED: missing source for {game}")
        con=sqlite3.connect(f"file:{db.resolve()}?mode=ro",uri=True)
        try:
            rounds=[x[0] for x in con.execute("SELECT DISTINCT round_number FROM hole_audit WHERE game_code=? AND qa_status='PASS' ORDER BY round_number",(game,))]
            pars=load_pars(sr,rounds); rows=build_transition_dataset(con,game,par_by_round_hole=pars)
        finally: con.close()
        g=defaultdict(list)
        for x in rows:
            if x.player_code=="10097": g[(x.round_number,x.hole)].append(x)
        for (rnd,hole),hs in g.items():
            hs.sort(key=lambda x:x.shot_no)
            if not hs or hs[-1].end_lie!=HOLED: continue
            final_to_par=len(hs)-hs[0].par
            for s in hs:
                b=band(s.start_distance_yd)
                if s.shot_no<2 or s.start_lie not in LIES or b is None: continue
                states.append({"game":game,"round":rnd,"hole":hole,"par":s.par,"shot_no":s.shot_no,"lie":s.start_lie,"band":b,"green":s.end_lie==GREEN,"end_green_distance":s.end_distance_yd if s.end_lie==GREEN else None,"birdie_or_better":final_to_par<=-1,"par_or_better":final_to_par<=0,"bogey_or_worse":final_to_par>=1})

    grouped=defaultdict(list)
    for x in states: grouped[(x["par"],x["shot_no"],x["lie"],x["band"])].append(x)
    cells=[]
    for key,xs in grouped.items():
        par,shot,lie,b=key; n=len(xs); pb=sum(x["par_or_better"] for x in xs); gr=sum(x["green"] for x in xs)
        rem=[x["end_green_distance"] for x in xs if x["end_green_distance"] is not None]
        events=len({x["game"] for x in xs})
        status="READY" if n>=a.min_n and events>=2 else "HOLD"
        bird=sum(x["birdie_or_better"] for x in xs)
        cells.append({"par":par,"shot_no":shot,"lie":lie,"distance_band":b,"n":n,"events":events,"green_reach_rate":gr/n,"avg_remaining_on_green_yd":sum(rem)/len(rem) if rem else None,"birdie_or_better_rate":bird/n,"par_or_better_rate":pb/n,"bogey_or_worse_rate":1-pb/n,"conservative_birdie_or_better":wilson_lower(bird,n),"conservative_par_or_better":wilson_lower(pb,n),"status":status})
    ready=[x for x in cells if x["status"]=="READY"]
    contexts=defaultdict(list)
    for x in ready: contexts[(x["par"],x["shot_no"])].append(x)
    rankings={}
    for k,xs in contexts.items():
        attack=sorted(xs,key=lambda x:(x["conservative_birdie_or_better"],x["green_reach_rate"],x["n"]),reverse=True)
        protect=sorted(xs,key=lambda x:(x["conservative_par_or_better"],-x["bogey_or_worse_rate"],x["n"]),reverse=True)
        rankings[f"Par{k[0]}|shot{k[1]}"]={"ATTACK":[dict(rank=i+1,**x) for i,x in enumerate(attack)],"PROTECT":[dict(rank=i+1,**x) for i,x in enumerate(protect)]}
    result={"engine":"best_next_state_v2_attack_protect","player":"김민선7","methodology":{"observed_only":True,"expected_strokes":False,"strokes_gained":False,"target_recommendation":False,"club_recommendation":False,"causality_claimed":False,"comparison_control":"same par + same shot_no","ready_gate":f"n>={a.min_n} and events>=2","ranking":"ATTACK = Wilson lower bound of observed birdie-or-better; PROTECT = Wilson lower bound of observed par-or-better. Descriptive only."},"qa":{"games":games,"state_rows":len(states),"cells":len(cells),"ready_cells":len(ready),"hold_cells":len(cells)-len(ready)},"rankings":rankings,"all_cells":sorted(cells,key=lambda x:(x["par"],x["shot_no"],x["lie"],x["distance_band"]))}
    txt=json.dumps(result,ensure_ascii=False,indent=2); print(txt); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(txt,encoding="utf-8")
if __name__=="__main__": main()
