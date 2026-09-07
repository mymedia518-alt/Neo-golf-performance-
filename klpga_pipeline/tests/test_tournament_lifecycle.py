"""NEO TOURNAMENT PIPELINE items 2/5: tournament_lifecycle.py bridges
real on-disk artifacts to the existing, already-tested generic engine
(tournament_engine/tournament_runtime) -- these tests prove the bridge
reads real artifact shapes correctly, not that the engine itself works
(that's already covered by the engine's own test suite)."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_engine import Stage  # noqa: E402
from klpga.tournament_lifecycle import infer_round_facts, infer_tournament_facts, resolve_lifecycle  # noqa: E402

IDENTITY = {
    "game_code": "TEST0001",
    "tournament_name": "Test Open",
    "season": 2026,
    "start_date": "2026-01-01",
    "end_date": "2026-01-03",
    "final_round_number": 3,
    "current_round_number": 1,
}
REGISTRY = {
    "TEST0001": {
        "url_base": "/tournaments/2026/test-open/",
        "stage_state_filename": "TEST_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
}
LIFECYCLE = {"game_code": "TEST0001", "cut_after_round": 2, "model_ready": False}


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def test_missing_round_snapshot_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    assert infer_round_facts(_context(), 1) is None


def test_withdrawn_players_do_not_count_as_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write(tmp_path, "TEST0001_R1_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": "18", "status": None},
        {"player_id": "P2", "holes_completed": "1", "status": "WD"},
    ]})
    facts = infer_round_facts(_context(), 1)
    assert facts.official_players == 2
    assert facts.incomplete_players == 0
    assert facts.complete is True


def test_in_progress_players_do_count_as_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write(tmp_path, "TEST0001_R1_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 18, "status": "ACTIVE"},
        {"player_id": "P2", "holes_completed": 5, "status": "INCOMPLETE"},
    ]})
    facts = infer_round_facts(_context(), 1)
    assert facts.incomplete_players == 1
    assert facts.complete is False
    assert facts.validated is True


def test_stage_resolves_from_real_artifacts_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "TEST0001_ENTRY_SNAPSHOT.json", {"records": [{"player_id": "P1"}]})
    _write(tmp_path, "TEST0001_PRE_WIN_FORECAST.json", {"records": [{"player_id": "P1", "win_probability": 1.0}]})
    _write(tmp_path, "TEST0001_R1_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 18, "status": None},
    ]})
    snapshot = resolve_lifecycle(context, LIFECYCLE)
    assert snapshot.stage == Stage.R1_COMPLETE.value


def test_facts_never_fabricated_for_a_round_with_no_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    facts = infer_tournament_facts(_context())
    assert facts.rounds == ()
    assert facts.entry_validated is False
    assert facts.pre_validated is False
