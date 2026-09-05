from types import SimpleNamespace

import pytest

from klpga.tournament_action_registry import (
    ActionAvailability,
    TournamentActionRegistry,
    no_change_runner,
)
from klpga.tournament_cycle import (
    CycleRequest,
    run_tournament_cycle,
)
from klpga.tournament_engine import Stage
from klpga.tournament_official_ingest import (
    OfficialPlayerRound,
    OfficialRoundSnapshot,
)
from klpga.tournament_operator import OperatorAction


def snapshot(game_code, round_number):
    return OfficialRoundSnapshot(
        game_code=game_code,
        round_number=round_number,
        players=(
            OfficialPlayerRound(
                player_id="1",
                player_name="Player",
                rank_display="1",
                status="ACTIVE",
                raw_inghole=18,
                holes_completed=18,
                holes_completed_display="18H",
                starting_tee_assumed=False,
                today_under_par_display="-3",
                total_under_par_display="-7",
            ),
        ),
    )


def fetcher(game_code, round_number):
    return snapshot(
        game_code,
        round_number,
    )


def registry_for(action):
    registry = TournamentActionRegistry()
    registry.register(
        action,
        no_change_runner(
            action,
            message="generic runner",
        ),
    )
    return registry


def test_54_hole_cut_routes_to_final():
    req = CycleRequest(
        game_code="FUTURE-54",
        final_round_number=3,
        current_round_number=2,
        validated_stage=Stage.CUT_CONFIRMED,
        model_ready=False,
    )

    result = run_tournament_cycle(
        request=req,
        official_fetcher=fetcher,
        registry=registry_for(
            OperatorAction.RUN_FINAL
        ),
    )

    assert result.decision.action == OperatorAction.RUN_FINAL
    assert result.decision.publish_factual is True
    assert result.decision.publish_model is False
    assert (
        result.action_result.availability
        == ActionAvailability.READY
    )


def test_72_hole_cut_routes_to_next_round():
    req = CycleRequest(
        game_code="FUTURE-72",
        final_round_number=4,
        current_round_number=2,
        validated_stage=Stage.CUT_CONFIRMED,
        model_ready=True,
    )

    result = run_tournament_cycle(
        request=req,
        official_fetcher=fetcher,
        registry=registry_for(
            OperatorAction.RUN_NEXT_ROUND
        ),
    )

    assert (
        result.decision.action
        == OperatorAction.RUN_NEXT_ROUND
    )
    assert result.decision.publish_model is True


def test_five_round_format_is_not_hardcoded():
    req = CycleRequest(
        game_code="FUTURE-5R",
        final_round_number=5,
        current_round_number=3,
        validated_stage=Stage.NEXT_ROUND_LIVE,
    )

    result = run_tournament_cycle(
        request=req,
        official_fetcher=fetcher,
        registry=registry_for(
            OperatorAction.RUN_NEXT_ROUND
        ),
    )

    assert (
        result.decision.action
        == OperatorAction.RUN_NEXT_ROUND
    )


def test_snapshot_game_code_mismatch_blocks():
    req = CycleRequest(
        game_code="EVENT-A",
        final_round_number=3,
        current_round_number=2,
        validated_stage=Stage.R2_LIVE,
    )

    def wrong_fetcher(game_code, round_number):
        return snapshot(
            "EVENT-B",
            round_number,
        )

    with pytest.raises(ValueError):
        run_tournament_cycle(
            request=req,
            official_fetcher=wrong_fetcher,
            registry=TournamentActionRegistry(),
        )


def test_snapshot_round_mismatch_blocks():
    req = CycleRequest(
        game_code="EVENT-A",
        final_round_number=4,
        current_round_number=2,
        validated_stage=Stage.R2_LIVE,
    )

    def wrong_fetcher(game_code, round_number):
        return snapshot(
            game_code,
            3,
        )

    with pytest.raises(ValueError):
        run_tournament_cycle(
            request=req,
            official_fetcher=wrong_fetcher,
            registry=TournamentActionRegistry(),
        )


def test_missing_generic_runner_remains_fail_closed():
    req = CycleRequest(
        game_code="FUTURE-NO-RUNNER",
        final_round_number=3,
        current_round_number=2,
        validated_stage=Stage.CUT_CONFIRMED,
    )

    from klpga.tournament_action_registry import ActionBlocked

    with pytest.raises(ActionBlocked):
        run_tournament_cycle(
            request=req,
            official_fetcher=fetcher,
            registry=TournamentActionRegistry(),
        )


def test_wait_does_not_need_registered_runner():
    req = CycleRequest(
        game_code="WAIT-EVENT",
        final_round_number=3,
        current_round_number=1,
        validated_stage=Stage.DISCOVERED,
    )

    result = run_tournament_cycle(
        request=req,
        official_fetcher=fetcher,
        registry=TournamentActionRegistry(),
    )

    assert result.decision.action == OperatorAction.WAIT
    assert (
        result.action_result.availability
        == ActionAvailability.WAIT
    )
