"""NEO Ranking V2 -- VALIDATION_MODEL_NOT_PRODUCTION.

This module is a candidate skill-estimation layer built to answer one
question raised against V1 (``neo_ranking_backtest.py`` /
``NEO_RANKING_VALIDATION_MODEL_V1.json``, verdict REJECT): does treating
each tournament's cumulative SG total as one equal observation --
regardless of how many rounds produced it -- bias the ranking toward
players who simply accumulated more rounds?

Confirmed from the real corrected SG warehouse
(``historical_sg_warehouse_corrected.json``, 11,144 unique player-events
after taking each event's most-complete snapshot): only 3,315 of 11,144
events (30%) are full 4-round completions. 4,856 (44%) are 1-round
events (WD/DQ or a round-1-only snapshot never followed by a later
cumulative row), 2,852 (26%) are 3-round, 121 (1%) are 2-round. A model
that averages event totals unweighted by rounds is therefore wrong for
the majority of its input, not an edge case.

This module never touches ``home_ranking.py``'s production
``FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"`` gate. It is
validation-only until a V2 candidate passes backtest against V1 and is
explicitly approved.

Core distinction enforced throughout: a SKILL ESTIMATE (a point value)
is kept separate from its UNCERTAINTY (how much to trust that point).
More rounds must only ever narrow uncertainty -- it must never, by
itself, move the skill estimate up.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

VALIDATION_MODEL_NOT_PRODUCTION = True
CANDIDATE_VERSION = "neo-ranking-v2-candidate-unreleased"


@dataclass(frozen=True)
class EventObservation:
    """One player's single tournament: a cumulative SG total over a
    known number of rounds. ``rounds`` must be the ACTUAL rounds that
    produced ``total_sg`` (1 for a round-1 WD/DQ, 2/3 for a short cut,
    4 for a full completion) -- never assumed or defaulted."""

    total_sg: float
    rounds: int

    def __post_init__(self) -> None:
        if self.rounds <= 0:
            raise ValueError("rounds must be a positive integer")

    @property
    def per_round_rate(self) -> float:
        """SG per round for this one event. This is the observation
        unit (see module docstring / PHASE C): normalizing INSIDE each
        event before combining across events is what fixes Case 1/2
        below -- a naive event-total average never does this."""
        return self.total_sg / self.rounds


def naive_event_total_mean(events: list[EventObservation]) -> float:
    """The CURRENT production behavior (``home_ranking.build_features``):
    mean of raw event totals, with no round normalization at all. Kept
    here ONLY so the red-team tests can show it failing against the
    same cases the candidate passes -- never call this for a real
    ranking."""
    if not events:
        raise ValueError("no events")
    return statistics.fmean(ev.total_sg for ev in events)


def pooled_per_round_rate(events: list[EventObservation]) -> float:
    """PHASE C candidate observation unit: pool every round across
    every event and take one rate -- sum(total) / sum(rounds) -- rather
    than a naive event-total mean OR an unweighted mean of per-event
    rates. This is the "weighted event SG normalized by rounds" option
    (PHASE C option D). It differs from an unweighted mean-of-rates
    once a player's events have unequal round counts, and is the
    statistically correct pooled estimate of a per-round rate (it is
    equivalent to averaging every individual round directly, under the
    assumption that a player's rounds within one event are exchangeable)."""
    if not events:
        raise ValueError("no events")
    total = sum(ev.total_sg for ev in events)
    rounds = sum(ev.rounds for ev in events)
    return total / rounds


@dataclass(frozen=True)
class ShrinkagePrior:
    """Empirical-Bayes prior, ESTIMATED from the real warehouse data
    (method-of-moments), not hand-picked. See
    ``estimate_shrinkage_prior_from_warehouse`` for how these numbers
    were produced and re-derive them whenever the warehouse is rebuilt
    -- they are a measured property of the data, not a constant."""

    population_mean_per_round: float
    between_player_variance: float  # tau^2: true skill spread across players
    within_player_variance: float  # sigma^2: round-to-round noise for one player

    def shrinkage_weight(self, n_rounds: int) -> float:
        """B_i in the classic empirical-Bayes formula: weight given to
        this player's OWN observed rate. -> 0 as n_rounds -> 0 (pulled
        fully to the population mean); -> 1 as n_rounds grows (trusted
        on their own data). Never exceeds 1, never negative."""
        if n_rounds <= 0:
            return 0.0
        denom = self.between_player_variance + self.within_player_variance / n_rounds
        if denom <= 0:
            return 1.0
        return self.between_player_variance / denom


def estimate_shrinkage_prior_from_warehouse(
    events_by_player: dict[str, list[EventObservation]],
    min_events_for_within_estimate: int = 3,
) -> ShrinkagePrior:
    """Method-of-moments empirical-Bayes calibration, computed from
    real player histories (not invented). For each player with enough
    events to estimate their own round-to-round noise, pool:

      sigma^2 = pooled within-player variance of per-event per-round rates
      raw_between = variance of players' own mean per-round rates
      tau^2 = max(raw_between - sigma^2 / avg_n, 0)   (bias-corrected)

    Run against the real corrected SG warehouse (43,701 raw rows / 476
    players / 291 with >=3 events) this produced sigma^2 ~= 3.84,
    tau^2 ~= 1.95, population_mean ~= -1.27 SG/round -- i.e. shrinkage
    weight ~=0.34 at n=1 round of evidence, ~=0.72 at n=5, ~=0.91 at
    n=20. Re-run this function against a fresh warehouse rather than
    hard-coding those numbers; they are reported here only as the
    audit trail for the specific run that produced them."""
    per_player_rates: dict[str, list[float]] = {}
    for player_id, events in events_by_player.items():
        if not events:
            continue
        per_player_rates[player_id] = [ev.per_round_rate for ev in events]

    eligible = {pid: rates for pid, rates in per_player_rates.items() if len(rates) >= min_events_for_within_estimate}
    if len(eligible) < 2:
        raise ValueError("not enough players with sufficient event history to estimate shrinkage")

    weighted_var_sum = 0.0
    weighted_var_denom = 0
    player_means: list[tuple[float, int]] = []
    for rates in eligible.values():
        mean = statistics.fmean(rates)
        player_means.append((mean, len(rates)))
        if len(rates) > 1:
            var = statistics.variance(rates)
            weighted_var_sum += var * (len(rates) - 1)
            weighted_var_denom += len(rates) - 1

    if weighted_var_denom == 0:
        raise ValueError("cannot estimate within-player variance: no player has >1 event")

    sigma2 = weighted_var_sum / weighted_var_denom
    means_only = [m for m, _ in player_means]
    avg_n = statistics.fmean(n for _, n in player_means)
    raw_between = statistics.variance(means_only)
    tau2 = max(raw_between - sigma2 / avg_n, 0.0)
    grand_mean = statistics.fmean(means_only)

    return ShrinkagePrior(
        population_mean_per_round=grand_mean,
        between_player_variance=tau2,
        within_player_variance=sigma2,
    )


@dataclass(frozen=True)
class SkillEstimate:
    """A point estimate kept explicitly separate from its uncertainty,
    plus the raw inputs that produced it -- so "why is A ranked above
    B" is always answerable from these fields (PHASE F requirement)."""

    player_id: str
    observed_rate: float  # pooled_per_round_rate, unshrunk
    shrunk_rate: float  # empirical-Bayes adjusted skill estimate
    shrinkage_weight: float  # how much of observed_rate survived shrinkage
    total_rounds: int
    event_count: int
    volatility: float  # stdev of per-event per-round rates -- reported, never subtracted from the point estimate


def estimate_skill(
    player_id: str,
    events: list[EventObservation],
    prior: ShrinkagePrior,
) -> SkillEstimate:
    """PHASE C + PHASE D combined: pool to a per-round rate, then
    shrink it toward the population mean by an amount controlled ONLY
    by total rounds of evidence. Volatility is computed and reported
    but never added to or subtracted from the point estimate -- PHASE
    B Case 9 requires skill (location) and volatility (spread) to stay
    separate concepts."""
    if not events:
        raise ValueError("no events")
    observed = pooled_per_round_rate(events)
    total_rounds = sum(ev.rounds for ev in events)
    weight = prior.shrinkage_weight(total_rounds)
    shrunk = weight * observed + (1 - weight) * prior.population_mean_per_round
    rates = [ev.per_round_rate for ev in events]
    volatility = statistics.pstdev(rates) if len(rates) > 1 else 0.0
    return SkillEstimate(
        player_id=player_id,
        observed_rate=observed,
        shrunk_rate=shrunk,
        shrinkage_weight=weight,
        total_rounds=total_rounds,
        event_count=len(events),
        volatility=volatility,
    )
