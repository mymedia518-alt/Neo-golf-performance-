"""NEO generic tournament state engine.

Tournament names, game codes and calendar dates MUST NOT control stage logic.
Only validated official-data facts may advance a tournament.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Stage(str, Enum):
    DISCOVERED = "DISCOVERED"
    ENTRY_READY = "ENTRY_READY"
    PRE_READY = "PRE_READY"
    R1_LIVE = "R1_LIVE"
    R1_COMPLETE = "R1_COMPLETE"
    R2_LIVE = "R2_LIVE"
    R2_COMPLETE = "R2_COMPLETE"
    CUT_CONFIRMED = "CUT_CONFIRMED"
    NEXT_ROUND_LIVE = "NEXT_ROUND_LIVE"
    NEXT_ROUND_COMPLETE = "NEXT_ROUND_COMPLETE"
    FINAL_LIVE = "FINAL_LIVE"
    FINAL_COMPLETE = "FINAL_COMPLETE"
    POST_EVALUATED = "POST_EVALUATED"

    # Backward-compatible aliases while old callers migrate.
    R3_LIVE = "NEXT_ROUND_LIVE"
    R3_COMPLETE = "NEXT_ROUND_COMPLETE"


@dataclass(frozen=True)
class RoundFacts:
    round_number: int
    expected_players: int
    official_players: int
    incomplete_players: int
    unresolved_players: int = 0

    def __post_init__(self) -> None:
        if self.round_number < 1:
            raise ValueError("round_number must be >= 1")

        for name in (
            "expected_players",
            "official_players",
            "incomplete_players",
            "unresolved_players",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")

        if self.incomplete_players > self.official_players:
            raise ValueError(
                "incomplete_players cannot exceed official_players"
            )

        if self.unresolved_players > self.official_players:
            raise ValueError(
                "unresolved_players cannot exceed official_players"
            )

    @property
    def validated(self) -> bool:
        return (
            self.official_players == self.expected_players
            and self.unresolved_players == 0
        )

    @property
    def complete(self) -> bool:
        return self.validated and self.incomplete_players == 0


@dataclass(frozen=True)
class TournamentFacts:
    entry_validated: bool = False
    pre_validated: bool = False
    rounds: tuple[RoundFacts, ...] = ()
    cut_validated: bool = False
    final_round_number: int = 4
    post_evaluated: bool = False

    def __post_init__(self) -> None:
        if self.final_round_number < 2:
            raise ValueError(
                "final_round_number must be >= 2"
            )

        numbers = [r.round_number for r in self.rounds]

        if len(numbers) != len(set(numbers)):
            raise ValueError(
                "duplicate round_number is not allowed"
            )

        if any(
            number > self.final_round_number
            for number in numbers
        ):
            raise ValueError(
                "round_number cannot exceed final_round_number"
            )

    def round(self, number: int) -> Optional[RoundFacts]:
        return next(
            (
                r
                for r in self.rounds
                if r.round_number == number
            ),
            None,
        )


def determine_stage(facts: TournamentFacts) -> Stage:
    """Return the highest stage justified by validated facts."""

    final = facts.round(facts.final_round_number)

    # Post evaluation is impossible before the official final is complete.
    if facts.post_evaluated:
        if not final or not final.complete:
            raise ValueError(
                "post_evaluated requires validated final completion"
            )
        return Stage.POST_EVALUATED

    if final and final.complete:
        return Stage.FINAL_COMPLETE

    if final and final.validated:
        return Stage.FINAL_LIVE

    # Rounds between R2 and the final are generic.
    intermediate_numbers = range(
        3,
        facts.final_round_number,
    )

    intermediate = [
        facts.round(number)
        for number in intermediate_numbers
    ]

    existing = [
        r for r in intermediate if r is not None
    ]

    if existing:
        latest = max(
            existing,
            key=lambda r: r.round_number,
        )

        if latest.complete:
            return Stage.NEXT_ROUND_COMPLETE

        if latest.validated:
            return Stage.NEXT_ROUND_LIVE

    if facts.cut_validated:
        return Stage.CUT_CONFIRMED

    r2 = facts.round(2)

    if r2 and r2.complete:
        return Stage.R2_COMPLETE

    if r2 and r2.validated:
        return Stage.R2_LIVE

    r1 = facts.round(1)

    if r1 and r1.complete:
        return Stage.R1_COMPLETE

    if r1 and r1.validated:
        return Stage.R1_LIVE

    if facts.pre_validated:
        return Stage.PRE_READY

    if facts.entry_validated:
        return Stage.ENTRY_READY

    return Stage.DISCOVERED


def publication_allowed(
    stage: Stage,
    artifact: str,
) -> bool:
    """Single publication gate used by every tournament."""

    artifact = artifact.upper()

    if artifact == "CUT":
        return stage in {
            Stage.CUT_CONFIRMED,
            Stage.NEXT_ROUND_LIVE,
            Stage.NEXT_ROUND_COMPLETE,
            Stage.FINAL_LIVE,
            Stage.FINAL_COMPLETE,
            Stage.POST_EVALUATED,
        }

    if artifact in {
        "NEXT_ROUND_FORECAST",
        "WIN_PROBABILITY",
    }:
        return stage in {
            Stage.CUT_CONFIRMED,
            Stage.NEXT_ROUND_COMPLETE,
            Stage.FINAL_LIVE,
            Stage.FINAL_COMPLETE,
            Stage.POST_EVALUATED,
        }

    return True
