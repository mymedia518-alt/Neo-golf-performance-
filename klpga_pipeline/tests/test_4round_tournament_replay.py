"""NEO TOURNAMENT PIPELINE Phase 2 item 7: a full 4-round tournament
replay, end to end through the exact same generic pipeline the real 3-
round OK Open/KG Ladies Open use (klpga.tournament_lifecycle ->
tournament_runtime -> tournament_operator -> tournament_cycle ->
run_tournament.py's registry), proving nothing in the forward pipeline
silently assumes "3 rounds". No repository has a real archived 4-round
KLPGA event, so this is a synthetic fixture tournament (never a real
game_code) -- but every artifact shape (player_table/holes_completed/
status, PRE win_forecast records) is the exact real shape the live
scripts already read and write, and every generic pipeline function
(resolve_lifecycle, decide_operator_action, run_postmortem) is the same
already-tested one the real tournaments use."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_lifecycle import resolve_lifecycle  # noqa: E402
from klpga.tournament_operator import OperatorAction, decide_operator_action  # noqa: E402
from klpga.tournament_postmortem import run_postmortem  # noqa: E402

spec = importlib.util.spec_from_file_location("run_tournament", Path(__file__).parents[1] / "scripts" / "run_tournament.py")
run_tournament = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_tournament)

IDENTITY = {
    "game_code": "FIXTURE4R01",
    "tournament_name": "Fixture 4-Round Championship",
    "season": 2027,
    "start_date": "2027-05-01",
    "end_date": "2027-05-04",
    "final_round_number": 4,
    "current_round_number": 1,
}
REGISTRY = {
    "FIXTURE4R01": {
        "url_base": "/tournaments/2027/fixture-4round-championship/",
        "stage_state_filename": "FIXTURE_4R_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "r4", "final"],
    }
}
FIELD = [f"P{i}" for i in range(1, 41)]  # 40-player synthetic field


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def _round_snapshot(players_complete: list[str], players_incomplete: list[str] | None = None):
    incomplete = set(players_incomplete or [])
    return {"player_table": [
        {"player_id": p, "holes_completed": (10 if p in incomplete else 18), "status": None}
        for p in players_complete
    ]}


def test_4round_tournament_never_reaches_final_after_only_r2_complete(tmp_path, monkeypatch):
    """The exact bug a 3-round-only assumption would cause: after the
    cut (round 2 complete), a 4-round tournament's next action must be
    RUN_NEXT_ROUND (round 3), never RUN_FINAL -- round 4 is final here,
    not round 3."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTURE4R01_ENTRY_SNAPSHOT.json", {"records": [{"player_id": p} for p in FIELD]})
    _write(tmp_path, "FIXTURE4R01_PRE_WIN_FORECAST.json", {"records": [{"player_id": p, "win_probability": 1 / len(FIELD)} for p in FIELD]})
    _write(tmp_path, "FIXTURE4R01_R1_LIVE_SNAPSHOT.json", _round_snapshot(FIELD))
    _write(tmp_path, "FIXTURE4R01_R2_LIVE_SNAPSHOT.json", _round_snapshot(FIELD[:24]))  # cut field
    _write(tmp_path, "FIXTURE4R01_POST_R2_INPUT.json", {"records": [{"player_id": p} for p in FIELD[:24]]})

    lifecycle = {"game_code": "FIXTURE4R01", "cut_after_round": 2, "model_ready": False}
    snapshot = resolve_lifecycle(context, lifecycle)
    assert snapshot.stage == "CUT_CONFIRMED"

    decision = decide_operator_action(
        stage=snapshot.stage, final_round_number=context.final_round_number,
        current_round_number=snapshot.current_round_number, model_ready=snapshot.model_ready,
    )
    assert decision.action == OperatorAction.RUN_NEXT_ROUND, (
        "a 4-round tournament must run an intermediate round after the cut, not jump to FINAL"
    )


def test_4round_tournament_reaches_final_only_after_round3_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTURE4R01_ENTRY_SNAPSHOT.json", {"records": [{"player_id": p} for p in FIELD]})
    _write(tmp_path, "FIXTURE4R01_PRE_WIN_FORECAST.json", {"records": [{"player_id": p, "win_probability": 1 / len(FIELD)} for p in FIELD]})
    _write(tmp_path, "FIXTURE4R01_R1_LIVE_SNAPSHOT.json", _round_snapshot(FIELD))
    _write(tmp_path, "FIXTURE4R01_R2_LIVE_SNAPSHOT.json", _round_snapshot(FIELD[:24]))
    _write(tmp_path, "FIXTURE4R01_POST_R2_INPUT.json", {"records": [{"player_id": p} for p in FIELD[:24]]})
    _write(tmp_path, "FIXTURE4R01_R3_LIVE_SNAPSHOT.json", _round_snapshot(FIELD[:24]))

    lifecycle = {"game_code": "FIXTURE4R01", "cut_after_round": 2, "model_ready": False}
    snapshot = resolve_lifecycle(context, lifecycle)
    assert snapshot.stage == "NEXT_ROUND_COMPLETE"
    assert snapshot.current_round_number == 3

    decision = decide_operator_action(
        stage=snapshot.stage, final_round_number=context.final_round_number,
        current_round_number=snapshot.current_round_number, model_ready=snapshot.model_ready,
    )
    assert decision.action == OperatorAction.RUN_FINAL


def test_4round_run_tournament_registry_dispatches_run_next_round_for_r3(tmp_path, monkeypatch):
    """run_tournament.py's own registry (the single entry point) must
    route a 4-round tournament's intermediate round through
    RUN_NEXT_ROUND -- proving the CLI wiring, not just the underlying
    engine, generalizes past 3 rounds."""
    from klpga.tournament_cycle import CycleRequest, run_tournament_cycle
    from klpga.tournament_action_registry import ActionAvailability, ActionResult, TournamentActionRegistry

    seen = []
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

    request = CycleRequest(
        game_code="FIXTURE4R01", final_round_number=4, current_round_number=3,
        validated_stage="CUT_CONFIRMED", model_ready=False,
    )

    def official_fetcher(game_code, round_number):
        raise AssertionError("CUT_CONFIRMED never requires a live official fetch")

    run_tournament_cycle(request, official_fetcher=official_fetcher, registry=registry)
    assert seen == [OperatorAction.RUN_NEXT_ROUND]


def test_4round_postmortem_evaluates_against_the_real_final_round_number(tmp_path, monkeypatch):
    """Postmortem must read r{final_round_number}_live_snapshot -- r4
    here, never a hardcoded r3 -- to find the real winner."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTURE4R01_PRE_WIN_FORECAST.json", {"records": [{"player_id": p, "win_probability": 1 / len(FIELD)} for p in FIELD]})
    snapshot = _round_snapshot(FIELD[:24])
    for row in snapshot["player_table"]:
        row["rank_display"] = "1" if row["player_id"] == "P1" else "2"
    _write(tmp_path, "FIXTURE4R01_R4_LIVE_SNAPSHOT.json", snapshot)

    result = run_postmortem(context)
    assert result.prediction.winner == "P1"
    assert result.winner_rank == 1
