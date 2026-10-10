"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- POST-R3 Stableford
Monte Carlo FR (4R) forecast (2026-10-10, operator instruction).

R1+R2+R3 are now REAL, officially observed results (not simulated): see
content/website_v2/HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json, collected
and cross-verified against klpga.co.kr's official 전체 스코어 record page
(this sandbox cannot reach klpga.co.kr directly -- fetched via
.github/workflows/fetch-hj-2026100004-stableford-rounds-oneoff.yml on a
GitHub-hosted runner with real network access). No additional cut is
applied after R2 for this tournament format -- the same 61 players who
survived the R2 cut play all of R3/R4; this script predicts ONLY the
single remaining round (R4/FR) for those 61 real players.

Deliberately reuses, unmodified, from stableford_monte_carlo_experiment
(the SAME engine the PRE-event V1 and POST-R2 runs used):
  - load_field() against the SAME frozen pre-event snapshot, to get
    each of the 61 survivors' own real historical per-hole outcome
    distribution (PlayerDistribution.probabilities) -- their skill
    model is NOT re-fit on R1/R2/R3 data; only their STARTING SCORE
    changes (from their real cum36 to their real, official cum54).
  - The exact same per-hole multinomial sampling mechanism
    (OUTCOMES/POINTS_VECTOR), the exact same seed (20261007) and
    cross-check seeds (20261008, 777), the exact same N_SIMS (60,000).

What's different from the POST-R2 run (necessarily, since only 1 round
remains instead of 2):
  - Only 1 round (R4) is drawn per player, not 2.
  - Starting score = real official cum54 (R1+R2+R3), not cum36.

Writes, under klpga_pipeline/content/website_v2/:
  HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json
  HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_METHODOLOGY.md
  HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json

PUBLIC DISCLOSURE LIMIT (operator instruction, updated 2026-10-10, then
again same day to add TOP20): FR (236_hj_2026100004_build_fr_page.py)
and its HOME mirror are allowed to read and render top20_pct/top5_pct
-- e.g. "probability of a top-5 finish after R4", not "the 5 highest
win_pct players". PRE/R1/R2/R3 must still never render TOP5 or TOP20
(see test_no_sg_or_top5_data_on_either_public_page). No SG value may
ever be rendered publicly on any page, on any stage -- that restriction
is unchanged. The earlier note that "TOP20 does not apply with only 61
players and 1 round left" was an editorial choice, not a computational
limit -- _topN_pct(20) is exactly as well-defined as _topN_pct(5/10)
for a 61-player field, and the operator has since asked for it.

Never touches STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json, the
PRE-event or POST-R2 results JSONs, or any docs/ public page.
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
R3_OFFICIAL_PATH = CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json"

RESULTS_PATH = CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
METHODOLOGY_PATH = CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_METHODOLOGY.md"
REPRODUCIBILITY_PATH = CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json"

PRIMARY_SEED = 20261007
CROSS_CHECK_SEEDS = (20261008, 777)
N_SIMS = 60_000
N_REMAINING_ROUNDS = 1
HOLES_PER_ROUND = 18


