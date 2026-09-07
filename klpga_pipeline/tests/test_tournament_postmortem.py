"""NEO TOURNAMENT PIPELINE item 4: the postmortem stage must connect to
the existing, already-tested klpga.models.metrics evaluation library --
never invent new scoring logic -- and must fail closed (never fabricate
a result) when the final round isn't actually complete."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_postmortem import PostmortemBlocked, run_postmortem  # noqa: E402

IDENTITY = {
    "game_code": "TEST0001",
    "tournament_name": "Test Open",
    "season": 2026,
    "start_date": "2026-01-01",
    "end_date": "2026-01-03",
    "final_round_number": 3,
    "current_round_number": 3,
}
REGISTRY = {
    "TEST0001": {
        "url_base": "/tournaments/2026/test-open/",
        "stage_state_filename": "TEST_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
}


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def test_postmortem_blocked_when_final_round_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "TEST0001_PRE_WIN_FORECAST.json", {"records": [{"player_id": "P1", "win_probability": 1.0}]})
    _write(tmp_path, "TEST0001_R3_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 10, "rank_display": "1", "status": None},
    ]})
    import pytest
    with pytest.raises(PostmortemBlocked, match="not complete"):
        run_postmortem(context)


def test_postmortem_blocked_when_no_pre_forecast(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "TEST0001_R3_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 18, "rank_display": "1", "status": None},
    ]})
    import pytest
    with pytest.raises(PostmortemBlocked, match="no PRE win forecast"):
        run_postmortem(context)


def test_postmortem_blocked_when_winner_not_in_pre_field(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "TEST0001_PRE_WIN_FORECAST.json", {"records": [{"player_id": "P9", "win_probability": 1.0}]})
    _write(tmp_path, "TEST0001_R3_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 18, "rank_display": "1", "status": None},
    ]})
    import pytest
    with pytest.raises(PostmortemBlocked, match="not in the PRE forecast field"):
        run_postmortem(context)


def test_withdrawn_player_does_not_block_completion(tmp_path, monkeypatch):
    """A WD player never finishing 18 holes must not be mistaken for an
    in-progress round -- matches klpga.tournament_runtime.NON_CUT_STATUSES."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "TEST0001_PRE_WIN_FORECAST.json", {"records": [
        {"player_id": "P1", "win_probability": 0.5},
        {"player_id": "P2", "win_probability": 0.5},
    ]})
    _write(tmp_path, "TEST0001_R3_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 18, "rank_display": "1", "status": None},
        {"player_id": "P2", "holes_completed": "3", "rank_display": "999", "status": "WD"},
    ]})
    result = run_postmortem(context)
    assert result.winner_rank == 1


def test_real_metrics_library_is_used_and_written(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    _write(tmp_path, "TEST0001_PRE_WIN_FORECAST.json", {"records": [
        {"player_id": "P1", "win_probability": 0.4},
        {"player_id": "P2", "win_probability": 0.3},
        {"player_id": "P3", "win_probability": 0.3},
    ]})
    _write(tmp_path, "TEST0001_R3_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": "P1", "holes_completed": 18, "rank_display": "1", "status": None},
        {"player_id": "P2", "holes_completed": 18, "rank_display": "2", "status": None},
        {"player_id": "P3", "holes_completed": 18, "rank_display": "3", "status": None},
    ]})

    from klpga.models.metrics import log_loss as expected_log_loss, make_prediction

    result = run_postmortem(context)

    expected = make_prediction("TEST0001", "TEST0001", "2026-01-01", {"P1": 0.4, "P2": 0.3, "P3": 0.3}, "P1", {})
    assert result.log_loss == expected_log_loss(expected)
    assert result.winner_rank == 1
    assert result.top5_hit is True

    written = json.loads((tmp_path / "TEST0001_POSTMORTEM_REPORT.json").read_text(encoding="utf-8"))
    assert written["evaluation_library"] == "klpga.models.metrics"
    assert written["winner"] == "P1"
