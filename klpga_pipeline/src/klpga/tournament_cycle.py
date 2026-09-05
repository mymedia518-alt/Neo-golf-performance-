"""Generic tournament cycle orchestration.

Official ingest occurs only while a round is actually LIVE.
Completed/preparation/cut/finalized stages must not require a network
fetch merely to decide their next action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from klpga.tournament_action_registry import (
    ActionContext,
    ActionResult,
    TournamentActionRegistry,
)
from klpga.tournament_official_ingest import OfficialRoundSnapshot
from klpga.tournament_operator import (
    OperatorDecision,
    decide_operator_action,
)


class TournamentCycleBlocked(RuntimeError):
    pass


LIVE_STAGES = frozenset({
    "R1_LIVE",
    "R2_LIVE",
    "NEXT_ROUND_LIVE",
    "R3_LIVE",
    "FINAL_LIVE",
})


@dataclass(frozen=True)
class CycleRequest:
    game_code: str
    final_round_number: int
    current_round_number: int
    validated_stage: str
    model_ready: bool = False

    def __post_init__(self):
        if not self.game_code.strip():
            raise ValueError("game_code required")

        if self.final_round_number < 2:
            raise ValueError(
                "final_round_number must be >= 2"
            )

        if not (
            1 <= self.current_round_number
            <= self.final_round_number
        ):
            raise ValueError(
                "current_round_number outside tournament"
            )


@dataclass(frozen=True)
class CycleResult:
    request: CycleRequest
    snapshot: OfficialRoundSnapshot | None
    decision: OperatorDecision
    action_result: ActionResult


def stage_requires_official_ingest(stage: str) -> bool:
    return str(stage).upper() in LIVE_STAGES


def run_tournament_cycle(
    request: CycleRequest,
    *,
    official_fetcher: Callable[
        [str, int], OfficialRoundSnapshot
    ],
    registry: TournamentActionRegistry,
) -> CycleResult:

    snapshot = None

    if stage_requires_official_ingest(
        request.validated_stage
    ):
        snapshot = official_fetcher(
            request.game_code,
            request.current_round_number,
        )

        if snapshot.game_code != request.game_code:
            raise TournamentCycleBlocked(
                "official snapshot game_code mismatch"
            )

        if (
            snapshot.round_number
            != request.current_round_number
        ):
            raise TournamentCycleBlocked(
                "official snapshot round mismatch"
            )

        if snapshot.row_count <= 0:
            raise TournamentCycleBlocked(
                "zero-row official LIVE snapshot"
            )

    decision = decide_operator_action(
        stage=request.validated_stage,
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
