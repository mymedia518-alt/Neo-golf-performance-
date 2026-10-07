"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- EXPERIMENTAL
60,000-iteration Stableford Monte Carlo (2026-10-07, operator
instruction). NOT a public model, NOT a website change -- see the
module docstring on klpga.website_v2.stableford_monte_carlo_experiment
for exactly what this does and does not touch.

Runs, in order:
  1. PRIMARY: 108-player field, the 2 real entrants with zero matched
     prior data given the field-neutral-prior distribution, seed=20261007.
  2. SENSITIVITY: same seed, but those 2 entrants EXCLUDED entirely
     (106-player field) -- compares how much the other 106 players'
     own Win/Top10/MakeCut move, to bound how much the synthetic prior
     is actually influencing the headline numbers.
  3. REPRODUCIBILITY: re-runs PRIMARY with the identical seed (must be
     bit-identical) and with 2 different seeds (20261008, 777) to
     check Top10/Win stability isn't a seed artifact.

Writes, under klpga_pipeline/content/website_v2/:
  HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json  (108-row table)
  HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_METHODOLOGY.md
  HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_REDTEAM.md
  HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json

Never touches STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json or any
docs/ public page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.website_v2.stableford_monte_carlo_experiment import (  # noqa: E402
    OUTCOMES,
    SimulationConfig,
    load_field,
    run_monte_carlo,
    validate_cut_rule,
    validate_field_identity,
    validate_no_impossible_outcome,
    validate_probability_sums_exactly,
    validate_probability_vectors,
    validate_scoring_table,
    validate_target_leakage,
)

CONTENT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
SNAPSHOT_PATH = CONTENT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"

RESULTS_PATH = CONTENT / "HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
METHODOLOGY_PATH = CONTENT / "HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_METHODOLOGY.md"
REDTEAM_PATH = CONTENT / "HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_REDTEAM.md"
REPRODUCIBILITY_PATH = CONTENT / "HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json"

PRIMARY_SEED = 20261007
CROSS_CHECK_SEEDS = (20261008, 777)
N_SIMS = 60_000
CUT_SIZE = 60


def _player_row(p, res, idx: int) -> dict:
    stddev_72hole = float(np.std(res.final_points[idx, :]))
    return {
        "player_code": p.player_code,
        "player_name": p.player_name,
        "official_sponsor": p.official_sponsor,
        "nationality": p.nationality,
        "v1_pre_event_rank": p.v1_pre_event_rank,
        "data_status": p.data_status,
        "prior_source": p.prior_source,
        "sample_rounds": p.sample_rounds,
        "sample_holes": p.sample_holes,
        "category_probabilities": dict(zip(OUTCOMES, [round(v, 6) for v in p.probabilities])),
        "expected_points_per_hole": round(float(res.expected_points_per_hole[idx]), 4),
        "expected_72_hole_points": round(float(res.expected_72_hole_points[idx]), 2),
        "median_final_points": float(res.median_final_points[idx]),
        "p10_final_points": float(res.p10_final_points[idx]),
        "p90_final_points": float(res.p90_final_points[idx]),
        "stddev_final_points": round(stddev_72hole, 2),
        "make_cut_pct": round(float(res.make_cut_pct[idx]) * 100, 3),
        "top20_pct": round(float(res.top20_pct[idx]) * 100, 3),
        "top10_pct": round(float(res.top10_pct[idx]) * 100, 3),
        "top5_pct": round(float(res.top5_pct[idx]) * 100, 3),
        "win_pct": round(float(res.win_pct[idx]) * 100, 3),
    }


