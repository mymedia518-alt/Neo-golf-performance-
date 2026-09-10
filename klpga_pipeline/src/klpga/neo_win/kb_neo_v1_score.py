"""Reproduce NEO Ranking V1's NEO_V1_score for a NEW target cohort
(e.g. KB 2026090003), using the exact frozen formula from
NEO_RANKING_VALIDATION_MODEL_V1.json and the same arithmetic as
klpga.website_v2.neo_ranking_backtest.run_backtest's per-event scoring
body -- copied inline here, not re-derived from prose, so the
computation is provably identical. See
content/website_v2/KB_2026090003_NEO_V1_SCORE_REPRODUCTION_BLOCKER_V1.json
for the two failed date-source attempts and why a complete, exact
game_code -> start_date mapping (TOURNAMENT_MASTER_DATES_V1.json,
extracted verbatim from tournament_master) is required: any other
tried source either had the wrong date value or incomplete game_code
coverage, and both silently changed the computed score. This module
changes NOTHING about the model: same weights, same cohort z-score
normalization, same 10-event eligibility minimum -- verified by
tests/test_kb_neo_v1_score.py to reproduce all 7830 real historical
NEO_V1_score observations exactly (0 mismatches, sha256-verified
config).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Optional


def _z(values: dict[str, float]) -> dict[str, float]:
    """Copied verbatim from klpga.website_v2.neo_ranking_backtest._z."""
    mean = statistics.fmean(values.values())
    sd = statistics.pstdev(values.values())
    return {k: (v - mean) / sd if sd else 0.0 for k, v in values.items()}


def build_history(
    sg_warehouse_corrected: dict, gc_date: dict[str, str], target_date: str
) -> dict[str, list[tuple[str, float]]]:
    """Per-player list of (date, SG total) for every prior event
    strictly before target_date. Exact equivalent of
    neo_ranking_backtest._latest_records, generalized to filter by an
    arbitrary target_date instead of iterating the whole historical
    corpus chronologically."""
    latest: dict[tuple[str, str], dict] = {}
    for row in sg_warehouse_corrected.get("records", ()):
        player_id = str(row.get("player_id") or "")
        game_code = row.get("game_code")
        if not player_id or game_code not in gc_date or row.get("identity_state") != "RETAINED":
            continue
        if not isinstance(row.get("total"), (int, float)):
            continue
        date = gc_date[game_code]
        if date is None or date >= target_date:
            continue
        key = (player_id, game_code)
        if key not in latest or int(row.get("rounds") or 0) >= int(latest[key].get("rounds") or 0):
            latest[key] = row

    history: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (player_id, game_code), row in latest.items():
        history[player_id].append((gc_date[game_code], float(row["total"])))
    for player_id in history:
        history[player_id].sort()
    return history


def score_cohort(
    player_ids: list[str],
    target_date: str,
    sg_warehouse_corrected: dict,
    gc_date: dict[str, str],
    weights: dict[str, float],
    minimum_sg_events: int,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Exact scoring arithmetic from run_backtest's per-event body,
    restricted to `player_ids` as the eligible-cohort universe. Returns
    (scores, contributions) -- a player_id absent from `scores` had
    fewer than `minimum_sg_events` prior SG events and is never
    assigned a fabricated/imputed value."""
    history = build_history(sg_warehouse_corrected, gc_date, target_date)
    eligible = {pid: [v for _, v in history.get(pid, [])] for pid in player_ids}
    eligible = {pid: vals for pid, vals in eligible.items() if len(vals) >= minimum_sg_events}
    if len(eligible) < 2:
        return {}, {}

    raw = {
        "recent_5_sg": {p: statistics.fmean(v[-5:]) for p, v in eligible.items()},
        "recent_10_sg": {p: statistics.fmean(v[-10:]) for p, v in eligible.items()},
        "long_term_sg": {p: statistics.fmean(v) for p, v in eligible.items()},
        "consistency": {p: -statistics.pstdev(v) if len(v) > 1 else 0.0 for p, v in eligible.items()},
    }
    z = {name: _z(vals) for name, vals in raw.items()}

    scores: dict[str, float] = {}
    contributions: dict[str, dict[str, float]] = {}
    for pid, vals in eligible.items():
        contributions[pid] = {name: weights[name] * z[name][pid] for name in z}
        contributions[pid]["sample_reliability"] = weights["sample_reliability"] * min(len(vals) / 20, 1)
        scores[pid] = sum(contributions[pid].values())
    return scores, contributions
