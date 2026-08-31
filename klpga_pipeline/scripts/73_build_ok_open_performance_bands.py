"""Apply the approved field-median/standard-error performance bands."""
from __future__ import annotations
import json, math, statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "content" / "website_v2"

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def main():
    master = json.loads((C / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))
    corrected = json.loads((C / "OK_OPEN_2026_PRE_PERFORMANCE_CORRECTED_V2.json").read_text(encoding="utf-8"))
    evidence = json.loads((C / "OK_OPEN_2026_NEO_PRE_RANKING_EVIDENCE.json").read_text(encoding="utf-8"))
    by_id = {str(p["player_id"]): p for p in corrected["profiles"]}
    sufficient = [p for p in corrected["profiles"] if p.get("coverage") == "ENTRY + SUFFICIENT SG" and p.get("level", {}).get("value") is not None]
    median = statistics.median(p["level"]["value"] for p in sufficient)
    z_by_id = {}
    for p in sufficient:
        n = p["level"].get("sample") or 0
        sd = p.get("consistency", {}).get("sample_sd")
        se = sd / math.sqrt(n) if sd is not None and n > 0 else None
        z_by_id[str(p["player_id"])] = ((p["level"]["value"] - median) / se if se and se > 0 else None)
    def band(pid):
        z = z_by_id.get(pid)
        if z is None: return "INSUFFICIENT_EVIDENCE"
        if z >= 1.96: return "VERY_HIGH"
        if z > 1.0: return "HIGH"
        if z >= -1.0: return "TYPICAL"
        if z > -1.96: return "LOW"
        return "VERY_LOW"
    out=[]
    for row in master["records"]:
        pid=str(row["player_id"]); p=by_id.get(pid, {})
        b=band(pid); row={**row, "neo_performance_band": b, "band_statistics": {"metric":"recent5 SG Total mean", "field_median":median, "standard_error": (p.get("consistency",{}).get("sample_sd") / math.sqrt(p.get("level",{}).get("sample")) if p.get("consistency",{}).get("sample_sd") is not None and p.get("level",{}).get("sample") else None), "z_vs_field_median":z_by_id.get(pid), "boundaries":{"very_high":"z >= 1.96","high":"1.00 < z < 1.96","typical":"-1.00 <= z <= 1.00","low":"-1.96 < z < -1.00","very_low":"z <= -1.96"}}, "validation_status":"PASS" if b != "INSUFFICIENT_EVIDENCE" else "INSUFFICIENT_EVIDENCE"}
        out.append(row)
    artifact={"schema_version":"neo_ok_open_pre_public_master_v2","game_code":"2026120001","cutoff":"2026-09-04T00:00:00+09:00","classifier_version":"field_median_se_1.0","methodology":"Field-median comparison using each player's validated standard error; z boundaries ±1.00 and ±1.96; no within-band performance ordering.","source_artifacts":["OK_OPEN_2026_CURRENT_PLAYER_MASTER.json","OK_OPEN_2026_PRE_PERFORMANCE_CORRECTED_V2.json","OK_OPEN_2026_NEO_PRE_RANKING_EVIDENCE.json"],"generated_at":now(),"entry_count":len(out),"records":out}
    (C/"OK_OPEN_2026_PRE_PUBLIC_MASTER.json").write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    counts={k:sum(r["neo_performance_band"]==k for r in out) for k in ["VERY_HIGH","HIGH","TYPICAL","LOW","VERY_LOW","INSUFFICIENT_EVIDENCE"]}
    report={"entry_count":len(out),"identity_count":sum(bool(r.get("current_official_player_name")) for r in out),"win_coverage":sum(r.get("win_probability") is not None for r in out),"klpga_rank_coverage":sum(r.get("official_klpga_rank") is not None for r in out),"sg_total_rank_coverage":sum(r.get("sg_total_rank") is not None for r in out),"band_distribution":counts,"methodology":"field_median_standard_error","future_data_excluded":True,"website_generation":"PENDING_MASTER_VALIDATION"}
    (C/"OK_OPEN_2026_PRE_PUBLIC_MASTER_VALIDATION.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(report,ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
