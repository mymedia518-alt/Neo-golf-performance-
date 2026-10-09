"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- POST-R2 Stableford
Monte Carlo R3 forecast (2026-10-09, operator instruction).

R1+R2 are now REAL, officially observed results (not simulated): see
content/website_v2/HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json,
collected and cross-verified against klpga.co.kr's live Stableford
leaderboard (this sandbox cannot reach klpga.co.kr directly -- fetched
via .github/workflows/fetch-hj-2026100004-stableford-rounds-oneoff.yml
on a GitHub-hosted runner with real network access). The official cut
(top 60 and ties) has already been applied by KLPGA itself: 61 players
advanced, 46 missed the cut, 1 withdrew. This script predicts ONLY the
remaining 2 rounds (R3+R4) for those 61 real survivors -- the 46 cut
and 1 WD players are excluded from simulation entirely, never assigned
a win/Top10/Top20 probability.

Deliberately reuses, unmodified, from stableford_monte_carlo_experiment
(the SAME engine the PRE-event V1 Monte Carlo run used):
  - load_field() against the SAME frozen pre-event snapshot, to get
    each of the 61 survivors' own real historical per-hole outcome
    distribution (PlayerDistribution.probabilities) -- their skill
    model is NOT re-fit on R1/R2 data; only their STARTING SCORE
    changes (from 0 to their real, official R1+R2 total).
  - The exact same per-hole multinomial sampling mechanism
    (OUTCOMES/POINTS_VECTOR), the exact same seed (20261007) and
    cross-check seeds (20261008, 777), the exact same N_SIMS (60,000).

What's different from the PRE-event run (necessarily, since the cut
has already happened and 2 of 4 rounds are no longer random):
  - Only 2 rounds (R3+R4) are drawn per player, not 4.
  - No cut-line computation: all 61 players already made the real
    official cut; simulated final score = their REAL cum36 + simulated
    (round3 + round4).
  - Win/Top5/Top10/Top20 are computed only among these 61 -- there is
    no "made_cut" boolean to gate on anymore, it's already true for all
    of them by construction.

Writes, under klpga_pipeline/content/website_v2/:
  HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json
  HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_METHODOLOGY.md
  HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json

PUBLIC DISCLOSURE LIMIT (operator instruction): the results JSON keeps
top5_pct for internal red-team use, but nothing outside this script's
own content/ output may render Top5 or any SG value -- the HOME/PRE/R1/
R3 page builders must only read make_cut_pct (trivially 100% here, kept
only for schema parity)/top20_pct/top10_pct/win_pct.

Never touches STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json, the
PRE-event HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json, or any
docs/ public page.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.website_v2.stableford_monte_carlo_experiment import (  # noqa: E402
    OUTCOMES,
    POINTS_VECTOR,
    load_field,
)

CONTENT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
SNAPSHOT_PATH = CONTENT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"
R2_OFFICIAL_PATH = CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json"

RESULTS_PATH = CONTENT / "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
METHODOLOGY_PATH = CONTENT / "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_METHODOLOGY.md"
REPRODUCIBILITY_PATH = CONTENT / "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json"

PRIMARY_SEED = 20261007
CROSS_CHECK_SEEDS = (20261008, 777)
N_SIMS = 60_000
N_REMAINING_ROUNDS = 2
HOLES_PER_ROUND = 18


def run_remaining_rounds(players, real_cum36: dict, *, seed: int, n_sims: int = N_SIMS):
    """players: list[PlayerDistribution], already filtered to the real
    R3 field (the 61 official cut survivors). real_cum36: player_code ->
    real, official R1+R2 Stableford point total. Simulates ONLY
    N_REMAINING_ROUNDS (R3+R4); returns final_points (n, n_sims) and
    per-player probability vectors, matching run_monte_carlo's own
    sampling mechanism exactly (same multinomial draw per round per
    player, same POINTS_VECTOR), just without any cut-line step."""
    n = len(players)
    rng = np.random.default_rng(seed)

    round_points = np.zeros((N_REMAINING_ROUNDS, n, n_sims), dtype=np.int32)
    for p_idx, player in enumerate(players):
        probs = np.array(player.probabilities, dtype=float)
        probs = probs / probs.sum()
        for round_idx in range(N_REMAINING_ROUNDS):
            counts = rng.multinomial(HOLES_PER_ROUND, probs, size=n_sims)
            round_points[round_idx, p_idx, :] = counts @ POINTS_VECTOR

    remaining_total = round_points.sum(axis=0)  # (n, n_sims)
    real_starting = np.array([real_cum36[p.player_code] for p in players], dtype=np.int64)
    final_points = remaining_total + real_starting[:, None]  # (n, n_sims)

    sorted_desc = -np.sort(-final_points, axis=0)
    max_score = sorted_desc[0, :]
    is_leader = final_points == max_score[None, :]
    n_leaders = is_leader.sum(axis=0)
    win_credit = is_leader * (1.0 / n_leaders)[None, :]

    def _topN_pct(N: int) -> np.ndarray:
        N = min(N, n)
        boundary = sorted_desc[N - 1, :]
        topN = final_points >= boundary[None, :]
        return topN.mean(axis=1)

    return {
        "final_points": final_points,
        "win_pct": win_credit.mean(axis=1),
        "top5_pct": _topN_pct(5),
        "top10_pct": _topN_pct(10),
        "top20_pct": _topN_pct(20),
        "median_final_points": np.median(final_points, axis=1),
    }


