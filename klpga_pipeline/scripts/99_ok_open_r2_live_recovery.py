from __future__ import annotations
import datetime, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
CONTENT=ROOT/"content"/"website_v2"
STATE=CONTENT/"OK_OPEN_STAGE_STATE.json"
SNAP=CONTENT/"OK_OPEN_2026_R2_LIVE_SNAPSHOT.json"
GAME="2026120001"
sys.path.insert(0,str(ROOT/"src"))
from klpga.collectors.leaderboard import fetch_round_leaderboard
from klpga.collectors.group_page import fetch_group_page_html
from klpga.parsers.group_page_parser import parse_round_grouping
from klpga.parsers.round_progress import resolve_round_progress
from klpga.http_client import PoliteHttpClient

def main():
    client=PoliteHttpClient(cache_dir=ROOT/"data"/"raw_cache"/"r2_active")
    rows=fetch_round_leaderboard(client,GAME,2,use_cache=False)
    if not rows: raise RuntimeError("official R2 returned zero rows")

    group_status,group_html=fetch_group_page_html(client,GAME)
    if group_status != 200:
        raise RuntimeError(f"group page HTTP {group_status}")

    groups=parse_round_grouping(group_html,2)
    if not groups:
        raise RuntimeError("official R2 grouping returned zero rows")

    progress=resolve_round_progress(rows,groups)

    ids=[str(r.player_code or "") for r in rows]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):
        raise RuntimeError("R2 identity gate failed")
    now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    data=[]
    for r in rows:
        st=str(r.status or "ACTIVE").upper()
        pid=str(r.player_code)
        pr=progress.get(pid)
        if pr is None:
            raise RuntimeError(f"missing R2 progress for {pid}")
        if pr.assumed_default_start:
            raise RuntimeError(f"unverified starting tee for {pid}")

        data.append({
          "player_id":pid,"player_name":r.player_name,
          "rank_display":None if st=="INCOMPLETE" else r.rank_display,
          "status":st,
          "raw_inghole":r.holes_completed,
          "holes_completed":pr.completed,
          "holes_completed_display":pr.display,
          "starting_tee_assumed":pr.assumed_default_start,
          "today_under_par_display":None if st=="INCOMPLETE" else r.today_under_par_display,
          "total_under_par_display":None if st=="INCOMPLETE" else r.total_under_par_display
        })
    payload={"schema_version":"neo_ok_open_r2_live_factual_v2","game_code":GAME,"round":2,
             "collected_at":now,"row_count":len(data),"player_table":data,
             "prediction_model_status":"BLOCKED_NOT_PUBLISHED"}
    SNAP.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"stages":{}}
    state.setdefault("stages",{})["r2"]={"validated":True,"retrieved_at":now,"row_count":len(data),
      "source":"official roundLeaderboard fresh fetch","factual_only":True}
    state["r1_complete"]=True
    state["r2_ready"]=True
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"action":"R2_SNAPSHOT_READY","rows":len(data),"at":now},ensure_ascii=False))
    return 0
if __name__=="__main__":
    raise SystemExit(main())