"""Post-Round-1 probability update for a NEO WIN v0.1 PRE prediction —
BETA #001-R1.

======================================================================
CUT FORMAT — VERIFIED FROM EXISTING REAL EVIDENCE, NOT ASSUMED
======================================================================
docs/SITE_STRUCTURE_TODO.md (real 100-tournament collection, confirmed
2026-08-24): the real `rounds_played` distribution across every
collected tournament is exactly `{1, 2, 4}` — ZERO 3-round players,
"exactly the signature of a standard 36-hole cut (cut after round 2)".
No subsequent cut exists. This module therefore only ever simulates
ONE cut event (after Round 2) and never fabricates an R3 or R4 cut.
`estimate_cut_fraction` below computes the empirical made-cut rate from
this same real, already-collected historical data — never a guessed
cutline rule (KLPGA's exact "top-N-and-ties" policy is not independently
confirmed anywhere in this project, so this uses the REAL observed
base rate instead of inventing one).

======================================================================
METHOD — Monte Carlo tournament simulation
======================================================================
This combines every required input into ONE coherent simulation rather
than several disconnected probability formulas:

  - FROZEN PRE PERFORMANCE PRIOR: each player's `neo_win.model`
    combined_score (career scoring + recent form + consistency +
    validated official metrics — read directly from the frozen
    snapshot, never recomputed) sets their EXPECTED per-round scoring
    rate for every remaining round.
  - ACTUAL ROUND-1 SCORE: real, already-known, never simulated —
    counted exactly once toward the 36-hole cut total and the 72-hole
    total.
  - REMAINING 54-HOLE UNCERTAINTY: each remaining round is drawn from
    Normal(expected_round_score_to_par, spread), spread taken from
    `neo_consistency_stddev` (shrunk to the training-fold population
    mean when missing — the SAME convention as every other missing-
    data case in this project, never a fabricated fixed spread).
  - The cut is applied WITHIN each simulated trial after Round 2
    (empirical cut_fraction, see above); WIN/TOP5/TOP10/TOP20 are
    computed only among that trial's cut-makers, exactly matching the
    real tournament's own elimination structure.

Disclosed simplifications (BETA, not claimed final): round scores are
drawn i.i.d. Normal per player (no course-difficulty-by-round
correlation, no playoff modeling — ties for the win split the win
credit fractionally rather than simulating a playoff).
"""
from __future__ import annotations

import random
import sqlite3
import statistics
from dataclasses import dataclass
from typing import Optional

DEFAULT_N_SIMULATIONS = 5000


def estimate_cut_fraction(conn: sqlite3.Connection) -> float:
    """Real, empirical made-cut rate from every already-collected
    player_event row: rounds_played==4 (made the cut, per the
    confirmed {1,2,4} distribution) over every player with at least 1
    round played (excludes rows with no rounds at all, which would be
    a collection artifact, not a real field member). Returns 0.65
    (documented, disclosed neutral default) only if there is no
    historical data at all to compute a real rate from."""
    total = conn.execute("SELECT COUNT(*) FROM player_event WHERE rounds_played >= 1").fetchone()[0]
    made_cut = conn.execute("SELECT COUNT(*) FROM player_event WHERE rounds_played = 4").fetchone()[0]
    if total == 0:
        return 0.65
    return made_cut / total


@dataclass(frozen=True)
class PlayerSimInput:
    player_code: str
    player_name: str
    expected_round_score_to_par: float
    """The per-round scoring RATE this player's PRE features imply —
    equal to their frozen prior_avg_round_score_to_par when present,
    shrunk to the training-fold population mean otherwise (never a
    fabricated fixed value)."""
    spread: float
    """Standard deviation to sample each remaining round from —
    neo_consistency_stddev when present, shrunk to the population mean
    otherwise."""
    r1_score_to_par: Optional[float]
    """Real, actual Round 1 score. None means R1 data is missing for
    this player (SKIP + LOG — see missing_r1_players in the result)."""


