"""Bounded recheck for Data Center profile access failures.

This never rewrites frozen evidence or deletes entrants. A successful retry
updates only the mutable profile-audit record and records a new timestamp.
"""
from __future__ import annotations
import json, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; C=ROOT/"content"/"website_v2"
AUDIT=C/"OK_OPEN_2026_DATA_CENTER_PROFILE_AUDIT.json"
URL="https://k-rankings.klpga.co.kr/playerprofile.jsp?player_code=7963&top_player=%EA%B9%80%EB%AF%BC%EC%86%94&last_week=2026%EB%85%84%2035%EC%A3%BC"
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def main():
    s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","Referer":"https://k-rankings.klpga.co.kr/kranking.jsp"}); error=None
    for attempt in range(3):
        try:
            r=s.get(URL,timeout=30); r.raise_for_status(); soup=BeautifulSoup(r.content.decode("utf-8","replace"),"html.parser")
            name=soup.select_one("table.rank-table .player-info h4")
            if not name: raise ValueError("profile parsed without current player name")
            d=json.loads(AUDIT.read_text(encoding="utf-8")); d["recheck"]={"status":"RECOVERED","retrieved_at":now(),"attempts":attempt+1}; AUDIT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print("RECOVERED"); return 0
        except (requests.RequestException, ValueError) as exc:
            error=str(exc); time.sleep(attempt+1)
    print(json.dumps({"status":"SOURCE_TEMPORARILY_UNAVAILABLE","player_id":"7963","attempts":3,"error":error},ensure_ascii=False)); return 2
if __name__=="__main__": raise SystemExit(main())
