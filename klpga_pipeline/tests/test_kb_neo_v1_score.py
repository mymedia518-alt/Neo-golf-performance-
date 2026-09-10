"""klpga.neo_win.kb_neo_v1_score -- regression tests.

The whole point of this module is exact reproduction of NEO Ranking
V1's frozen scoring. These tests re-derive ALL 7830 real historical
NEO_V1_score observations across all 82 tournaments in
NEO_RANKING_V1_REDTEAM_BACKTEST.json and require an exact match
(within 1e-6) for every single one -- not a sample -- since this is
the regression gate the whole KB application depends on.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.kb_neo_v1_score import score_cohort  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _config():
    config = _load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    assert hashlib.sha256((CONTENT / "NEO_RANKING_VALIDATION_MODEL_V1.json").read_bytes()).hexdigest() == \
        "0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643"
    weights = {name: float(spec["weight"]) for name, spec in config["features"].items()}
    minimum = int(config["eligibility"]["minimum_sg_events"])
    return weights, minimum


def test_reproduces_every_historical_neo_v1_score_exactly():
    weights, minimum = _config()
    sg_warehouse = _load("historical_sg_warehouse_corrected.json")
    tm_dates = _load("TOURNAMENT_MASTER_DATES_V1.json")
    gc_date = dict(tm_dates["dates"])

    backtest = _load("NEO_RANKING_V1_REDTEAM_BACKTEST.json")
    obs_by_event = defaultdict(list)
    for o in backtest["observations"]:
        obs_by_event[o["event"]].append(o)

    total_rows = 0
    total_mismatches = 0
    for event, obs in obs_by_event.items():
        target_date = obs[0]["target_start_date"]
        player_ids = [o["player_id"] for o in obs]
        scores, _ = score_cohort(player_ids, target_date, sg_warehouse, gc_date, weights, minimum)
        for o in obs:
            total_rows += 1
            expected = o["neo_score"]
            actual = round(scores.get(o["player_id"], float("nan")), 8)
            if abs(actual - expected) > 1e-6:
                total_mismatches += 1

    assert total_rows == backtest["observation_count"] == 7830
    assert total_mismatches == 0


def test_ineligible_player_gets_no_score_not_a_fabricated_one():
    weights, minimum = _config()
    sg_warehouse = _load("historical_sg_warehouse_corrected.json")
    tm_dates = _load("TOURNAMENT_MASTER_DATES_V1.json")
    gc_date = dict(tm_dates["dates"])

    scores, _ = score_cohort(["nonexistent-rookie-999999"], "2026-09-10", sg_warehouse, gc_date, weights, minimum)
    assert "nonexistent-rookie-999999" not in scores


def test_reproduction_requires_tournament_master_dates_not_a_substitute():
    """Guard against a future edit reintroducing one of the two
    already-proven-wrong date sources."""
    source = (ROOT / "scripts" / "108_apply_r1_model_to_kb.py").read_text(encoding="utf-8")
    assert "TOURNAMENT_MASTER_DATES_V1.json" in source
    assert "historical_sg_warehouse.json" not in source  # the wrong 'date' field source
    assert 'NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json' not in source  # the incomplete-coverage source
