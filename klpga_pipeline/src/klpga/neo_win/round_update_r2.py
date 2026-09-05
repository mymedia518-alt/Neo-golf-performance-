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


def _feature(e, name: str) -> Optional[float]:
    """Real-data-shape fix (BETA #001 R1->R2 pipeline preparation): a
    frozen PRE snapshot's `predictions` entries are EITHER a legacy
    `NeoWinEntrantSnapshot` (klpga.neo_win.archive) — which stores
    `prior_avg_round_score_to_par` / `neo_consistency_stddev` as real
    top-level attributes — OR a `NeoWinCEntrantSnapshot` (klpga.neo_win.
    beta001c_archive, the current BETA #001-C production shape) — which
    stores the exact same two quantities only inside its `feature_values`
    dict (confirmed: both are in `klpga.neo_win.model.BASE_FEATURES`,
    always present regardless of which of Model A/B/C was selected).
    `build_r2_sim_inputs_from_frozen_snapshot` previously read `e.name`
    directly, which raises AttributeError for the #001-C shape (the
    default/preferred path in scripts/44) since it has no such top-level
    field at all. This is a pure data-access correction — the SAME
    dual-shape accessor convention scripts/44_predict_neo_win_post_r2.py
    already uses elsewhere (`getattr(x, "model_version", None) or
    getattr(x, "selected_model_id", "")`) — not a change to any
    simulation formula, weight, or feature."""
    value = getattr(e, name, None)
    if value is not None:
        return value
    feature_values = getattr(e, "feature_values", None)
    if feature_values is not None:
        return feature_values.get(name)
    return None


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
    known_scores = [v for e in pre_snapshot.predictions if (v := _feature(e, "prior_avg_round_score_to_par")) is not None]
    pop_mean_score = statistics.mean(known_scores) if known_scores else 0.0
    known_spreads = [v for e in pre_snapshot.predictions if (v := _feature(e, "neo_consistency_stddev")) is not None]
    pop_mean_spread = statistics.mean(known_spreads) if known_spreads else 3.0

    sim_inputs = []
    missing: list[str] = []
    for e in pre_snapshot.predictions:
        r1 = r1_scores.get(e.player_code)
        r2 = r2_scores.get(e.player_code)
        made_cut = made_cut_by_player.get(e.player_code)
        if r1 is None or r2 is None or made_cut is None:
            missing.append(e.player_code)
        prior_avg = _feature(e, "prior_avg_round_score_to_par")
        consistency = _feature(e, "neo_consistency_stddev")
        expected = prior_avg if prior_avg is not None else pop_mean_score
        spread = consistency if consistency is not None else pop_mean_spread
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
    remaining_rounds: int = 2,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    rng: Optional[random.Random] = None,
) -> dict[str, dict]:
    """Only real cutmakers (made_cut is True) are simulated for the
    configured number of remaining rounds.
    A player with real, complete data but made_cut=False gets
    win_pct=top5_pct=top10_pct=top20_pct=make_cut_pct=0.0 — a real,
    KNOWN outcome (they are mathematically eliminated), never an
    estimate. A player missing any required real input (not in
    `sim_inputs` with all fields non-None) is simply absent from the
    returned dict — the caller (scripts/44) is responsible for
    reporting those as `unavailable`, never as a fabricated 0."""
    if remaining_rounds < 1:
        raise ValueError("remaining_rounds must be >= 1")

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
            remaining_score = sum(
                rng.normalvariate(
                    p.expected_round_score_to_par,
                    p.spread,
                )
                for _ in range(remaining_rounds)
            )
            total = (
                p.r1_score_to_par
                + p.r2_score_to_par
                + remaining_score
            )
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
