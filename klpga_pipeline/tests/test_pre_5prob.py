"""NEO_PRE_5PROB_V1 -- unit + adversarial tests for the new PRE-only
5-probability Monte Carlo candidate (src/klpga/neo_win/pre_5prob.py),
plus regression coverage for the evidence artifacts this task's
historical-reproduction / backtest / publication-gate work produced.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONTENT = ROOT / "content" / "website_v2"

from klpga.neo_win.pre_5prob import (  # noqa: E402
    DISCLOSED_HISTORICAL_CUT_FRACTION,
    POPULATION_MEAN_SPREAD_FALLBACK,
    PreSimInput,
    build_pre_sim_inputs,
    simulate_pre_tournament,
    verify_monotonicity,
)


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# build_pre_sim_inputs
# ---------------------------------------------------------------------

def test_build_pre_sim_inputs_uses_real_score_when_present():
    rows = [{"player_code": "1", "player_name": "A", "prior_avg_round_score_to_par": -2.0}]
    sim = build_pre_sim_inputs(rows, spread_field=None)
    assert sim[0].expected_round_score_to_par == -2.0
    assert sim[0].expected_source == "prior_avg_round_score_to_par"


def test_build_pre_sim_inputs_falls_back_to_population_mean_when_missing():
    rows = [
        {"player_code": "1", "player_name": "A", "prior_avg_round_score_to_par": -4.0},
        {"player_code": "2", "player_name": "B", "prior_avg_round_score_to_par": None},
    ]
    sim = build_pre_sim_inputs(rows, spread_field=None)
    b = next(p for p in sim if p.player_code == "2")
    assert b.expected_round_score_to_par == -4.0  # population mean of the single known value
    assert b.expected_source == "population_mean_fallback"


def test_build_pre_sim_inputs_spread_fallback_uses_disclosed_constant_when_field_has_no_real_spread():
    rows = [{"player_code": "1", "player_name": "A", "prior_avg_round_score_to_par": -1.0}]
    sim = build_pre_sim_inputs(rows, spread_field="neo_consistency_stddev")
    assert sim[0].spread == POPULATION_MEAN_SPREAD_FALLBACK
    assert sim[0].spread_source == "population_mean_fallback"


def test_build_pre_sim_inputs_never_produces_a_spread_below_the_floor():
    rows = [{"player_code": "1", "player_name": "A", "prior_avg_round_score_to_par": 0.0, "neo_consistency_stddev": 0.01}]
    sim = build_pre_sim_inputs(rows)
    assert sim[0].spread >= 0.5


# ---------------------------------------------------------------------
# simulate_pre_tournament -- invariants
# ---------------------------------------------------------------------

def _fixture_field(n: int = 30) -> list[PreSimInput]:
    rng = random.Random(1)
    return [
        PreSimInput(
            player_code=str(i), player_name=f"P{i}",
            expected_round_score_to_par=rng.uniform(-3, 3), spread=rng.uniform(1.0, 4.0),
            expected_source="test_fixture", spread_source="test_fixture",
        )
        for i in range(n)
    ]


def test_simulate_pre_tournament_every_player_obeys_monotonicity_invariant():
    results = simulate_pre_tournament(_fixture_field(), n_simulations=2000, rng=random.Random(42))
    assert verify_monotonicity(results) == []


def test_simulate_pre_tournament_probabilities_are_bounded_0_to_100():
    results = simulate_pre_tournament(_fixture_field(), n_simulations=2000, rng=random.Random(7))
    for r in results.values():
        for key in ("win_pct", "top5_pct", "top10_pct", "top20_pct", "make_cut_pct"):
            assert 0.0 <= r[key] <= 100.0


def test_simulate_pre_tournament_win_probabilities_sum_to_approximately_100():
    results = simulate_pre_tournament(_fixture_field(), n_simulations=5000, rng=random.Random(3))
    total = sum(r["win_pct"] for r in results.values())
    assert abs(total - 100.0) < 1.0


def test_simulate_pre_tournament_is_deterministic_given_a_fixed_seed():
    field = _fixture_field()
    r1 = simulate_pre_tournament(field, n_simulations=500, rng=random.Random(99))
    r2 = simulate_pre_tournament(field, n_simulations=500, rng=random.Random(99))
    assert r1 == r2


def test_simulate_pre_tournament_never_uses_a_real_round_score_as_input():
    """Adversarial: PreSimInput has no field a real, already-played
    round score could occupy -- unlike round_update.PlayerSimInput
    (r1_score_to_par). This test locks in that PRE-time contract by
    asserting the dataclass's own field set."""
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(PreSimInput)}
    assert "r1_score_to_par" not in field_names
    assert field_names == {"player_code", "player_name", "expected_round_score_to_par", "spread", "expected_source", "spread_source"}


def test_simulate_pre_tournament_stronger_prior_wins_more_often():
    """Sanity: a player with a much better (more negative) expected
    score should win more of the simulated trials than a much worse
    player -- confirms the simulator carries real signal, not noise."""
    strong = PreSimInput("A", "Strong", expected_round_score_to_par=-4.0, spread=1.5, expected_source="t", spread_source="t")
    weak = PreSimInput("B", "Weak", expected_round_score_to_par=4.0, spread=1.5, expected_source="t", spread_source="t")
    field = [strong, weak] + _fixture_field(10)
    results = simulate_pre_tournament(field, n_simulations=3000, rng=random.Random(11))
    assert results["A"]["win_pct"] > results["B"]["win_pct"]