def main() -> None:
    r2_official = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    advanced = r2_official["advanced_to_r3"]
    assert len(advanced) == r2_official["advanced_count"] == 61, (
        f"expected exactly 61 advancing players, found {len(advanced)}"
    )
    real_cum36 = {p["player_code"]: p["cum36_points"] for p in advanced}
    advancing_codes = set(real_cum36)

    all_players = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    by_code = {p.player_code: p for p in all_players}
    missing = advancing_codes - set(by_code)
    if missing:
        raise ValueError(f"{len(missing)} R3-advancing player_code(s) not found in the frozen snapshot: {missing}")
    r3_players = [by_code[code] for code in real_cum36]
    assert len(r3_players) == 61

    primary = run_remaining_rounds(r3_players, real_cum36, seed=PRIMARY_SEED)

    # reproducibility: identical seed -> bit-identical result
    primary_rerun = run_remaining_rounds(r3_players, real_cum36, seed=PRIMARY_SEED)
    same_seed_bit_identical = bool(np.array_equal(primary["final_points"], primary_rerun["final_points"]))

    cross_seed_checks = []
    for seed in CROSS_CHECK_SEEDS:
        alt = run_remaining_rounds(r3_players, real_cum36, seed=seed)
        max_abs_win_delta = float(np.max(np.abs(alt["win_pct"] - primary["win_pct"]))) * 100
        mean_abs_win_delta = float(np.mean(np.abs(alt["win_pct"] - primary["win_pct"]))) * 100
        primary_top10_names = {r3_players[i].player_name for i in np.argsort(-primary["win_pct"])[:10]}
        alt_top10_names = {r3_players[i].player_name for i in np.argsort(-alt["win_pct"])[:10]}
        cross_seed_checks.append({
            "seed": seed,
            "max_abs_win_pct_delta_pct_points": round(max_abs_win_delta, 4),
            "mean_abs_win_pct_delta_pct_points": round(mean_abs_win_delta, 4),
            "top10_win_overlap_with_primary": len(primary_top10_names & alt_top10_names),
        })

    rows = []
    for i, p in enumerate(r3_players):
        rows.append({
            "player_code": p.player_code,
            "player_name": p.player_name,
            "official_sponsor": p.official_sponsor,
            "nationality": p.nationality,
            "real_cum36_points": real_cum36[p.player_code],
            "make_cut_pct": 1.0,  # already officially through -- kept only for schema parity, never meant to read as a forecast
            "top20_pct": round(float(primary["top20_pct"][i]), 6),
            "top10_pct": round(float(primary["top10_pct"][i]), 6),
            "top5_pct": round(float(primary["top5_pct"][i]), 6),  # INTERNAL ONLY -- never render publicly
            "win_pct": round(float(primary["win_pct"][i]), 6),
            "median_final_points": float(primary["median_final_points"][i]),
        })
    rows.sort(key=lambda r: -r["win_pct"])

    out = {
        "schema_version": 1,
        "target_game_code": "2026100004",
        "stage": "POST_R2_R3_FORECAST",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "field_size_total": 108,
        "advanced_to_r3_count": len(r3_players),
        "missed_cut_count": r2_official["missed_cut_count"],
        "withdrawn_count": r2_official["wd_count"],
        "source_r2_official_results": "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json",
        "monte_carlo_config": {
            "primary_seed": PRIMARY_SEED,
            "n_sims": N_SIMS,
            "remaining_rounds_simulated": N_REMAINING_ROUNDS,
            "holes_per_round": HOLES_PER_ROUND,
            "reused_engine": "klpga.website_v2.stableford_monte_carlo_experiment (same OUTCOMES/POINTS_VECTOR/load_field/player distributions as the PRE-event V1 run; only the per-round-count and the real-cum36 starting offset differ)",
        },
        "reproducibility": {
            "same_seed_rerun_bit_identical": same_seed_bit_identical,
            "cross_seed_checks": cross_seed_checks,
        },
        "public_disclosure_limit": "cut/top20/top10/win only -- top5_pct is kept in this file for internal red-team use but must never be rendered on any public page",
        "players": rows,
    }
    assert same_seed_bit_identical, "same-seed rerun was not bit-identical -- do not publish"

    RESULTS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    METHODOLOGY_PATH.write_text(
        "# HJ 2026100004 POST-R2 Stableford Monte Carlo V1 -- Methodology\n\n"
        "R1+R2 are real, official KLPGA results (not simulated); the official\n"
        "cut (top 60 and ties) has already been applied by KLPGA, yielding\n"
        "61 real survivors, 46 missed-cut, 1 WD. Only rounds 3+4 are drawn,\n"
        "per-player, from the SAME per-hole outcome distribution\n"
        "(stableford_monte_carlo_experiment.load_field) used by the PRE-event\n"
        "V1 run -- their skill model is not re-fit on R1/R2 results. Final\n"
        "score = real R1+R2 total + simulated R3 + simulated R4. Seed=20261007,\n"
        f"n_sims={N_SIMS}, cross-seed checks at {CROSS_CHECK_SEEDS}.\n"
        "No cut-line is simulated -- all 61 players are already through by\n"
        "construction. Public output is limited to 컷 통과(always 100% here,\n"
        "kept for schema parity)/TOP20/TOP10/우승 -- Top5 and SG are never\n"
        "rendered publicly.\n",
        encoding="utf-8",
    )

    REPRODUCIBILITY_PATH.write_text(json.dumps({
        "primary_seed": PRIMARY_SEED,
        "n_simulations": N_SIMS,
        "same_seed_rerun_bit_identical": same_seed_bit_identical,
        "cross_seed_checks": cross_seed_checks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "advanced_to_r3_count": len(r3_players),
        "same_seed_rerun_bit_identical": same_seed_bit_identical,
        "cross_seed_checks": cross_seed_checks,
        "top5_by_win_pct": [(r["player_name"], r["win_pct"]) for r in rows[:5]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
