"""Generic runtime contracts for every NEO tournament.

This module contains no tournament-specific game code, name or date.
Tournament differences are data supplied through TournamentConfig.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from klpga.tournament_engine import (
    RoundFacts,
    Stage,
    TournamentFacts,
    determine_stage,
)


@dataclass(frozen=True)
class TournamentConfig:
    game_code: str
    tournament_name: str
    final_round_number: int
    cut_after_round: Optional[int] = 2

    def __post_init__(self):
        if not self.game_code.strip():
            raise ValueError("game_code required")
        if not self.tournament_name.strip():
            raise ValueError("tournament_name required")
        if self.final_round_number < 1:
            raise ValueError("final_round_number must be >= 1")
        if (
            self.cut_after_round is not None
            and not 1 <= self.cut_after_round < self.final_round_number
        ):
            raise ValueError("invalid cut_after_round")


@dataclass(frozen=True)
class PlayerEventFact:
    player_code: str
    status: str
    made_cut: Optional[bool]

    @property
    def normalized_status(self) -> str:
        return (self.status or "").strip().upper()


@dataclass(frozen=True)
class CutValidation:
    validated: bool
    advancing: tuple[str, ...]
    eliminated: tuple[str, ...]
    exempt_status: tuple[str, ...]
    unresolved: tuple[str, ...]


NON_CUT_STATUSES = frozenset({"WD", "DQ", "DNS"})


def validate_cut(
    players: Iterable[PlayerEventFact],
    *,
    round_complete: bool,
) -> CutValidation:
    """Validate factual cut state.

    CUT is never inferred from rank or score here.
    made_cut must come from reconciled official/event evidence.
    """

    players = tuple(players)

    if not round_complete:
        return CutValidation(
            validated=False,
            advancing=(),
            eliminated=(),
            exempt_status=(),
            unresolved=tuple(sorted(p.player_code for p in players)),
        )

    advancing = []
    eliminated = []
    exempt = []
    unresolved = []

    for p in players:
        status = p.normalized_status

        if status in NON_CUT_STATUSES:
            exempt.append(p.player_code)
            continue

        if p.made_cut is True:
            advancing.append(p.player_code)
        elif p.made_cut is False:
            eliminated.append(p.player_code)
        else:
            unresolved.append(p.player_code)

    return CutValidation(
        validated=not unresolved,
        advancing=tuple(sorted(advancing)),
        eliminated=tuple(sorted(eliminated)),
        exempt_status=tuple(sorted(exempt)),
        unresolved=tuple(sorted(unresolved)),
    )


def build_tournament_facts(
    config: TournamentConfig,
    *,
    entry_validated: bool,
    pre_validated: bool,
    rounds: Iterable[RoundFacts],
    cut_validation: Optional[CutValidation] = None,
    post_evaluated: bool = False,
) -> TournamentFacts:
    return TournamentFacts(
        entry_validated=entry_validated,
        pre_validated=pre_validated,
        rounds=tuple(rounds),
        cut_validated=bool(
            cut_validation is not None and cut_validation.validated
        ),
        final_round_number=config.final_round_number,
        post_evaluated=post_evaluated,
    )


def resolve_runtime_stage(
    config: TournamentConfig,
    *,
    entry_validated: bool,
    pre_validated: bool,
    rounds: Iterable[RoundFacts],
    cut_validation: Optional[CutValidation] = None,
    post_evaluated: bool = False,
) -> Stage:
    facts = build_tournament_facts(
        config,
        entry_validated=entry_validated,
        pre_validated=pre_validated,
        rounds=rounds,
        cut_validation=cut_validation,
        post_evaluated=post_evaluated,
    )
    return determine_stage(facts)