def test_simulate_pre_tournament_empty_field_returns_empty():
    assert simulate_pre_tournament([], n_simulations=100) == {}


def test_disclosed_cut_fraction_matches_published_evidence():
    """Locks in the exact real, published made_cut split this project's
    own docs disclose (docs/SITE_STRUCTURE_TODO.md: made_cut (0,266)/(1,336)
    across 602 rows) -- if that source number is ever corrected, this
    constant must be updated deliberately, never silently."""
    assert abs(DISCLOSED_HISTORICAL_CUT_FRACTION - (336 / 602)) < 1e-9


# ---------------------------------------------------------------------
# Evidence artifacts this task produced -- regression lock-in
# ---------------------------------------------------------------------

def test_backtest_artifact_shows_no_monotonicity_violation():
    doc = _load("NEO_PRE_5PROB_BACKTEST_V1.json")
    assert doc["any_monotonicity_violation"] is False
    for event in doc["events"].values():
        assert event["monotonicity_violations"] == []


def test_backtest_artifact_discloses_ok_field_completeness_limitation():
    doc = _load("NEO_PRE_5PROB_BACKTEST_V1.json")
    ok = doc["events"]["ok_savings_bank_open_2026120001"]
    assert ok["field_completeness"].startswith("CUT_SURVIVORS_ONLY")
    assert ok["cut_calibration"]["n_missed_cut"] == 0


def test_publication_gate_is_blocked_with_evidence():
    doc = _load("NEO_PRE_5PROB_PUBLICATION_GATE_V1.json")
    assert doc["global_verdict"].startswith("BLOCKED")
    assert doc["checks"]["MODEL_VALIDATION"]["status"] == "BLOCKED_INSUFFICIENT_SAMPLE"
    assert doc["checks"]["PROBABILITY_INVARIANTS"]["status"] == "PASS"
    assert doc["checks"]["PUBLICATION_APPROVAL"]["status"] == "BLOCKED"


def test_kb_pre_5prob_status_is_blocked_and_no_candidate_file_exists():
    doc = _load("KB_2026090003_PRE_5PROB_STATUS.json")
    assert doc["KB_PRE_5PROB_STATUS"] == "BLOCKED_MISSING_RAW_FEATURES_IN_SANDBOX"
    assert doc["no_frozen_forecast_created"] is True
    assert not (CONTENT / "KB_2026090003_PRE_5PROB_CANDIDATE_V1.json").is_file()
    assert not (CONTENT / "KB_2026090003_PRE_5PROB_FROZEN_V1.json").is_file()


def test_historical_reproduction_kg_matches_two_event_report_exactly():
    doc = _load("NEO_HISTORICAL_PROBABILITY_REPRODUCTION_V1.json")
    kg = doc["kg_ladies_open_2026080001"]["independent_recomputation"]
    assert kg["winner_hit"] is False
    assert abs(kg["brier"] - 0.00829809) < 1e-6
    assert abs(kg["log_loss"] - 3.96541603) < 1e-6
    assert abs(kg["top5_coverage"] - 0.285714) < 1e-4
    assert abs(kg["top10_coverage"] - 0.2) < 1e-9


def test_historical_reproduction_ok_winner_hit_and_logloss_match():
    doc = _load("NEO_HISTORICAL_PROBABILITY_REPRODUCTION_V1.json")
    ok = doc["ok_savings_bank_open_2026120001"]["independent_recomputation"]
    assert ok["winner_hit"] is True
    assert abs(ok["log_loss"] - 0.006621876308886858) < 1e-9
    assert abs(ok["top5_coverage"] - 0.6) < 1e-9


def test_recovered_ok_final_result_hash_matches_its_own_source_audit():
    """The single individually-reviewed file recovery
    (OK_OPEN_2026_FINAL_RESULT.json, from commit 3047c45) must stay
    self-consistent with its own companion source-audit file."""
    import hashlib
    result_bytes = (CONTENT / "OK_OPEN_2026_FINAL_RESULT.json").read_bytes()
    audit = _load("OK_OPEN_2026_FINAL_RESULT_SOURCE_AUDIT.json")
    assert hashlib.sha256(result_bytes).hexdigest() == audit["result_sha256"]
    assert audit["official_final_confirmed"] is True
    assert "live_snapshot" in audit["not_from"]


def test_integration_status_confirms_no_production_code_was_changed():
    doc = _load("NEO_PRE_5PROB_INTEGRATION_STATUS.json")
    assert doc["code_changed_in_run_tournament_py"] is False
    assert doc["status"] == "DEFERRED_PENDING_PUBLICATION_APPROVAL"


def test_lineage_recovery_doc_exists():
    assert (ROOT / "docs" / "NEO_PROBABILITY_ENGINE_LINEAGE_RECOVERY_V1.md").is_file()
    doc = _load("NEO_PROBABILITY_ENGINE_LINEAGE_RECOVERY_V1.json")
    assert doc["answers"]["does_it_exist_in_current_head"] is True
    assert doc["answers"]["classification"].startswith("PIPELINE_DISCONNECTED")
