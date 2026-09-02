"""Evaluation-only NEO ranking for the official K-Ranking TOP120 cohort."""
from __future__ import annotations

import math
import statistics

from .home_ranking import build_features


def validate_cohort(document: dict) -> list[dict]:
    if document.get("population_kind") != "official_klpga_kranking_top120":
        raise ValueError("population is not official K-Ranking TOP120")
    rows = list(document.get("records", ()))
    ranks = [row.get("official_k_rank") for row in rows]
    ids = [str(row.get("player_id") or "") for row in rows]
    if len(rows) != 120 or ranks != list(range(1, 121)):
        raise ValueError("official ranks must be exactly 1..120")
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("player_id must be populated and unique")
    if len({row.get("player_name") for row in rows}) != 120:
        raise ValueError("player names must be unique")
    if any(not row.get("player_name") or not row.get("official_source") or not row.get("retrieved_at") for row in rows):
        raise ValueError("name and provenance are required")
    return rows


def _z(values: dict[str, float]) -> dict[str, float]:
    mean = statistics.fmean(values.values())
    sd = statistics.pstdev(values.values())
    return {key: (value - mean) / sd if sd else 0.0 for key, value in values.items()}


def evaluate(cohort: dict, warehouse: dict, config: dict) -> tuple[list[dict], dict]:
    rows = validate_cohort(cohort)
    features = build_features(warehouse)
    minimum = int(config["eligibility"]["minimum_sg_events"])
    # Eligibility gates only the optional NEO value.  It never changes HOME membership.
    eligible_ids = [str(row["player_id"]) for row in rows if features.get(str(row["player_id"]), {}).get("sample_count", 0) >= minimum]
    components = {}
    for name in ("recent_5_sg", "recent_10_sg", "long_term_sg"):
        components[name] = _z({pid: float(features[pid][name]) for pid in eligible_ids}) if eligible_ids else {}
    components["consistency"] = _z({pid: -float(features[pid]["volatility"]) for pid in eligible_ids}) if eligible_ids else {}
    weights = {name: float(spec["weight"]) for name, spec in config["features"].items()}
    scores = {}
    contributions = {}
    for pid in eligible_ids:
        reliability = min(float(features[pid]["sample_count"]) / 20.0, 1.0)
        contributions[pid] = {name: weights[name] * components[name][pid] for name in components}
        contributions[pid]["sample_reliability"] = weights["sample_reliability"] * reliability
        scores[pid] = sum(contributions[pid].values())
    ordered = sorted(scores, key=lambda pid: (-scores[pid], pid))
    neo_rank = {pid: rank for rank, pid in enumerate(ordered, 1)}
    output = []
    for row in rows:
        pid = str(row["player_id"]); feature = features.get(pid)
        rank = neo_rank.get(pid)
        output.append({**row, "features": feature, "sg_join_state": "PASS" if feature else "DATA_INSUFFICIENT", "neo_validation_rank": rank,
                       "validation_score": round(scores[pid], 6) if rank else None,
                       "feature_contributions": ({key: round(value, 6) for key, value in contributions[pid].items()} if rank else None),
                       "neo_ranking_state": "VALIDATION_MODEL" if rank else "VALIDATION_PENDING",
                       "rank_delta": int(row["official_k_rank"]) - rank if rank else None,
                       "model_id": config["model_id"]})
    summary = {
        "cohort_count": 120,
        "identity_connected": sum(row.get("identity_validation_state") == "PASS_OFFICIAL_PLAYER_ID" for row in rows),
        "sg_connected": sum(row["features"] is not None for row in output),
        "sg_not_connected": sum(row["features"] is None for row in output),
        "recent5_ready": sum(bool(row["features"] and row["features"]["sample_count"] >= 5) for row in output),
        "recent10_ready": sum(bool(row["features"] and row["features"]["sample_count"] >= 10) for row in output),
        "neo_ranked": len(eligible_ids),
        "validation_pending": 120 - len(eligible_ids),
    }
    return output, summary
