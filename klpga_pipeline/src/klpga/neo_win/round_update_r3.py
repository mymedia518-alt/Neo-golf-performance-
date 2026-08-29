"""Post-Round-3 probability update — a NEW, parallel module (never
modifies `klpga.neo_win.round_update`/`round_update_r2.py`, BETA #001-
R1/R2's own pipelines). Reuses the same Monte Carlo mechanics (Normal-
distributed remaining-round draws from the frozen PRE prior) but with
only ONE remaining round (Round 4) left to simulate.

======================================================================
THE CUT IS ALREADY A REAL, KNOWN FACT — SETTLED SINCE ROUND 2
======================================================================
By the time Round 3 has concluded, `made_cut` was already determined
after Round 2 (see round_update_r2.py) — there is no new cut event at
Round 3. A player with a real Round-3 score is, by construction, a
confirmed cutmaker; `made_cut` is still threaded through here purely
as a cross-check against `player_event`'s own record (catching a real
data inconsistency — e.g. a stray R3 row for someone whose made_cut
fact says otherwise — rather than trusting round-score presence alone).

======================================================================
NO "ADVANCES TO FINAL" PROBABILITY — ALREADY DECIDED
======================================================================
Every real cutmaker who completes Round 3 is guaranteed to play Round
4 (barring a separate, unpredictable WD/DQ event this module does not
model) — there is no cut or elimination event left between R3 and
FINAL. This module therefore computes ONLY win/top-N probabilities
over the single remaining round (R4); it never fabricates a redundant
"R4 qualification %" the tournament format does not have.

======================================================================
MISSING DATA
======================================================================
A player missing a real R1, R2, or made_cut fact is EXCLUDED from
simulation (SKIP + LOG, reported in `missing_r3_players`) — never
assigned a fabricated average or a guessed cut status. Callers should
classify each missing player via `klpga.neo_win.player_status` for a
real, evidence-based reason (WD/DQ/DNS/CUT/COLLECTION_MISSING/UNKNOWN),
never a bare, unexplained code.

A real R3 score is required ONLY when `made_cut` is True — a confirmed
cutmaker who completes Round 3 always has one, and it feeds the R4
simulation floor. A confirmed CUT player (made_cut=False) structurally
has NO R3 score at all — they never played it — so its absence is NOT
treated as missing data here; see `simulate_post_round3`'s real,
known-zero result for that case. Requiring r3 unconditionally would
wrongly exclude every real cut player from ever being reported.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Optional

from klpga.neo_win.round_update import DEFAULT_N_SIMULATIONS

__all__ = [
    "DEFAULT_N_SIMULATIONS",
    "PlayerR3SimInput",
    "build_r3_sim_inputs_from_frozen_snapshot",
    "simulate_post_round3",
]


def _feature(e, name: str) -> Optional[float]:
    """Same dual-shape accessor round_update_r2.py already established
    (see that module's own docstring for the full incident writeup): a
    frozen PRE snapshot's `predictions` entries are EITHER a legacy
    `NeoWinEntrantSnapshot` (klpga.neo_win.archive) — which stores
    `prior_avg_round_score_to_par` / `neo_consistency_stddev` as real
    top-level attributes — OR a `NeoWinCEntrantSnapshot` (klpga.neo_win.
    beta001c_archive, the current BETA #001-C production shape) — which
    stores the exact same two quantities only inside its `feature_values`
    dict (confirmed: both are in `klpga.neo_win.model.BASE_FEATURES`,
    always present regardless of which of Model A/B/C was selected).
    This module previously read `e.name` directly, which raises
    AttributeError for the #001-C shape (the real production PRE source
    — see run_beta001_r3_update.py's own PRE-snapshot resolution, which
    prefers #001-C). A pure data-access correction — not a change to any
    simulation formula, weight, or feature."""
    value = getattr(e, name, None)
    if value is not None:
        return value
    feature_values = getattr(e, "feature_values", None)
    if feature_values is not None:
        return feature_values.get(name)
    return None


@dataclass(frozen=True)
class PlayerR3SimInput:
    player_code: str
    player_name: str
    expected_round_score_to_par: float
    spread: float
    r1_score_to_par: Optional[float]
    r2_score_to_par: Optional[float]
    r3_score_to_par: Optional[float]
    made_cut: Optional[bool]
    """Real, known made-cut fact (settled after Round 2) — None means
    genuinely unknown (SKIP + LOG), never guessed True/False."""


def build_r3_sim_inputs_from_frozen_snapshot(
    pre_snapshot,
    r1_scores: dict[str, float],
    r2_scores: dict[str, float],
    r3_scores: dict[str, float],
    made_cut_by_player: dict[str, bool],
) -> tuple[list[PlayerR3SimInput], list[str]]:
    """Same population-mean-shrink convention as round_update_r2.py's
    equivalent function, for the frozen PRE prior. A player is reported
    in `missing_r3_players` (and excluded from simulation) if r1_score,
    r2_score, or a real made_cut fact is unavailable, OR made_cut is
    True and r3_score is unavailable (a confirmed cutmaker missing
    their own R3 score is a real ingestion gap). A confirmed CUT player
    (made_cut=False) missing r3_score is NOT reported here — that
    absence is the real, expected outcome (see module docstring)."""
    known_scores = [v for e in pre_snapshot.predictions if (v := _feature(e, "prior_avg_round_score_to_par")) is not None]
    pop_mean_score = statistics.mean(known_scores) if known_scores else 0.0
    known_spreads = [v for e in pre_snapshot.predictions if (v := _feature(e, "neo_consistency_stddev")) is not None]
    pop_mean_spread = statistics.mean(known_spreads) if known_spreads else 3.0

    sim_inputs = []
    missing: list[str] = []
    for e in pre_snapshot.predictions:
        r1 = r1_scores.get(e.player_code)
        r2 = r2_scores.get(e.player_code)
        r3 = r3_scores.get(e.player_code)
        made_cut = made_cut_by_player.get(e.player_code)
        if r1 is None or r2 is None or made_cut is None or (made_cut is True and r3 is None):
            missing.append(e.player_code)
        prior_avg = _feature(e, "prior_avg_round_score_to_par")
        consistency = _feature(e, "neo_consistency_stddev")
        expected = prior_avg if prior_avg is not None else pop_mean_score
        spread = consistency if consistency is not None else pop_mean_spread
        sim_inputs.append(
            PlayerR3SimInput(
                player_code=e.player_code, player_name=e.player_name,
                expected_round_score_to_par=expected, spread=max(spread, 0.5),
                r1_score_to_par=r1, r2_score_to_par=r2, r3_score_to_par=r3, made_cut=made_cut,
            )
        )
    return sim_inputs, missing


def simulate_post_round3(
    sim_inputs: list[PlayerR3SimInput],
    *,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    rng: Optional[random.Random] = None,
) -> dict[str, dict]:
    """Only real, confirmed cutmakers (made_cut is True) with complete
    R1-R3 real data are simulated over the single remaining round (R4).
    A real, confirmed CUT player (made_cut is False) — who structurally
    has no R3 score at all, since they never played it — gets a real,
    known 0.0 for everything, same convention as round_update_r2.py; r3
    is NOT required for this case. A player missing any required real
    input (r1, r2, made_cut, or — for a confirmed cutmaker only — r3)
    is absent from the returned dict — the caller is responsible for
    reporting those via klpga.neo_win.player_status, never a fabricated
    0."""
    rng = rng or random.Random()
    cutmakers = [
        p for p in sim_inputs
        if p.made_cut is True and p.r1_score_to_par is not None and p.r2_score_to_par is not None
        and p.r3_score_to_par is not None
    ]
    cut_players = [
        p for p in sim_inputs
        if p.made_cut is False and p.r1_score_to_par is not None and p.r2_score_to_par is not None
    ]

    wins = {p.player_code: 0.0 for p in cutmakers}
    top5 = {p.player_code: 0 for p in cutmakers}
    top10 = {p.player_code: 0 for p in cutmakers}
    top20 = {p.player_code: 0 for p in cutmakers}

    for _ in range(n_simulations):
        totals = []
        for p in cutmakers:
            r4 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            total = p.r1_score_to_par + p.r2_score_to_par + p.r3_score_to_par + r4
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
        }
    for p in cut_players:
        result[p.player_code] = {"win_pct": 0.0, "top5_pct": 0.0, "top10_pct": 0.0, "top20_pct": 0.0}
    return result
