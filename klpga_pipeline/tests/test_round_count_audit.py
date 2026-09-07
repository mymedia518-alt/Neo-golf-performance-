"""Regression tests for scripts/103_round_count_audit.py's claims against
the real, committed artifacts. Items 1/2/3 (unit-mismatch arithmetic) and
5/6 (WD/DQ round preservation) are already covered by
test_neo_ranking_v2_unequal_participation_redteam.py's Cases 1/2/5/6 --
this file covers what's specific to the round-count audit itself: scope
separation, the hard-gate outcome, and the WD/DQ-population finding."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("round_count_audit", ROOT / "scripts" / "103_round_count_audit.py")
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)  # type: ignore[union-attr]


def test_hard_gate_is_blocked_not_pass():
    """The audit must never silently upgrade an unverified round count to
    VERIFIED/PASS -- this is the single most important behavioral
    contract from the task instructions."""
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["hard_gate"]["status"] == "BLOCKED"
    assert report["round_count_state"]["verified"] == 0
    assert report["model_state"] == "VALIDATION_MODEL_NOT_PRODUCTION"


def test_frozen_v1_baseline_matches_cited_reference_numbers():
    """The task's cited V1 baseline (82 tournaments, 7830 observations,
    specific Spearman/precision/AUC values) must match the actual frozen
    artifact byte-for-byte -- if this ever fails, either the artifact was
    modified (forbidden) or the citation was wrong."""
    redteam = json.loads((ROOT / "content" / "website_v2" / "NEO_RANKING_V1_REDTEAM_BACKTEST.json").read_text(encoding="utf-8"))
    assert redteam["tournament_count"] == 82
    assert redteam["observation_count"] == 7830
    m = redteam["metrics"]
    assert abs(m["spearman_neo_rank_vs_finish"] - 0.4813430331167408) < 1e-9
    assert abs(m["made_cut_auc"] - 0.7120195073989171) < 1e-9


def test_frozen_v1_population_has_zero_withdrawn_or_disqualified_records():
    """GENUINE FINDING: the 7830-record frozen V1 population contains
    ZERO withdrawn and ZERO disqualified players across all 82
    tournaments. This is either an implausible real-world fact or (more
    likely) evidence that the population-construction pipeline
    systematically excludes WD/DQ players before they reach this
    warehouse -- flagged as UNKNOWN root cause per instruction, not
    assumed. This test locks the finding in as a regression guard: if a
    future warehouse rebuild introduces WD/DQ rows, that is a real change
    worth re-auditing, not something that should silently pass unnoticed."""
    truth = json.loads((ROOT / "content" / "website_v2" / "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json").read_text(encoding="utf-8"))
    records = truth["records"]
    assert len(records) == 7830
    assert sum(1 for r in records if r["outcome"]["withdrawn"]) == 0
    assert sum(1 for r in records if r["outcome"]["disqualified"]) == 0


def test_scope_separation_never_mixes_single_round_into_cumulative_audit():
    """Per explicit instruction ('tournament_cumulative와 single_round를
    절대로 혼합하지 말라'), the round-count audit must use ONLY
    tournament_cumulative rows for its round distribution -- a
    single_round-only event (no cumulative row at all) must be excluded
    and reported separately, never silently substituted in."""
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["single_round_only_events_excluded_not_mixed_in"] > 0, (
        "the real warehouse does contain single_round-only events -- this must be a "
        "nonzero, explicitly reported exclusion, not silently zero"
    )

    sg = json.loads((ROOT / "content" / "website_v2" / "historical_sg_warehouse_corrected.json").read_text(encoding="utf-8"))
    cumulative_keys = {
        (r.get("player_id"), r.get("game_code"))
        for r in sg["records"] if r.get("identity_state") == "RETAINED" and r.get("scope") == "tournament_cumulative"
    }
    assert report["player_events_checked"] == len(cumulative_keys)


def test_9682_vs_7830_gap_is_reported_as_unknown_not_assumed_wd_dq():
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    gap = report["gap_9682_vs_7830_explanation"]
    assert gap["verified_field_players"] == 9682
    assert gap["SG_field_players"] == 7830
    assert gap["missing_from_SG"] == 1852
    assert gap["classification"].startswith("UNKNOWN")


def test_round_distribution_is_recomputed_not_reused_from_stale_prior_claim():
    """The task explicitly discards the old '~44% are 1-round events'
    claim and requires recomputation. This test locks in that the
    recomputed distribution is internally consistent (sums to the
    checked player-event count) rather than re-asserting any specific
    percentage as ground truth."""
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    dist = report["round_distribution"]
    assert sum(dist.values()) == report["player_events_checked"]


def test_duplicate_player_event_keys_are_not_double_counted():
    """Progressive tournament_cumulative snapshots for the same
    (player_id, game_code) (e.g. captured after round 3, then again after
    round 4) must collapse to exactly one player-event, not be counted
    twice."""
    sg = json.loads((ROOT / "content" / "website_v2" / "historical_sg_warehouse_corrected.json").read_text(encoding="utf-8"))
    cumulative_rows = [r for r in sg["records"] if r.get("identity_state") == "RETAINED" and r.get("scope") == "tournament_cumulative"]
    distinct_keys = {(r.get("player_id"), r.get("game_code")) for r in cumulative_rows}
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["player_events_checked"] == len(distinct_keys)
    assert len(cumulative_rows) >= len(distinct_keys)  # raw rows may include progressive duplicates
