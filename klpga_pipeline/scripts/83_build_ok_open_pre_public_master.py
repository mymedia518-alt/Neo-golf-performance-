"""Generate the single canonical OK Open PRE public master after Tier-2 PASS."""
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; C=ROOT/"content"/"website_v2"
def main():
    gate=json.loads((C/"OK_OPEN_2026_TIER2_PUBLICATION_GATE.json").read_text(encoding="utf-8"))
    if gate.get("overall_state") != "PASS": raise SystemExit("Tier-2 gate is not PASS")
    base=json.loads((C/"OK_OPEN_2026_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))
    bands=json.loads((C/"OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_CORRECTED_V2.json").read_text(encoding="utf-8")); b={str(x["player_id"]):x for x in bands["profiles"]}
    ranks=json.loads((C/"OK_OPEN_2026_PRE_SG_TOTAL_RANK_CORRECTED_V2.json").read_text(encoding="utf-8")); r={str(x["player_id"]):x for x in ranks["records"]}
    out=[]
    for row in base["records"]:
        pid=str(row["player_id"]); bp=b[pid]; rp=r[pid]
        out.append({**row,"neo_pre_rank":None,"sg_total_rank":rp.get("sg_total_rank"),"neo_performance_band":bp.get("neo_performance_band"),"band_statistics":bp.get("band_statistics"),"source_artifacts":{"identity":"OK_OPEN_2026_CURRENT_PLAYER_MASTER.json","sg_rank":"OK_OPEN_2026_PRE_SG_TOTAL_RANK_CORRECTED_V2.json","sg_band":"OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_CORRECTED_V2.json","win":"OK_OPEN_2026_PRE_WIN_FORECAST.json"},"validation_status":"PASS" if bp.get("neo_performance_band") != "INSUFFICIENT_EVIDENCE" else "INSUFFICIENT_EVIDENCE"})
    artifact={"schema_version":"neo_ok_open_pre_public_master_v3","game_code":"2026120001","cutoff":"2026-09-04T00:00:00+09:00","entry_count":len(out),"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),"tier2_gate":"OK_OPEN_2026_TIER2_PUBLICATION_GATE.json","source_artifacts":["OK_OPEN_2026_CURRENT_PLAYER_MASTER.json","OK_OPEN_2026_PRE_SG_TOTAL_RANK_CORRECTED_V2.json","OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_CORRECTED_V2.json","OK_OPEN_2026_PRE_WIN_FORECAST.json"],"no_unsupported_top_probabilities":True,"records":out}
    (C/"OK_OPEN_2026_PRE_PUBLIC_MASTER.json").write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={"entry_count":len(out),"identity_count":len({x["player_id"] for x in out}),"win_coverage":sum(x.get("win_probability") is not None for x in out),"klpga_rank_coverage":sum(x.get("official_klpga_rank") is not None for x in out),"sg_total_rank_coverage":sum(x.get("sg_total_rank") is not None for x in out),"band_distribution":{k:sum(x.get("neo_performance_band")==k for x in out) for k in ("VERY_HIGH","HIGH","TYPICAL","LOW","VERY_LOW","INSUFFICIENT_EVIDENCE")},"tier2":"PASS","website_generation":"NOT_RUN"}
    (C/"OK_OPEN_2026_PRE_PUBLIC_MASTER_VALIDATION.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__": main()
