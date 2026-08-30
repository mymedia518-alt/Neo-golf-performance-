"""Produce deterministic coverage audit for the multi-event SG warehouse."""
from __future__ import annotations
import json, collections
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from klpga.analytics.sg_performance import compute_sg_windows

def main():
    warehouse=json.loads((ROOT/"content/website_v2/historical_sg_warehouse.json").read_text(encoding="utf-8")); checkpoint=json.loads((ROOT/"content/website_v2/sg_warehouse_checkpoint.json").read_text(encoding="utf-8")); rows=warehouse["records"]
    by_player=collections.defaultdict(list)
    for row in rows: by_player[row["player_id"]].append(row)
    components=("total","tee_to_green","off_the_tee","approach","around_green","putting")
    missing={c:sum(row.get(c) is None for row in rows) for c in components}
    windows={pid:compute_sg_windows(rs,pid) for pid,rs in by_player.items()}
    out={"seasons":sorted({r["season"] for r in rows}),"events_attempted":warehouse["attempted_events"],"events_with_sg":warehouse["events"],"events_without_sg":warehouse["attempted_events"]-warehouse["events"],"no_row_reason_breakdown":collections.Counter(v.get("no_row_reason") or "RECOVERED_AFTER_RETRY" for v in checkpoint.values() if not v.get("records")),"players":len(by_player),"total_rows":len(rows),"cumulative_rows":sum(r["scope"]=="tournament_cumulative" for r in rows),"round_rows":sum(r["scope"]=="single_round" for r in rows),"component_missingness":missing,"recent5_eligible_players":sum(v["recent5"]["event_count"]>=5 for v in windows.values()),"recent10_eligible_players":sum(v["recent10"]["event_count"]>=10 for v in windows.values()),"season_profile_eligible_players":sum(v["season"]["event_count"]>=1 for v in windows.values()),"provenance":warehouse["provenance"]}
    out["no_row_reason_breakdown"]=dict(out["no_row_reason_breakdown"]); dest=ROOT/"content/website_v2/sg_warehouse_audit.json"; dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
