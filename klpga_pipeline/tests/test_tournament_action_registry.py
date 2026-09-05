import pytest

from klpga.tournament_action_registry import (
    ActionAvailability,
    ActionBlocked,
    ActionContext,
    TournamentActionRegistry,
    no_change_runner,
)
from klpga.tournament_engine import Stage
from klpga.tournament_operator import (
    OperatorAction,
    OperatorDecision,
)


def decision(action):
    return OperatorDecision(
        stage=Stage.CUT_CONFIRMED,
        action=action,
        publish_factual=True,
        publish_model=False,
        reason="test",
    )


def context(game_code="FUTURE-2030-001"):
    return ActionContext(
        game_code=game_code,
        final_round_number=4,
        current_round_number=2,
    )


def test_missing_runner_is_fail_closed():
    registry = TournamentActionRegistry()

    with pytest.raises(ActionBlocked):
        registry.execute(
            context(),
            decision(OperatorAction.RUN_FINAL),
        )


def test_future_game_code_requires_no_code_change():
    registry = TournamentActionRegistry()

    registry.register(
        OperatorAction.RUN_FINAL,
        no_change_runner(
            OperatorAction.RUN_FINAL,
            message="generic final runner",
        ),
    )

    result = registry.execute(
        context("SOME-NEW-EVENT-2040"),
        decision(OperatorAction.RUN_FINAL),
    )

    assert result.availability == ActionAvailability.READY
    assert result.changed is False


def test_wait_needs_no_runner():
    registry = TournamentActionRegistry()

    d = OperatorDecision(
        stage=Stage.DISCOVERED,
        action=OperatorAction.WAIT,
        publish_factual=False,
        publish_model=False,
        reason="official state incomplete",
    )

    result = registry.execute(
        context(),
        d,
    )

    assert result.availability == ActionAvailability.WAIT
    assert result.changed is False


def test_duplicate_registration_is_rejected():
    registry = TournamentActionRegistry()

    runner = no_change_runner(
        OperatorAction.RUN_R2,
        message="r2",
    )

    registry.register(
        OperatorAction.RUN_R2,
        runner,
    )

    with pytest.raises(ValueError):
        registry.register(
            OperatorAction.RUN_R2,
            runner,
        )


def test_runner_cannot_return_different_action():
    registry = TournamentActionRegistry()

    def bad_runner(context, decision):
        from klpga.tournament_action_registry import (
            ActionResult,
        )

        return ActionResult(
            action=OperatorAction.RUN_R1,
            availability=ActionAvailability.READY,
            changed=False,
            message="bad",
        )

    registry.register(
        OperatorAction.RUN_FINAL,
        bad_runner,
    )

    with pytest.raises(ValueError):
        registry.execute(
            context(),
            decision(OperatorAction.RUN_FINAL),
        )
