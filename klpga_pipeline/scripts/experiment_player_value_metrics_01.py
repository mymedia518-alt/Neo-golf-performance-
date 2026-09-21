"""NEO Player Value Metrics Experiment 01.
Read-only descriptive experiment. No Expected Strokes, no SG, no ranking model.

Computes three candidate product metrics from verified cmpro shot transitions:
1) Miss Cost: Par4/5 tee-shot FAIRWAY vs ROUGH subsequent hole score-to-par.
2) Damage Control: outcome distribution after a Par4/5 tee-shot ends ROUGH.
3) Opportunity Conversion: birdie-or-better conversion after first green entry,
   bucketed by remaining distance.

Outputs JSON only. All values are observed; no causal claim is made.
"""
from __future__ import annotations
import argparse, json, sqlite3, sys
from collections import defaultdict
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klpga.expected_strokes.transitions import build_transition_dataset\nfrom klpga.collectors.score_record import parse_score_record_hole_par

FAIRWAY="페어웨이"; ROUGH="러프"; GREEN="그린"; HOLED="홀인"

def groups(rows):
    out=defaultdict(list)
    for r in rows:
        out[(r.player_code,r.round_number,r.hole)].append(r)
    for v in out.values(): v.sort(key=lambda x:x.shot_no)
    return out

def hole_records(rows):
    rec=[]
    for (pc,rnd,hole), hs in groups(rows).items():
        first=hs[0]
        par=first.par
        if par is None or hs[-1].end_lie != HOLED:
            continue
        strokes=len(hs)
        entry=next((s for s in hs if s.end_lie==GREEN),None)
        rec.append({
            "player_code":pc,"player_name":first.player_name,"round":rnd,"hole":hole,
            "par":par,"strokes":strokes,"to_par":strokes-par,
            "tee_end_lie":first.end_lie if first.shot_no==1 else "",
            "green_entry_remaining_yd":entry.end_distance_yd if entry else None,
        })
    return rec

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def miss_cost(recs):
    p45=[x for x in recs if x["par"] in (4,5) and x["tee_end_lie"] in (FAIRWAY,ROUGH)]
    def one(lie):
        xs=[x["to_par"] for x in p45 if x["tee_end_lie"]==lie]
        return {"n":len(xs),"avg_hole_to_par":mean(xs)}
    fw,rg=one(FAIRWAY),one(ROUGH)
    delta=None
    if fw["avg_hole_to_par"] is not None and rg["avg_hole_to_par"] is not None:
        delta=rg["avg_hole_to_par"]-fw["avg_hole_to_par"]
    return {"fairway":fw,"rough":rg,"rough_minus_fairway_to_par":delta}

def damage_control(recs):
    xs=[x for x in recs if x["par"] in (4,5) and x["tee_end_lie"]==ROUGH]
    n=len(xs)
    def cnt(fn): return sum(1 for x in xs if fn(x["to_par"]))
    par_or_better=cnt(lambda z:z<=0); bogey=cnt(lambda z:z==1); double_plus=cnt(lambda z:z>=2)
    return {
        "n":n,
        "par_or_better":{"count":par_or_better,"rate":par_or_better/n if n else None},
        "bogey":{"count":bogey,"rate":bogey/n if n else None},
        "double_or_worse":{"count":double_plus,"rate":double_plus/n if n else None},
    }

def band(d):
    if d is None: return None
    if d < 3: return "<3yd"
    if d < 6: return "3-6yd"
    if d < 10: return "6-10yd"
    if d < 15: return "10-15yd"
    return "15yd+"

def opportunity(recs):
    buckets=defaultdict(list)
    for x in recs:
        b=band(x["green_entry_remaining_yd"])
        if b: buckets[b].append(x)
    order=["<3yd","3-6yd","6-10yd","10-15yd","15yd+"]
    out={}
    for b in order:
        xs=buckets.get(b,[])
        bird=sum(1 for x in xs if x["to_par"]<=-1)
        out[b]={"n":len(xs),"birdie_or_better":bird,
                "conversion_rate":bird/len(xs) if xs else None}
    return out

def metrics(recs):
    return {"miss_cost":miss_cost(recs),"damage_control":damage_control(recs),
            "opportunity_conversion":opportunity(recs)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sqlite",type=Path,required=True)
    ap.add_argument("--game",default="2026090002")
    ap.add_argument("--player",default="김민선7")
    ap.add_argument("--output",type=Path,default=None)\n    ap.add_argument("--official-score-source",type=Path,required=True)\n    ap.add_argument("--round-tabs",default="round-one,round-two,round-three,round-four")
    a=ap.parse_args()
    if not a.sqlite.is_file(): raise SystemExit("BLOCKED: sqlite not found")
    con=sqlite3.connect(f"file:{a.sqlite.resolve()}?mode=ro",uri=True)
    try: rows=build_transition_dataset(con,a.game)
    finally: con.close()
    recs=hole_records(rows)
    player=[x for x in recs if x["player_name"]==a.player]
    if not player: raise SystemExit("BLOCKED: player not found")
    result={
        "experiment":"player_value_metrics_01",
        "game_code":a.game,
        "player":a.player,
        "methodology":{
            "observed_only":True,"expected_strokes":False,"strokes_gained":False,
            "miss_cost_definition":"Par4/5 rough tee-end avg hole-to-par minus fairway tee-end avg hole-to-par",
            "damage_control_definition":"Par4/5 holes whose tee shot ended rough; final hole outcome distribution",
            "opportunity_definition":"birdie-or-better rate by first-green-entry remaining-distance bucket",
            "causality_claimed":False
        },
        "qa":{"transition_rows":len(rows),"verified_par_round_holes":len(par_by_round_hole),"valid_terminal_holes":len(recs),"player_valid_holes":len(player)},
        "field":metrics(recs),
        "player_metrics":metrics(player),
    }
    txt=json.dumps(result,ensure_ascii=False,indent=2)
    print(txt)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(txt,encoding="utf-8")

if __name__=="__main__":
    main()
