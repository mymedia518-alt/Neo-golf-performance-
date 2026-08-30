"""Resumable multi-event official KLPGA SG warehouse collector.

Uses the established getGameList, roundLeaderboard, and strokesGained_detail
surfaces.  Checkpoint state is written after every event; failures are
recorded and never replaced with synthetic values.
"""
from __future__ import annotations
import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path
import requests
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from klpga.collectors.tournaments import fetch_game_list, filter_completed_regular_tour
from klpga.http_client import PoliteHttpClient
from klpga.website_v2.official_data import parse_leaderboard_html, parse_sg_html, validate_sg_record
from klpga.analytics.sg_performance import standardize_player_name

BASE="https://klpga.co.kr"; SG_PATH="/load/leaderboard/strokesGained_detail"; LB_PATH="/load/leaderboard/roundLeaderboard"

def _post(path, data):
    r=requests.post(BASE+path,data=data,headers={"X-Requested-With":"XMLHttpRequest","Referer":BASE},timeout=60); r.raise_for_status(); r.encoding="utf-8"; return r.text

def collect(seasons: list[int], checkpoint: Path, output: Path) -> dict:
    state=json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {}
    events=[]
    client=PoliteHttpClient(cache_dir=ROOT/"data/raw_cache/http")
    for season in seasons:
        listings=filter_completed_regular_tour(fetch_game_list(client,season))
        events.extend(listings)
    for listing in sorted({e.game_code:e for e in events}.values(), key=lambda e:(e.end_date or 0,e.game_code or "")):
        code=str(listing.game_code)
        if state.get(code,{}).get("status")=="success" and state.get(code,{}).get("records"): continue
        try:
            lb=[]; latest_round=0
            for candidate_round in (4,3,2,1):
                parsed_lb=parse_leaderboard_html(_post(LB_PATH,{"gameCode":code,"round":str(candidate_round)}))
                if parsed_lb:
                    lb=parsed_lb; latest_round=candidate_round; break
            if not lb: raise ValueError("roundLeaderboard returned no rows for rounds 4..1")
            ids={str(x.get("player")):str(x.get("player_id")) for x in lb}
            rows=[]; sg_response_rows=0; parsed_rows=0
            for rnd in (None,*range(1,latest_round+1)):
                html=_post(SG_PATH,{"gameCode":code,"round":"" if rnd is None else str(rnd)})
                from bs4 import BeautifulSoup
                sg_response_rows += len(BeautifulSoup(html,"html.parser").select("table tbody tr"))
                parsed=parse_sg_html(html,scope="tournament_cumulative" if rnd is None else "single_round",round_number=rnd)
                parsed_rows += len(parsed)
                for row in parsed:
                    row.update({"player_id":ids.get(str(row.get("player"))),"season":listing.season,"game_code":code,"tournament":listing.game_title,"date":(listing.end_date.isoformat() if listing.end_date else None),"source":f"{BASE}{SG_PATH} POST gameCode={code}, round blank/1..4","retrieved_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"validation":validate_sg_record(row)})
                    if row["player_id"]: rows.append(row)
            reason = None if rows else ("OFFICIAL_SG_NOT_AVAILABLE" if sg_response_rows == 0 else "PARSER/HTML_STRUCTURE_ISSUE" if parsed_rows == 0 else "UNKNOWN")
            state[code]={"status":"success","season":listing.season,"event":listing.game_title,"rows":len(rows),"records":rows,"no_row_reason":reason,"sg_response_rows":sg_response_rows,"parsed_rows":parsed_rows}
        except Exception as exc:
            state[code]={"status":"error","season":listing.season,"event":listing.game_title,"error":f"{type(exc).__name__}: {exc}"}
        checkpoint.parent.mkdir(parents=True,exist_ok=True); checkpoint.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    all_rows=[]
    for entry in state.values():
        if entry.get("status")!="success": continue
        for row in entry.get("records",[]):
            row=dict(row); row.update(standardize_player_name(row.get("player"),row.get("player_id"))); all_rows.append(row)
    out={"schema_version":"1.0","generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"seasons":seasons,"attempted_events":len([e for e in state.values() if e.get("status")=="success"]),"events":len({r.get("game_code") for r in all_rows if r.get("game_code")}),"records":all_rows,"checkpoint":str(checkpoint.name),"provenance":"official KLPGA public endpoints; resumable candidate-only collection"}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--seasons",default="2026,2025"); ap.add_argument("--checkpoint",default=str(ROOT/"content/website_v2/sg_warehouse_checkpoint.json")); ap.add_argument("--output",default=str(ROOT/"content/website_v2/historical_sg_warehouse.json")); a=ap.parse_args(); out=collect([int(x) for x in a.seasons.split(",")],Path(a.checkpoint),Path(a.output)); print(f"events={out['events']} rows={len(out['records'])}")
if __name__=="__main__": main()
