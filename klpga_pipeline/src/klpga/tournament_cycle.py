"""One-cycle orchestration for the generic NEO Tournament Engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from klpga.tournament_action_registry import (
    ActionContext,
    ActionResult,
    TournamentActionRegistry,
)
from klpga.tournament_engine import Stage
from klpga.tournament_official_ingest import (
    OfficialRoundSnapshot,
)
from klpga.tournament_operator import (
    OperatorDecision,
    decide_operator_action,
)


@dataclass(frozen=True)
class CycleRequest:
    game_code: str
    final_round_number: int
    current_round_number: int
    validated_stage: Stage
    model_ready: bool = False

    def __post_init__(self) -> None:
        if not self.game_code.strip():
            raise ValueError("game_code required")

        if self.final_round_number < 2:
            raise ValueError(
                "final_round_number must be >= 2"
            )

        if not (
            1
            <= self.current_round_number
            <= self.final_round_number
        ):
            raise ValueError(
                "invalid current_round_number"
            )


@dataclass(frozen=True)
class CycleResult:
    request: CycleRequest
    snapshot: OfficialRoundSnapshot
    decision: OperatorDecision
    action_result: ActionResult


OfficialFetcher = Callable[
    [str, int],
    OfficialRoundSnapshot,
]


def run_tournament_cycle(
    *,
    request: CycleRequest,
    official_fetcher: OfficialFetcher,
    registry: TournamentActionRegistry,
) -> CycleResult:
    """Run exactly one fail-closed tournament cycle.

    Stage is supplied only after external validation. This function
    never promotes stage merely because a leaderboard fetch succeeded.
    """

    snapshot = official_fetcher(
        request.game_code,
        request.current_round_number,
    )

    if snapshot.game_code != request.game_code:
        raise ValueError(
            "official snapshot game_code mismatch"
        )

    if snapshot.round_number != request.current_round_number:
        raise ValueError(
            "official snapshot round mismatch"
        )

    if snapshot.row_count <= 0:
        raise ValueError(
            "official snapshot contains zero rows"
        )

    decision = decide_operator_action(
        request.validated_stage,
        final_round_number=request.final_round_number,
        current_round_number=request.current_round_number,
        model_ready=request.model_ready,
    )

    context = ActionContext(
        game_code=request.game_code,
        final_round_number=request.final_round_number,
        current_round_number=request.current_round_number,
    )

    action_result = registry.execute(
        context,
        decision,
    )

    return CycleResult(
        request=request,
        snapshot=snapshot,
        decision=decision,
        action_result=action_result,
    )
