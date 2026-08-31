"""Export internal empirical SG validation artifacts from the canonical warehouse.

This is deliberately an internal, data-only export.  It never imputes SG,
converts missing starts to zero, or writes public website content.
"""
from __future__ import annotations

import csv, json, math, statistics, os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "website_v2" / os.environ.get("NEO_SG_EXPORT_DIR", "empirical_sg")
COMPONENTS = ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")

def _quantile(values, q):
    vals = sorted(float(x) for x in values if x is not None)
    if not vals: return None
    if len(vals) == 1: return vals[0]
    pos = (len(vals) - 1) * q; lo, hi = math.floor(pos), math.ceil(pos)
    return vals[lo] if lo == hi else vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)

def _stats(values):
    vals = [float(x) for x in values if x is not None]
    if not vals: return {"sample_count": 0, "mean": None, "stddev": None, "median": None, "mad": None, "iqr": None}
    med = statistics.median(vals)
    return {"sample_count": len(vals), "mean": statistics.mean(vals),
            "stddev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "median": med, "mad": statistics.median(abs(x-med) for x in vals),
            "iqr": _quantile(vals,.75)-_quantile(vals,.25)}

def _window(rows, n=None, season=None):
    rows = [r for r in rows if r.get("scope") == "tournament_cumulative" and (season is None or r.get("season") == season)]
    rows.sort(key=lambda r: (r.get("date") or "", r.get("game_code") or ""))
    return rows[-n:] if n else rows

