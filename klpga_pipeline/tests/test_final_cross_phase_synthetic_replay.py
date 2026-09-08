"""FINAL CROSS-PHASE VALIDATION: synthetic 3-round and 4-round lifecycle
replays proving the exact stage->action sequence a real tournament of
each shape walks through, using the same already-tested generic engine
every real tournament uses (klpga.tournament_operator.decide_operator_action
via klpga.tournament_cycle.run_tournament_cycle) -- no per-game_code
branching anywhere in this path.

These are deliberately independent of test_phase3_r1_r2_lifecycle.py /
test_phase4_cut_contract.py / test_4round_tournament_replay.py, which
already prove individual transitions are inferred correctly from real
on-disk artifacts (RoundFacts/CutValidation/PostEvaluated) -- this file
proves the ORDERED, END-TO-END action sequence the operator dispatches
across an entire tournament of each shape, plus the terminal historical
manifest handoff after POST_EVALUATE.

For a 3-round event, round 3 IS the final round: CUT_CONFIRMED dispatches
straight to RUN_FINAL/FINAL_LIVE/FINAL_COMPLETE -- there is no separate
"R3" stage distinct from FINAL for a 3-round tournament (that is the
correct, already-tested behavior, not a gap). A 4-round event instead
inserts NEXT_ROUND_LIVE/NEXT_ROUND_COMPLETE (round 3) between
CUT_CONFIRMED and FINAL_LIVE/FINAL_COMPLETE (round 4).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_action_registry import ActionAvailability, ActionResult, TournamentActionRegistry  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_cycle import CycleRequest, run_tournament_cycle  # noqa: E402
from klpga.tournament_historical_manifest import write_historical_manifest_if_absent  # noqa: E402
from klpga.tournament_official_ingest import OfficialRoundSnapshot  # noqa: E402
from klpga.tournament_operator import OperatorAction  # noqa: E402
from klpga.tournament_postmortem import run_postmortem  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_tournament_replay", ROOT / "scripts" / "run_tournament.py")
run_tournament = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_tournament)


def _stub_registry(seen: list[OperatorAction]) -> TournamentActionRegistry:
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


def _dispatch(stage: str, *, final_round_number: int, current_round_number: int, seen: list[OperatorAction]):
    request = CycleRequest(
        game_code="FIXTUREREPLAY", final_round_number=final_round_number,
        current_round_number=current_round_number, validated_stage=stage, model_ready=False,
    )

    def official_fetcher(game_code, round_number):
        # LIVE stages (R1_LIVE/R2_LIVE/NEXT_ROUND_LIVE/FINAL_LIVE) fetch
        # official data before dispatch (see tournament_cycle's own
        # module docstring / test_run_tournament.py) -- any real
        # OfficialRoundSnapshot suffices here since this test's focus
        # is the dispatched ACTION, not fetch-gating itself (already
        # covered by test_run_tournament.py).
        return OfficialRoundSnapshot(game_code=game_code, round_number=round_number, players=(object(),))

    run_tournament_cycle(request, official_fetcher=official_fetcher, registry=_stub_registry(seen))


def test_3round_synthetic_replay_exact_action_sequence():
    """DISCOVERY -> ENTRY -> PRE -> R1 -> R2 -> CUT -> FINAL -> POSTMORTEM,
    exactly, for a 3-round event where round 3 IS the final round."""
    stage_sequence = [
        ("DISCOVERED", 1), ("ENTRY_READY", 1), ("PRE_READY", 1),
        ("R1_LIVE", 1), ("R1_COMPLETE", 1),
        ("R2_LIVE", 2), ("R2_COMPLETE", 2),
        ("CUT_CONFIRMED", 2),
        ("FINAL_LIVE", 3), ("FINAL_COMPLETE", 3),
        ("POST_EVALUATED", 3),
    ]
    expected_actions = [
        None,  # DISCOVERED -> WAIT (no runner ever dispatched)
        OperatorAction.PREPARE_PRE,
        OperatorAction.RUN_R1,
        OperatorAction.RUN_R1,
        OperatorAction.CLOSE_R1,
        OperatorAction.RUN_R2,
        OperatorAction.CONFIRM_CUT,
        OperatorAction.RUN_FINAL,  # cut confirmed; round 3 IS final for a 3-round event
        OperatorAction.RUN_FINAL,
        OperatorAction.CLOSE_FINAL,
        OperatorAction.POST_EVALUATE,
    ]
    for (stage, current_round), expected in zip(stage_sequence, expected_actions):
        seen: list[OperatorAction] = []
        _dispatch(stage, final_round_number=3, current_round_number=current_round, seen=seen)
        assert seen == ([] if expected is None else [expected]), f"stage={stage}: expected {expected}, dispatched {seen}"


def test_4round_synthetic_replay_exact_action_sequence():
    """DISCOVERY -> ENTRY -> PRE -> R1 -> R2 -> CUT -> R3 (intermediate,
    NEXT_ROUND_*) -> R4/FINAL -> POSTMORTEM, exactly, for a 4-round event
    where round 4 is the final round and round 3 is a real intermediate
    round distinct from FINAL (unlike the 3-round case above)."""
    stage_sequence = [
        ("DISCOVERED", 1), ("ENTRY_READY", 1), ("PRE_READY", 1),
        ("R1_LIVE", 1), ("R1_COMPLETE", 1),
        ("R2_LIVE", 2), ("R2_COMPLETE", 2),
        ("CUT_CONFIRMED", 2),
        ("NEXT_ROUND_LIVE", 3), ("NEXT_ROUND_COMPLETE", 3),
        ("FINAL_LIVE", 4), ("FINAL_COMPLETE", 4),
        ("POST_EVALUATED", 4),
    ]
    expected_actions = [
        None,
        OperatorAction.PREPARE_PRE,
        OperatorAction.RUN_R1,
        OperatorAction.RUN_R1,
        OperatorAction.CLOSE_R1,
        OperatorAction.RUN_R2,
        OperatorAction.CONFIRM_CUT,
        OperatorAction.RUN_NEXT_ROUND,  # cut confirmed; round 3 is intermediate, not final, for a 4-round event
        OperatorAction.RUN_NEXT_ROUND,  # round 3 still live
        OperatorAction.RUN_FINAL,       # round 3 complete, current+1 (4) >= final (4) -> final follows
        OperatorAction.RUN_FINAL,
        OperatorAction.CLOSE_FINAL,
        OperatorAction.POST_EVALUATE,
    ]
    for (stage, current_round), expected in zip(stage_sequence, expected_actions):
        seen: list[OperatorAction] = []
        _dispatch(stage, final_round_number=4, current_round_number=current_round, seen=seen)
        assert seen == ([] if expected is None else [expected]), f"stage={stage}: expected {expected}, dispatched {seen}"


IDENTITY = {
    "game_code": "FIXTUREREPLAY", "tournament_name": "Fixture Replay Open", "season": 2027,
    "start_date": "2027-09-01", "end_date": "2027-09-04", "final_round_number": 3, "current_round_number": 3,
}
REGISTRY = {
    "FIXTUREREPLAY": {
        "url_base": "/tournaments/2027/fixture-replay-open/",
        "stage_state_filename": "FIXTURE_REPLAY_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "final"],
    }
}
FIELD = [f"P{i}" for i in range(1, 6)]


def test_terminal_historical_manifest_follows_post_evaluate(tmp_path, monkeypatch):
    """After POST_EVALUATE genuinely runs (real postmortem_report written),
    the historical terminal manifest step must complete too -- the last
    link in the DISCOVERY->...->POSTMORTEM->HISTORICAL MANIFEST chain,
    already unit-tested piece by piece in
    test_phase5_final_postmortem_handoff.py; this closes the loop by
    running it against this file's own synthetic 3-round context."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = resolve_context(IDENTITY, REGISTRY)
    (tmp_path / "FIXTUREREPLAY_R3_LIVE_SNAPSHOT.json").write_text(json.dumps({"player_table": [
        {"player_id": p, "holes_completed": 18, "status": None, "rank_display": ("1" if p == "P1" else "2")}
        for p in FIELD
    ]}), encoding="utf-8")
    (tmp_path / "FIXTUREREPLAY_PRE_WIN_FORECAST.json").write_text(json.dumps({
        "records": [{"player_id": p, "win_probability": 1 / len(FIELD)} for p in FIELD],
    }), encoding="utf-8")
    (tmp_path / "FIXTUREREPLAY_ENTRY_SNAPSHOT.json").write_text(json.dumps({
        "entries": [{"player_id": p} for p in FIELD],
    }), encoding="utf-8")

    run_postmortem(context)
    manifest_path, written = write_historical_manifest_if_absent(context)
    assert written is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["postmortem_report"]["present"] is True
    assert manifest["final_snapshot"]["present"] is True
    real_hash = hashlib.sha256((tmp_path / "FIXTUREREPLAY_R3_LIVE_SNAPSHOT.json").read_bytes()).hexdigest()
    assert manifest["final_snapshot"]["sha256"] == real_hash


def test_a_brand_new_synthetic_game_code_needs_no_source_edit_to_replay():
    """The two stage-sequence tests above use game_code=FIXTUREREPLAY, a
    game_code that has never existed anywhere in this repository's
    source before this test file was written -- proving (again, at the
    full-lifecycle level rather than one function at a time) that a
    genuinely new tournament needs zero source edits to run through the
    real generic engine."""
    import subprocess
    result = subprocess.run(
        ["git", "grep", "-l", "FIXTUREREPLAY", "--", "src/", "scripts/"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        "FIXTUREREPLAY must not appear anywhere in operational source (src/ or scripts/) -- "
        "only in this test file"
    )
