"""Bounded recheck for Data Center profile access failures, for the
active tournament (klpga.tournament_context).

This never rewrites frozen evidence or deletes entrants. A successful
retry updates only the mutable profile-audit record for the entries
that actually failed, and records a new timestamp per entry plus one
top-level recheck summary.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.tournament_context import load_active_tournament_context
from klpga.kranking_week import resolve_ranking_week
from klpga.kranking_profile import collect_profile

_CONTEXT = load_active_tournament_context()
AUDIT=_CONTEXT.artifact_path("data_center_profile_audit")
_, RANKING_WEEK_LABEL, RANKING_WEEK_KOREAN = resolve_ranking_week(_CONTEXT.start_date)

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def main():
    d=json.loads(AUDIT.read_text(encoding="utf-8"))
    failing=[r for r in d.get("records", []) if r.get("parse_state") != "PASS"]
    if not failing:
        print(json.dumps({"status":"NOTHING_TO_RECHECK","attempts":0},ensure_ascii=False)); return 0
    s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","Referer":"https://k-rankings.klpga.co.kr/kranking.jsp"})
    by_id={r["player_id"]:i for i,r in enumerate(d["records"])}
    recovered=[]; still_failing=[]
    for row in failing:
        pid=row["player_id"]
        result=collect_profile(pid, s, RANKING_WEEK_LABEL, RANKING_WEEK_KOREAN)
        if result["parse_state"]=="PASS":
            d["records"][by_id[pid]]=result; recovered.append(pid)
        else:
            still_failing.append(pid)
    d["recheck"]={"status":"RECOVERED" if recovered and not still_failing else ("PARTIAL" if recovered else "SOURCE_TEMPORARILY_UNAVAILABLE"),"retrieved_at":now(),"attempted":[r["player_id"] for r in failing],"recovered":recovered,"still_failing":still_failing}
    AUDIT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(d["recheck"],ensure_ascii=False))
    return 0 if not still_failing else 2
if __name__=="__main__": raise SystemExit(main())
