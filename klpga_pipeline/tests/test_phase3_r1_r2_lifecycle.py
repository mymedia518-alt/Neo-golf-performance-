"""Phase 3 (fix/phase5-generic-pipeline-hardening): R1 -> R2 lifecycle
deadlock.

Reproduced bug: once round 1's real official data shows every player
finished, determine_stage() correctly returns Stage.R1_COMPLETE and the
operator correctly decides CLOSE_R1 -- but nothing in the generic
engine ever collects round 2's official data while the tournament
still sits at R1_COMPLETE (official ingest is intentionally gated to
already-LIVE stages only, see klpga.tournament_cycle's own module
docstring). Every subsequent cycle re-evaluates the exact same facts
and decides CLOSE_R1 again, forever: "First call: R1_COMPLETE /
CLOSE_R1. After close: R1_COMPLETE / CLOSE_R1."

This file has two independent halves:
  1. A synthetic, fixture-driven proof that the CORE engine (Stage /
     TournamentFacts / decide_operator_action) correctly advances to
     R2_LIVE/RUN_R2 the moment real round-2 evidence exists -- i.e.
     the deadlock is a pure orchestration gap (nothing ever produces
     that evidence), not a bug in the pure state machine itself.
  2. Direct tests of scripts/run_tournament.py's new _close_r1_runner(),
     which closes that gap by probing for round 2's official data
     immediately after attempting to close R1 out (mirroring the same
     pattern already used for CUT_CONFIRMED/NEXT_ROUND_COMPLETE via
     _promote_current_round), and treats a genuine "R2 not published
     yet" probe failure as an expected WAIT rather than a crash.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_action_registry import ActionContext  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_lifecycle import resolve_lifecycle  # noqa: E402
from klpga.tournament_operator import OperatorAction, decide_operator_action  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_tournament_phase3", ROOT / "scripts" / "run_tournament.py")
run_tournament = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_tournament)

IDENTITY = {
    "game_code": "FIXTURER1R2",
    "tournament_name": "Fixture R1R2 Deadlock Open",
    "season": 2027,
    "start_date": "2027-06-01",
    "end_date": "2027-06-03",
    "final_round_number": 3,
    "current_round_number": 1,
}
REGISTRY = {
    "FIXTURER1R2": {
        "url_base": "/tournaments/2027/fixture-r1r2-open/",
        "stage_state_filename": "FIXTURE_R1R2_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
}
FIELD = [f"P{i}" for i in range(1, 21)]


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def _round_snapshot(players_complete, players_incomplete=None):
    incomplete = set(players_incomplete or [])
    return {"player_table": [
        {"player_id": p, "holes_completed": (10 if p in incomplete else 18), "status": None}
        for p in players_complete
    ]}


def _decide(context, snapshot):
    return decide_operator_action(
        stage=snapshot.stage, final_round_number=context.final_round_number,
        current_round_number=snapshot.current_round_number, model_ready=snapshot.model_ready,
    )


# ---------------------------------------------------------------------------
# 1. Core engine: the loop breaks the moment real R2 evidence exists.
# ---------------------------------------------------------------------------

def test_r1_complete_deadlocks_on_close_r1_while_no_r2_evidence_exists(tmp_path, monkeypatch):
    """Reproduces the bug exactly: with R1 fully complete and no round-2
    snapshot at all, the cycle decides R1_COMPLETE/CLOSE_R1 -- and
    re-evaluating the SAME facts again (nothing collected R2 in
    between) decides the exact same thing again."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTURER1R2_ENTRY_SNAPSHOT.json", {"entries": [{"player_id": p} for p in FIELD], "player_count": len(FIELD)})
    _write(tmp_path, "FIXTURER1R2_R1_LIVE_SNAPSHOT.json", _round_snapshot(FIELD))

    lifecycle = {"game_code": "FIXTURER1R2", "cut_after_round": 2, "model_ready": False}
    snapshot = resolve_lifecycle(context, lifecycle)
    assert snapshot.stage == "R1_COMPLETE"
    decision = _decide(context, snapshot)
    assert decision.action == OperatorAction.CLOSE_R1

    # Re-evaluate again -- nothing changed on disk, so nothing should
    # have changed in the decision either. This IS the deadlock.
    snapshot_again = resolve_lifecycle(context, lifecycle)
    assert snapshot_again.stage == "R1_COMPLETE"
    decision_again = _decide(context, snapshot_again)
    assert decision_again.action == OperatorAction.CLOSE_R1


