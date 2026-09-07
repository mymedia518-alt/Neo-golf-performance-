"""NEO TOURNAMENT PIPELINE item 5: run_tournament.py must dispatch
through the real, already-tested klpga.tournament_cycle.run_tournament_cycle
-- these tests exercise that wiring with a stub official_fetcher and
stub action runners (no network, no subprocess), proving the decision
routing itself is correct without needing a live klpga.co.kr fetch."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

spec = importlib.util.spec_from_file_location("run_tournament", Path(__file__).parents[1] / "scripts" / "run_tournament.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

from klpga.tournament_action_registry import ActionAvailability, ActionResult, TournamentActionRegistry  # noqa: E402
from klpga.tournament_cycle import CycleRequest, run_tournament_cycle  # noqa: E402
from klpga.tournament_official_ingest import OfficialRoundSnapshot  # noqa: E402
from klpga.tournament_operator import OperatorAction  # noqa: E402


def test_every_reachable_action_has_a_registered_runner():
    registry = module.build_registry()
    for action in OperatorAction:
        if action is OperatorAction.WAIT:
            continue  # WAIT is handled by the registry itself, never a runner
        assert registry.has_runner(action), f"{action.value} has no registered runner"


def _stub_registry(seen):
    registry = TournamentActionRegistry()
    for action in OperatorAction:
        if action is OperatorAction.WAIT:
            continue

        def _make(action=action):
            def _run(context, decision):
                seen.append(action)
                return ActionResult(action=action, availability=ActionAvailability.READY, changed=True, message="stub")
            return _run

        registry.register(action, _make())
    return registry


def test_pre_ready_dispatches_run_r1_without_touching_network():
    seen = []
    request = CycleRequest(
        game_code="TEST0001", final_round_number=3, current_round_number=1,
        validated_stage="PRE_READY", model_ready=False,
    )

    def official_fetcher(game_code, round_number):
        raise AssertionError("official_fetcher must not be called for a non-LIVE stage")

    result = run_tournament_cycle(request, official_fetcher=official_fetcher, registry=_stub_registry(seen))
    assert seen == [OperatorAction.RUN_R1]
    assert result.decision.action == OperatorAction.RUN_R1


def test_r1_live_calls_official_fetcher_before_dispatch():
    seen = []
    request = CycleRequest(
        game_code="TEST0001", final_round_number=3, current_round_number=1,
        validated_stage="R1_LIVE", model_ready=False,
    )
    calls = []

    def official_fetcher(game_code, round_number):
        calls.append((game_code, round_number))
        return OfficialRoundSnapshot(game_code=game_code, round_number=round_number, players=(object(),))

    run_tournament_cycle(request, official_fetcher=official_fetcher, registry=_stub_registry(seen))
    assert calls == [("TEST0001", 1)]
    assert seen == [OperatorAction.RUN_R1]


def test_wait_stage_never_needs_a_runner():
    seen = []
    request = CycleRequest(
        game_code="TEST0001", final_round_number=3, current_round_number=1,
        validated_stage="DISCOVERED", model_ready=False,
    )

    def official_fetcher(game_code, round_number):
        raise AssertionError("must not fetch while WAITing")

    result = run_tournament_cycle(request, official_fetcher=official_fetcher, registry=_stub_registry(seen))
    assert seen == []
    assert result.action_result.availability.value == "WAIT"
