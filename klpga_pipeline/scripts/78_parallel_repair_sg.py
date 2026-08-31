"""Parallel, restart-safe backfill of official round-specific SG identities."""
from __future__ import annotations
import json, concurrent.futures, requests, sys
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from klpga.website_v2.official_data import parse_leaderboard_html,parse_sg_html,validate_sg_record
BASE="https://klpga.co.kr"; LB="/load/leaderboard/roundLeaderboard"; SG="/load/leaderboard/strokesGained_detail"
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def worker(item):
 code,old=item; s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","X-Requested-With":"XMLHttpRequest"})
 def post(path,data):
  r=s.post(BASE+path,data=data,headers={"Referer":BASE},timeout=45); r.raise_for_status(); return r.content.decode("utf-8","replace")
 try:
  maps={}; latest=0
  needed=sorted({int(r.get("round")) for r in old.get("records",[]) if r.get("round")},reverse=True) or [4,3,2,1]
  for rnd in needed:
   lb=parse_leaderboard_html(post(LB,{"gameCode":code,"round":str(rnd)}));
   if lb: maps[rnd]={str(x.get("player")):str(x.get("player_id")) for x in lb if x.get("player_id")}; latest=max(latest,rnd)
  if not maps: raise ValueError("no round leaderboard")
  all_ids={name:pid for m in maps.values() for name,pid in m.items()}; rows=[]; unresolved=0; source_rows=0
  for rnd in (None,*range(1,latest+1)):
   html=post(SG,{"gameCode":code,"round":"" if rnd is None else str(rnd)}); source_rows+=len(BeautifulSoup(html,"html.parser").select("table tbody tr")); parsed=parse_sg_html(html,scope="tournament_cumulative" if rnd is None else "single_round",round_number=rnd); lookup=all_ids if rnd is None else maps.get(rnd,{})
   for row in parsed:
    pid=lookup.get(str(row.get("player"))); unresolved += pid is None; row.update({"player_id":pid,"identity_state":"RETAINED" if pid else "UNRESOLVED_IDENTITY","season":old.get("season"),"game_code":str(code),"tournament":old.get("event"),"source":f"{BASE}{SG} + round leaderboard {rnd or 'cumulative'}","retrieved_at":now(),"validation":validate_sg_record(row)}); rows.append(row)
  return code,{"status":"success","season":old.get("season"),"event":old.get("event"),"rows":len(rows),"retained_rows":len(rows)-unresolved,"unresolved_rows":unresolved,"source_sg_rows":source_rows,"records":rows}
 except Exception as exc: return code,{"status":"error","season":old.get("season"),"event":old.get("event"),"error":f"{type(exc).__name__}: {exc}"}
def main():
 legacy=json.loads((ROOT/"content/website_v2/sg_warehouse_checkpoint.json").read_text(encoding="utf-8")); cp=ROOT/"content/website_v2/sg_warehouse_checkpoint_corrected_v2.json"; state=json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
 todo=[(c,v) for c,v in legacy.items() if c not in state or state[c].get("status")!="success"]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
  for i,(code,res) in enumerate(ex.map(worker,todo),1):
   state[code]=res
   if i%5==0: print(f"events {i}/{len(todo)}",flush=True)
   cp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 rows=[r for e in state.values() if e.get("status")=="success" for r in e.get("records",[])]; w={"schema_version":"1.1-corrected-row-retention-v2","generated_at":now(),"events":len(state),"records":rows,"identity_rule":"round-specific official leaderboard identity; cumulative uses union of all completed round identities","legacy_manifest":"historical_sg_warehouse_legacy_manifest.json"}; (ROOT/"content/website_v2/historical_sg_warehouse_corrected_v2.json").write_text(json.dumps(w,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"events":len(state),"rows":len(rows),"unresolved":sum(e.get('unresolved_rows',0) for e in state.values())},ensure_ascii=False))
if __name__=="__main__": main()
