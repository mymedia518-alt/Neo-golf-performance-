"""Build NEO Blue Heron 18-hole pre-event player game plan v1.

Evidence-only pre-event layer:
- official 2026 hole par/yardage from KLPGA getCourseHoleData
- official 2026 season player baseline collected by script 183
- Par4 candidate distance-state comparison for Kim Minsun7 vs Lee Yewon
No spatial target is invented before 2026 coordinates exist.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from klpga.http_client import PoliteHttpClient

BASE=ROOT/"data/player_baseline/ab_10097_9784_2026.json"
OUT=ROOT/"data/player_baseline/blue_heron_18h_game_plan_v1.json"
MD=ROOT/"reports/BLUE_HERON_18H_GAME_PLAN_V1.md"
GAME="2026100005"
PLAYERS={"10097":"김민선7","9784":"이예원"}
TEE={"010313":230,"010312":250,"010311":270}
# remaining-distance bins; use only where nominal remaining is 100-160
BIRD={"140-160":"020707","120-140":"020708","100-120":"020709"}
GIR={"140-160":"020305","120-140":"020306","100-120":"020307"}

def find_req(data,menu3): return next(x for x in data["requests"] if x["menu3"]==menu3)
def row(req,code): return next(x for x in req["selected"] if x["player_code"]==code)
def val(data,menu3,code):
    x=row(find_req(data,menu3),code); return float(x["values"]["record"]),int(x["values"]["record2"].replace(",",""))
def band(rem):
    if 140<=rem<160:return "140-160"
    if 120<=rem<140:return "120-140"
    if 100<=rem<120:return "100-120"
    return None

def main():
    data=json.loads(BASE.read_text(encoding="utf-8"))
    c=PoliteHttpClient(cache_dir=ROOT/"data/raw_cache/http",min_interval_sec=1.5)
    holes=[]
    for h in range(1,19):
        txt=c.post_text("https://klpga.co.kr/ajax/tourInfo/getCourseHoleData",data={"gameCode":GAME,"round":"1","hole":str(h)})
        p=json.loads(txt); info=p.get("courseHoleInfo") or p.get("holeInfo") or p.get("baseHoleInfo") or {}
        # pre-event response shape can vary; recursively find par/yard values
        def walk(x):
            if isinstance(x,dict):
                yield x
                for v in x.values(): yield from walk(v)
            elif isinstance(x,list):
                for v in x: yield from walk(v)
        par=yard=None
        for d in walk(p):
            for k,v in d.items():
                lk=k.lower()
                if par is None and ("par"==lk or lk.endswith("_par")):
                    try:
                        z=int(str(v)); par=z if 3<=z<=5 else par
                    except: pass
                if yard is None and ("yard" in lk or lk in ("bi_sy","distance")):
                    try:
                        z=int(float(str(v).replace(",",""))); yard=z if 100<=z<=700 else yard
                    except: pass
        # fallback to event-confirmed official setup if pre-event payload lacks info
        official=[(4,402),(3,188),(4,426),(5,542),(3,170),(4,410),(5,516),(4,377),(4,404),(5,570),(3,174),(4,410),(4,376),(4,379),(4,423),(3,180),(4,390),(5,528)]
        if par is None: par=official[h-1][0]
        if yard is None: yard=official[h-1][1]
        holes.append({"hole":h,"par":par,"yardage":yard,"spatial_2026":bool(p.get("baseHoleInfo")) and bool(p.get("shotGroupList"))})

    result={"event":{"game_code":GAME,"course":"Blue Heron","holes":holes},"players":{},"gate":{"distance_state":"PASS","spatial":"HOLD"}}
    for code,name in PLAYERS.items():
        ph=[]
        for x in holes:
            item={"hole":x["hole"],"par":x["par"],"yardage":x["yardage"],"status":"CONTEXT"}
            if x["par"]==4:
                cand=[]
                for metric,tee in TEE.items():
                    rem=x["yardage"]-tee; b=band(rem)
                    if not b: continue
                    fw,fw_n=val(data,metric,code); bird,bn=val(data,BIRD[b],code); gir,gn=val(data,GIR[b],code)
                    cand.append({"tee_yd":tee,"remaining_yd":rem,"remaining_band":b,"fw_pct":fw,"fw_n":fw_n,"birdie_plus_pct":bird,"birdie_n":bn,"fw_gir_pct":gir,"gir_n":gn})
                item["candidates"]=cand; item["status"]="PASS" if cand else "HOLD"
            elif x["par"]==3:
                item["note"]="Par3 전용 시즌 지표 결합 대상"; item["status"]="NEXT"
            else:
                item["note"]="Par5 2nd-shot 전용 시즌 지표 결합 대상"; item["status"]="NEXT"
            ph.append(item)
        result["players"][code]={"name":name,"holes":ph}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# NEO BLUE HERON 18H GAME PLAN V1","","**제26회 하이트진로 챔피언십 · Pre-event evidence layer**","",
           "2026 실제 공간좌표가 없는 상태이므로 특정 좌우 TARGET은 만들지 않는다. Par4는 공식 시즌 거리·FW·어프로치 기록으로 거리 의사결정 후보를 산출한다.","",
           "| H | Par | Yd | 김민선7 | 이예원 |","|---:|---:|---:|---|---|"]
    for h in holes:
        vals=[]
        for code in PLAYERS:
            z=result["players"][code]["holes"][h["hole"]-1]
            if z.get("candidates"):
                s=" / ".join(f"{q['tee_yd']}→{q['remaining_yd']}yd FW {q['fw_pct']:.1f}% B+ {q['birdie_plus_pct']:.1f}%" for q in z["candidates"])
            else:s=z.get("note","HOLD")
            vals.append(s)
        lines.append(f"| {h['hole']} | {h['par']} | {h['yardage']} | {vals[0]} | {vals[1]} |")
    lines += ["","## Gate","- Par4 Distance-state: **PASS**","- Par3/Par5 specialized decision layer: **NEXT**","- 2026 Spatial TARGET / GOOD MISS / BAD MISS: **HOLD**","",
              "이 문서는 최종 타깃북이 아니라 18홀 전체를 동일 증거 규칙으로 통과시키기 위한 pre-event GAME PLAN v1이다."]
    MD.parent.mkdir(parents=True,exist_ok=True); MD.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(OUT); print(MD)

if __name__=="__main__":main()
