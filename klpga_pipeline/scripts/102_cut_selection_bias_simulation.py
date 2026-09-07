"""PHASE A red-team: does cut-selection (players reach R3/R4 partly BECAUSE
their R1/R2 was good enough to survive) create systematic bias in the
per-round skill estimator from neo_ranking_v2_candidate.py, on top of the
already-fixed unequal-rounds-denominator problem?

VALIDATION_MODEL_NOT_PRODUCTION. This script only runs simulations and
writes a report artifact -- it never touches home_ranking.py's approval
gate, never touches production content, and is not itself the V2 formula.

Model: each player has a fixed latent true_skill (SG/round). Each round's
observed SG is true_skill + N(0, sigma). sigma and tau (spread of
true_skill across players) are seeded from the real, empirically-derived
values in docs/NEO_RANKING_V2_PHASE_A_TO_D_FINDINGS.md (sigma^2~=3.84,
tau^2~=1.95) -- this script re-derives them as parameters rather than
importing that file, so the simulation stays self-contained and its
assumptions are visible in one place.

Cut rule: after R1+R2, a player's tournament is played against a
simulated field of FIELD_SIZE other players (independently drawn true
skills); only the top CUT_FRACTION of that field's R1+R2 total advances
to R3/R4. This mirrors the real ~120 -> ~65-70 cut ratio confirmed in the
real OK Open data (120 -> 118 -> 68, i.e. the R2 cut trims to ~55-58%).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path_src = ROOT / "src"
import sys
sys.path.insert(0, str(sys_path_src))

from klpga.website_v2.neo_ranking_v2_candidate import (  # noqa: E402
    EventObservation,
    ShrinkagePrior,
    pooled_per_round_rate,
    estimate_skill,
)

SIGMA = (3.8414) ** 0.5  # within-player round-to-round noise stdev, from real calibration
TAU = (1.9498) ** 0.5  # between-player true-skill spread stdev, from real calibration
POP_MEAN = -1.2743
FIELD_SIZE = 118  # real OK Open R2 field size before the R2 cut
CUT_FRACTION = 68 / 118  # real OK Open R2->R3 survival ratio
PRIOR = ShrinkagePrior(population_mean_per_round=POP_MEAN, between_player_variance=1.9498, within_player_variance=3.8414)


@dataclass
class TournamentResult:
    rounds: list[float]  # per-round SG actually observed for this player in this tournament
    made_cut: bool


def play_tournament(true_skill: float, rng: random.Random) -> TournamentResult:
    r1 = true_skill + rng.gauss(0, SIGMA)
    r2 = true_skill + rng.gauss(0, SIGMA)
    field_r1r2_totals = [
        2 * rng.gauss(POP_MEAN, TAU) + rng.gauss(0, SIGMA) + rng.gauss(0, SIGMA)
        for _ in range(FIELD_SIZE - 1)
    ]
    own_total = r1 + r2
    all_totals = field_r1r2_totals + [own_total]
    all_totals.sort(reverse=True)
    cut_index = int(len(all_totals) * CUT_FRACTION)
    cutline = all_totals[min(cut_index, len(all_totals) - 1)]
    made_cut = own_total >= cutline
    rounds = [r1, r2]
    if made_cut:
        rounds.append(true_skill + rng.gauss(0, SIGMA))
        rounds.append(true_skill + rng.gauss(0, SIGMA))
    return TournamentResult(rounds=rounds, made_cut=made_cut)


def naive_event_total_mean_of_events(events: list[EventObservation]) -> float:
    return statistics.fmean(ev.total_sg for ev in events)


def restricted_r1r2_rate(tournaments: list[TournamentResult]) -> float:
    """Test A5 control: use ONLY the first two rounds of every tournament,
    regardless of whether the player made the cut."""
    total = sum(t.rounds[0] + t.rounds[1] for t in tournaments)
    return total / (2 * len(tournaments))


def complete_case_rate(tournaments: list[TournamentResult]) -> float | None:
    """Test A4: discard any tournament where the player did not complete
    all 4 rounds. Returns None if the player never made a single cut."""
    complete = [t for t in tournaments if t.made_cut]
    if not complete:
        return None
    events = [EventObservation(total_sg=sum(t.rounds), rounds=len(t.rounds)) for t in complete]
    return pooled_per_round_rate(events)


def run_simulation(
    n_players: int,
    n_tournaments: int,
    identical_skill: float | None,
    rng: random.Random,
) -> dict:
    players = []
    for _ in range(n_players):
        true_skill = identical_skill if identical_skill is not None else rng.gauss(POP_MEAN, TAU)
        tournaments = [play_tournament(true_skill, rng) for _ in range(n_tournaments)]
        events = [EventObservation(total_sg=sum(t.rounds), rounds=len(t.rounds)) for t in tournaments]
        naive = naive_event_total_mean_of_events(events)
        pooled = pooled_per_round_rate(events)
        shrunk = estimate_skill("sim", events, PRIOR).shrunk_rate
        restricted = restricted_r1r2_rate(tournaments)
        complete = complete_case_rate(tournaments)
        cut_rate = statistics.fmean(1.0 if t.made_cut else 0.0 for t in tournaments)
        players.append({
            "true_skill": true_skill,
            "cut_rate": cut_rate,
            "naive": naive,
            "pooled": pooled,
            "shrunk": shrunk,
            "restricted_r1r2": restricted,
            "complete_case": complete,
        })
    return {"players": players}


def bias_stats(players: list[dict], key: str, subset: str = "all") -> dict:
    if subset in ("made_cut_heavy", "missed_cut_heavy"):
        # Tercile split on this population's OWN cut-rate distribution, not a
        # fixed 0.5 threshold -- with identical true skill the mean cut rate
        # equals CUT_FRACTION (~0.58 here), so a fixed 0.5 cutoff puts almost
        # everyone in one bucket. A tercile split guarantees a real contrast
        # between players who got unusually lucky vs unlucky across their
        # n_tournaments replicates, purely from sampling noise.
        rates = sorted(p["cut_rate"] for p in players)
        lo_cut = rates[len(rates) // 3]
        hi_cut = rates[(2 * len(rates)) // 3]
        if subset == "made_cut_heavy":
            rows = [p for p in players if p["cut_rate"] >= hi_cut]
        else:
            rows = [p for p in players if p["cut_rate"] <= lo_cut]
    else:
        rows = players
    values = [p[key] - p["true_skill"] for p in rows if p.get(key) is not None]
    if not values:
        return {"n": 0, "mean_bias": None, "rmse": None}
    rmse = (statistics.fmean(v * v for v in values)) ** 0.5
    return {"n": len(values), "mean_bias": round(statistics.fmean(values), 4), "rmse": round(rmse, 4)}


def rank_correlation(true_skills: list[float], estimates: list[float]) -> float:
    n = len(true_skills)
    true_ranks = {v: r for r, v in enumerate(sorted(true_skills))}
    est_ranks = {v: r for r, v in enumerate(sorted(estimates))}
    tr = [true_ranks[v] for v in true_skills]
    er = [est_ranks[v] for v in estimates]
    mean_tr, mean_er = statistics.fmean(tr), statistics.fmean(er)
    cov = sum((a - mean_tr) * (b - mean_er) for a, b in zip(tr, er))
    var_t = sum((a - mean_tr) ** 2 for a in tr)
    var_e = sum((b - mean_er) ** 2 for b in er)
    if var_t == 0 or var_e == 0:
        return float("nan")
    return cov / (var_t ** 0.5 * var_e ** 0.5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260907)
    parser.add_argument("--n-players", type=int, default=400)
    parser.add_argument("--n-tournaments", type=int, default=20)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # --- Test A1: identical true skill across all players ---
    a1 = run_simulation(args.n_players, args.n_tournaments, identical_skill=0.0, rng=rng)
    a1_result = {
        "naive_all": bias_stats(a1["players"], "naive", "all"),
        "naive_made_cut_heavy": bias_stats(a1["players"], "naive", "made_cut_heavy"),
        "naive_missed_cut_heavy": bias_stats(a1["players"], "naive", "missed_cut_heavy"),
        "pooled_all": bias_stats(a1["players"], "pooled", "all"),
        "pooled_made_cut_heavy": bias_stats(a1["players"], "pooled", "made_cut_heavy"),
        "pooled_missed_cut_heavy": bias_stats(a1["players"], "pooled", "missed_cut_heavy"),
        "shrunk_all": bias_stats(a1["players"], "shrunk", "all"),
        "shrunk_made_cut_heavy": bias_stats(a1["players"], "shrunk", "made_cut_heavy"),
        "shrunk_missed_cut_heavy": bias_stats(a1["players"], "shrunk", "missed_cut_heavy"),
    }

    # --- Test A2: realistic skill distribution ---
    a2 = run_simulation(args.n_players, args.n_tournaments, identical_skill=None, rng=rng)
    true_skills = [p["true_skill"] for p in a2["players"]]
    a2_result = {
        "pooled_bias_rmse": bias_stats(a2["players"], "pooled", "all"),
        "shrunk_bias_rmse": bias_stats(a2["players"], "shrunk", "all"),
        "rank_correlation_pooled": round(rank_correlation(true_skills, [p["pooled"] for p in a2["players"]]), 4),
        "rank_correlation_shrunk": round(rank_correlation(true_skills, [p["shrunk"] for p in a2["players"]]), 4),
        "cut_rate_vs_true_skill_correlation": round(
            rank_correlation(true_skills, [p["cut_rate"] for p in a2["players"]]), 4
        ),
    }

    # --- Test A3: cut-line noise, matched-true-skill pairs ---
    matched_skill = 0.0
    n_pairs = 300
    lucky, unlucky = [], []
    for _ in range(n_pairs):
        t = play_tournament(matched_skill, rng)
        (lucky if t.made_cut else unlucky).append(t)
    # For players who cleared/missed the SAME cutline by luck alone (one tournament
    # each, matched true skill), compare their R1+R2 rate -- this isolates the
    # cutline-noise effect directly, before any later-round dilution.
    lucky_r1r2 = [statistics.fmean(t.rounds[:2]) for t in lucky] if lucky else []
    unlucky_r1r2 = [statistics.fmean(t.rounds[:2]) for t in unlucky] if unlucky else []
    a3_result = {
        "n_lucky_survivors": len(lucky),
        "n_unlucky_non_survivors": len(unlucky),
        "lucky_mean_r1r2_rate": round(statistics.fmean(lucky_r1r2), 4) if lucky_r1r2 else None,
        "unlucky_mean_r1r2_rate": round(statistics.fmean(unlucky_r1r2), 4) if unlucky_r1r2 else None,
        "true_skill": matched_skill,
        "gap_explained_entirely_by_r1r2_selection_noise": True,
    }

    # --- Test A4 vs A5: complete-case fallacy vs R1/R2 common window ---
    a4a5_players = a2["players"]  # reuse A2's realistic-skill population
    a4_result = bias_stats([p for p in a4a5_players if p["complete_case"] is not None], "complete_case", "all")
    a5_result = bias_stats(a4a5_players, "restricted_r1r2", "all")
    full_result = bias_stats(a4a5_players, "pooled", "all")

    report = {
        "model": {
            "sigma": round(SIGMA, 4), "tau": round(TAU, 4), "population_mean": POP_MEAN,
            "field_size": FIELD_SIZE, "cut_fraction": round(CUT_FRACTION, 4),
            "seed": args.seed, "n_players": args.n_players, "n_tournaments": args.n_tournaments,
        },
        "A1_identical_skill_bias": a1_result,
        "A2_different_skills": a2_result,
        "A3_cutline_noise": a3_result,
        "A4_complete_case_bias": a4_result,
        "A5_r1r2_common_window_bias": a5_result,
        "A_all_available_rounds_bias_for_reference": full_result,
    }

    out_json = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_CUT_SELECTION_SIMULATION.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
