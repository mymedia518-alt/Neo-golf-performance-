"""Generic NEO Tournament Operator.

This module selects work from validated tournament state.
Tournament names and game codes are data, never control flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from klpga.tournament_engine import Stage


class OperatorAction(str, Enum):
    WAIT = "WAIT"
    PREPARE_PRE = "PREPARE_PRE"
    RUN_R1 = "RUN_R1"
    CLOSE_R1 = "CLOSE_R1"
    RUN_R2 = "RUN_R2"
    CONFIRM_CUT = "CONFIRM_CUT"
    RUN_NEXT_ROUND = "RUN_NEXT_ROUND"
    RUN_FINAL = "RUN_FINAL"
    CLOSE_FINAL = "CLOSE_FINAL"
    POST_EVALUATE = "POST_EVALUATE"


@dataclass(frozen=True)
class OperatorDecision:
    stage: Stage
    action: OperatorAction
    publish_factual: bool
    publish_model: bool
    reason: str


def decide_operator_action(
    stage: Stage,
    *,
    final_round_number: int,
    current_round_number: int | None = None,
    model_ready: bool = False,
) -> OperatorDecision:
    """Map validated state to one generic operational action."""

    if final_round_number < 2:
        raise ValueError(
            "final_round_number must be >= 2"
        )

    if current_round_number is not None:
        if current_round_number < 1:
            raise ValueError(
                "current_round_number must be >= 1"
            )

        if current_round_number > final_round_number:
            raise ValueError(
                "current_round_number exceeds final round"
            )

    if stage == Stage.DISCOVERED:
        return OperatorDecision(
            stage,
            OperatorAction.WAIT,
            False,
            False,
            "entry not yet validated",
        )

    if stage == Stage.ENTRY_READY:
        return OperatorDecision(
            stage,
            OperatorAction.PREPARE_PRE,
            False,
            False,
            "entry validated",
        )

    if stage == Stage.PRE_READY:
        return OperatorDecision(
            stage,
            OperatorAction.RUN_R1,
            True,
            False,
            "PRE frozen; wait for official R1 facts",
        )

    if stage == Stage.R1_LIVE:
        return OperatorDecision(
            stage,
            OperatorAction.RUN_R1,
            True,
            False,
            "R1 official facts are live",
        )

    if stage == Stage.R1_COMPLETE:
        return OperatorDecision(
            stage,
            OperatorAction.CLOSE_R1,
            True,
            False,
            "R1 validated complete",
        )

    if stage == Stage.R2_LIVE:
        return OperatorDecision(
            stage,
            OperatorAction.RUN_R2,
            True,
            False,
            "R2 official facts are live",
        )

    if stage == Stage.R2_COMPLETE:
        return OperatorDecision(
            stage,
            OperatorAction.CONFIRM_CUT,
            True,
            False,
            "R2 complete; cut requires explicit validation",
        )

    if stage == Stage.CUT_CONFIRMED:
        if final_round_number == 3:
            action = OperatorAction.RUN_FINAL
            reason = "cut confirmed; next round is final"
        else:
            action = OperatorAction.RUN_NEXT_ROUND
            reason = "cut confirmed; intermediate round follows"

        return OperatorDecision(
            stage,
            action,
            True,
            model_ready,
            reason,
        )

    if stage in {
        Stage.NEXT_ROUND_LIVE,
        Stage.NEXT_ROUND_COMPLETE,
    }:
        if (
            current_round_number is not None
            and current_round_number + 1
            >= final_round_number
            and stage == Stage.NEXT_ROUND_COMPLETE
        ):
            action = OperatorAction.RUN_FINAL
            reason = "intermediate round complete; final follows"
        else:
            action = OperatorAction.RUN_NEXT_ROUND
            reason = "intermediate tournament round"

        return OperatorDecision(
            stage,
            action,
            True,
            model_ready and stage == Stage.NEXT_ROUND_COMPLETE,
            reason,
        )

    if stage == Stage.FINAL_LIVE:
        return OperatorDecision(
            stage,
            OperatorAction.RUN_FINAL,
            True,
            False,
            "official final round is live",
        )

    if stage == Stage.FINAL_COMPLETE:
        return OperatorDecision(
            stage,
            OperatorAction.CLOSE_FINAL,
            True,
            False,
            "official final validated complete",
        )

    if stage == Stage.POST_EVALUATED:
        return OperatorDecision(
            stage,
            OperatorAction.POST_EVALUATE,
            True,
            False,
            "post-event evaluation complete",
        )

    raise ValueError(
        f"unsupported stage: {stage}"
    )