def run_remaining_rounds(players, real_cum54: dict, *, seed: int, n_sims: int = N_SIMS):
    """players: list[PlayerDistribution], already filtered to the real
    R4/FR field (the 61 official R2-cut survivors, now with a real,
    official R3 result too). real_cum54: player_code -> real, official
    R1+R2+R3 Stableford point total. Simulates ONLY N_REMAINING_ROUNDS
    (R4), matching run_monte_carlo's own sampling mechanism exactly
    (same multinomial draw per round per player, same POINTS_VECTOR),
    just without any cut-line step."""
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
    real_starting = np.array([real_cum54[p.player_code] for p in players], dtype=np.int64)
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
    r3_official = json.loads(R3_OFFICIAL_PATH.read_text(encoding="utf-8"))
    active = r3_official["active_players"]
    assert len(active) == r3_official["active_count"] == 61, (
        f"expected exactly 61 active players, found {len(active)}"
    )
    real_cum54 = {p["player_code"]: p["cum54_points"] for p in active}
    active_codes = set(real_cum54)

    all_players = load_field(SNAPSHOT_PATH, no_prior_data_policy="field_neutral_prior")
    by_code = {p.player_code: p for p in all_players}
    missing = active_codes - set(by_code)
    if missing:
        raise ValueError(f"{len(missing)} FR-active player_code(s) not found in the frozen snapshot: {missing}")
    fr_players = [by_code[code] for code in real_cum54]
    assert len(fr_players) == 61

    primary = run_remaining_rounds(fr_players, real_cum54, seed=PRIMARY_SEED)

    # reproducibility: identical seed -> bit-identical result
    primary_rerun = run_remaining_rounds(fr_players, real_cum54, seed=PRIMARY_SEED)
    same_seed_bit_identical = bool(np.array_equal(primary["final_points"], primary_rerun["final_points"]))

    cross_seed_checks = []
    for seed in CROSS_CHECK_SEEDS:
        alt = run_remaining_rounds(fr_players, real_cum54, seed=seed)
        max_abs_win_delta = float(np.max(np.abs(alt["win_pct"] - primary["win_pct"]))) * 100
        mean_abs_win_delta = float(np.mean(np.abs(alt["win_pct"] - primary["win_pct"]))) * 100
        primary_top10_names = {fr_players[i].player_name for i in np.argsort(-primary["win_pct"])[:10]}
        alt_top10_names = {fr_players[i].player_name for i in np.argsort(-alt["win_pct"])[:10]}
        cross_seed_checks.append({
            "seed": seed,
            "max_abs_win_pct_delta_pct_points": round(max_abs_win_delta, 4),
            "mean_abs_win_pct_delta_pct_points": round(mean_abs_win_delta, 4),
            "top10_win_overlap_with_primary": len(primary_top10_names & alt_top10_names),
        })

    rows = []
    for i, p in enumerate(fr_players):
        rows.append({
            "player_code": p.player_code,
            "player_name": p.player_name,
            "official_sponsor": p.official_sponsor,
            "nationality": p.nationality,
            "real_cum54_points": real_cum54[p.player_code],
            "make_cut_pct": 1.0,  # already officially through -- kept only for schema parity, never meant to read as a forecast
            "top20_pct": round(float(primary["top20_pct"][i]), 6),
            "top10_pct": round(float(primary["top10_pct"][i]), 6),
            "top5_pct": round(float(primary["top5_pct"][i]), 6),
            "win_pct": round(float(primary["win_pct"][i]), 6),
            "median_final_points": float(primary["median_final_points"][i]),
        })
    rows.sort(key=lambda r: -r["win_pct"])

    out = {
        "schema_version": 1,
        "target_game_code": "2026100004",
        "stage": "POST_R3_FR_FORECAST",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "field_size_total": 108,
        "active_for_fr_count": len(fr_players),
        "missed_cut_count": r3_official["missed_cut_count"],
        "withdrawn_count": r3_official["wd_count"],
        "source_r3_official_results": "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json",
        "monte_carlo_config": {
            "primary_seed": PRIMARY_SEED,
            "n_sims": N_SIMS,
            "remaining_rounds_simulated": N_REMAINING_ROUNDS,
            "holes_per_round": HOLES_PER_ROUND,
            "reused_engine": "klpga.website_v2.stableford_monte_carlo_experiment (same OUTCOMES/POINTS_VECTOR/load_field/player distributions as the PRE-event and POST-R2 runs; only the per-round-count and the real-cum54 starting offset differ)",
        },
        "reproducibility": {
            "same_seed_rerun_bit_identical": same_seed_bit_identical,
            "cross_seed_checks": cross_seed_checks,
        },
        "public_disclosure_limit": "top20/top10/top5/win on FR and its HOME mirror only (updated 2026-10-10); PRE/R1/R2/R3 must still never render top5_pct or top20_pct",
        "players": rows,
    }
    assert same_seed_bit_identical, "same-seed rerun was not bit-identical -- do not publish"

    RESULTS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    METHODOLOGY_PATH.write_text(
        "# HJ 2026100004 POST-R3 Stableford Monte Carlo V1 -- Methodology\n\n"
        "R1+R2+R3 are real, official KLPGA results (not simulated); no\n"
        "additional cut is applied after R2 for this tournament format, so\n"
        "the same 61 real survivors continue through R4. Only round 4 is\n"
        "drawn, per-player, from the SAME per-hole outcome distribution\n"
        "(stableford_monte_carlo_experiment.load_field) used by the PRE-event\n"
        "and POST-R2 runs -- their skill model is not re-fit on R1/R2/R3\n"
        "results. Final score = real R1+R2+R3 total + simulated R4.\n"
        f"Seed={PRIMARY_SEED}, n_sims={N_SIMS}, cross-seed checks at {CROSS_CHECK_SEEDS}.\n"
        "No cut-line is simulated -- all 61 players are already through by\n"
        "construction. Public output on FR/HOME is TOP20/TOP10/TOP5/우승\n"
        "(updated 2026-10-10); PRE/R1/R2/R3 never show TOP20 or TOP5. SG is\n"
        "never rendered publicly, on any page.\n",
        encoding="utf-8",
    )

    REPRODUCIBILITY_PATH.write_text(json.dumps({
        "primary_seed": PRIMARY_SEED,
        "n_simulations": N_SIMS,
        "same_seed_rerun_bit_identical": same_seed_bit_identical,
        "cross_seed_checks": cross_seed_checks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "active_for_fr_count": len(fr_players),
        "same_seed_rerun_bit_identical": same_seed_bit_identical,
        "cross_seed_checks": cross_seed_checks,
        "top5_by_win_pct": [(r["player_name"], r["win_pct"]) for r in rows[:5]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
