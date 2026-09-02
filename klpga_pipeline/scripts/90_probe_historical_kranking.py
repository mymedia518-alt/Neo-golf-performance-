"""Read-only forensic probe of official historical K-Ranking behavior."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; CONTENT=ROOT/"content"/"website_v2"
BASE="https://k-rankings.klpga.co.kr/"; WEEKS=("202630","202620","202535","202435")

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def parse(body:bytes)->dict:
    text=body.decode("utf-8","replace"); soup=BeautifulSoup(text,"html.parser")
    selected=soup.select_one('select[name="Rank_week"] option[selected]')
    selected_value=selected.get("value") if selected else None
    selected_label=selected.get_text(" ",strip=True) if selected else None
    rows=[]
    table=soup.select_one("table#example")
    if table:
        for tr in table.select("tbody tr"):
            cells=tr.find_all("td"); link=tr.find("a",href=lambda x:x and "player_code=" in x)
            if not cells or not link: continue
            rank_text=cells[0].get_text(" ",strip=True)
            if not rank_text.isdigit(): continue
            pid=link.get("href").split("player_code=")[-1].split("&")[0]
            rows.append({"rank":int(rank_text),"player_id":pid,"player_name":link.get_text(" ",strip=True),"ranking_value":cells[3].get_text(" ",strip=True) if len(cells)>3 else None})
    embedded=re.findall(r'\{"id":\s*(\d+),"text":\s*"([^"]+)',text)
    champion=re.search(r"<strong>RANK\s*1</strong>\s*([^<]+)",text)
    population=rows or [{"rank":i,"player_id":pid,"player_name":name,"ranking_value":None} for i,(pid,name) in enumerate(embedded,1)]
    digest=hashlib.sha256("|".join(f'{r["rank"]}:{r["player_id"]}:{r["player_name"]}:{r["ranking_value"]}' for r in population).encode()).hexdigest() if population else None
    return {"selected_week":selected_value,"selected_week_label":selected_label,"table_player_count":len(rows),"embedded_player_count":len(embedded),"player_count":len(population),"top_ranked_player_id":population[0]["player_id"] if population else None,"top_ranked_player_name":population[0]["player_name"] if population else (champion.group(1).strip() if champion else None),"top10":population[:10],"ranking_population_order_hash":digest}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=CONTENT/"HISTORICAL_KRANKING_RECOVERY_AUDIT_V1.json");parser.add_argument("--evidence-dir",type=Path,default=ROOT/"evidence"/"historical_kranking_v1");args=parser.parse_args();args.evidence_dir.mkdir(parents=True,exist_ok=True)
    session=requests.Session();session.headers.update({"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
    retrieved=now(); probes=[]; bodies={}
    methods=(("POST","allplayer.jsp","Rank_week"),("GET","allplayer.jsp","Rank_week"),("POST","index.jsp","Rank_week"),("POST","kranking.jsp","Rank_week"),("POST","allplayer.jsp","rank_week"),("POST","allplayer.jsp","rankWeek"))
    for week in WEEKS:
        for method,endpoint,key in methods:
            params={key:week,"top_player":"김민솔","last_week":"null"}; url=BASE+endpoint
            try:
                response=session.request(method,url,params=params if method=="GET" else None,data=params if method=="POST" else None,timeout=75)
                body=response.content; sha=hashlib.sha256(body).hexdigest(); parsed=parse(body); bodies.setdefault(sha,body)
                probes.append({"requested_week":week,"endpoint":url,"method":method,"parameters":params,"retrieved_at":retrieved,"http_status":response.status_code,"response_sha256":sha,"response_size":len(body),**parsed})
            except requests.RequestException as exc:
                probes.append({"requested_week":week,"endpoint":url,"method":method,"parameters":params,"retrieved_at":retrieved,"http_status":None,"error":str(exc),"classification":"UNAVAILABLE"})
    current=[p for p in probes if p.get("embedded_player_count",0)>=120 and p.get("top_ranked_player_id")]
    current_hash=current[0]["ranking_population_order_hash"] if current else None
    for p in probes:
        if "classification" in p: continue
        selected=p.get("selected_week"); has_table=p.get("table_player_count",0)>=120
        differs=p.get("ranking_population_order_hash") not in (None,current_hash)
        requested_selected=selected==p["requested_week"]
        if has_table and requested_selected and differs: cls="VERIFIED_HISTORICAL"
        elif p.get("player_count",0)>=120 and not differs: cls="CURRENT_FALLBACK"
        elif p.get("player_count",0)>0 or requested_selected: cls="PARTIAL"
        else: cls="UNAVAILABLE"
        p["differs_from_current_w35"]=differs; p["requested_week_selected"]=requested_selected;p["classification"]=cls
    for sha,body in bodies.items(): (args.evidence_dir/f"response_{sha}.html").write_bytes(body)
    result={"schema_version":"neo_historical_kranking_recovery_audit_v1","parser_version":"90_probe_historical_kranking.py@v1","official_service":BASE,"retrieved_at":retrieved,"tested_weeks":list(WEEKS),"probe_count":len(probes),"unique_response_count":len(bodies),"verified_historical_weeks":sorted({p["requested_week"] for p in probes if p["classification"]=="VERIFIED_HISTORICAL"}),"conclusion":"HISTORICAL_RECOVERY_UNAVAILABLE" if not any(p["classification"]=="VERIFIED_HISTORICAL" for p in probes) else "HISTORICAL_RECOVERY_PARTIAL_OR_AVAILABLE","probes":probes,"raw_evidence":{"directory":str(args.evidence_dir.relative_to(ROOT)),"deduplication":"one immutable response per unique SHA-256"}}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:result[k] for k in ("probe_count","unique_response_count","verified_historical_weeks","conclusion")},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
