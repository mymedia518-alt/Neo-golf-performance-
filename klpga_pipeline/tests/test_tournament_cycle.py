from pathlib import Path

import pytest

from klpga.tournament_action_registry import (
    ActionAvailability,
    ActionBlocked,
    ActionResult,
    TournamentActionRegistry,
    no_change_runner,
)
from klpga.tournament_cycle import (
    CycleRequest,
    TournamentCycleBlocked,
    run_tournament_cycle,
    stage_requires_official_ingest,
)
from klpga.tournament_official_ingest import (
    OfficialPlayerRound,
    OfficialRoundSnapshot,
)
from klpga.tournament_operator import OperatorAction


def snapshot(game="FUTURE-GAME", rnd=2):
    return OfficialRoundSnapshot(
        game_code=game,
        round_number=rnd,
        players=(
            OfficialPlayerRound(
                player_id="1001",
                player_name="Player One",
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


def fetcher(calls, *, wrong_game=None, wrong_round=None):
    def _fetch(game, rnd):
        calls.append((game, rnd))
        return snapshot(
            game=wrong_game or game,
            rnd=wrong_round or rnd,
        )
    return _fetch


def registry_for(action):
    registry = TournamentActionRegistry()
    registry.register(
        action,
        no_change_runner(
            action,
            message="validated test runner",
        ),
    )
    return registry


def test_r2_live_fetches_exact_current_round():
    calls = []

    result = run_tournament_cycle(
        request=CycleRequest(
            game_code="YEAR-LATER-GAME",
            final_round_number=3,
            current_round_number=2,
            validated_stage="R2_LIVE",
            model_ready=False,
        ),
        official_fetcher=fetcher(calls),
        registry=registry_for(
            OperatorAction.RUN_R2
        ),
    )

    assert calls == [("YEAR-LATER-GAME", 2)]
    assert result.snapshot is not None
    assert result.snapshot.game_code == "YEAR-LATER-GAME"
    assert result.snapshot.round_number == 2
    assert result.decision.action == OperatorAction.RUN_R2


def test_live_snapshot_game_mismatch_blocks():
    calls = []

    with pytest.raises(TournamentCycleBlocked):
        run_tournament_cycle(
            request=CycleRequest(
                game_code="RIGHT",
                final_round_number=3,
                current_round_number=2,
                validated_stage="R2_LIVE",
                model_ready=False,
            ),
            official_fetcher=fetcher(
                calls,
                wrong_game="WRONG",
            ),
            registry=registry_for(
                OperatorAction.RUN_R2
            ),
        )

    assert calls == [("RIGHT", 2)]


def test_live_snapshot_round_mismatch_blocks():
    calls = []

    with pytest.raises(TournamentCycleBlocked):
        run_tournament_cycle(
            request=CycleRequest(
                game_code="GAME",
                final_round_number=3,
                current_round_number=2,
                validated_stage="R2_LIVE",
                model_ready=False,
            ),
            official_fetcher=fetcher(
                calls,
                wrong_round=1,
            ),
            registry=registry_for(
                OperatorAction.RUN_R2
            ),
        )

    assert calls == [("GAME", 2)]


def test_cut_confirmed_54_hole_does_not_fetch():
    calls = []

    def forbidden(game, rnd):
        calls.append((game, rnd))
        raise AssertionError(
            "CUT_CONFIRMED must not fetch official"
        )

    result = run_tournament_cycle(
        request=CycleRequest(
            game_code="GAME54",
            final_round_number=3,
            current_round_number=2,
            validated_stage="CUT_CONFIRMED",
            model_ready=False,
        ),
        official_fetcher=forbidden,
        registry=registry_for(
            OperatorAction.RUN_FINAL
        ),
    )

    assert calls == []
    assert result.snapshot is None
    assert result.decision.action == OperatorAction.RUN_FINAL
    assert result.decision.publish_factual is True
    assert result.decision.publish_model is False


def test_cut_confirmed_72_hole_does_not_fetch():
    calls = []

    def forbidden(game, rnd):
        calls.append((game, rnd))
        raise AssertionError(
            "CUT_CONFIRMED must not fetch official"
        )

    result = run_tournament_cycle(
        request=CycleRequest(
            game_code="GAME72",
            final_round_number=4,
            current_round_number=2,
            validated_stage="CUT_CONFIRMED",
            model_ready=True,
        ),
        official_fetcher=forbidden,
        registry=registry_for(
            OperatorAction.RUN_NEXT_ROUND
        ),
    )

    assert calls == []
    assert result.snapshot is None
    assert result.decision.action == OperatorAction.RUN_NEXT_ROUND


def test_five_round_format_generic():
    calls = []

    def forbidden(game, rnd):
        calls.append((game, rnd))
        raise AssertionError(
            "completed intermediate stage must not fetch"
        )

    result = run_tournament_cycle(
        request=CycleRequest(
            game_code="FIVE-ROUND-GAME",
            final_round_number=5,
            current_round_number=3,
            validated_stage="NEXT_ROUND_COMPLETE",
            model_ready=False,
        ),
        official_fetcher=forbidden,
        registry=registry_for(
            OperatorAction.RUN_NEXT_ROUND
        ),
    )

    assert calls == []
    assert result.snapshot is None
    assert result.decision.action == OperatorAction.RUN_NEXT_ROUND


def test_r2_complete_network_independent():
    calls = []

    def forbidden(game, rnd):
        calls.append((game, rnd))
        raise AssertionError(
            "R2_COMPLETE must not fetch official"
        )

    result = run_tournament_cycle(
        request=CycleRequest(
            game_code="ANY-GAME",
            final_round_number=4,
            current_round_number=2,
            validated_stage="R2_COMPLETE",
            model_ready=False,
        ),
        official_fetcher=forbidden,
        registry=registry_for(
            OperatorAction.CONFIRM_CUT
        ),
    )

    assert calls == []
    assert result.snapshot is None
    assert result.decision.action == OperatorAction.CONFIRM_CUT


def test_wait_needs_no_runner_and_no_fetch():
    calls = []

    def forbidden(game, rnd):
        calls.append((game, rnd))
        raise AssertionError(
            "DISCOVERED must not fetch"
        )

    result = run_tournament_cycle(
        request=CycleRequest(
            game_code="WAIT-GAME",
            final_round_number=4,
            current_round_number=1,
            validated_stage="DISCOVERED",
            model_ready=False,
        ),
        official_fetcher=forbidden,
        registry=TournamentActionRegistry(),
    )

    assert calls == []
    assert result.snapshot is None
    assert result.decision.action == OperatorAction.WAIT
    assert result.action_result.availability == ActionAvailability.WAIT


def test_missing_live_runner_fail_closed():
    calls = []

    with pytest.raises(ActionBlocked):
        run_tournament_cycle(
            request=CycleRequest(
                game_code="GAME",
                final_round_number=3,
                current_round_number=2,
                validated_stage="R2_LIVE",
                model_ready=False,
            ),
            official_fetcher=fetcher(calls),
            registry=TournamentActionRegistry(),
        )

    assert calls == [("GAME", 2)]


@pytest.mark.parametrize(
    "stage,expected",
    [
        ("R1_LIVE", True),
        ("R2_LIVE", True),
        ("NEXT_ROUND_LIVE", True),
        ("R3_LIVE", True),
        ("FINAL_LIVE", True),
        ("DISCOVERED", False),
        ("ENTRY_READY", False),
        ("PRE_READY", False),
        ("R1_COMPLETE", False),
        ("R2_COMPLETE", False),
        ("CUT_CONFIRMED", False),
        ("NEXT_ROUND_COMPLETE", False),
        ("FINAL_COMPLETE", False),
        ("POST_EVALUATED", False),
    ],
)
def test_stage_ingest_contract(stage, expected):
    assert stage_requires_official_ingest(stage) is expected