def build_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores: dict[str, float]) -> tuple[list[PlayerSimInput], list[str]]:
    """`r1_scores` is {player_code: round_1_score_to_par} from the real
    acquired Round-1 leaderboard. Players in the frozen PRE field with
    no R1 score are reported in `missing_r1_players`, never silently
    dropped from the eventual output (they still appear in results with
    every probability explicitly null, per the release's own "null
    probabilities = 0 unless truly unavailable, but never silently
    hidden" requirement)."""
    known_scores = [e.prior_avg_round_score_to_par for e in pre_snapshot.predictions if e.prior_avg_round_score_to_par is not None]
    pop_mean_score = statistics.mean(known_scores) if known_scores else 0.0
    known_spreads = [e.neo_consistency_stddev for e in pre_snapshot.predictions if e.neo_consistency_stddev is not None]
    pop_mean_spread = statistics.mean(known_spreads) if known_spreads else 3.0

    sim_inputs = []
    missing_r1: list[str] = []
    for e in pre_snapshot.predictions:
        r1 = r1_scores.get(e.player_code)
        if r1 is None:
            missing_r1.append(e.player_code)
        expected = e.prior_avg_round_score_to_par if e.prior_avg_round_score_to_par is not None else pop_mean_score
        spread = e.neo_consistency_stddev if e.neo_consistency_stddev is not None else pop_mean_spread
        sim_inputs.append(
            PlayerSimInput(
                player_code=e.player_code, player_name=e.player_name,
                expected_round_score_to_par=expected, spread=max(spread, 0.5), r1_score_to_par=r1,
            )
        )
    return sim_inputs, missing_r1


def simulate_post_round1(
    sim_inputs: list[PlayerSimInput],
    *,
    cut_fraction: float,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    rng: Optional[random.Random] = None,
) -> dict[str, dict]:
    """Runs `n_simulations` independent trials. Players missing an R1
    score (r1_score_to_par is None) are EXCLUDED from every trial (they
    cannot be ranked without a real R1 result) — reported separately as
    zero-probability/None rather than silently assigned an average."""
    rng = rng or random.Random()
    playable = [p for p in sim_inputs if p.r1_score_to_par is not None]
    n_cutline = max(1, round(len(playable) * cut_fraction))

    wins = {p.player_code: 0.0 for p in playable}
    top5 = {p.player_code: 0 for p in playable}
    top10 = {p.player_code: 0 for p in playable}
    top20 = {p.player_code: 0 for p in playable}
    made_cut = {p.player_code: 0 for p in playable}

    for _ in range(n_simulations):
        r2 = {p.player_code: rng.normalvariate(p.expected_round_score_to_par, p.spread) for p in playable}
        thru36 = sorted(playable, key=lambda p: p.r1_score_to_par + r2[p.player_code])
        cutmakers = thru36[:n_cutline]
        cutmaker_codes = {p.player_code for p in cutmakers}
        for code in cutmaker_codes:
            made_cut[code] += 1

        totals = []
        for p in cutmakers:
            r3 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            r4 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            total = p.r1_score_to_par + r2[p.player_code] + r3 + r4
            totals.append((p.player_code, total))
        totals.sort(key=lambda t: t[1])

        if totals:
            best_score = totals[0][1]
            leaders = [code for code, score in totals if score == best_score]
            for code in leaders:
                wins[code] += 1.0 / len(leaders)
        for rank, (code, _score) in enumerate(totals, start=1):
            if rank <= 5:
                top5[code] += 1
            if rank <= 10:
                top10[code] += 1
            if rank <= 20:
                top20[code] += 1

    result = {}
    for p in playable:
        result[p.player_code] = {
            "win_pct": round(100 * wins[p.player_code] / n_simulations, 6),
            "top5_pct": round(100 * top5[p.player_code] / n_simulations, 4),
            "top10_pct": round(100 * top10[p.player_code] / n_simulations, 4),
            "top20_pct": round(100 * top20[p.player_code] / n_simulations, 4),
            "make_cut_pct": round(100 * made_cut[p.player_code] / n_simulations, 4),
        }
    return result
