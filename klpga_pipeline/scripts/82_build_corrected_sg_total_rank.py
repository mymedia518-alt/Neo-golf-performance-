"""Build PRE SG Total rank from the canonical corrected warehouse only,
for the active tournament (klpga.tournament_context)."""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; C=ROOT/"content"/"website_v2"
sys.path.insert(0, str(ROOT / "src"))
from klpga.tournament_context import load_active_tournament_context

_CONTEXT = load_active_tournament_context()
GAME_CODE = _CONTEXT.game_code
CUTOFF = f"{_CONTEXT.start_date}T00:00:00+09:00"
# historical_sg_warehouse_corrected_v2.json is a shared, cross-tournament
# artifact (built by scripts 77/78) -- deliberately NOT routed through
# TournamentContext.artifact_path(), which is per-tournament.
WH=C/"historical_sg_warehouse_corrected_v2.json"
ENTRY=_CONTEXT.artifact_path("entry_snapshot")
OUT=_CONTEXT.artifact_path("pre_sg_total_rank_corrected_v2")

def main():
    w=json.loads(WH.read_text(encoding="utf-8")); entries=json.loads(ENTRY.read_text(encoding="utf-8"))["entries"]; by={}
    for r in w["records"]:
        if r.get("scope")=="tournament_cumulative" and r.get("player_id") and str(r.get("game_code"))!=GAME_CODE: by.setdefault(str(r["player_id"]),[]).append(r)
    rec=[]
    for e in entries:
        rs=sorted(by.get(str(e["player_id"]),[]),key=lambda r:(str(r.get("game_code") or "")))
        vals=[r.get("total") for r in rs[-5:] if r.get("total") is not None]
        rec.append({"player_id":str(e["player_id"]),"sg_total_mean":sum(vals)/len(vals) if vals else None,"sample_count":len(vals),"provenance":{"source_artifact":WH.name,"warehouse_sha256":"56da79abe8e97b82623fcb6b6368f3c864b51d1031fe421c2d69d98576653a62","cutoff":CUTOFF,"window":"latest five pre-cutoff tournament_cumulative SG Total observations","scope":"official tournament_cumulative; arithmetic mean of completed single-round SG","calculation_version":"corrected_sg_total_rank_v2"}})
    ranked=sorted([r for r in rec if r["sg_total_mean"] is not None],key=lambda r:(-r["sg_total_mean"],r["player_id"]))
    prev=None; rank=0
    for i,r in enumerate(ranked,1):
        if prev is None or r["sg_total_mean"] != prev: rank=i; prev=r["sg_total_mean"]
        r["sg_total_rank"]=rank
    for r in rec:
        r.setdefault("sg_total_rank",None)
    payload={"schema_version":"neo_tournament_pre_sg_total_rank_corrected_v2","game_code":GAME_CODE,"cutoff":CUTOFF,"window":"latest five pre-cutoff tournament_cumulative SG Total observations","scope":"official tournament_cumulative arithmetic mean of completed single-round SG; never summed","minimum_sample":1,"tie_rule":"equal full-precision means share competition rank; player_id orders computation only","missing_rule":"NULL rank when no validated observation","warehouse":WH.name,"warehouse_sha256":"56da79abe8e97b82623fcb6b6368f3c864b51d1031fe421c2d69d98576653a62","generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),"records":rec}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"eligible":len(ranked),"insufficient":len(rec)-len(ranked),"ties":len(ranked)-len({r['sg_total_mean'] for r in ranked})},ensure_ascii=False))
if __name__=="__main__": main()
