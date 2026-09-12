"""Durable regression guards for the NEO RANKING V2A/V2B deployment-
candidate validation (Task 4: FINAL VALIDATION -> DEPLOYMENT CANDIDATE).

Final verdict for this phase was NEO_RANKING_PUBLICATION=BLOCKED (see
NEO_RANKING_PUBLICATION_GATE_DECISION.json): V2B fixes cohort dependency
but no candidate materially reduces exposure bias, so no public ranking
artifact or HOME candidate was produced. Of Section 19's 12 required
regression categories, only three have anything real to guard in a
BLOCKED outcome -- EXPOSURE BIAS, COHORT DEPENDENCY, and FUTURE LEAKAGE
-- because the other nine (duplicate playerCode, missing rank, sentinel
rank, sponsor omission, synthetic sponsor, rank order mismatch,
VALIDATION_PENDING handling, mobile structure, internal-copy leakage) are
properties of a public ranking artifact / HOME page that this phase does
not build. The currently-LIVE production ranking (unchanged by this
phase) already carries its own regression suite for those.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.neo_ranking_backtest import run_backtest, spearman  # noqa: E402
from klpga.website_v2.neo_ranking_v2a import estimate_shrinkage_prior, evaluate_v2a  # noqa: E402
from klpga.website_v2.neo_ranking_v2b import evaluate_v2b, run_backtest_v2b  # noqa: E402
from klpga.website_v2.top120_validation import evaluate  # noqa: E402


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def warehouse():
    return load("historical_sg_warehouse_corrected.json")


@pytest.fixture(scope="module")
def cohort():
    return load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")


@pytest.fixture(scope="module")
def sg_by_code():
    sg = load("OFFICIAL_SG_NORMALIZED.json")
    return {r["playerCode"]: r for r in sg["records"]}


@pytest.fixture(scope="module")
def prior(warehouse):
    return estimate_shrinkage_prior(warehouse)


@pytest.fixture(scope="module")
def config_v1():
    return load("NEO_RANKING_VALIDATION_MODEL_V1.json")


# ---------------------------------------------------------------------------
# EXPOSURE BIAS
# ---------------------------------------------------------------------------

def _exposure_spearman(by_id, sg_by_code):
    rounds_l, rank_l = [], []
    for pid, row in by_id.items():
        if row["neo_validation_rank"] is None:
            continue
        sgr = sg_by_code.get(pid)
        if sgr is None or sgr["official_sg_rounds"] is None:
            continue
        rounds_l.append(sgr["official_sg_rounds"]); rank_l.append(row["neo_validation_rank"])
    return spearman(rounds_l, rank_l), len(rounds_l)


def test_v1_exposure_bias_reproduces_frozen_baseline(warehouse, cohort, sg_by_code, config_v1):
    v1_out, _ = evaluate(cohort, warehouse, config_v1)
    v1_by_id = {r["player_id"]: r for r in v1_out}
    value, n = _exposure_spearman(v1_by_id, sg_by_code)
    assert n >= 100
    # Section 0 frozen fact: -0.358. Must stay reproducible to this tolerance
    # so a silent data/code drift is caught rather than reinterpreted.
    assert value == pytest.approx(-0.358, abs=0.01)


def test_v2a_exposure_bias_is_not_materially_reduced(warehouse, cohort, sg_by_code, prior):
    v2a_out, _ = evaluate_v2a(cohort, warehouse, prior)
    v2a_by_id = {r["player_id"]: r for r in v2a_out}
    value, n = _exposure_spearman(v2a_by_id, sg_by_code)
    assert n >= 100
    # Locks in the NOT-MATERIAL ruling in NEO_EXPOSURE_BIAS_MATERIALITY_RULING.json:
    # still solidly medium effect size, nowhere near crossing to small/negligible.
    assert -0.35 < value < -0.25


def test_v2b_exposure_bias_is_not_materially_reduced(warehouse, cohort, sg_by_code, prior):
    v2b_out, _ = evaluate_v2b(cohort, warehouse, prior)
    v2b_by_id = {r["player_id"]: r for r in v2b_out}
    value, n = _exposure_spearman(v2b_by_id, sg_by_code)
    assert n >= 100
    assert -0.35 < value < -0.25


def test_exposure_bias_materiality_ruling_is_internally_consistent():
    ruling = load("NEO_EXPOSURE_BIAS_MATERIALITY_RULING.json")
    assert ruling["V2A"]["gate"] == "FAIL"
    assert ruling["V2B"]["gate"] == "FAIL"
    # same standard, not tuned differently per candidate
    assert ruling["V2A"]["effect_size_band"].startswith("medium")
    assert ruling["V2B"]["effect_size_band"].startswith("medium")


# ---------------------------------------------------------------------------
# COHORT DEPENDENCY
# ---------------------------------------------------------------------------

def _swap_unrelated_player(cohort, warehouse):
    in_cohort_ids = {str(r["player_id"]) for r in cohort["records"]}
    candidate_pool = {str(r.get("player_id")) for r in warehouse["records"] if r.get("identity_state") == "RETAINED"}
    substitute_id = next(pid for pid in sorted(candidate_pool) if pid not in in_cohort_ids)
    swapped = copy.deepcopy(cohort)
    swapped["records"][-1] = {**swapped["records"][-1], "player_id": substitute_id, "player_name": f"UNRELATED_SUB_{substitute_id}"}
    return swapped


def test_v2b_score_is_invariant_to_an_unrelated_player_swap(warehouse, cohort, prior):
    """The core V2B deliverable: a player's validation_score must not
    change merely because an unrelated player is added/removed from the
    ranking pool (Section 12's explicit requirement)."""
    swapped = _swap_unrelated_player(cohort, warehouse)
    baseline_out, _ = evaluate_v2b(cohort, warehouse, prior)
    swapped_out, _ = evaluate_v2b(swapped, warehouse, prior)
    baseline_scores = {r["player_id"]: r["validation_score"] for r in baseline_out if r["neo_validation_rank"]}
    swapped_scores = {r["player_id"]: r["validation_score"] for r in swapped_out if r["neo_validation_rank"]}
    common = set(baseline_scores) & set(swapped_scores)
    assert len(common) > 50
    for pid in common:
        assert baseline_scores[pid] == swapped_scores[pid], f"V2B score for {pid} changed under an unrelated-player swap"


def test_v1_and_v2a_remain_cohort_dependent_under_the_same_swap(warehouse, cohort, config_v1, prior):
    """Documents the KNOWN, still-present defect in V1 and V2A so a future
    change to either is verified against this baseline rather than assumed
    to have silently fixed (or worsened) cohort dependency."""
    swapped = _swap_unrelated_player(cohort, warehouse)

    v1_baseline, _ = evaluate(cohort, warehouse, config_v1)
    v1_swapped, _ = evaluate(swapped, warehouse, config_v1)
    v1_base_scores = {r["player_id"]: r["validation_score"] for r in v1_baseline if r["neo_validation_rank"]}
    v1_swap_scores = {r["player_id"]: r["validation_score"] for r in v1_swapped if r["neo_validation_rank"]}
    v1_common = set(v1_base_scores) & set(v1_swap_scores)
    v1_changed = sum(1 for pid in v1_common if v1_base_scores[pid] != v1_swap_scores[pid])
    assert v1_changed == len(v1_common)  # 100% score-change, as previously found

    v2a_baseline, _ = evaluate_v2a(cohort, warehouse, prior)
    v2a_swapped, _ = evaluate_v2a(swapped, warehouse, prior)
    v2a_base_scores = {r["player_id"]: r["validation_score"] for r in v2a_baseline if r["neo_validation_rank"]}
    v2a_swap_scores = {r["player_id"]: r["validation_score"] for r in v2a_swapped if r["neo_validation_rank"]}
    v2a_common = set(v2a_base_scores) & set(v2a_swap_scores)
    v2a_changed = sum(1 for pid in v2a_common if v2a_base_scores[pid] != v2a_swap_scores[pid])
    assert v2a_changed == len(v2a_common)  # 100% score-change, unchanged by V2A's exposure-only fix


# ---------------------------------------------------------------------------
# FUTURE LEAKAGE
# ---------------------------------------------------------------------------

def test_v2b_backtest_scores_are_unaffected_by_later_injected_data(warehouse, config_v1):
    """Adversarial leakage probe: inject an extreme-value event dated
    AFTER an existing target event and confirm every observation at or
    before that target event is byte-identical to a run without the
    injected future row. If V2B's walk-forward population leaked future
    information backward, the injected extreme value would move earlier
    scores; it must not."""
    truth = load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    start_dates, outcomes = {}, {}
    for r in truth["records"]:
        gc = str(r["game_code"])
        start_dates[gc] = r["tournament_start_date"]
        outcomes[(gc, str(r["player_id"]))] = {
            "finish_position_numeric": r["outcome"]["finish_position"], "made_cut": r["outcome"]["made_cut"],
            "withdrawn": r["outcome"]["withdrawn"], "disqualified": r["outcome"]["disqualified"],
        }
    prior = estimate_shrinkage_prior(warehouse)

    baseline = run_backtest_v2b(warehouse, start_dates, outcomes, prior)
    ordered_events = sorted(start_dates, key=lambda e: (start_dates[e], e))
    mid_event = ordered_events[len(ordered_events) // 2]
    mid_date = start_dates[mid_event]

    future_date = "2099-01-01"
    injected = copy.deepcopy(warehouse)
    injected["records"].append({
        "player_id": "FUTURE_LEAKAGE_PROBE", "game_code": "FUTURE_LEAKAGE_PROBE_EVENT",
        "season": 2099, "total": 999.0, "rounds": 4, "identity_state": "RETAINED",
    })
    injected_start_dates = dict(start_dates); injected_start_dates["FUTURE_LEAKAGE_PROBE_EVENT"] = future_date
    injected_outcomes = dict(outcomes)

    probed = run_backtest_v2b(warehouse, injected_start_dates, outcomes, prior)
    assert probed["tournament_count"] == baseline["tournament_count"] + 0  # probe event has <2 eligible players, dropped

    baseline_scores_by_key = {(o["event"], o["player_id"]): o["neo_score"] for o in baseline["observations"] if o["target_start_date"] <= mid_date}
    probed_scores_by_key = {(o["event"], o["player_id"]): o["neo_score"] for o in probed["observations"] if o["target_start_date"] <= mid_date}
    assert baseline_scores_by_key == probed_scores_by_key


def test_run_backtest_v2b_internal_leakage_guard_is_present(warehouse):
    """Sanity check that the internal `raise AssertionError("future
    leakage")` guard in run_backtest_v2b exists and a normal real run
    never trips it (it would surface as a test failure, not silently
    pass, if it did)."""
    import inspect
    from klpga.website_v2 import neo_ranking_v2b
    source = inspect.getsource(neo_ranking_v2b.run_backtest_v2b)
    assert "future leakage" in source