def main():
    warehouse_name = os.environ.get("NEO_SG_WAREHOUSE", "historical_sg_warehouse.json")
    checkpoint_name = os.environ.get("NEO_SG_CHECKPOINT", "sg_warehouse_checkpoint.json")
    warehouse = json.loads((ROOT/"content/website_v2"/warehouse_name).read_text(encoding="utf-8"))
    checkpoint = json.loads((ROOT/"content/website_v2"/checkpoint_name).read_text(encoding="utf-8"))
    rows = warehouse["records"]
    cumulative = [r for r in rows if r.get("scope") == "tournament_cumulative"]
    rounds = [r for r in rows if r.get("scope") == "single_round"]
    by_player = defaultdict(list)
    for r in cumulative: by_player[str(r.get("player_id"))].append(r)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. One row per player/event (identity is player_id; names are descriptive only).
    event_series = []
    for r in sorted(cumulative, key=lambda x:(x.get("date") or "",x.get("game_code") or "",str(x.get("player_id")))):
        event_series.append({"player_id":r.get("player_id"),"player":r.get("player_name",r.get("player")),"season":r.get("season"),"game_code":r.get("game_code"),"tournament":r.get("tournament"),"tournament_start":r.get("date"),"rank":r.get("rank"),"scope":r.get("scope"),**{c:r.get(c) for c in COMPONENTS},"source":r.get("source"),"retrieved_at":r.get("retrieved_at")})
    (OUT/"player_event_series.json").write_text(json.dumps({"generated_at":generated,"rows":event_series},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # 2. History depth and 3. within-player dispersion.
    depths = {"1_plus":0,"3_plus":0,"5_plus":0,"10_plus":0,"20_plus":0,"30_plus":0,"multi_season":0}
    profiles = []
    for pid, rs in sorted(by_player.items()):
        events = {r.get("game_code") for r in rs}; seasons = {r.get("season") for r in rs}
        for k, threshold in (("1_plus",1),("3_plus",3),("5_plus",5),("10_plus",10),("20_plus",20),("30_plus",30)):
            if len(events) >= threshold: depths[k] += 1
        if len(seasons)>1: depths["multi_season"] += 1
        profiles.append({"player_id":pid,"event_count":len(events),"season_count":len(seasons),"components":{c:_stats([r.get(c) for r in rs]) for c in COMPONENTS}})
    (OUT/"player_history_depth.json").write_text(json.dumps({"generated_at":generated,"distribution":depths,"players":profiles},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # 4. Between-player distributions (all observed cumulative event values).
    between = {c:{"sample_count":sum(r.get(c) is not None for r in cumulative),"percentiles":{"p01":_quantile([r.get(c) for r in cumulative],.01),"p05":_quantile([r.get(c) for r in cumulative],.05),"p25":_quantile([r.get(c) for r in cumulative],.25),"p50":_quantile([r.get(c) for r in cumulative],.50),"p75":_quantile([r.get(c) for r in cumulative],.75),"p95":_quantile([r.get(c) for r in cumulative],.95),"p99":_quantile([r.get(c) for r in cumulative],.99)},"variance":_stats([r.get(c) for r in cumulative])["stddev"]**2 if sum(r.get(c) is not None for r in cumulative)>1 else 0.0} for c in COMPONENTS}
    (OUT/"between_player_distributions.json").write_text(json.dumps({"generated_at":generated,"components":between,"sample_size_distribution":Counter(len({r.get('game_code') for r in rs}) for rs in by_player.values())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # 5. Incremental windows retain counts and never infer missing values.
    windows = {}
    for pid, rs in by_player.items():
        windows[pid] = {name:{"event_count":len(_window(rs,n)),"components":{c:_stats([r.get(c) for r in _window(rs,n)]) for c in COMPONENTS}} for name,n in (("current",1),("recent3",3),("recent5",5),("recent10",10),("multi_season",None))}
        seasons = sorted({r.get("season") for r in rs})
        windows[pid]["season"]={str(s):{"event_count":len(_window(rs,season=s)),"components":{c:_stats([r.get(c) for r in _window(rs,season=s)]) for c in COMPONENTS}} for s in seasons}
    (OUT/"incremental_windows.json").write_text(json.dumps({"generated_at":generated,"players":windows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # 6. Bad-tail distributions; thresholds intentionally left to validation.
    bad_tail = {"event_sg": {}, "round_sg": {}}
    for label, source_rows in (("event_sg", cumulative), ("round_sg", rounds)):
        for c in COMPONENTS:
            vals = [r.get(c) for r in source_rows]
            bad_tail[label][c] = {"sample_count": sum(v is not None for v in vals), "percentiles": {"p01": _quantile(vals,.01), "p05": _quantile(vals,.05), "p10": _quantile(vals,.10)}}
    (OUT/"bad_tail_distributions.json").write_text(json.dumps({"generated_at":generated,"threshold_status":"NOT_SELECTED","data":bad_tail},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # 7/8. Event status and coverage tracker; no-row starts remain explicit.
    statuses=[]
    for code,e in sorted(checkpoint.items()):
        if e.get("records"):
            status = "SG_AVAILABLE"
        elif e.get("no_row_reason"):
            status = e["no_row_reason"]
        elif "roundLeaderboard returned no rows" in str(e.get("error", "")):
            status = "ROUND-SELECTION_ISSUE"
        elif e.get("error"):
            status = "REQUEST/PARAMETER_ISSUE"
        else:
            status = "UNKNOWN"
        statuses.append({"game_code":code,"season":e.get("season"),"tournament":e.get("event"),"status":status,"sg_rows":len(e.get("records",[])),"sg_available":bool(e.get("records"))})
    coverage={"events":statuses,"player_sg_event_rows":len(event_series),"zero_sample_players":0,"low_sample_players":sum(1 for rs in by_player.values() if len({r.get('game_code') for r in rs})<5),"survivorship_bias_note":"Participation records are limited to official tournament listings and SG response availability; no absent-start is converted to zero."}
    (OUT/"participation_sg_coverage.json").write_text(json.dumps({"generated_at":generated,"coverage":coverage},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # 9. Result/performance join where official result data exists (target event).
    result=[]
    official_path=ROOT/"content/website_v2/kg_2026080001_official.json"
    if official_path.exists():
        official=json.loads(official_path.read_text(encoding="utf-8")); sg_by_id={str(r.get("player_id")):r for r in cumulative if str(r.get("game_code"))=="2026080001"}
        for r in official.get("leaderboard",[]):
            s=sg_by_id.get(str(r.get("player_id")),{}); result.append({"game_code":"2026080001","player_id":r.get("player_id"),"player":r.get("player"),"rank":r.get("rank_numeric",r.get("rank")),"rounds":r.get("rounds"),"total":r.get("total"),"to_par":r.get("to_par"),"status":r.get("status"),**{c:s.get(c) for c in COMPONENTS}})
    (OUT/"result_performance_join.json").write_text(json.dumps({"generated_at":generated,"rows":result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    summary={"generated_at":generated,"event_series_rows":len(event_series),"cumulative_rows":len(cumulative),"round_rows":len(rounds),"players":len(by_player),"events":len({r.get('game_code') for r in cumulative}),"history_depth":depths,"component_missingness":{c:sum(r.get(c) is None for r in cumulative) for c in COMPONENTS},"event_status_counts":Counter(x["status"] for x in statuses),"artifacts":sorted(p.name for p in OUT.glob("*.json"))}
    (OUT/"export_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