def main() -> int:
    print("=== VALIDATION (pre-run) ===")
    validate_scoring_table()
    validate_target_leakage(SNAPSHOT_PATH)
    print("scoring table + target leakage: PASS")

    players_primary = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    validate_field_identity(players_primary, expected_size=108)
    validate_probability_vectors(players_primary)
    print(f"field identity (108) + probability vectors: PASS")

    cfg_primary = SimulationConfig(n_sims=N_SIMS, seed=PRIMARY_SEED, cut_size=CUT_SIZE)
    print(f"=== PRIMARY RUN (seed={PRIMARY_SEED}, n_sims={N_SIMS}) ===")
    res_primary = run_monte_carlo(players_primary, cfg_primary)
    validate_no_impossible_outcome(res_primary)
    validate_cut_rule(res_primary, cut_size=CUT_SIZE)
    validate_probability_sums_exactly(res_primary)
    print("post-run validation: PASS")

    print("=== SENSITIVITY RUN (exclude the 2 no-prior-data players, field=106) ===")
    players_sensitivity = load_field(SNAPSHOT_PATH, no_prior_data_policy="exclude")
    validate_field_identity(players_sensitivity, expected_size=106)
    cfg_sensitivity = SimulationConfig(n_sims=N_SIMS, seed=PRIMARY_SEED, cut_size=CUT_SIZE)
    res_sensitivity = run_monte_carlo(players_sensitivity, cfg_sensitivity)
    validate_cut_rule(res_sensitivity, cut_size=CUT_SIZE)

    sens_by_code = {c: i for i, c in enumerate(res_sensitivity.player_codes)}
    sensitivity_deltas = []
    for i, code in enumerate(res_primary.player_codes):
        if code not in sens_by_code:
            continue  # one of the 2 excluded players
        j = sens_by_code[code]
        sensitivity_deltas.append({
            "player_code": code,
            "win_pct_primary": round(float(res_primary.win_pct[i]) * 100, 4),
            "win_pct_sensitivity": round(float(res_sensitivity.win_pct[j]) * 100, 4),
            "win_pct_delta": round(float(res_sensitivity.win_pct[j] - res_primary.win_pct[i]) * 100, 4),
            "top10_pct_delta": round(float(res_sensitivity.top10_pct[j] - res_primary.top10_pct[i]) * 100, 4),
            "make_cut_pct_delta": round(float(res_sensitivity.make_cut_pct[j] - res_primary.make_cut_pct[i]) * 100, 4),
        })
    max_abs_win_delta = max(abs(d["win_pct_delta"]) for d in sensitivity_deltas)
    max_abs_top10_delta = max(abs(d["top10_pct_delta"]) for d in sensitivity_deltas)
    print(f"sensitivity: max |win_pct delta| across 106 shared players = {max_abs_win_delta:.4f} pct points")
    print(f"sensitivity: max |top10_pct delta| across 106 shared players = {max_abs_top10_delta:.4f} pct points")

    print("=== REPRODUCIBILITY ===")
    res_repeat = run_monte_carlo(players_primary, cfg_primary)
    same_seed_identical = (
        np.array_equal(res_primary.final_points, res_repeat.final_points)
        and np.array_equal(res_primary.win_pct, res_repeat.win_pct)
    )
    print(f"same-seed re-run bit-identical: {same_seed_identical}")

    cross_seed_results = []
    primary_top10_win_order = list(np.argsort(-res_primary.win_pct)[:10])
    for seed in CROSS_CHECK_SEEDS:
        cfg_cross = SimulationConfig(n_sims=N_SIMS, seed=seed, cut_size=CUT_SIZE)
        res_cross = run_monte_carlo(players_primary, cfg_cross)
        win_deltas = np.abs(res_cross.win_pct - res_primary.win_pct)
        cross_top10 = set(np.argsort(-res_cross.win_pct)[:10].tolist())
        overlap = len(cross_top10 & set(primary_top10_win_order))
        cross_seed_results.append({
            "seed": seed,
            "max_abs_win_pct_delta_pct_points": round(float(win_deltas.max()) * 100, 4),
            "mean_abs_win_pct_delta_pct_points": round(float(win_deltas.mean()) * 100, 4),
            "top10_win_overlap_with_primary": overlap,
        })
        print(f"seed={seed}: max |win delta|={win_deltas.max()*100:.3f}pp, "
              f"Top10-by-win overlap with primary = {overlap}/10")

    print("=== BUILDING OUTPUT TABLE ===")
    rows = [_player_row(p, res_primary, i) for i, p in enumerate(players_primary)]

    v1_ranked = [r for r in rows if r["v1_pre_event_rank"] is not None]
    top20_by_v1 = sorted(v1_ranked, key=lambda r: r["v1_pre_event_rank"])[:20]
    top20_by_win = sorted(rows, key=lambda r: -r["win_pct"])[:20]

    # V1 rank vs MC win-rank movement, restricted to players who HAVE a
    # real V1 rank (no_prior_data players have no V1 rank to diff against).
    win_rank_by_code = {r["player_code"]: i + 1 for i, r in enumerate(sorted(rows, key=lambda r: -r["win_pct"]))}
    movers = []
    for r in v1_ranked:
        mc_rank = win_rank_by_code[r["player_code"]]
        movers.append({
            "player_code": r["player_code"], "player_name": r["player_name"],
            "v1_pre_event_rank": r["v1_pre_event_rank"], "mc_win_rank": mc_rank,
            "rank_delta": r["v1_pre_event_rank"] - mc_rank,  # positive = moved UP in MC
            "win_pct": r["win_pct"], "top10_pct": r["top10_pct"], "make_cut_pct": r["make_cut_pct"],
            "stddev_final_points": r["stddev_final_points"],
            "category_probabilities": r["category_probabilities"],
        })
    movers.sort(key=lambda m: -abs(m["rank_delta"]))

    results_doc = {
        "schema_version": 1,
        "status": "EXPERIMENTAL -- not deployed to public website, see WEBSITE policy in methodology report",
        "target_game_code": "2026100004",
        "target_cutoff": "2026-10-08",
        "v1_frozen_snapshot_sha256": json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))["sha256"],
        "field_size": 108,
        "eligible_v1_ranked": len(v1_ranked),
        "data_limited_no_prior_data": sum(1 for r in rows if r["data_status"] == "DATA_LIMITED_NO_PRIOR_DATA"),
        "data_limited_thin_sample": sum(1 for r in rows if r["data_status"] == "DATA_LIMITED_THIN_SAMPLE"),
        "simulation": {
            "n_simulations": N_SIMS, "seed": PRIMARY_SEED, "cut_size": CUT_SIZE,
            "cut_rule": "top 60 cumulative Stableford points after R1+R2 (36 holes), ties all advance",
            "scoring_rule": "albatross +8, eagle +5, birdie +2, par 0, bogey -1, double-bogey-or-worse -3",
            "win_tie_rule": "equal win-credit split among tied co-leaders (e.g. 2-way tie = 0.5 each)",
            "topN_tie_rule": "all players tied at the Nth-place boundary score count as making TopN",
            "course_effect": "NONE -- player Stableford distribution only, no A-One course multiplier (section 12 of the operator spec)",
        },
        "players": rows,
        "top20_by_win_probability": top20_by_win,
        "top20_by_v1_pre_event_rank": top20_by_v1,
        "v1_vs_mc_rank_movers": movers,
        "sensitivity_no_prior_data_policy": {
            "max_abs_win_pct_delta_pct_points": round(max_abs_win_delta, 4),
            "max_abs_top10_pct_delta_pct_points": round(max_abs_top10_delta, 4),
            "per_player": sensitivity_deltas,
        },
    }
    RESULTS_PATH.write_text(json.dumps(results_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH} ({RESULTS_PATH.stat().st_size} bytes)")

    reproducibility_doc = {
        "primary_seed": PRIMARY_SEED,
        "n_simulations": N_SIMS,
        "same_seed_rerun_bit_identical": same_seed_identical,
        "cross_seed_checks": cross_seed_results,
    }
    REPRODUCIBILITY_PATH.write_text(json.dumps(reproducibility_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {REPRODUCIBILITY_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
