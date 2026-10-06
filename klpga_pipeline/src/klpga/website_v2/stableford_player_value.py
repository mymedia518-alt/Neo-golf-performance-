"""Stableford player-value layer (HJ 2026100004 gap, pre-event blind
backtest, continued 2026-10-06).

Pure arithmetic over klpga.website_v2.stableford_scoring's existing,
already-tested HoleOutcomeProbabilities -- no new scoring table, no new
formula invented here. This module's only job is to decompose the
single expected_points() number into the separately-explainable
components the task requires (positive scoring contribution / bogey
cost / double+ downside / net expectation), so a report never has to
collapse straight to one opaque score.

Albatross is explicitly NEVER invented here. See
klpga.website_v2.stableford_player_value.from_season_rates: passing a
non-zero albatross_rate requires a non-empty albatross_source string
naming where that rate actually came from -- there is no default, no
estimate, no "assume it's rare so use 0.001". Every real event sample
this project has captured (2023100002/2024100009/2025100001, see
tests/test_stableford_2025100001_reconstruction.py and
tests/test_stableford_2024_2023_reconstruction.py) contains ZERO
albatross-classed cells, so the honest default is exactly 0.0, not a
small positive guess."""
from __future__ import annotations

from dataclasses import dataclass

from klpga.website_v2.stableford_scoring import HoleOutcomeProbabilities, SCORING_TABLE


@dataclass(frozen=True)
class StablefordValueBreakdown:
    """Per-hole expected Stableford points, decomposed into the pieces
    a reader actually needs to explain a player's value -- never just
    the single net number."""
    positive_scoring_contribution: float  # 8*P(albatross) + 5*P(eagle) + 2*P(birdie)
    bogey_cost: float  # -1*P(bogey)
    double_plus_downside: float  # -3*P(double_or_worse)
    net_expectation: float  # sum of the three above == probs.expected_points()
    probabilities: HoleOutcomeProbabilities
    albatross_source: str | None


def from_season_rates(
    *,
    eagle_rate: float,
    birdie_rate: float,
    par_rate: float,
    bogey_rate: float,
    double_or_worse_rate: float,
    albatross_rate: float = 0.0,
    albatross_source: str | None = None,
) -> StablefordValueBreakdown:
    """Builds a StablefordValueBreakdown from pre-event per-hole outcome
    RATES (e.g. a player's season-to-date birdie rate) -- the caller's
    job, not this function's, is making sure those rates were computed
    only from data that predates the target event (see
    klpga.backtest.temporal.is_strictly_before and
    klpga.backtest.point_in_time_features for the leakage-safe way to
    produce them).

    Raises ValueError if albatross_rate is non-zero but no
    albatross_source is given -- this is the one place this module
    actively refuses to silently fabricate an input, rather than just
    documenting the risk in a comment."""
    if albatross_rate != 0.0 and not albatross_source:
        raise ValueError(
            "albatross_rate is non-zero but no albatross_source was given -- "
            "this project never invents an albatross rate; name the real source "
            "or leave albatross_rate at its default 0.0"
        )
    probs = HoleOutcomeProbabilities(
        albatross=albatross_rate,
        eagle=eagle_rate,
        birdie=birdie_rate,
        par=par_rate,
        bogey=bogey_rate,
        double_or_worse=double_or_worse_rate,
    )
    positive = (
        probs.albatross * SCORING_TABLE["albatross"]
        + probs.eagle * SCORING_TABLE["eagle"]
        + probs.birdie * SCORING_TABLE["birdie"]
    )
    bogey_cost = probs.bogey * SCORING_TABLE["bogey"]
    double_plus = probs.double_or_worse * SCORING_TABLE["double_or_worse"]
    net = positive + bogey_cost + double_plus  # par contributes 0, excluded from the sum on purpose
    return StablefordValueBreakdown(
        positive_scoring_contribution=round(positive, 4),
        bogey_cost=round(bogey_cost, 4),
        double_plus_downside=round(double_plus, 4),
        net_expectation=round(net, 4),
        probabilities=probs,
        albatross_source=albatross_source,
    )
