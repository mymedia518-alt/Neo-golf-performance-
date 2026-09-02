"""Collect every officially selectable historical K-Ranking week, read-only."""
from __future__ import annotations
import argparse,gzip,hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1];CONTENT=ROOT/"content"/"website_v2";URL="https://k-rankings.klpga.co.kr/allplayer.jsp"
def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def parse(body):
 text=body.decode("utf-8","replace");s=BeautifulSoup(text,"html.parser");selected=s.select_one('select[name="Rank_week"] option[selected]');rows=[]
 for tr in s.select("table#example tbody tr"):
  cells=tr.find_all("td");link=tr.find("a",href=lambda x:x and "player_code=" in x)
  if not cells or not link or not cells[0].get_text(strip=True).isdigit():continue
  rows.append({"rank":int(cells[0].get_text(strip=True)),"player_id":link["href"].split("player_code=")[-1].split("&")[0],"player_name":link.get_text(" ",strip=True),"ranking_points":cells[3].get_text(" ",strip=True) if len(cells)>3 else None,"total_points":cells[4].get_text(" ",strip=True) if len(cells)>4 else None,"events_played":cells[5].get_text(" ",strip=True) if len(cells)>5 else None})
 return (selected.get("value") if selected else None),rows,[x.get("value") for x in s.select('select[name="Rank_week"] option[value]') if re.fullmatch(r"\d{6}",x.get("value",''))]
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=CONTENT/"HISTORICAL_KRANKING_SNAPSHOT_INDEX_V1.json");p.add_argument("--raw-dir",type=Path,default=ROOT/"evidence"/"historical_kranking_snapshots_v1");a=p.parse_args();a.raw_dir.mkdir(parents=True,exist_ok=True)
 ses=requests.Session();ses.headers.update({"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"});base=ses.get(URL,timeout=75);base.raise_for_status();_,_,weeks=parse(base.content);retrieved=now();snapshots=[]
 for week in weeks:
  params={"Rank_week":week,"top_player":"김민솔","last_week":"null"};r=ses.get(URL,params=params,timeout=75);body=r.content;sha=hashlib.sha256(body).hexdigest();selected,rows,_=parse(body);classification="VERIFIED_HISTORICAL" if r.status_code==200 and selected==week and len(rows)>=120 else ("CURRENT_FALLBACK" if selected and selected!=week else "UNAVAILABLE")
  raw_name=f"{week}_{sha}.html.gz";gzip.open(a.raw_dir/raw_name,"wb",compresslevel=9).write(body)
  order_hash=hashlib.sha256("|".join(f'{x["rank"]}:{x["player_id"]}:{x["ranking_points"]}' for x in rows).encode()).hexdigest() if rows else None
  ranks=[x["rank"] for x in rows];player_ids=[x["player_id"] for x in rows]
  snapshots.append({"requested_week":week,"returned_week":selected,"classification":classification,"official_source":URL,"request_method":"GET","request_parameters":params,"retrieved_at":retrieved,"http_status":r.status_code,"response_sha256":sha,"response_size":len(body),"raw_evidence":raw_name,"player_count":len(rows),"official_rank_tie_count":len(ranks)-len(set(ranks)),"duplicate_player_id_count":len(player_ids)-len(set(player_ids)),"top_ranked_player":rows[0] if rows else None,"top10":rows[:10],"ranking_population_order_hash":order_hash,"records":rows if classification=="VERIFIED_HISTORICAL" else []})
  print(week,classification,len(rows),flush=True);time.sleep(.05)
 out={"schema_version":"neo_historical_kranking_snapshot_index_v1","parser_version":"91_collect_available_historical_kranking.py@v1","official_source":URL,"retrieved_at":retrieved,"publication_date_status":"K_PUBLICATION_DATE_UNVERIFIED","rank_semantics":"OFFICIAL_COMPETITION_RANK_WITH_TIES_PRESERVED","available_selector_weeks":weeks,"verified_week_count":sum(x["classification"]=="VERIFIED_HISTORICAL" for x in snapshots),"snapshots":snapshots};a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({"weeks":len(weeks),"verified":out["verified_week_count"]},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
