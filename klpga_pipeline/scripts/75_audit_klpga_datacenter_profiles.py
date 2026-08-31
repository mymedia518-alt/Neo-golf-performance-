"""Audit current KLPGA Data Center player profiles for the frozen OK field."""
from __future__ import annotations
import json, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; C=ROOT/"content"/"website_v2"
ENTRY=C/"OK_OPEN_2026_ENTRY_SNAPSHOT.json"; URL="https://k-rankings.klpga.co.kr/playerprofile.jsp"; CANONICAL_RANKING="https://k-rankings.klpga.co.kr/kranking.jsp"

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def text(node): return node.get_text(" ",strip=True) if node else None
def collect(pid, session):
    u=URL+f"?player_code={pid}&top_player=김민솔&last_week=2026년 35주"
    exc = None
    for attempt in range(3):
        try:
            r=session.get(u,timeout=30); r.raise_for_status(); break
        except requests.RequestException as err:
            exc = err; time.sleep(1.0 * (attempt + 1))
    else:
        return {"player_id":str(pid),"current_player_name":None,"current_k_ranking":None,"current_team":None,"ranking_points":None,"total_points":None,"events_played":None,"ranking_date":"2026-W35","official_source":u,"retrieved_at":now(),"parse_state":"ACCESS_FAILURE","team_state":"ACCESS_FAILURE","error":str(exc)}
    soup=BeautifulSoup(r.content.decode("utf-8","replace"),"html.parser")
    rank=text(soup.select_one("table.rank-table th.rank h1")); name=text(soup.select_one("table.rank-table .player-info h4"));
    vals=[text(x) for x in soup.select("table.point-table tbody td h4")]
    # rows: team, ranking points, total points, events played
    team=vals[0] if len(vals)>0 else None; rp=vals[1] if len(vals)>1 else None; total=vals[2] if len(vals)>2 else None; events=vals[3] if len(vals)>3 else None
    def num(v):
        try:return float(v.replace(",","")) if v is not None else None
        except ValueError:return None
    return {"player_id":str(pid),"current_player_name":name,"current_k_ranking":int(rank) if rank and rank.isdigit() else None,"current_team":team or None,"ranking_points":num(rp),"total_points":num(total),"events_played":int(events) if events and events.isdigit() else None,"ranking_date":"2026-W35","official_source":u,"retrieved_at":now(),"parse_state":"PASS" if name and rank else "FAIL","team_state":"OFFICIAL_BLANK" if name and not team else ("PARSED" if team else "UNKNOWN")}

def main():
    entries=json.loads(ENTRY.read_text(encoding="utf-8"))["entries"]; s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","Referer":CANONICAL_RANKING,"Accept-Language":"ko-KR,ko;q=0.9"}); s.get(CANONICAL_RANKING,timeout=30).raise_for_status()
    records=[]
    for i,e in enumerate(entries,1):
        records.append(collect(e["player_id"],s));
        if i%20==0: print(f"profiles {i}/{len(entries)}",flush=True)
        time.sleep(.12)
    controls=[collect("11134",s), collect("10725",s)]
    out={"schema_version":"neo_klpga_datacenter_profile_audit_v1","game_code":"2026120001","source_surface":"KLPGA Data Center · K-RANKING | PLAYER PROFILE","official_source":CANONICAL_RANKING,"profile_source":URL,"ranking_week":"2026-W35","retrieved_at":now(),"entry_count":len(records),"records":records,"control_cases":controls,"coverage":{"name":sum(bool(r["current_player_name"]) for r in records),"k_ranking":sum(r["current_k_ranking"] is not None for r in records),"team":sum(bool(r["current_team"]) for r in records),"ranking_points":sum(r["ranking_points"] is not None for r in records),"total_points":sum(r["total_points"] is not None for r in records),"events_played":sum(r["events_played"] is not None for r in records),"parse_failures":sum(r["parse_state"]!="PASS" for r in records),"official_blank_team":sum(r["team_state"]=="OFFICIAL_BLANK" for r in records)}}
    (C/"OK_OPEN_2026_DATA_CENTER_PROFILE_AUDIT.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n"); print(json.dumps(out["coverage"],ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
