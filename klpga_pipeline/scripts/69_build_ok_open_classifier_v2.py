"""Correct the prospective OK Open interpretation layer without rewriting evidence."""
from __future__ import annotations
import hashlib, json, statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
SOURCE = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"
OUT = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_CORRECTED_V2.json"
DIFF = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_CLASSIFIER_DIFF_V2.json"
REPORT = CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_CLASSIFIER_V2.md"
COMPONENTS = ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")
DIRS = ("recent3_vs_season", "recent5_vs_season", "recent10_vs_season")


def direction(value, baseline):
    if value is None or baseline is None:
        return "INSUFFICIENT"
    d = float(value) - float(baseline)
    return "UP" if d >= 0.25 else "DOWN" if d <= -0.25 else "FLAT"


def sample_band(n):
    return "N<5" if n < 5 else "N5-9" if n < 10 else "N10-19" if n < 20 else "N20+"


def _mean(window, component):
    return ((window or {}).get("components") or {}).get(component, {}).get("mean")


def _events(window):
    return int((window or {}).get("event_count") or 0)


def _leading(window, keys=("off_the_tee", "approach", "around_green", "putting")):
    values = {k: _mean(window, k) for k in keys if _mean(window, k) is not None}
    return max(values, key=values.get) if values else None


def corrected_profile(original):
    windows = original.get("windows", {})
    r3, r5, r10, season, multi = (windows.get(k, {}) for k in ("recent3", "recent5", "recent10", "season2026", "multi_season"))
    n5, n10, ns = _events(r5), _events(r10), _events(season)
    sample_sufficiency = "SUPPORTED" if n5 >= 5 else "PARTIALLY_SUPPORTED" if _events(r3 := windows.get("recent3", {})) >= 3 else "INSUFFICIENT"
    dir_components = {}
    conflicts = {}
    for c in COMPONENTS:
        states = {k: direction(_mean(w, c), _mean(season, c)) for k, w in (("recent3_vs_season", r3), ("recent5_vs_season", r5), ("recent10_vs_season", r10))}
        usable = [v for v in states.values() if v != "INSUFFICIENT"]
        conflict = "UP" in usable and "DOWN" in usable
        conflicts[c] = conflict
        dir_components[c] = states
    total_states = [dir_components["total"][k] for k in DIRS if dir_components["total"][k] != "INSUFFICIENT"]
    window_agreement = "WINDOW_CONFLICT" if len(set(total_states)) > 1 else "AGREES" if len(total_states) >= 2 else "INSUFFICIENT"
    if window_agreement == "AGREES" and total_states and total_states[0] == "UP" and n5 >= 5:
        direction_conf = "SUPPORTED"
    elif window_agreement == "WINDOW_CONFLICT":
        direction_conf = "PARTIALLY_SUPPORTED"
    elif total_states and all(v == "DOWN" for v in total_states):
        direction_conf = "CONTRADICTED"
    elif total_states:
        direction_conf = "PARTIALLY_SUPPORTED"
    else:
        direction_conf = "INSUFFICIENT"
    level_value = _mean(r5, "total")
    baseline_value = _mean(multi, "total")
    level_conf = "SUPPORTED" if level_value is not None and n5 >= 5 and baseline_value is not None else "INSUFFICIENT"
    variance = ((multi.get("components") or {}).get("total") or {})
    consistency = {"sample_sd": variance.get("sample_sd"), "population_sd_research": variance.get("population_sd"), "bad_tail_frequency": original.get("consistency", {}).get("bad_tail_frequency"), "sample_band": sample_band(_events(multi))}
    composition_states = {k: _leading(w) for k, w in (("recent5", r5), ("recent10", r10), ("season", season))}
    comp_values = [v for v in composition_states.values() if v is not None]
    comp_agreement = "AGREES" if len(comp_values) >= 2 and len(set(comp_values)) == 1 else "WINDOW_CONFLICT" if len(set(comp_values)) > 1 else "INSUFFICIENT"
    comp_conf = "SUPPORTED" if comp_agreement == "AGREES" and n5 >= 5 and n10 >= 5 else "PARTIALLY_SUPPORTED" if comp_agreement == "WINDOW_CONFLICT" else "INSUFFICIENT"
    return {
        "player_id": original["player_id"], "player_name": original.get("player_name"), "coverage": original.get("coverage"),
        "level": {"metric": "recent5 SG Total mean", "value": level_value, "baseline": "all pre-cutoff multi-season SG Total mean", "baseline_value": baseline_value, "window": "recent5", "sample": n5, "sample_sufficiency": sample_sufficiency, "dimension_confidence": level_conf},
        "direction": {"components": dir_components, "window_agreement": window_agreement, "window_conflict": conflicts, "sample_sufficiency": sample_sufficiency, "dimension_confidence": direction_conf},
        "consistency": {**consistency, "materiality_evidence": "VARIANCE_OBSERVED" if consistency["population_sd_research"] is not None else "INSUFFICIENT", "dimension_confidence": "SUPPORTED" if consistency["population_sd_research"] is not None and _events(multi) >= 10 else "PARTIALLY_SUPPORTED" if consistency["population_sd_research"] is not None else "INSUFFICIENT"},
        "composition": {"leading_component_by_window": composition_states, "window_agreement": comp_agreement, "sample_sufficiency": sample_sufficiency, "materiality_evidence": "COMPONENT_VALUES_AVAILABLE" if comp_values else "INSUFFICIENT", "dimension_confidence": comp_conf},
        "result_divergence": {"dimension_confidence": "UNKNOWN"},
    }


