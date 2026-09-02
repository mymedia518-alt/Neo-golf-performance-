"""Reconcile historical SG rows using round-specific official identities."""
from __future__ import annotations
import json, requests
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from klpga.website_v2.official_data import parse_leaderboard_html, parse_sg_html, validate_sg_record
BASE="https://klpga.co.kr"; LB="/load/leaderboard/roundLeaderboard"; SG="/load/leaderboard/strokesGained_detail"
def post(s,path,data):
 r=s.post(BASE+path,data=data,headers={"X-Requested-With":"XMLHttpRequest","Referer":BASE},timeout=45); r.raise_for_status(); return r.content.decode("utf-8","replace")
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def main():
 legacy=json.loads((ROOT/"content/website_v2/sg_warehouse_checkpoint.json").read_text(encoding="utf-8")); out={}; s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0"})
 for i,(code,old) in enumerate(legacy.items(),1):
  try:
   maps={}; latest=0
   for rnd in (4,3,2,1):
    lb=parse_leaderboard_html(post(s,LB,{"gameCode":code,"round":str(rnd)}))
    if lb: maps[rnd]={str(x.get("player")):str(x.get("player_id")) for x in lb if x.get("player_id")}; latest=max(latest,rnd)
   if not maps: raise ValueError("no official round leaderboard")
   rows=[]; source_rows=0; parsed_rows=0; unresolved=0
   for rnd in (None,*range(1,latest+1)):
    html=post(s,SG,{"gameCode":code,"round":"" if rnd is None else str(rnd)}); source_rows += len(BeautifulSoup(html,"html.parser").select("table tbody tr"))
    parsed=parse_sg_html(html,scope="tournament_cumulative" if rnd is None else "single_round",round_number=rnd); parsed_rows += len(parsed)
    lookup=maps.get(latest,{}) if rnd is None else maps.get(int(rnd),{})
    for row in parsed:
     pid=lookup.get(str(row.get("player"))); state="RETAINED" if pid else "UNRESOLVED_IDENTITY"; unresolved += pid is None
     row.update({"player_id":pid,"identity_state":state,"season":old.get("season"),"game_code":str(code),"tournament":old.get("event"),"source":f"{BASE}{SG} + round leaderboard {rnd or 'cumulative'}","retrieved_at":now(),"validation":validate_sg_record(row)}) ; rows.append(row)
   out[code]={"status":"success","season":old.get("season"),"event":old.get("event"),"rows":len(rows),"retained_rows":len(rows)-unresolved,"unresolved_rows":unresolved,"source_sg_rows":source_rows,"parsed_rows":parsed_rows,"records":rows}
  except Exception as exc: out[code]={"status":"error","season":old.get("season"),"event":old.get("event"),"error":f"{type(exc).__name__}: {exc}"}
  if i%5==0: print(f"events {i}/{len(legacy)}",flush=True)
  (ROOT/"content/website_v2/sg_warehouse_checkpoint_corrected.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 rows=[r for e in out.values() if e.get("status")=="success" for r in e.get("records",[])]
 warehouse={"schema_version":"1.1-corrected-row-retention","generated_at":now(),"events":len(out),"records":rows,"identity_rule":"round-specific official leaderboard identity; cumulative uses latest completed round","legacy_manifest":"historical_sg_warehouse_legacy_manifest.json"}
 (ROOT/"content/website_v2/historical_sg_warehouse_corrected.json").write_text(json.dumps(warehouse,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"events":len(out),"rows":len(rows),"unresolved":sum(e.get("unresolved_rows",0) for e in out.values())},ensure_ascii=False))
if __name__=="__main__": main()
