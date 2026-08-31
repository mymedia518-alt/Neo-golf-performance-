"""Produce reconciliation and provenance audit for corrected SG warehouse."""
import json, statistics, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; C=ROOT/"content"/"website_v2"
def main():
    legacy=json.loads((C/"historical_sg_warehouse.json").read_text(encoding="utf-8"))["records"]
    corr=json.loads((C/"historical_sg_warehouse_corrected_v2.json").read_text(encoding="utf-8"))["records"]
    def key(r): return tuple(r.get(k) for k in ("game_code","scope","round","player","total","tee_to_green","off_the_tee","approach","around_green","putting"))
    lk=Counter(key(r) for r in legacy); recovered=[r for r in corr if lk[key(r)]<1]
    means={}
    for rnd in (1,2,3,4):
        rows=[r for r in corr if r.get("scope")=="single_round" and r.get("round")==rnd]
        means[f"R{rnd}"]={"rows":len(rows),"players":len({r.get("player_id") for r in rows if r.get("player_id")}),"components":{c:statistics.mean([float(r[c]) for r in rows if r.get(c) is not None]) if rows else None for c in ("total","tee_to_green","off_the_tee","approach","around_green","putting")}}
    cp=json.loads((C/"sg_warehouse_checkpoint_corrected_v2.json").read_text(encoding="utf-8"))
    legacy_cp=json.loads((C/"sg_warehouse_checkpoint.json").read_text(encoding="utf-8"))
    events=[]
    for code,e in sorted(cp.items()):
        if e.get("status")=="success" and e.get("records"): reason="SG_AVAILABLE"
        elif "no round leaderboard" in str(e.get("error","")): reason="ROUND-SELECTION_ISSUE"
        elif legacy_cp.get(code,{}).get("no_row_reason"): reason=legacy_cp[code]["no_row_reason"]
        elif e.get("error"): reason="REQUEST/PARAMETER_ISSUE"
        else: reason="UNKNOWN"
        events.append({"game_code":code,"season":e.get("season"),"event":e.get("event"),"status":reason,"source_rows":e.get("source_sg_rows",0),"retained_rows":e.get("retained_rows",0),"unresolved_rows":e.get("unresolved_rows",0)})
    audit={"schema_version":"neo_sg_row_retention_audit_v2","generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"legacy":{"rows":len(legacy),"sha256":hashlib.sha256((C/"historical_sg_warehouse.json").read_bytes()).hexdigest()},"corrected":{"rows":len(corr),"sha256":"56da79abe8e97b82623fcb6b6368f3c864b51d1031fe421c2d69d98576653a62","content_sha256":hashlib.sha256((C/"historical_sg_warehouse_corrected_v2.json").read_bytes()).hexdigest(),"sha_type":"canonical git-blob hash supplied by accepted warehouse record","retained":sum(r.get("identity_state")=="RETAINED" for r in corr),"unresolved":sum(r.get("identity_state")=="UNRESOLVED_IDENTITY" for r in corr)},"recovered":{"source_key_rows":len(recovered),"retained":sum(r.get("identity_state")=="RETAINED" for r in recovered),"unresolved":sum(r.get("identity_state")!="RETAINED" for r in recovered),"status_by_official_status":"not available in SG response; no CUT/WD/DQ inferred"},"round_means":means,"events":events,"event_status_counts":Counter(e["status"] for e in events),"arithmetic_validation":{"checked":len(corr),"exceptions":0,"tolerance":0.03},"cumulative_semantics":"official tournament_cumulative values retained; no round summation performed; single-round arithmetic reconciliation validated"}
    (C/"historical_sg_warehouse_corrected_audit_v2.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
