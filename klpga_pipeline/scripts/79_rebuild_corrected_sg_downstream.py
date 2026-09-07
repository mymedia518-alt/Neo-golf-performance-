"""Rebuild internal SG-derived evidence from the row-retention-corrected warehouse.

All outputs are versioned separately from the legacy warehouse and frozen PRE
artifacts.  No missing values are imputed and no forecast model is changed.
"""
from __future__ import annotations
import hashlib, json, math, statistics, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))
from klpga.tournament_context import load_active_tournament_context

_CONTEXT = load_active_tournament_context()
OUT = _CONTEXT.artifact_path("pre_performance_row_retention_corrected_v2")
DIFF = _CONTEXT.artifact_path("pre_performance_row_retention_diff_v2")
ENTRY = _CONTEXT.artifact_path("entry_snapshot")
OLD = _CONTEXT.artifact_path("pre_public_master")
# historical_sg_warehouse_corrected_v2.json is a shared, cross-tournament
# artifact (built by scripts 77/78 from every historical event, not just
# the active tournament) -- deliberately NOT routed through
# TournamentContext.artifact_path(), which would wrongly prefix it with
# this tournament's game_code.
WH = CONTENT / "historical_sg_warehouse_corrected_v2.json"
# historical_sg_warehouse_corrected_v2.json's tournament_cumulative rows
# carry no per-record event date (scripts 77/78 never wrote one --
# "retrieved_at" is the scrape timestamp, not the event date). The only
# real, evidence-based per-game_code date available is
# TOURNAMENT_K_WEEK_MAPPING_V1.json's start_date, sourced from the
# official tournament_master table (see scripts/92). A game_code absent
# from that mapping has no verified date and must be excluded, not
# assumed safe.
K_WEEK_MAPPING = CONTENT / "TOURNAMENT_K_WEEK_MAPPING_V1.json"
COMP = ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")
GAME_CODE = _CONTEXT.game_code
CUTOFF = _CONTEXT.start_date

def _verified_event_dates() -> dict:
    if not K_WEEK_MAPPING.exists():
        return {}
    mapping = json.loads(K_WEEK_MAPPING.read_text(encoding="utf-8"))
    return {r["game_code"]: r["start_date"] for r in mapping.get("records", []) if r.get("start_date")}

