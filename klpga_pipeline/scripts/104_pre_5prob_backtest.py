"""NEO PRE 5-PROBABILITY CANDIDATE V1 -- historical walk-forward smoke
test against the ONLY two historical events with a real, complete
final result present in this sandbox: KG Ladies Open (2026080001) and
OK Savings Bank Open (2026120001).

======================================================================
HONEST SAMPLE-SIZE DISCLOSURE -- READ BEFORE TRUSTING ANY NUMBER BELOW
======================================================================
N=2. This is a smoke test proving the simulator RUNS and its outputs
obey the required invariants against real data -- it is NOT a
statistically powered validation and must never be reported as one.
No calibration or generalization claim can be made from 2 events. See
NEO_PRE_5PROB_PUBLICATION_GATE_V1.json, which reads this file's output
and is expected to record BLOCKED_INSUFFICIENT_SAMPLE for exactly this
reason, regardless of how good these two smoke-test scores look.

======================================================================
PER-EVENT INPUT PROVENANCE (deliberately NOT uniform across events --
disclosed, not hidden)
======================================================================
KG (2026080001): `prior_avg_round_score_to_par` from the frozen PRE
prediction (predictions/2026/prediction_001_2026080001.json). No
`neo_consistency_stddev` is available anywhere in this sandbox for
KG's real players (the frozen archive that would carry it,
neo_win_predictions/, was never actually populated here) -- every KG
player's spread therefore falls back to
`pre_5prob.POPULATION_MEAN_SPREAD_FALLBACK`, exactly as
`build_pre_sim_inputs` already discloses it will when the field carries
no real spread at all.

OK (2026120001): `expected_final_round_to_par` and `spread` read
directly from the already-frozen, already-published
OK_OPEN_2026_POST_R2_FINAL_FORECAST.json (`expected_source:"recent5"`,
`spread_source:"legacy_sample_sd"` per that file's own records) -- both
are genuine PRE-time features (a player's historical recent-5-tournament
scoring average and its sample stddev), unaffected by this specific
tournament's own R1/R2 result, so reusing them here as this player's
PRE-tournament prior is legitimate REUSE of an already-computed,
already-disclosed feature -- not new leakage. This is disclosed here
as a real methodological difference from KG's input source, not
smoothed over.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.pre_5prob import (  # noqa: E402
    DISCLOSED_HISTORICAL_CUT_FRACTION,
    MODEL_ID,
    build_pre_sim_inputs,
    simulate_pre_tournament,
    verify_monotonicity,
)

CONTENT = ROOT / "content" / "website_v2"
SEED = 20260909
N_SIMULATIONS = 20000


def _brier_and_logloss_for_win(results: dict, actual_winner_id: str) -> tuple[float, float]:
    sq_errs = []
    p_winner = 0.0
    for pid, r in results.items():
        p = r["win_pct"] / 100.0
        y = 1.0 if pid == actual_winner_id else 0.0
        sq_errs.append((p - y) ** 2)
        if pid == actual_winner_id:
            p_winner = p
    brier = sum(sq_errs) / len(sq_errs)
    log_loss = -math.log(max(p_winner, 1e-12))
    return brier, log_loss


def _topn_coverage(results: dict, actual_rank_by_id: dict, prob_field: str, n: int) -> float:
    actual_topn = {pid for pid, rank in actual_rank_by_id.items() if rank <= n}
    pred_sorted = sorted(results.items(), key=lambda kv: -kv[1][prob_field])
    pred_topn = {pid for pid, _ in pred_sorted[:n]}
    if not actual_topn:
        return 0.0
    return len(actual_topn & pred_topn) / len(actual_topn)


def _cut_calibration(results: dict, actual_made_cut_by_id: dict) -> dict:
    """Mean predicted make_cut_pct for players who actually made the
    cut vs. those who did not -- a real players should show higher
    mean predicted make_cut_pct than missed-cut players if the model
    carries any real signal; this does NOT compute a full reliability
    curve (N is far too small for bins to mean anything)."""
    made = [results[pid]["make_cut_pct"] for pid, made_cut in actual_made_cut_by_id.items() if made_cut and pid in results]
    missed = [results[pid]["make_cut_pct"] for pid, made_cut in actual_made_cut_by_id.items() if not made_cut and pid in results]
    return {
        "mean_predicted_make_cut_pct_for_actual_made_cut": round(sum(made) / len(made), 4) if made else None,
        "mean_predicted_make_cut_pct_for_actual_missed_cut": round(sum(missed) / len(missed), 4) if missed else None,
        "n_made_cut": len(made),
        "n_missed_cut": len(missed),
    }


def run_kg() -> dict:
    pred = json.loads((ROOT / "predictions" / "2026" / "prediction_001_2026080001.json").read_text(encoding="utf-8"))
    official = json.loads((CONTENT / "kg_2026080001_official.json").read_text(encoding="utf-8"))

    field_rows = [
        {"player_code": e["player_code"], "player_name": e["player_name_display"], "prior_avg_round_score_to_par": e["prior_avg_round_score_to_par"]}
        for e in pred["predictions"]
    ]
    sim_inputs = build_pre_sim_inputs(field_rows, spread_field=None)
    rng = random.Random(SEED)
    results = simulate_pre_tournament(sim_inputs, n_simulations=N_SIMULATIONS, rng=rng)

    leaderboard = official["leaderboard"]
    actual_rank_by_id = {r["player_id"]: r["rank_numeric"] for r in leaderboard if r.get("rank_numeric") is not None}
    actual_made_cut_by_id = {
        r["player_id"]: sum(1 for s in r.get("rounds", []) if s is not None) >= 4
        for r in leaderboard
    }
    actual_winner_id = min(actual_rank_by_id, key=lambda pid: actual_rank_by_id[pid])

    brier, log_loss = _brier_and_logloss_for_win(results, actual_winner_id)
    return {
        "game_code": "2026080001",
        "tournament_name": "KG Ladies Open",
        "n_field": len(sim_inputs),
        "actual_winner_id": actual_winner_id,
        "predicted_winner_id": max(results, key=lambda pid: results[pid]["win_pct"]),
        "winner_hit": max(results, key=lambda pid: results[pid]["win_pct"]) == actual_winner_id,
        "win_probability_pct_assigned_to_actual_winner": results.get(actual_winner_id, {}).get("win_pct"),
        "win_brier": round(brier, 8),
        "win_log_loss": round(log_loss, 8),
        "top5_coverage": round(_topn_coverage(results, actual_rank_by_id, "top5_pct", 5), 6),
        "top10_coverage": round(_topn_coverage(results, actual_rank_by_id, "top10_pct", 10), 6),
        "top20_coverage": round(_topn_coverage(results, actual_rank_by_id, "top20_pct", 20), 6),
        "cut_calibration": _cut_calibration(results, actual_made_cut_by_id),
        "monotonicity_violations": verify_monotonicity(results),
        "input_provenance": "prior_avg_round_score_to_par (real, frozen PRE); spread = population_mean_fallback (no real neo_consistency_stddev available in this sandbox)",
        "field_completeness": "FULL_FIELD (120 of 120 real entrants) -- cut/win/top-N metrics below cover the genuine full PRE-stage field.",
    }


def run_ok() -> dict:
    forecast = json.loads((CONTENT / "OK_OPEN_2026_POST_R2_FINAL_FORECAST.json").read_text(encoding="utf-8"))
    final = json.loads((CONTENT / "OK_OPEN_2026_FINAL_RESULT.json").read_text(encoding="utf-8"))

    field_rows = [
        {
            "player_code": r["player_id"], "player_name": r["player_name"],
            "prior_avg_round_score_to_par": r["expected_final_round_to_par"],
            "neo_consistency_stddev": r["spread"],
        }
        for r in forecast["records"]
    ]
    sim_inputs = build_pre_sim_inputs(field_rows)
    rng = random.Random(SEED)
    results = simulate_pre_tournament(sim_inputs, n_simulations=N_SIMULATIONS, rng=rng)

    final_records = final["records"]
    actual_rank_by_id = {r["player_code"]: r["rank"] for r in final_records}
    actual_made_cut_by_id = {r["player_code"]: True for r in final_records}
    for r in forecast["records"]:
        actual_made_cut_by_id.setdefault(r["player_id"], False)
    actual_winner_id = min(actual_rank_by_id, key=lambda pid: actual_rank_by_id[pid])

    brier, log_loss = _brier_and_logloss_for_win(results, actual_winner_id)
    return {
        "game_code": "2026120001",
        "tournament_name": "OK Savings Bank Open",
        "n_field": len(sim_inputs),
        "actual_winner_id": actual_winner_id,
        "predicted_winner_id": max(results, key=lambda pid: results[pid]["win_pct"]),
        "winner_hit": max(results, key=lambda pid: results[pid]["win_pct"]) == actual_winner_id,
        "win_probability_pct_assigned_to_actual_winner": results.get(actual_winner_id, {}).get("win_pct"),
        "win_brier": round(brier, 8),
        "win_log_loss": round(log_loss, 8),
        "top5_coverage": round(_topn_coverage(results, actual_rank_by_id, "top5_pct", 5), 6),
        "top10_coverage": round(_topn_coverage(results, actual_rank_by_id, "top10_pct", 10), 6),
        "top20_coverage": round(_topn_coverage(results, actual_rank_by_id, "top20_pct", 20), 6),
        "cut_calibration": _cut_calibration(results, actual_made_cut_by_id),
        "monotonicity_violations": verify_monotonicity(results),
        "input_provenance": "expected_final_round_to_par + spread reused verbatim from OK_OPEN_2026_POST_R2_FINAL_FORECAST.json (real recent5/legacy_sample_sd PRE-time features)",
        "field_completeness": (
            "CUT_SURVIVORS_ONLY (68 of the real ~120-entrant field) -- "
            "OK_OPEN_2026_POST_R2_FINAL_FORECAST.json only carries PRE-time expected-score/spread "
            "features for players who survived the real cut, because it was built post-cut. "
            "make_cut_pct / cut_calibration for this event is NOT a genuine PRE-stage cut estimate "
            "(confirmed by n_missed_cut=0 above -- every player in this reduced field made the real "
            "cut) and must not be read as one. win/top5/top10/top20 are conditioned on this reduced "
            "68-player field, not the full 120-entrant PRE field, and are directional only."
        ),
    }


def _uniform_baseline(n_field: int) -> tuple[float, float]:
    """Field-rate baseline: every player assigned win probability
    1/n_field. brier = (1/n - 1)^2/n * 1 + (1/n)^2 * (n-1)/n (one
    winner, n-1 losers, all assigned the same p=1/n)."""
    p = 1.0 / n_field
    brier = ((p - 1.0) ** 2 + (n_field - 1) * p ** 2) / n_field
    log_loss = -math.log(p)
    return round(brier, 8), round(log_loss, 8)


def main() -> None:
    kg = run_kg()
    ok = run_ok()
    kg["uniform_field_rate_baseline"] = dict(zip(("win_brier", "win_log_loss"), _uniform_baseline(kg["n_field"])))
    kg["beats_uniform_baseline_on_brier"] = kg["win_brier"] < kg["uniform_field_rate_baseline"]["win_brier"]
    kg["existing_model_reference"] = {
        "model": "M4 (win-only, current production PRE model)",
        "win_brier": 0.00829809,
        "note": "M4's own real, independently-reproduced KG Brier (see NEO_HISTORICAL_PROBABILITY_REPRODUCTION_V1.json) -- this candidate's KG win_brier above is NOT better than M4's; a new model does not automatically outperform an existing one just for existing.",
    }
    ok["uniform_field_rate_baseline"] = dict(zip(("win_brier", "win_log_loss"), _uniform_baseline(ok["n_field"])))
    ok["beats_uniform_baseline_on_brier"] = ok["win_brier"] < ok["uniform_field_rate_baseline"]["win_brier"]
    doc = {
        "schema_version": "neo_pre_5prob_backtest_v1",
        "model_id": MODEL_ID,
        "purpose": "Smoke-test the new PRE-only 5-probability Monte Carlo candidate against the only 2 historical events with a real, complete final result present in this sandbox. N=2 is NOT a statistically powered validation -- see module docstring and NEO_PRE_5PROB_PUBLICATION_GATE_V1.json.",
        "n_simulations": N_SIMULATIONS,
        "seed": SEED,
        "cut_fraction_used": DISCLOSED_HISTORICAL_CUT_FRACTION,
        "cut_fraction_source": "docs/SITE_STRUCTURE_TODO.md disclosed made_cut split (336 made-cut / 602 total player_event rows) -- real evidence, not invented; a live-DB caller should prefer round_update.estimate_cut_fraction instead",
        "sample_size_disclosure": "N=2 historical events. No Brier/log-loss/coverage figure below should be read as a calibration claim -- both are single-event smoke-test outcomes only.",
        "events": {"kg_ladies_open_2026080001": kg, "ok_savings_bank_open_2026120001": ok},
        "any_monotonicity_violation": bool(kg["monotonicity_violations"] or ok["monotonicity_violations"]),
    }
    out_path = CONTENT / "NEO_PRE_5PROB_BACKTEST_V1.json"
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_path}")
    print(json.dumps(doc, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
