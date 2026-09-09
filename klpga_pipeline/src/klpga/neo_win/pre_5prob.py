"""NEO PRE 5-PROBABILITY CANDIDATE V1 -- a genuinely new, PRE-only Monte
Carlo tournament simulator producing CUT/TOP20/TOP10/TOP5/WIN together.

======================================================================
WHY THIS MODULE EXISTS (do not confuse with round_update.py)
======================================================================
`klpga.neo_win.round_update.simulate_post_round1` already produces all
five tiers, but it REQUIRES each player's real, already-played Round 1
score as the anchor for the 36-hole cut ranking -- it is architecturally
usable only from the POST-R1 checkpoint onward. There is no PRE-stage
equivalent anywhere in this codebase: before this module, CUT/TOP20/
TOP10/TOP5 simply had no PRE-stage implementation (see
NEO_PRE_PROBABILITY_MODEL_AUDIT_V1.json section 5). This module fills
that specific, previously-empty slot.

======================================================================
METHOD
======================================================================
Every one of a player's 4 rounds -- including Round 1 -- is drawn from
Normal(expected_round_score_to_par, spread). Nothing about a real,
already-played round is used anywhere, because at PRE nothing has been
played yet. `expected_round_score_to_par` / `spread` are the SAME two
frozen PRE-time features `round_update.py` already uses for a player's
REMAINING rounds (never retuned, never given new weights here) --
this module only removes the real-R1-anchor round_update.py relies on,
it does not invent a new skill signal.

The cut is applied after the simulated Round 2 using an EMPIRICAL,
already-disclosed cut fraction (see `DISCLOSED_HISTORICAL_CUT_FRACTION`
below) -- never an invented cutline rule. WIN/TOP5/TOP10/TOP20 are
tallied only among that trial's cut survivors, exactly mirroring
`round_update.simulate_post_round1`'s own elimination structure.

Disclosed simplifications (identical to round_update.py, not new):
i.i.d. per-round Normal draws (no course-difficulty correlation, no
playoff modeling -- ties for the win split the win credit fractionally).

======================================================================
PUBLICATION STATUS
======================================================================
This module is an EXECUTABLE CANDIDATE, not an approved production
model. See NEO_PRE_5PROB_PUBLICATION_GATE_V1.json for the current
BLOCKED verdict and its evidence. Nothing in this module writes to any
public-facing artifact on its own; callers decide what to do with its
output.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Optional

MODEL_ID = "NEO_PRE_5PROB_V1"
DEFAULT_N_SIMULATIONS = 5000

DISCLOSED_HISTORICAL_CUT_FRACTION = 336 / 602
"""Real, already-published made-cut split from this project's own
100-tournament collection run: `made_cut` split (0, 266) / (1, 336)
across 602 player_event rows -- see docs/SITE_STRUCTURE_TODO.md, the
"WORKING" made_cut derivation note. Used here ONLY as the disclosed
neutral default when a live database (and therefore
`round_update.estimate_cut_fraction`'s own DB-backed computation) is
unavailable to the caller -- never a newly-invented number. A caller
with real DB access should prefer `round_update.estimate_cut_fraction`
and pass its result in explicitly instead of relying on this default."""

POPULATION_MEAN_SPREAD_FALLBACK = 3.0
"""Identical fallback constant already used by
`round_update.build_sim_inputs_from_frozen_snapshot` when a player has
no `neo_consistency_stddev` at all and the field itself has no known
spreads to average -- reused verbatim here, not a new invented value."""


@dataclass(frozen=True)
class PreSimInput:
    player_code: str
    player_name: str
    expected_round_score_to_par: float
    spread: float
    expected_source: str
    """Free-text provenance for `expected_round_score_to_par` (e.g.
    "prior_avg_round_score_to_par" or "population_mean_fallback") --
    required so every backtest/candidate run can show, per player,
    whether a real or a fallback value was used. Never omitted."""
    spread_source: str


def build_pre_sim_inputs(
    field_rows: list[dict],
    *,
    player_code_field: str = "player_code",
    player_name_field: str = "player_name",
    score_field: str = "prior_avg_round_score_to_par",
    spread_field: Optional[str] = "neo_consistency_stddev",
) -> list[PreSimInput]:
    """Builds sim inputs from a PRE-time field snapshot. `field_rows` is
    a list of dicts -- one per entrant -- each expected to carry
    `player_code_field`/`player_name_field`/`score_field` and,
    optionally, `spread_field`. Any missing `score_field` value falls
    back to the field's own population mean (never a fabricated fixed
    number); any missing/absent `spread_field` value falls back to the
    field's own population mean spread, or `POPULATION_MEAN_SPREAD_
    FALLBACK` if no player in the field has a real spread at all --
    identical convention to round_update.py's own fallback."""
    known_scores = [
        row[score_field] for row in field_rows
        if row.get(score_field) is not None
    ]
    pop_mean_score = statistics.mean(known_scores) if known_scores else 0.0

    known_spreads = []
    if spread_field is not None:
        known_spreads = [
            row[spread_field] for row in field_rows
            if row.get(spread_field) is not None
        ]
    pop_mean_spread = statistics.mean(known_spreads) if known_spreads else POPULATION_MEAN_SPREAD_FALLBACK

    sim_inputs = []
    for row in field_rows:
        raw_score = row.get(score_field)
        if raw_score is not None:
            expected, expected_source = raw_score, score_field
        else:
            expected, expected_source = pop_mean_score, "population_mean_fallback"

        raw_spread = row.get(spread_field) if spread_field is not None else None
        if raw_spread is not None:
            spread, spread_source = raw_spread, spread_field
        else:
            spread, spread_source = pop_mean_spread, "population_mean_fallback"

        sim_inputs.append(
            PreSimInput(
                player_code=row[player_code_field],
                player_name=row.get(player_name_field, ""),
                expected_round_score_to_par=expected,
                spread=max(spread, 0.5),
                expected_source=expected_source,
                spread_source=spread_source,
            )
        )
    return sim_inputs


def simulate_pre_tournament(
    sim_inputs: list[PreSimInput],
    *,
    cut_fraction: float = DISCLOSED_HISTORICAL_CUT_FRACTION,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    rng: Optional[random.Random] = None,
) -> dict[str, dict]:
    """Simulates ALL 4 rounds from the PRE prior alone (no real round
    ever used as an anchor). Returns {player_code: {win_pct, top5_pct,
    top10_pct, top20_pct, make_cut_pct}} -- by construction these five
    values obey `0 <= win <= top5 <= top10 <= top20 <= make_cut <= 100`
    for every player, since each tier's count is a superset of the
    stricter tier's count within the same simulated trials; this is a
    structural guarantee of the tallying loop below, not a
    post-hoc-enforced clip."""
    rng = rng or random.Random()
    if not sim_inputs:
        return {}
    n_cutline = max(1, round(len(sim_inputs) * cut_fraction))

    wins = {p.player_code: 0.0 for p in sim_inputs}
    top5 = {p.player_code: 0 for p in sim_inputs}
    top10 = {p.player_code: 0 for p in sim_inputs}
    top20 = {p.player_code: 0 for p in sim_inputs}
    made_cut = {p.player_code: 0 for p in sim_inputs}

    for _ in range(n_simulations):
        r1 = {p.player_code: rng.normalvariate(p.expected_round_score_to_par, p.spread) for p in sim_inputs}
        r2 = {p.player_code: rng.normalvariate(p.expected_round_score_to_par, p.spread) for p in sim_inputs}
        thru36 = sorted(sim_inputs, key=lambda p: r1[p.player_code] + r2[p.player_code])
        cutmakers = thru36[:n_cutline]
        cutmaker_codes = {p.player_code for p in cutmakers}
        for code in cutmaker_codes:
            made_cut[code] += 1

        totals = []
        for p in cutmakers:
            r3 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            r4 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            total = r1[p.player_code] + r2[p.player_code] + r3 + r4
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
    for p in sim_inputs:
        result[p.player_code] = {
            "win_pct": round(100 * wins[p.player_code] / n_simulations, 6),
            "top5_pct": round(100 * top5[p.player_code] / n_simulations, 4),
            "top10_pct": round(100 * top10[p.player_code] / n_simulations, 4),
            "top20_pct": round(100 * top20[p.player_code] / n_simulations, 4),
            "make_cut_pct": round(100 * made_cut[p.player_code] / n_simulations, 4),
            "expected_source": p.expected_source,
            "spread_source": p.spread_source,
        }
    return result


def verify_monotonicity(results: dict[str, dict]) -> list[str]:
    """Returns player_codes that VIOLATE 0<=win<=top5<=top10<=top20<=
    make_cut<=100 (should always be empty given the tallying loop's
    structure -- this is a red-team / regression check, not a fix)."""
    violations = []
    for code, r in results.items():
        chain = [r["win_pct"], r["top5_pct"], r["top10_pct"], r["top20_pct"], r["make_cut_pct"]]
        if not all(0.0 <= a <= b + 1e-9 for a, b in zip(chain, chain[1:])) or chain[-1] > 100.0 + 1e-9 or chain[0] < 0.0:
            violations.append(code)
    return violations
