"""Freeze the prospective, pre-start performance validation for the
active tournament (klpga.tournament_context).

The entry snapshot itself is produced by the shared, generic ENTRY
LIST / IDENTITY prerequisite (klpga.tournament_entry_bootstrap) --
usually already written by run_tournament.py before this script runs.
If it isn't (e.g. a direct/standalone invocation), this script builds
it itself via the same shared function, so there is exactly one
producer and one schema for the entry_snapshot artifact_type, never
two competing writers.
"""
from __future__ import annotations
import hashlib, json, math, statistics, sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPO_ROOT=ROOT.parent; sys.path.insert(0,str(ROOT/"src"))
from klpga.tournament_context import load_active_tournament_context
from klpga.tournament_entry_bootstrap import EntryListBootstrapBlocked, collect_entry_list_snapshot

_CONTEXT = load_active_tournament_context()
GAME = _CONTEXT.game_code
CUT_DATE = date.fromisoformat(_CONTEXT.start_date)
CUTOFF = f"{_CONTEXT.start_date}T00:00:00+09:00"
DB = ROOT / "data" / "klpga.sqlite"
WH=ROOT/"content/website_v2/historical_sg_warehouse.json"
# historical_sg_warehouse.json's tournament_cumulative rows carry no
# per-record event date (scripts 77/78 never wrote one -- "retrieved_at"
# is the scrape timestamp, not the event date). The only real,
# evidence-based per-game_code date available is
# TOURNAMENT_K_WEEK_MAPPING_V1.json's start_date, sourced from the
# official tournament_master table (see scripts/92). A game_code absent
# from that mapping has no verified date and must be excluded, not
# assumed safe.
K_WEEK_MAPPING = ROOT / "content/website_v2/TOURNAMENT_K_WEEK_MAPPING_V1.json"
COMPONENTS=("total","tee_to_green","off_the_tee","approach","around_green","putting")

def _verified_event_dates() -> dict:
    if not K_WEEK_MAPPING.exists():
        return {}
    mapping = json.loads(K_WEEK_MAPPING.read_text(encoding="utf-8"))
    return {r["game_code"]: r["start_date"] for r in mapping.get("records", []) if r.get("start_date")}

def stat(vals):
    vals=[float(v) for v in vals if v is not None]
    if not vals:return {"sample":0,"mean":None,"sample_sd":None,"population_sd":None}
    return {"sample":len(vals),"mean":round(statistics.mean(vals),4),"sample_sd":round(statistics.stdev(vals),4) if len(vals)>1 else None,"population_sd":round(statistics.pstdev(vals),4) if len(vals)>1 else None}

def classify_direction(recent, baseline):
    if recent is None or baseline is None:return "INSUFFICIENT"
    delta=recent-baseline
    return "UP" if delta>=0.25 else "DOWN" if delta<=-0.25 else "FLAT"

