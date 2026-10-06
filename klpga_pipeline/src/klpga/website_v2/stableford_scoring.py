"""NEO HJ 2026 (gameCode 2026100004) Stableford scoring primitives.

Official modified-Stableford point table (user relay, OFFICIAL RELAY,
source https://data.klpga.co.kr/pressn_detail.jsp?Rownum=1&pageNum=1&sn=131870
-- Claude's network cannot independently fetch klpga.co.kr/data.klpga.co.kr,
confirmed blocked again this turn via curl + WebFetch, EGRESS_BLOCKED):

    albatross: +8   eagle: +5   birdie: +2   par: 0
    bogey: -1       double bogey or worse: -3

This module is the ONLY part of the HJ Stableford build that needed no new
data to implement for real -- it's pure arithmetic over whatever
hole-outcome counts or probabilities are supplied. Everything downstream
(backtest, Monte Carlo) is blocked on data that hasn't been obtained; see
HJ_2026100004_STABLEFORD_GAP.md.
"""
from __future__ import annotations

from dataclasses import dataclass

OUTCOMES = ("albatross", "eagle", "birdie", "par", "bogey", "double_or_worse")

SCORING_TABLE: dict[str, int] = {
    "albatross": 8,
    "eagle": 5,
    "birdie": 2,
    "par": 0,
    "bogey": -1,
    "double_or_worse": -3,
}


@dataclass(frozen=True)
class HoleOutcomeCounts:
    """Actual outcome counts across some number of holes (e.g. a completed
    round or tournament). Used to score REAL results, never a prediction."""
    albatross: int = 0
    eagle: int = 0
    birdie: int = 0
    par: int = 0
    bogey: int = 0
    double_or_worse: int = 0

    @property
    def total_holes(self) -> int:
        return (self.albatross + self.eagle + self.birdie + self.par
                + self.bogey + self.double_or_worse)

    def total_points(self) -> int:
        return (
            self.albatross * SCORING_TABLE["albatross"]
            + self.eagle * SCORING_TABLE["eagle"]
            + self.birdie * SCORING_TABLE["birdie"]
            + self.par * SCORING_TABLE["par"]
            + self.bogey * SCORING_TABLE["bogey"]
            + self.double_or_worse * SCORING_TABLE["double_or_worse"]
        )


@dataclass(frozen=True)
class HoleOutcomeProbabilities:
    """Per-hole outcome probabilities for ONE hole (must sum to 1.0, within
    floating-point tolerance). Used for an EXPECTED-value / distribution
    projection, never presented as an actual result."""
    albatross: float = 0.0
    eagle: float = 0.0
    birdie: float = 0.0
    par: float = 0.0
    bogey: float = 0.0
    double_or_worse: float = 0.0

    def __post_init__(self):
        total = (self.albatross + self.eagle + self.birdie + self.par
                 + self.bogey + self.double_or_worse)
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"outcome probabilities must sum to 1.0, got {total}")
        for name in OUTCOMES:
            v = getattr(self, name)
            if v < 0 or v > 1:
                raise ValueError(f"{name} probability out of [0,1]: {v}")

    def expected_points(self) -> float:
        """8*P(albatross) + 5*P(eagle) + 2*P(birdie) - P(bogey) - 3*P(double+)
        -- the official formula, applied exactly, to ONE hole's probabilities."""
        return (
            self.albatross * SCORING_TABLE["albatross"]
            + self.eagle * SCORING_TABLE["eagle"]
            + self.birdie * SCORING_TABLE["birdie"]
            + self.par * SCORING_TABLE["par"]
            + self.bogey * SCORING_TABLE["bogey"]
            + self.double_or_worse * SCORING_TABLE["double_or_worse"]
        )

    def variance_points(self) -> float:
        """Var(X) = E[X^2] - E[X]^2 for this hole's point distribution --
        preserves spread, not just the mean, per the explicit instruction
        not to collapse the distribution to an average."""
        mean = self.expected_points()
        second_moment = sum(
            getattr(self, name) * (SCORING_TABLE[name] ** 2) for name in OUTCOMES
        )
        return second_moment - mean ** 2


def expected_round_points(hole_probs: list[HoleOutcomeProbabilities]) -> tuple[float, float]:
    """18 (or however many) holes' worth of independent per-hole
    distributions -> (expected total points, total variance). Holes are
    NOT assumed independent of player skill (each hole's probabilities are
    themselves player- and hole-specific inputs) but outcomes on different
    holes in the same round are treated as independent random draws given
    those per-hole probabilities -- the standard simplifying assumption
    for this kind of model; flagged explicitly rather than silently
    assumed, so Red Team can evaluate it (see stableford_redteam.py)."""
    mean = sum(h.expected_points() for h in hole_probs)
    variance = sum(h.variance_points() for h in hole_probs)
    return mean, variance
