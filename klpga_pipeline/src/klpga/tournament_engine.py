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
    R3_LIVE = "R3_LIVE"
    R3_COMPLETE = "R3_COMPLETE"
    FINAL_LIVE = "FINAL_LIVE"
    FINAL_COMPLETE = "FINAL_COMPLETE"
    POST_EVALUATED = "POST_EVALUATED"


@dataclass(frozen=True)
class RoundFacts:
    round_number: int
    expected_players: int
    official_players: int
    incomplete_players: int
    unresolved_players: int = 0

    @property
    def validated(self) -> bool:
        return (
            self.expected_players >= 0
            and self.official_players == self.expected_players
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

    def round(self, number: int) -> Optional[RoundFacts]:
        return next(
            (r for r in self.rounds if r.round_number == number),
            None,
        )


def determine_stage(facts: TournamentFacts) -> Stage:
    """Highest stage justified by validated facts."""

    if facts.post_evaluated:
        return Stage.POST_EVALUATED

    final = facts.round(facts.final_round_number)
    if final and final.complete:
        return Stage.FINAL_COMPLETE
    if final and final.validated:
        return Stage.FINAL_LIVE

    r3 = facts.round(3)
    if r3 and r3.complete:
        return Stage.R3_COMPLETE
    if r3 and r3.validated:
        return Stage.R3_LIVE

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


def publication_allowed(stage: Stage, artifact: str) -> bool:
    """Single publication gate used by every tournament."""

    artifact = artifact.upper()

    if artifact == "CUT":
        return stage in {
            Stage.CUT_CONFIRMED,
            Stage.R3_LIVE,
            Stage.R3_COMPLETE,
            Stage.FINAL_LIVE,
            Stage.FINAL_COMPLETE,
            Stage.POST_EVALUATED,
        }

    if artifact in {"NEXT_ROUND_FORECAST", "WIN_PROBABILITY"}:
        return stage in {
            Stage.CUT_CONFIRMED,
            Stage.R3_COMPLETE,
            Stage.FINAL_LIVE,
            Stage.FINAL_COMPLETE,
            Stage.POST_EVALUATED,
        }

    return True
