"""Data contracts and feature extraction for the persistent player HOME.

HOME ranking is deliberately isolated from ``klpga.neo_win``.  Until an
approved, versioned formula exists this module never emits a numeric NEO rank.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"
NEO_RANKING_VERSION = None


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_population(document: dict) -> list[dict]:
    records = list(document.get("records", ()))
    ids = [str(row.get("player_id", "")).strip() for row in records]
    if not records:
        raise ValueError("HOME population is empty")
    if any(not player_id for player_id in ids):
        raise ValueError("HOME population contains a blank player_id")
    if len(ids) != len(set(ids)):
        raise ValueError("HOME population contains duplicate player_id")
    if any(not str(row.get("player_name", "")).strip() for row in records):
        raise ValueError("HOME population contains a blank player_name")
    if document.get("population_kind") != "regular_tour_historical_player_master":
        raise ValueError("HOME population must use the canonical regular-tour player master")
    if document.get("population_validation_state") != "BLOCKED_CURRENT_REGISTRY_EQUIVALENCE_NOT_PROVEN":
        raise ValueError("population scope must retain its current-registration validation block")
    return records


def build_features(warehouse: dict) -> dict[str, dict]:
    """Reduce the corrected SG warehouse once, keyed only by player_id.

    The source holds cumulative snapshots for several rounds.  For each
    player/event, the most complete snapshot (largest rounds value) is used.
    """
    latest: dict[tuple[str, str], dict] = {}
    for row in warehouse.get("records", ()):
        player_id = str(row.get("player_id") or "").strip()
        game_code = str(row.get("game_code") or "").strip()
        if not player_id or not game_code or row.get("identity_state") != "RETAINED":
            continue
        total = row.get("total")
        if not isinstance(total, (int, float)) or not math.isfinite(float(total)):
            continue
        key = (player_id, game_code)
        if key not in latest or int(row.get("rounds") or 0) >= int(latest[key].get("rounds") or 0):
            latest[key] = row

    grouped: dict[str, list[dict]] = defaultdict(list)
    for (player_id, _), row in latest.items():
        grouped[player_id].append(row)

    result = {}
    for player_id, rows in grouped.items():
        rows.sort(key=lambda row: (int(row.get("season") or 0), str(row.get("game_code") or "")))
        totals = [float(row["total"]) for row in rows]
        result[player_id] = {
            "recent_5_sg": round(statistics.fmean(totals[-5:]), 3),
            "recent_10_sg": round(statistics.fmean(totals[-10:]), 3),
            "long_term_sg": round(statistics.fmean(totals), 3),
            "sample_count": len(totals),
            "volatility": round(statistics.pstdev(totals), 3) if len(totals) > 1 else 0.0,
            "eligibility": "FEATURES_READY" if len(totals) >= 10 else "INSUFFICIENT_SAMPLE",
            "validation_state": "PASS_CORRECTED_SG_WAREHOUSE",
            "source_artifact": "historical_sg_warehouse_corrected.json",
        }
    return result


def join_home_rows(population: dict, ranking: dict, warehouse: dict) -> tuple[list[dict], dict]:
    players = validate_population(population)
    ranking_by_id = {str(row["player_id"]): row for row in ranking.get("records", ())}
    features = build_features(warehouse)
    rows = []
    joined = 0
    for player in players:
        player_id = str(player["player_id"])
        official = ranking_by_id.get(player_id)
        if official and official.get("validation_state") == "PASS":
            joined += 1
        rows.append({
            "player_id": player_id,
            "player_name": player["player_name"],
            "neo_rank": None,
            "neo_ranking_state": FORMULA_STATE,
            "k_rank": official.get("official_rank") if official else None,
            "k_ranking_state": "PASS" if official else "NOT_FOUND_IN_AVAILABLE_OFFICIAL_SNAPSHOT",
            "k_ranking_source": ranking.get("official_source"),
            "features": features.get(player_id),
            "population_provenance": player.get("provenance"),
        })
    return rows, {
        "population_count": len(rows),
        "k_ranking_join_success": joined,
        "k_ranking_join_failure": len(rows) - joined,
        "neo_ranking_published": 0,
        "neo_ranking_pending": len(rows),
        "neo_formula_state": FORMULA_STATE,
    }
