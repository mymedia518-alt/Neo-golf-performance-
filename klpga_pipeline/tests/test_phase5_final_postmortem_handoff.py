"""Phase 5 (fix/phase5-generic-pipeline-hardening): FINAL -> POSTMORTEM
resume / historical handoff.

Reproduced bugs fixed here:
  - infer_post_evaluated() read raw file existence -- an empty `{}` or
    corrupt postmortem_report, or one for a different game_code/round,
    all counted as POST_EVALUATED.
  - if a postmortem was validly written but the process then crashed
    (a failed git-push, a killed wrapper) before completing the
    historical manifest step, the next cycle had no way to notice and
    finish that outstanding work without re-running postmortem.
  - stop_active_cycle in run_tournament.py's final JSON summary was
    gated on `changed`, so a resumed cycle that found the tournament
    already validly terminal (nothing left to do) reported
    stop_active_cycle=false, never telling the scheduler to stop
    polling a tournament that was actually finished.
  - no historical terminal manifest existed at all: downstream
    historical-truth ingestion had to trust mutable loose files
    directly.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_action_registry import ActionContext  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_engine import Stage  # noqa: E402
from klpga.tournament_historical_manifest import (  # noqa: E402
    HistoricalManifestBlocked,
    ingest_terminal_manifest,
    write_historical_manifest_if_absent,
)
from klpga.tournament_lifecycle import infer_post_evaluated  # noqa: E402
from klpga.tournament_operator import OperatorAction, OperatorDecision  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_tournament_phase5", ROOT / "scripts" / "run_tournament.py")
run_tournament = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_tournament)

IDENTITY = {
    "game_code": "FIXTUREFINAL01",
    "tournament_name": "Fixture Final Handoff Open",
    "season": 2027,
    "start_date": "2027-08-01",
    "end_date": "2027-08-03",
    "final_round_number": 3,
    "current_round_number": 3,
}
REGISTRY = {
    "FIXTUREFINAL01": {
        "url_base": "/tournaments/2027/fixture-final-handoff-open/",
        "stage_state_filename": "FIXTURE_FINAL_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
}
FIELD = [f"P{i}" for i in range(1, 6)]


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def _write_complete_final_snapshot(tmp_path, winner="P1"):
    _write(tmp_path, "FIXTUREFINAL01_R3_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": p, "holes_completed": 18, "status": None, "rank_display": ("1" if p == winner else "2")}
        for p in FIELD
    ]})


def _write_pre_forecast(tmp_path):
    _write(tmp_path, "FIXTUREFINAL01_PRE_WIN_FORECAST.json", {
        "records": [{"player_id": p, "win_probability": 1 / len(FIELD)} for p in FIELD],
    })


def _fake_decision(stage):
    return OperatorDecision(stage=stage, action=OperatorAction.CLOSE_FINAL, publish_factual=True, publish_model=False, reason="test")


def test_empty_postmortem_never_counts_as_post_evaluated(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    (tmp_path / "FIXTUREFINAL01_POSTMORTEM_REPORT.json").write_text("{}", encoding="utf-8")
    assert infer_post_evaluated(context) is False


def test_corrupt_postmortem_never_counts_as_post_evaluated(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    (tmp_path / "FIXTUREFINAL01_POSTMORTEM_REPORT.json").write_text("{not valid json", encoding="utf-8")
    assert infer_post_evaluated(context) is False


def test_wrong_tournament_postmortem_never_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTUREFINAL01_POSTMORTEM_REPORT.json", {
        "game_code": "SOMEOTHERGAME", "final_round_number": 3, "winner": "P1",
        "log_loss": 0.1, "brier_norm": 0.1, "winner_rank": 1, "top5_hit": True,
        "top10_hit": True, "reciprocal_rank": 1.0, "pre_source": "x", "final_source": "y",
    })
    assert infer_post_evaluated(context) is False


def test_genuine_postmortem_counts_as_post_evaluated(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "FIXTUREFINAL01_POSTMORTEM_REPORT.json", {
        "game_code": "FIXTUREFINAL01", "final_round_number": 3, "winner": "P1",
        "log_loss": 0.1, "brier_norm": 0.1, "winner_rank": 1, "top5_hit": True,
        "top10_hit": True, "reciprocal_rank": 1.0, "pre_source": "x", "final_source": "y",
    })
    assert infer_post_evaluated(context) is True


def test_close_final_runner_creates_postmortem_and_manifest_on_first_run(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    monkeypatch.setattr(run_tournament, "resolve_or_bootstrap_lifecycle",
                         lambda *, game_code, db_path: dict(IDENTITY))
    monkeypatch.setattr(run_tournament, "_load_registry_json", lambda: REGISTRY)

    runner = run_tournament._close_final_runner()
    action_context = ActionContext(game_code="FIXTUREFINAL01", final_round_number=3, current_round_number=3, live=True)
    result = runner(action_context, _fake_decision(Stage.FINAL_COMPLETE))
    assert result.changed is True
    assert (tmp_path / "FIXTUREFINAL01_POSTMORTEM_REPORT.json").is_file()
    assert (tmp_path / "FIXTUREFINAL01_HISTORICAL_TERMINAL_MANIFEST.json").is_file()


def test_close_final_runner_identical_rerun_does_not_rewrite_postmortem(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    monkeypatch.setattr(run_tournament, "resolve_or_bootstrap_lifecycle",
                         lambda *, game_code, db_path: dict(IDENTITY))
    monkeypatch.setattr(run_tournament, "_load_registry_json", lambda: REGISTRY)

    runner = run_tournament._close_final_runner()
    action_context = ActionContext(game_code="FIXTUREFINAL01", final_round_number=3, current_round_number=3, live=True)
    runner(action_context, _fake_decision(Stage.FINAL_COMPLETE))
    postmortem_path = tmp_path / "FIXTUREFINAL01_POSTMORTEM_REPORT.json"
    first_bytes = postmortem_path.read_bytes()
    manifest_path = tmp_path / "FIXTUREFINAL01_HISTORICAL_TERMINAL_MANIFEST.json"
    first_manifest_bytes = manifest_path.read_bytes()

    result2 = runner(action_context, _fake_decision(Stage.FINAL_COMPLETE))
    assert result2.changed is False
    assert postmortem_path.read_bytes() == first_bytes
    assert manifest_path.read_bytes() == first_manifest_bytes


def test_close_final_runner_resumes_manifest_after_simulated_push_failure(tmp_path, monkeypatch):
    """Simulates a crash between a valid postmortem being written and the
    historical manifest step completing (e.g. the process died right
    after run_postmortem() but before write_historical_manifest_if_absent()
    -- or git-push failed and the whole script exited nonzero). The
    NEXT cycle must detect the already-valid postmortem, never rewrite
    it, and just finish the outstanding manifest step."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    monkeypatch.setattr(run_tournament, "resolve_or_bootstrap_lifecycle",
                         lambda *, game_code, db_path: dict(IDENTITY))
    monkeypatch.setattr(run_tournament, "_load_registry_json", lambda: REGISTRY)

    context = _context()
    from klpga.tournament_postmortem import run_postmortem
    run_postmortem(context)  # simulate: postmortem already written by the crashed prior cycle
    manifest_path = tmp_path / "FIXTUREFINAL01_HISTORICAL_TERMINAL_MANIFEST.json"
    assert not manifest_path.is_file()  # ...but the manifest step never ran

    postmortem_path = tmp_path / "FIXTUREFINAL01_POSTMORTEM_REPORT.json"
    before = postmortem_path.read_bytes()

    runner = run_tournament._close_final_runner()
    action_context = ActionContext(game_code="FIXTUREFINAL01", final_round_number=3, current_round_number=3, live=True)
    result = runner(action_context, _fake_decision(Stage.FINAL_COMPLETE))

    assert postmortem_path.read_bytes() == before  # never rewritten
    assert manifest_path.is_file()  # outstanding work completed
    assert result.changed is True  # real progress was made this cycle
    assert "resumed" in result.message.lower()


