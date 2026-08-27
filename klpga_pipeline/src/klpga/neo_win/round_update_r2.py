"""Post-Round-2 probability update — a NEW, parallel module (never
modifies `klpga.neo_win.round_update`, BETA #001's own R1-specific
pipeline). Reuses that module's exact Monte Carlo mechanics (Normal-
distributed remaining-round draws from the frozen PRE prior) but with
a structurally different cut treatment:

======================================================================
POST-R2: THE CUT IS A REAL, KNOWN FACT — NEVER SIMULATED
======================================================================
`klpga.neo_win.round_update`'s own verified real evidence (docs/
SITE_STRUCTURE_TODO.md): this tournament format has exactly ONE cut,
after Round 2 (36 holes), and no subsequent cut. By the time Round 2
has genuinely CONCLUDED for the whole field, every player's made-cut
status is a real, already-determined fact (`player_event.made_cut` /
the real R2 leaderboard) — simulating a cutline (as the post-R1 module
correctly must, since round 2 hasn't happened yet at that point) would
be wrong here: it would replace a known fact with a probability.

======================================================================
NEO R3 % / NEO FINAL % ARE THE SAME REAL EVENT AS MAKE CUT %
======================================================================
Given the single-cut format, a cutmaker is guaranteed to play BOTH
Round 3 and Round 4 (barring withdrawal/disqualification, a separate,
unpredictable real event this module does not model) — there is no
independent "advanced to R3" vs "advanced to FINAL" probability to
compute. Reporting them as separately-simulated numbers would fabricate
a distinction the real tournament format does not have. This module
computes ONE real make-cut fact and the caller (scripts/44) presents
it under all three requested labels, documented as identical, never
silently duplicated as if independently derived.

======================================================================
MISSING DATA
======================================================================
A player missing a real R1 score, R2 score, or made_cut fact is
EXCLUDED from simulation (SKIP + LOG, reported in `missing_r2_players`)
— never assigned a fabricated average or a guessed cut status.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Optional

from klpga.neo_win.round_update import DEFAULT_N_SIMULATIONS

__all__ = [
    "DEFAULT_N_SIMULATIONS",
    "PlayerR2SimInput",
    "build_r2_sim_inputs_from_frozen_snapshot",
    "simulate_post_round2",
]


@dataclass(frozen=True)
class PlayerR2SimInput:
    player_code: str
    player_name: str
    expected_round_score_to_par: float
    spread: float
    r1_score_to_par: Optional[float]
    r2_score_to_par: Optional[float]
    made_cut: Optional[bool]
    """Real, known made-cut fact for this player (player_event.made_cut
    as of Round 2's real conclusion) — None means genuinely unknown
    (SKIP + LOG), never guessed True/False."""


def build_r2_sim_inputs_from_frozen_snapshot(
    pre_snapshot,
    r1_scores: dict[str, float],
    r2_scores: dict[str, float],
    made_cut_by_player: dict[str, bool],
) -> tuple[list[PlayerR2SimInput], list[str]]:
    """Same population-mean-shrink convention as `klpga.neo_win.
    round_update.build_sim_inputs_from_frozen_snapshot` for the frozen
    PRE prior. A player is reported in `missing_r2_players` (and
    excluded from simulation) if ANY of r1_score, r2_score, or a real
    made_cut fact is unavailable — never partially simulated on
    incomplete real data."""
    known_scores = [e.prior_avg_round_score_to_par for e in pre_snapshot.predictions if e.prior_avg_round_score_to_par is not None]
    pop_mean_score = statistics.mean(known_scores) if known_scores else 0.0
    known_spreads = [e.neo_consistency_stddev for e in pre_snapshot.predictions if e.neo_consistency_stddev is not None]
    pop_mean_spread = statistics.mean(known_spreads) if known_spreads else 3.0

    sim_inputs = []
    missing: list[str] = []
    for e in pre_snapshot.predictions:
        r1 = r1_scores.get(e.player_code)
        r2 = r2_scores.get(e.player_code)
        made_cut = made_cut_by_player.get(e.player_code)
        if r1 is None or r2 is None or made_cut is None:
            missing.append(e.player_code)
        expected = e.prior_avg_round_score_to_par if e.prior_avg_round_score_to_par is not None else pop_mean_score
        spread = e.neo_consistency_stddev if e.neo_consistency_stddev is not None else pop_mean_spread
        sim_inputs.append(
            PlayerR2SimInput(
                player_code=e.player_code, player_name=e.player_name,
                expected_round_score_to_par=expected, spread=max(spread, 0.5),
                r1_score_to_par=r1, r2_score_to_par=r2, made_cut=made_cut,
            )
        )
    return sim_inputs, missing


def simulate_post_round2(
    sim_inputs: list[PlayerR2SimInput],
    *,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    rng: Optional[random.Random] = None,
) -> dict[str, dict]:
    """Only real cutmakers (made_cut is True) are simulated for R3+R4.
    A player with real, complete data but made_cut=False gets
    win_pct=top5_pct=top10_pct=top20_pct=make_cut_pct=0.0 — a real,
    KNOWN outcome (they are mathematically eliminated), never an
    estimate. A player missing any required real input (not in
    `sim_inputs` with all fields non-None) is simply absent from the
    returned dict — the caller (scripts/44) is responsible for
    reporting those as `unavailable`, never as a fabricated 0."""
    rng = rng or random.Random()
    complete = [p for p in sim_inputs if p.r1_score_to_par is not None and p.r2_score_to_par is not None and p.made_cut is not None]
    cutmakers = [p for p in complete if p.made_cut]
    cut_players = [p for p in complete if not p.made_cut]

    wins = {p.player_code: 0.0 for p in cutmakers}
    top5 = {p.player_code: 0 for p in cutmakers}
    top10 = {p.player_code: 0 for p in cutmakers}
    top20 = {p.player_code: 0 for p in cutmakers}

    for _ in range(n_simulations):
        totals = []
        for p in cutmakers:
            r3 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            r4 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            total = p.r1_score_to_par + p.r2_score_to_par + r3 + r4
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

    result: dict[str, dict] = {}
    for p in cutmakers:
        result[p.player_code] = {
            "win_pct": round(100 * wins[p.player_code] / n_simulations, 6) if n_simulations else 0.0,
            "top5_pct": round(100 * top5[p.player_code] / n_simulations, 4) if n_simulations else 0.0,
            "top10_pct": round(100 * top10[p.player_code] / n_simulations, 4) if n_simulations else 0.0,
            "top20_pct": round(100 * top20[p.player_code] / n_simulations, 4) if n_simulations else 0.0,
            "make_cut_pct": 100.0,
        }
    for p in cut_players:
        result[p.player_code] = {
            "win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0, "make_cut_pct": 0.0,
        }
    return result