def build():
    raw = SOURCE.read_bytes(); original = json.loads(raw.decode("utf-8"))
    profiles = [corrected_profile(p) for p in original["profiles"]]
    # Evidence-ranked cohorts, never array slices.
    level_ranked = sorted((p for p in profiles if p["level"]["value"] is not None), key=lambda p: p["level"]["value"], reverse=True)
    cutoff = max(1, len(level_ranked) // 4)
    high_ids = {p["player_id"] for p in level_ranked[:cutoff]}
    variance_values = [(p["consistency"]["population_sd_research"], p) for p in profiles if p["consistency"]["population_sd_research"] is not None]
    variance_values.sort(key=lambda x: x[0]); q = max(1, len(variance_values)//4)
    high_variance_ids = {p["player_id"] for _, p in variance_values[-q:]}
    high_consistency_ids = {p["player_id"] for _, p in variance_values[:q]}
    groups = {"CURRENT HIGH LEVEL": [], "RISING — SUPPORTED": [], "RISING — WINDOW CONFLICT": [], "HIGH VARIANCE / BAD TAIL": [], "HIGH CONSISTENCY": [], "APPROACH-LED": [], "PUTTING-LED": [], "LIMITED DATA": []}
    for p in profiles:
        pid = p["player_id"]
        if pid in high_ids: groups["CURRENT HIGH LEVEL"].append(pid)
        if p["direction"]["dimension_confidence"] == "SUPPORTED": groups["RISING — SUPPORTED"].append(pid)
        if p["direction"]["window_agreement"] == "WINDOW_CONFLICT": groups["RISING — WINDOW CONFLICT"].append(pid)
        if pid in high_variance_ids: groups["HIGH VARIANCE / BAD TAIL"].append(pid)
        if pid in high_consistency_ids: groups["HIGH CONSISTENCY"].append(pid)
        if p["composition"]["dimension_confidence"] == "SUPPORTED" and p["composition"]["leading_component_by_window"].get("recent5") == "approach": groups["APPROACH-LED"].append(pid)
        if p["composition"]["dimension_confidence"] == "SUPPORTED" and p["composition"]["leading_component_by_window"].get("recent5") == "putting": groups["PUTTING-LED"].append(pid)
        if p["coverage"] != "ENTRY + SUFFICIENT SG": groups["LIMITED DATA"].append(pid)
    v2 = {**original, "schema_version": "neo_ok_open_pre_performance_corrected_v2", "original_artifact_sha256": hashlib.sha256(raw).hexdigest(), "original_freeze_timestamp": original.get("cutoff"), "correction_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "tournament_start_timestamp": original.get("cutoff"), "PRE_TOURNAMENT_CORRECTION": True, "correction_reasons": ["evidence-ranked level cohorts replace array-order slicing", "direction preserves cross-window conflicts", "variance cohorts use observed dispersion", "composition confidence is independent from level confidence"], "classifier_version": "ok_open_pre_performance_classifier_v2", "profiles": profiles, "highlight_groups": groups}
    OUT.write_text(json.dumps(v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    changes = []
    counts = {"total":0, "direction":0, "composition":0, "variance_group":0, "window_conflict":0}
    orig_by = {p["player_id"]: p for p in original["profiles"]}
    for p in profiles:
        old = orig_by[p["player_id"]]; changed=[]
        old_level = old.get("dimensions",{}).get("level",{}).get("confidence"); new_level=p["level"]["dimension_confidence"]
        old_dir = old.get("direction",{}).get("confidence"); new_dir=p["direction"]["dimension_confidence"]
        old_comp = old.get("composition",{}).get("confidence"); new_comp=p["composition"]["dimension_confidence"]
        if old_level != new_level: changed.append({"dimension":"level","original":old_level,"v2":new_level,"reason":"ranked recent5 metric and fixed baseline"}); counts["total"]+=1
        if old_dir != new_dir: changed.append({"dimension":"direction","original":old_dir,"v2":new_dir,"reason":"window agreement/conflict retained"}); counts["direction"]+=1
        if old_comp != new_comp: changed.append({"dimension":"composition","original":old_comp,"v2":new_comp,"reason":"cross-window component agreement"}); counts["composition"]+=1
        if p["direction"]["window_agreement"] == "WINDOW_CONFLICT": counts["window_conflict"]+=1
        changes.append({"player_id":p["player_id"],"original_classification":{"level":old_level,"direction":old_dir,"composition":old_comp},"v2_classification":{"level":new_level,"direction":new_dir,"composition":new_comp},"what_changed":changed})
    diff={"schema_version":"neo_ok_open_pre_performance_classifier_diff_v2","original_artifact_sha256":v2["original_artifact_sha256"],"profiles":changes,"summary":{**counts,"entrants":len(changes),"supported_to_partially_supported":sum(1 for x in changes for c in x["what_changed"] if c["original"]=="SUPPORTED" and c["v2"]=="PARTIALLY_SUPPORTED"),"supported_to_contradicted":sum(1 for x in changes for c in x["what_changed"] if c["original"]=="SUPPORTED" and c["v2"]=="CONTRADICTED"),"supported_to_insufficient":sum(1 for x in changes for c in x["what_changed"] if c["original"]=="SUPPORTED" and c["v2"]=="INSUFFICIENT")}}
    DIFF.write_text(json.dumps(diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines=["# OK Open PRE Performance Classifier V2", "", f"Original artifact SHA-256: `{v2['original_artifact_sha256']}`", "", "Classifier uses evidence-ranked Recent5 SG Total against one all-pre-cutoff multi-season baseline. Direction and composition retain cross-window disagreement; variance groups use observed dispersion, not sample count.", "", "## Cohorts", ""]
    for k, ids in groups.items(): lines.append(f"- **{k}**: {len(ids)} entrants")
    lines += ["", "## Diff summary", "", json.dumps(diff["summary"], ensure_ascii=False, indent=2), "", "Original artifact remains immutable; both original and corrected outputs are retained for prospective evaluation."]
    REPORT.write_text("\n".join(lines)+"\n", encoding="utf-8", newline="\n")
    return v2, diff


if __name__ == "__main__":
    v2, diff = build(); print(json.dumps({"profiles":len(v2["profiles"]),"groups":{k:len(v) for k,v in v2["highlight_groups"].items()},"diff":diff["summary"]}, ensure_ascii=False))
