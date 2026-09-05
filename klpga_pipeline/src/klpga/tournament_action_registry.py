"""Fail-closed action registry for the NEO Tournament Engine.

The registry is intentionally tournament-independent.
Legacy event-specific scripts are never selected implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping

from klpga.tournament_operator import (
    OperatorAction,
    OperatorDecision,
)


class ActionAvailability(str, Enum):
    READY = "READY"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"


class ActionBlocked(RuntimeError):
    """Raised when no validated generic action implementation exists."""


@dataclass(frozen=True)
class ActionContext:
    game_code: str
    final_round_number: int
    current_round_number: int | None = None

    def __post_init__(self) -> None:
        if not self.game_code.strip():
            raise ValueError("game_code required")

        if self.final_round_number < 2:
            raise ValueError(
                "final_round_number must be >= 2"
            )

        if self.current_round_number is not None:
            if not (
                1
                <= self.current_round_number
                <= self.final_round_number
            ):
                raise ValueError(
                    "invalid current_round_number"
                )


@dataclass(frozen=True)
class ActionResult:
    action: OperatorAction
    availability: ActionAvailability
    changed: bool
    message: str


ActionRunner = Callable[
    [ActionContext, OperatorDecision],
    ActionResult,
]


class TournamentActionRegistry:
    """Explicit registry of validated generic action runners."""

    def __init__(
        self,
        runners: Mapping[
            OperatorAction,
            ActionRunner,
        ] | None = None,
    ) -> None:
        self._runners = dict(runners or {})

    def register(
        self,
        action: OperatorAction,
        runner: ActionRunner,
    ) -> None:
        if action in self._runners:
            raise ValueError(
                f"runner already registered: {action.value}"
            )

        self._runners[action] = runner

    def has_runner(
        self,
        action: OperatorAction,
    ) -> bool:
        return action in self._runners

    def execute(
        self,
        context: ActionContext,
        decision: OperatorDecision,
    ) -> ActionResult:
        if decision.action == OperatorAction.WAIT:
            return ActionResult(
                action=decision.action,
                availability=ActionAvailability.WAIT,
                changed=False,
                message=decision.reason,
            )

        runner = self._runners.get(decision.action)

        if runner is None:
            raise ActionBlocked(
                "no validated generic runner for "
                f"{decision.action.value}; "
                "legacy tournament-specific scripts "
                "must not be selected implicitly"
            )

        result = runner(context, decision)

        if result.action != decision.action:
            raise ValueError(
                "action runner returned mismatched action"
            )

        return result


def no_change_runner(
    action: OperatorAction,
    *,
    message: str,
) -> ActionRunner:
    """Create an explicit safe runner used for validated no-op stages."""

    def _run(
        context: ActionContext,
        decision: OperatorDecision,
    ) -> ActionResult:
        del context

        if decision.action != action:
            raise ValueError(
                "runner invoked for wrong action"
            )

        return ActionResult(
            action=action,
            availability=ActionAvailability.READY,
            changed=False,
            message=message,
        )

    return _run