def test_r1_complete_advances_to_r2_live_once_round2_evidence_exists(tmp_path, monkeypatch):
    """The moment real round-2 official data actually gets collected
    (regardless of HOW), the very next cycle must move past
    R1_COMPLETE/CLOSE_R1 to R2_LIVE/RUN_R2, never back to CLOSE_R1."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTURER1R2_ENTRY_SNAPSHOT.json", {"entries": [{"player_id": p} for p in FIELD], "player_count": len(FIELD)})
    _write(tmp_path, "FIXTURER1R2_R1_LIVE_SNAPSHOT.json", _round_snapshot(FIELD))
    lifecycle = {"game_code": "FIXTURER1R2", "cut_after_round": 2, "model_ready": False}

    # Cycle 1: R1_COMPLETE / CLOSE_R1, as expected.
    snapshot = resolve_lifecycle(context, lifecycle)
    assert snapshot.stage == "R1_COMPLETE"
    assert _decide(context, snapshot).action == OperatorAction.CLOSE_R1

    # Simulate the CLOSE_R1 runner's R2 probe having succeeded: round 2
    # is genuinely live (some players still mid-round).
    _write(tmp_path, "FIXTURER1R2_R2_LIVE_SNAPSHOT.json", _round_snapshot(FIELD, players_incomplete=FIELD[:5]))

    # Cycle 2: must be R2_LIVE / RUN_R2 -- never CLOSE_R1 again.
    snapshot2 = resolve_lifecycle(context, lifecycle)
    assert snapshot2.stage == "R2_LIVE"
    decision2 = _decide(context, snapshot2)
    assert decision2.action == OperatorAction.RUN_R2
    assert decision2.action != OperatorAction.CLOSE_R1


# ---------------------------------------------------------------------------
# 2. Orchestration: _close_r1_runner() actually probes for R2.
# ---------------------------------------------------------------------------

def _fake_run_script_factory(*, close_summary, r2_raises):
    calls = []

    def _fake(*relative_path, extra_args=None):
        name = relative_path[0]
        calls.append(name)
        if name == "98_ok_open_r1_final_reconciliation.py":
            stdout = json.dumps(close_summary)
            return 0, stdout
        if name == "99_ok_open_r2_live_recovery.py":
            if r2_raises:
                raise subprocess.CalledProcessError(1, ["python", name])
            return 0, json.dumps({"status": "ok"})
        raise AssertionError(f"unexpected script invocation: {name}")

    return _fake, calls


def test_close_r1_runner_probes_r2_and_reports_changed_when_r2_arrives(monkeypatch):
    fake_run_script, calls = _fake_run_script_factory(
        close_summary={"action": "FINAL_RECONCILED"}, r2_raises=False,
    )
    monkeypatch.setattr(run_tournament, "_run_script", fake_run_script)
    runner = run_tournament._close_r1_runner()
    context = ActionContext(game_code="FIXTURER1R2", final_round_number=3, current_round_number=1, live=True)
    from klpga.tournament_operator import OperatorDecision
    from klpga.tournament_engine import Stage
    fake_decision = OperatorDecision(stage=Stage.R1_COMPLETE, action=OperatorAction.CLOSE_R1, publish_factual=True, publish_model=False, reason="test")
    result = runner(context, fake_decision)
    assert calls == ["98_ok_open_r1_final_reconciliation.py", "99_ok_open_r2_live_recovery.py"]
    assert result.changed is True


def test_close_r1_runner_treats_r2_not_yet_published_as_wait_not_crash(monkeypatch):
    """The genuine, expected case right after R1 closes: R2 hasn't
    started yet. This must be a clean WAIT, never an unhandled
    exception that crashes the whole cycle."""
    fake_run_script, calls = _fake_run_script_factory(
        close_summary={"action": "FINAL_RECONCILED"}, r2_raises=True,
    )
    monkeypatch.setattr(run_tournament, "_run_script", fake_run_script)
    runner = run_tournament._close_r1_runner()
    context = ActionContext(game_code="FIXTURER1R2", final_round_number=3, current_round_number=1, live=True)
    from klpga.tournament_operator import OperatorDecision
    from klpga.tournament_engine import Stage
    fake_decision = OperatorDecision(stage=Stage.R1_COMPLETE, action=OperatorAction.CLOSE_R1, publish_factual=True, publish_model=False, reason="test")
    result = runner(context, fake_decision)  # must not raise
    assert calls == ["98_ok_open_r1_final_reconciliation.py", "99_ok_open_r2_live_recovery.py"]
    # R1 itself was still genuinely closed (FINAL_RECONCILED), so this
    # cycle did make real progress even though R2 isn't up yet.
    assert result.changed is True
    assert "not yet available" in result.message


def test_close_r1_runner_never_probes_r2_without_live(monkeypatch):
    fake_run_script, calls = _fake_run_script_factory(
        close_summary={"action": "PARSER_NOT_IMPLEMENTED"}, r2_raises=True,
    )
    monkeypatch.setattr(run_tournament, "_run_script", fake_run_script)
    runner = run_tournament._close_r1_runner()
    context = ActionContext(game_code="FIXTURER1R2", final_round_number=3, current_round_number=1, live=False)
    from klpga.tournament_operator import OperatorDecision
    from klpga.tournament_engine import Stage
    fake_decision = OperatorDecision(stage=Stage.R1_COMPLETE, action=OperatorAction.CLOSE_R1, publish_factual=True, publish_model=False, reason="test")
    result = runner(context, fake_decision)
    assert calls == ["98_ok_open_r1_final_reconciliation.py"]
    assert result.changed is False
