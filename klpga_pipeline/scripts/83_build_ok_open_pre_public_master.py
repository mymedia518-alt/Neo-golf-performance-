"""Generate the single canonical OK Open PRE public master after Tier-2 PASS."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.tournament_context import load_active_tournament_context  # noqa: E402
def main():
    # NEO TOURNAMENT PIPELINE: game_code/cutoff resolved from the shared
    # context instead of this script's own hardcoded literals -- see
    # src/klpga/tournament_context.py. Cutoff is 00:00 KST on the
    # tournament's start_date, matching the existing PRE-freeze
    # convention (freeze at tournament start).
    context = load_active_tournament_context()
    cutoff = f"{context.start_date}T00:00:00+09:00"
    tier2_gate_path = context.artifact_path("tier2_publication_gate")
    current_player_master_path = context.artifact_path("current_player_master")
    row_retention_path = context.artifact_path("pre_performance_row_retention_corrected_v2")
    sg_total_rank_path = context.artifact_path("pre_sg_total_rank_corrected_v2")
    pre_win_forecast_path = context.artifact_path("pre_win_forecast")
    gate=json.loads(tier2_gate_path.read_text(encoding="utf-8"))
    if gate.get("overall_state") != "PASS": raise SystemExit("Tier-2 gate is not PASS")
    base=json.loads(current_player_master_path.read_text(encoding="utf-8"))
    bands=json.loads(row_retention_path.read_text(encoding="utf-8")); b={str(x["player_id"]):x for x in bands["profiles"]}
    ranks=json.loads(sg_total_rank_path.read_text(encoding="utf-8")); r={str(x["player_id"]):x for x in ranks["records"]}
    out=[]
    for row in base["records"]:
        pid=str(row["player_id"]); bp=b[pid]; rp=r[pid]
        out.append({**row,"neo_pre_rank":None,"sg_total_rank":rp.get("sg_total_rank"),"neo_performance_band":bp.get("neo_performance_band"),"band_statistics":bp.get("band_statistics"),"source_artifacts":{"identity":current_player_master_path.name,"sg_rank":sg_total_rank_path.name,"sg_band":row_retention_path.name,"win":pre_win_forecast_path.name},"validation_status":"PASS" if bp.get("neo_performance_band") != "INSUFFICIENT_EVIDENCE" else "INSUFFICIENT_EVIDENCE"})
    artifact={"schema_version":"neo_ok_open_pre_public_master_v3","game_code":context.game_code,"cutoff":cutoff,"entry_count":len(out),"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),"tier2_gate":tier2_gate_path.name,"source_artifacts":[current_player_master_path.name,sg_total_rank_path.name,row_retention_path.name,pre_win_forecast_path.name],"no_unsupported_top_probabilities":True,"records":out}
    context.artifact_path("pre_public_master").write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={"entry_count":len(out),"identity_count":len({x["player_id"] for x in out}),"win_coverage":sum(x.get("win_probability") is not None for x in out),"klpga_rank_coverage":sum(x.get("official_klpga_rank") is not None for x in out),"sg_total_rank_coverage":sum(x.get("sg_total_rank") is not None for x in out),"band_distribution":{k:sum(x.get("neo_performance_band")==k for x in out) for k in ("VERY_HIGH","HIGH","TYPICAL","LOW","VERY_LOW","INSUFFICIENT_EVIDENCE")},"tier2":"PASS","website_generation":"NOT_RUN"}
    context.artifact_path("pre_public_master_validation").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__": main()