def classifier_view(p):
    """Apply the existing V2 dimension logic to corrected windows only."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("neo_classifier_v2", ROOT / "scripts" / "69_build_ok_open_classifier_v2.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.corrected_profile(p)

def stat(vals):
    x = [float(v) for v in vals if v is not None]
    if not x: return {"sample": 0, "mean": None, "sample_sd": None, "population_sd": None}
    # Keep full precision for classification; presentation layers may round later.
    return {"sample": len(x), "mean": statistics.mean(x),
            "sample_sd": statistics.stdev(x) if len(x) > 1 else None,
            "population_sd": statistics.pstdev(x) if len(x) > 1 else None}

def main():
    # PRE LEAKAGE (Phase 5 item 5): the shared warehouse accumulates
    # every historical tournament over time, independent of any one
    # tournament's own cutoff -- excluding this tournament's own
    # game_code is not sufficient by itself; a row whose game_code has
    # no verified event date (or whose verified date is on/after this
    # tournament's cutoff) must also be excluded, or a future event
    # added to the warehouse later would silently leak into a
    # historical PRE replay run again after the fact.
    event_dates = _verified_event_dates()
    wh = json.loads(WH.read_text(encoding="utf-8")); rows = [r for r in wh["records"] if r.get("scope") == "tournament_cumulative" and str(r.get("game_code")) != GAME_CODE and r.get("player_id") and event_dates.get(str(r.get("game_code"))) is not None and event_dates[str(r.get("game_code"))] < CUTOFF]
    entry = json.loads(ENTRY.read_text(encoding="utf-8")); ids = [str(e["player_id"]) for e in entry["entries"]]
    by = {}
    for r in rows: by.setdefault(str(r["player_id"]), []).append(r)
    for rs in by.values(): rs.sort(key=lambda r: (r.get("date") or "", str(r.get("game_code") or "")))
    profiles = []
    for pid in ids:
        rs = by.get(pid, [])
        wins = {"current": rs[-1:], "recent3": rs[-3:], "recent5": rs[-5:], "recent10": rs[-10:], "multi_season": rs,
                "season2026": [r for r in rs if r.get("season") == _CONTEXT.season]}
        windows = {name: {"event_count": len(v), "components": {c: stat([r.get(c) for r in v]) for c in COMP}} for name, v in wins.items()}
        base = {"player_id": pid, "player_name": next((e.get("player_name") for e in entry["entries"] if str(e["player_id"]) == pid), None), "coverage": "ENTRY + SUFFICIENT SG" if len(rs) >= 5 else "ENTRY + LIMITED SG" if rs else "ENTRY + NO OFFICIAL SG", "windows": windows, "consistency": {"bad_tail_frequency": None}}
        dimensions = classifier_view(base)
        base.update({k: dimensions[k] for k in ("level", "direction", "consistency", "composition", "result_divergence")})
        profiles.append(base)
    # Band-eligible population is exactly the validated minimum-event rule (N >= 5).
    eligible = [p["windows"]["recent5"]["components"]["total"]["mean"] for p in profiles if p["windows"]["recent5"]["components"]["total"]["sample"] >= 5]
    field_median = statistics.median(eligible) if eligible else None
    for p in profiles:
        w = p["windows"]; r5 = w["recent5"]["components"]["total"]; multi = w["multi_season"]["components"]["total"]
        n = r5["sample"]; se = (multi["sample_sd"] / math.sqrt(n)) if multi.get("sample_sd") is not None and n else None
        z = ((r5["mean"] - field_median) / se) if se and field_median is not None else None
        if z is None or n < 5: band = "INSUFFICIENT_EVIDENCE"
        elif z >= 1.96: band = "VERY_HIGH"
        elif z > 1.0: band = "HIGH"
        elif z >= -1.0: band = "TYPICAL"
        elif z > -1.96: band = "LOW"
        else: band = "VERY_LOW"
        p["neo_performance_band"] = band
        p["band_statistics"] = {"metric": "recent5 SG Total mean", "field_median": field_median, "standard_error": se, "z_vs_field_median": z, "boundaries": {"very_high": "z >= 1.96", "high": "1.00 < z < 1.96", "typical": "-1.00 <= z <= 1.00", "low": "-1.96 < z < -1.00", "very_low": "z <= -1.96"}}
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    original = json.loads(OLD.read_text(encoding="utf-8"))
    payload = {"schema_version": "neo_sg_row_retention_corrected_v2", "generated_at": generated, "game_code": GAME_CODE, "cutoff": f"{CUTOFF}T00:00:00+09:00", "warehouse": WH.name, "warehouse_sha256": "56da79abe8e97b82623fcb6b6368f3c864b51d1031fe421c2d69d98576653a62", "warehouse_hash_type": "canonical git-blob hash supplied by accepted warehouse record", "legacy_warehouse_sha256": hashlib.sha256((CONTENT/"historical_sg_warehouse.json").read_bytes()).hexdigest(), "future_data_excluded": True, "band_eligibility_rule": "recent5 SG Total sample >= 5", "profiles": profiles, "field_median": field_median}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    old_by = {str(r["player_id"]): r for r in original.get("records", [])}; changes=[]
    for p in profiles:
        old = old_by.get(p["player_id"], {}); old_band = old.get("neo_performance_band"); new_band = p["neo_performance_band"]
        changes.append({"player_id": p["player_id"], "old_band": old_band, "corrected_band": new_band, "changed": old_band != new_band, "old_dimensions": {k: old.get(k, {}) for k in ("level", "direction", "consistency", "composition")}, "corrected_dimensions": {k: p.get(k, {}) for k in ("level", "direction", "consistency", "composition")}, "reason": "recomputed from row-retention-corrected pre-cutoff SG; no imputation"})
    DIFF.write_text(json.dumps({"schema_version":"neo_sg_row_retention_diff_v2","generated_at":generated,"profiles":changes,"summary":{"entrants":len(changes),"band_changed":sum(x["changed"] for x in changes),"band_unchanged":sum(not x["changed"] for x in changes),"insufficient_to_eligible":sum((x["old_band"]=="INSUFFICIENT_EVIDENCE") and x["corrected_band"]!="INSUFFICIENT_EVIDENCE" for x in changes),"corrected_distribution":{b:sum(x["corrected_band"]==b for x in changes) for b in ("VERY_HIGH","HIGH","TYPICAL","LOW","VERY_LOW","INSUFFICIENT_EVIDENCE")}}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"profiles":len(profiles),"field_median":field_median,"distribution":{b:sum(p["neo_performance_band"]==b for p in profiles) for b in ("VERY_HIGH","HIGH","TYPICAL","LOW","VERY_LOW","INSUFFICIENT_EVIDENCE")}}, ensure_ascii=False))
if __name__ == "__main__": main()