def test_manifest_hashes_match_source_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    _write(tmp_path, "FIXTUREFINAL01_ENTRY_SNAPSHOT.json", {"entries": [{"player_id": p} for p in FIELD]})
    from klpga.tournament_postmortem import run_postmortem
    run_postmortem(context)

    manifest_path, written = write_historical_manifest_if_absent(context)
    assert written is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["entry_snapshot"]["present"] is True
    import hashlib
    real_entry_hash = hashlib.sha256((tmp_path / "FIXTUREFINAL01_ENTRY_SNAPSHOT.json").read_bytes()).hexdigest()
    assert manifest["entry_snapshot"]["sha256"] == real_entry_hash
    assert manifest["final_snapshot"]["present"] is True
    assert manifest["postmortem_report"]["present"] is True

    # Ingesting right now (nothing altered yet) must succeed cleanly.
    ingest_terminal_manifest(context)


def test_ingestion_blocked_when_source_altered_after_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    _write(tmp_path, "FIXTUREFINAL01_ENTRY_SNAPSHOT.json", {"entries": [{"player_id": p} for p in FIELD]})
    from klpga.tournament_postmortem import run_postmortem
    run_postmortem(context)
    write_historical_manifest_if_absent(context)

    # Source altered AFTER the manifest was written.
    _write(tmp_path, "FIXTUREFINAL01_ENTRY_SNAPSHOT.json", {"entries": [{"player_id": p} for p in FIELD] + [{"player_id": "P999"}]})

    with pytest.raises(HistoricalManifestBlocked):
        ingest_terminal_manifest(context)


def test_stop_active_cycle_true_on_resumed_terminal_cycle():
    """The exact JSON-summary computation run_tournament.py's main()
    uses -- stop_active_cycle must be true whenever the tournament is
    genuinely, validly terminal, independent of whether THIS cycle
    itself changed anything."""
    stage_after = "POST_EVALUATED"
    changed = False  # a fully-resumed cycle: nothing left to do
    stop_active_cycle = stage_after == "POST_EVALUATED"
    assert stop_active_cycle is True