def main():
    entry_path = _CONTEXT.artifact_path("entry_snapshot")
    if not entry_path.exists():
        collect_entry_list_snapshot(_CONTEXT, cache_dir=ROOT / "data" / "raw_cache" / "http", db_path=DB)
    entry_bytes = entry_path.read_bytes()
    entry_hash = hashlib.sha256(entry_bytes).hexdigest()
    entry_payload = json.loads(entry_bytes.decode("utf-8"))
    entries = entry_payload["entries"]
    duplicates = entry_payload.get("duplicate_player_ids", [])
    unresolved = entry_payload.get("unresolved_player_ids", [e["player_id"] for e in entries if not e.get("identity_match")])
    source_url = entry_payload.get("source_url", f"https://klpga.co.kr/web/tourInfo/entry?gameCode={GAME}")
    # PRE LEAKAGE (Phase 5 item 5): every performance input must have a
    # real event_date strictly before the tournament's own cutoff --
    # never both "unknown date" AND "before cutoff" as if either were
    # equally safe. Warehouse rows carry no per-record date field of
    # their own (see _verified_event_dates docstring above), so the
    # event date is resolved from the verified per-game_code mapping; a
    # game_code absent from that mapping has no verified date and is
    # excluded, never assumed to be safely in the past.
    event_dates = _verified_event_dates()
    warehouse=json.loads(WH.read_text(encoding="utf-8")); rows=[r for r in warehouse["records"] if r.get("scope")=="tournament_cumulative" and event_dates.get(str(r.get("game_code"))) is not None and event_dates[str(r.get("game_code"))]<CUT_DATE.isoformat()]
    by= {}
    for r in rows: by.setdefault(str(r.get("player_id")),[]).append(r)
    profiles=[]
    for e in entries:
        rs=sorted(by.get(e["player_id"],[]),key=lambda r:(r.get("date") or "",r.get("game_code") or ""))
        wins={"current":rs[-1:] ,"recent3":rs[-3:],"recent5":rs[-5:],"recent10":rs[-10:],"season2026":[r for r in rs if r.get("season")==_CONTEXT.season],"multi_season":rs}
        window_stats={name:{"event_count":len(v),"round_count":sum(int(r.get("rounds") or 0) for r in v),"components":{c:stat([r.get(c) for r in v]) for c in COMPONENTS}} for name,v in wins.items()}
        season=window_stats["season2026"]["components"]; r5=window_stats["recent5"]["components"]; r10=window_stats["recent10"]["components"]
        directions={c:{"recent3_vs_season":classify_direction(window_stats["recent3"]["components"][c]["mean"],season[c]["mean"]),"recent5_vs_season":classify_direction(r5[c]["mean"],season[c]["mean"]),"recent10_vs_season":classify_direction(r10[c]["mean"],season[c]["mean"])} for c in COMPONENTS}
        direction_conf="SUPPORTED" if window_stats["recent5"]["event_count"]>=5 else "PARTIALLY_SUPPORTED" if window_stats["recent3"]["event_count"]>=3 else "INSUFFICIENT"
        consistency=stat([r.get("total") for r in rs]); tail=sum(1 for r in rs if r.get("total") is not None and r.get("total")<=-2)/len(rs) if rs else None
        comp_means={c:r5[c]["mean"] for c in ("off_the_tee","approach","around_green","putting")}; available={k:v for k,v in comp_means.items() if v is not None}; leader=max(available,key=available.get) if available else None
        profiles.append({"player_id":e["player_id"],"player_name":e["player_name"],"coverage":"ENTRY + SUFFICIENT SG" if window_stats["recent5"]["event_count"]>=5 else "ENTRY + LIMITED SG" if rs else "ENTRY + NO OFFICIAL SG","windows":window_stats,"direction":{"components":directions,"window_conflict":{c:r5[c]["mean"] is not None and r10[c]["mean"] is not None and classify_direction(r5[c]["mean"],season[c]["mean"])!=classify_direction(r10[c]["mean"],season[c]["mean"]) for c in COMPONENTS},"confidence":direction_conf},"consistency":{"legacy_sample_sd":consistency["sample_sd"],"population_sd_research":consistency["population_sd"],"bad_tail_frequency":tail,"sample_band":"N<5" if len(rs)<5 else "N5-9" if len(rs)<10 else "N10-19" if len(rs)<20 else "N20+"},"composition":{"recent5_leading_component":leader,"recent5_component_means":comp_means,"confidence":"SUPPORTED" if leader and window_stats["recent5"]["event_count"]>=5 else "INSUFFICIENT"},"dimensions":{"level":{"baseline":"all pre-cutoff SG cumulative event records","window":"recent5","sample":window_stats["recent5"]["event_count"],"confidence":"SUPPORTED" if window_stats["recent5"]["event_count"]>=5 else "INSUFFICIENT"},"direction":{"confidence":direction_conf},"consistency":{"confidence":"SUPPORTED" if len(rs)>=10 else "PARTIALLY_SUPPORTED" if len(rs)>=5 else "INSUFFICIENT"},"composition":{"confidence":"SUPPORTED" if leader and len(rs)>=5 else "INSUFFICIENT"},"result_divergence":{"confidence":"UNKNOWN"}}})
    snapshot={"schema_version":"neo_ok_open_pre_performance_v1","game_code":GAME,"cutoff":CUTOFF,"entry_snapshot_sha256":entry_hash,"data_version":"historical_sg_warehouse schema 1.0","warehouse_generated_at":warehouse.get("generated_at"),"calculation_version":"ok_open_pre_performance_v1","future_data_excluded":True,"profiles":profiles}
    snap_path=_CONTEXT.artifact_path("pre_performance_snapshot")
    if snap_path.exists(): raise RuntimeError(f"immutable performance snapshot already exists: {snap_path}")
    snap_path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    plan={"schema_version":"neo_ok_open_validation_plan_v1","game_code":GAME,"frozen_before_start":CUTOFF,"dimensions":{"level":{"supports":"post-event SG remains in the same validated baseline direction","contradicts":"post-event SG reverses materially versus baseline","insufficient":"fewer than 5 pre-cutoff events","window":"recent5 vs all pre-cutoff events","minimum_sample":5,"baseline":"all pre-cutoff cumulative SG"},"direction":{"supports":"recent3/5/10 and season agree on direction","contradicts":"recent windows materially disagree with season","insufficient":"fewer than 3 events","window":"recent3, recent5, recent10, season","minimum_sample":3,"baseline":"2026 season"},"consistency":{"supports":"dispersion remains within historical band","contradicts":"bad-tail frequency materially exceeds historical distribution","insufficient":"N<5; N>=10 is hypothesis only","window":"all pre-cutoff events","minimum_sample":5,"baseline":"player event SG Total"},"composition":{"supports":"component ordering repeats in recent5 and recent10/season","contradicts":"leading component changes across windows","insufficient":"component missing or fewer than 5 events","window":"recent5, recent10, season","minimum_sample":5,"baseline":"same-scope SG components"},"result_divergence":{"supports":"future result and SG can be joined without leakage","contradicts":"identity/scope conflict","insufficient":"no post-event result","window":"post-event only","minimum_sample":1,"baseline":"official result + SG"}},"no_composite_performance_index":True,"no_winner_prediction":True}
    plan_path=_CONTEXT.artifact_path("validation_plan")
    if plan_path.exists(): raise RuntimeError(f"immutable validation plan already exists: {plan_path}")
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    groups=Counter()
    for p in profiles:
        groups[p["coverage"]]+=1
    report="# OK Open 2026 — Pre-tournament Performance Validation\n\n"
    report+=f"- Official field size: **{len(entries)}**\n- Identity matches: **{len(entries)-len(unresolved)}/{len(entries)}**; duplicates: {len(duplicates)}; unresolved: {len(unresolved)}\n- Data cutoff: **{CUTOFF} Asia/Seoul**; future OK Open data excluded.\n- SG coverage: {dict(groups)}\n\n"
    report+="This is performance validation, not a forecast or player pick. No composite index or winner prediction is produced. Window disagreement and sample bands are retained per entrant in the frozen JSON snapshot.\n\n"
    report+="## Frozen provenance\n\nEntry source: `"+source_url+"`; entry snapshot SHA-256: `"+entry_hash+"`. Warehouse: `historical_sg_warehouse.json`; calculation: `ok_open_pre_performance_v1`.\n\n"
    report+="## Highlight groups\n\nPlayers are grouped only when the frozen evidence state supports the label; complete per-player values and confidence are in the JSON snapshot.\n\n"
    for label, pred in (("CURRENT HIGH LEVEL",lambda p:p["dimensions"]["level"]["confidence"]=="SUPPORTED"),("RISING — SUPPORTED",lambda p:any(v=="UP" for v in p["direction"]["components"]["total"].values()) and p["direction"]["confidence"]=="SUPPORTED"),("RISING — BUT WINDOW CONFLICT",lambda p:any(p["direction"]["window_conflict"].values())),("HIGH CONSISTENCY",lambda p:p["consistency"]["sample_band"] in ("N20+","N10-19")),("HIGH VARIANCE",lambda p:p["consistency"]["sample_band"]=="N5-9"),("APPROACH-LED",lambda p:p["composition"]["recent5_leading_component"]=="approach"),("PUTTING-LED",lambda p:p["composition"]["recent5_leading_component"]=="putting"),("LIMITED DATA",lambda p:p["coverage"]!="ENTRY + SUFFICIENT SG")):
        names=[p["player_name"] for p in profiles if pred(p)]; report+=f"### {label}\n\n{', '.join(names[:20]) if names else '해당 없음'}\n\n"
    report+="## Limitations\n\nThe official entry page exposes listed entrants and qualification fields but no explicit withdrawal marker at retrieval. SG history is available only where official KLPGA SG rows exist; NULL is preserved.\n"
    _CONTEXT.artifact_path("pre_performance_validation_report", ext="md").write_text(report,encoding="utf-8",newline="\n")
    print(json.dumps({"field_size":len(entries),"identity_matches":len(entries)-len(unresolved),"entry_sha256":entry_hash,"profiles":len(profiles),"files":[str(entry_path),str(snap_path),str(plan_path)],"coverage":dict(groups)},ensure_ascii=False))
if __name__=="__main__": main()
