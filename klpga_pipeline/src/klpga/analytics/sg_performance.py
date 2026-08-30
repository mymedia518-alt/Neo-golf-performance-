"""Canonical historical KLPGA SG series and player-performance windows.

This module consumes records already collected by the official KLPGA SG
collector.  It never turns missing values into zero and remains separate
from NEO's win-probability model.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean, stdev
from typing import Any, Iterable

SG_COMPONENTS = ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")
SCOPES = {"tournament_cumulative", "single_round", "season_average"}
TREND_THRESHOLD = 0.25
MIN_TREND_SAMPLES = 3


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_sg_records(records: Iterable[dict], *, source: str | None = None) -> list[dict]:
    """Return canonical SG rows with explicit scope and nullable components."""
    output = []
    for row in records:
        scope = row.get("scope", "tournament_cumulative")
        if scope not in SCOPES:
            raise ValueError(f"unsupported SG scope: {scope}")
        item = dict(row)
        item["player_id"] = str(row.get("player_id") or row.get("player_code") or "")
        item["season"] = int(row["season"]) if row.get("season") is not None else None
        item["game_code"] = str(row.get("game_code") or "")
        item["round"] = row.get("round")
        item["scope"] = scope
        item["source"] = source or row.get("source")
        for component in SG_COMPONENTS:
            item[component] = _number(row.get(component, row.get({"tee_to_green":"teeToGreen", "off_the_tee":"tee", "around_green":"around"}.get(component, component))))
        output.append(item)
    return output


def validate_sg_records(records: Iterable[dict]) -> dict:
    rows = list(records); errors=[]; seen=set(); missing_identity=0
    for row in rows:
        key=(row.get("player_id"),row.get("season"),row.get("game_code"),row.get("scope"),row.get("round"))
        if not row.get("player_id") or not row.get("game_code"):
            missing_identity += 1
        if key in seen: errors.append({"type":"duplicate","key":key})
        seen.add(key)
        if row.get("scope") not in SCOPES: errors.append({"type":"scope","key":key})
    return {"valid":not errors and missing_identity == 0,"rows":len(rows),"duplicate_count":sum(e["type"]=="duplicate" for e in errors),"missing_identity":missing_identity,"errors":errors}


def _summary(values: list[float | None]) -> dict:
    clean=[v for v in values if v is not None]
    return {"mean":round(mean(clean),3) if clean else None,"sample_count":len(clean),"dispersion":round(stdev(clean),3) if len(clean)>=2 else None}


def sg_window_summary(records: Iterable[dict], player_id: str, *, window: int | str = "season") -> dict:
    rows=[r for r in records if str(r.get("player_id"))==str(player_id) and r.get("scope")=="tournament_cumulative"]
    rows=sorted(rows,key=lambda r:(r.get("date") or "",r.get("game_code") or ""),reverse=True)
    if isinstance(window,int): rows=rows[:window]
    result={"window":window,"player_id":str(player_id),"components":{c:_summary([r.get(c) for r in rows]) for c in SG_COMPONENTS},"event_count":len(rows)}
    return result


def compute_sg_windows(records: Iterable[dict], player_id: str) -> dict:
    return {"recent5":sg_window_summary(records,player_id,window=5),"recent10":sg_window_summary(records,player_id,window=10),"season":sg_window_summary(records,player_id,window="season")}


def sg_trend(recent: dict, baseline: dict, *, threshold: float = TREND_THRESHOLD, minimum_samples: int = MIN_TREND_SAMPLES) -> dict:
    output={}
    for component in SG_COMPONENTS:
        r=recent.get("components",{}).get(component,{ }); b=baseline.get("components",{}).get(component,{ })
        if min(r.get("sample_count",0),b.get("sample_count",0)) < minimum_samples or r.get("mean") is None or b.get("mean") is None:
            state="표본 부족"; delta=None
        else:
            delta=round(r["mean"]-b["mean"],3)
            state="최근 상승" if delta >= threshold else "최근 하락" if delta <= -threshold else "비슷한 흐름"
        output[component]={"state":state,"delta":delta,"threshold":threshold}
    return output


def build_player_performance_profile(*, player_id: str, player_name: str, sg_records: Iterable[dict], score_to_par: dict | None = None, recent_form: dict | None = None, consistency: dict | None = None, hole_tendencies: dict | None = None) -> dict:
    windows=compute_sg_windows(sg_records,player_id)
    return {"player_id":str(player_id),"player_name":player_name,"sg":windows,"score_to_par":score_to_par or {},"recent_form":recent_form or {},"consistency":consistency or {},"hole_tendencies":hole_tendencies or {},"forecast_model_inputs":[],"model_separation":"historical performance analysis; SG is not added to win model"}
