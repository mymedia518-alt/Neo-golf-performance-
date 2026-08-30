"""Tests for scripts/final_close_preflight.py -- the one-command FINAL
CLOSE preflight orchestrator. Every underlying piece (cache inspection,
collect_and_persist_tournament, finalist reconciliation, readiness
gate) is already covered by its own dedicated test file; this file
only checks final_close_preflight.py's own wiring and verdict
aggregation: does STEP 1-6 output feed into the right GO/WARN/
HARD_STOP conclusion, and does it never import anything that could
freeze history/evaluation or touch docs/index.html.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.collectors.cache_inspection import RoundCacheInspection
from klpga.collectors.single_tournament import STATUS_SUCCESS, SingleTournamentCollectionResult
from klpga.collectors.tournaments import TournamentListing
from klpga.neo_win.finalist_reconciliation import FinalistReconciliationReport
from klpga.neo_win.player_status import READINESS_GO, FieldReadiness
from klpga.neo_win.round_reconciliation import VERDICT_PASS

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "final_close_preflight.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
MODULE_NAME = "final_close_preflight_script_under_test"
GAME_CODE = "2026080001"


def _load():
    spec = importlib.util.spec_from_file_location(MODULE_NAME, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date, winner, winner_score, "
        "rounds_completed) VALUES (?, ?, 'Test Open', 2026, '2026-08-30', 'Player One', '279', 4)",
        (GAME_CODE, GAME_CODE),
    )
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES (?, '1001', 'Player One', 'test', '2026-08-30T00:00:00Z')",
        (GAME_CODE,),
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def finalists_path(tmp_path):
    path = tmp_path / "roster.csv"
    path.write_text("player_code,player_name\n1001,Player One\n", encoding="utf-8")
    return path


def _listing():
    return TournamentListing(
        game_code=GAME_CODE, game_title="Test Open", game_eng_title=None, tour_type="RE",
        course_text=None, course_eng_text=None, out_course_text=None, in_course_text=None,
        start_date=date(2026, 8, 27), start_date_raw="20260827", end_date=date(2026, 8, 30), end_date_raw="20260830",
        game_finish="F", prize_money=None, winner_code="1001", winner_name="Player One", game_method="0",
        season=2026, raw={"gameCode": GAME_CODE},
    )


def _clean_collection():
    return SingleTournamentCollectionResult(
        status=STATUS_SUCCESS, game_code=GAME_CODE, match=_listing(),
        rounds_data={4: []}, final_round=4, expected_final_round=4,
        player_rows=[], player_event_rows=[], player_round_rows=[], winner_score="279",
    )


def _no_cache_entry():
    return RoundCacheInspection(game_code=GAME_CODE, round_number=4, cache_path=Path("/tmp/x"), exists=False)


def _clean_finalist_report():
    return FinalistReconciliationReport(
        round_number=4, expected_finalists=1, official_round_total=1, official_round_in_roster=1,
        db_round_total=1, matched=["1001"], missing=[], extra=[], unresolved=[], wd=[], dq=[],
        anomalies=[], verdict=VERDICT_PASS, reconciliation=None,
    )


def _go_readiness():
    return FieldReadiness(
        round_number=4, field_size=1, statuses=(), verdict=READINESS_GO,
        unknown_players=(), collection_missing_players=(), reason="all accounted for",
    )


def _patched(module, snapshot_found: bool, finalist_report=None, readiness=None):
    """Context-manager stack patching every STEP's underlying call."""
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch(f"{MODULE_NAME}.inspect_round_leaderboard_cache", return_value=_no_cache_entry()))
    stack.enter_context(patch(f"{MODULE_NAME}.collect_and_persist_tournament", return_value=_clean_collection()))
    stack.enter_context(patch(f"{MODULE_NAME}.normalize_official_round", return_value={}))
    stack.enter_context(patch(f"{MODULE_NAME}.normalize_db_round", return_value={}))
    stack.enter_context(patch(
        f"{MODULE_NAME}.reconcile_finalists", return_value=finalist_report or _clean_finalist_report()
    ))
    stack.enter_context(patch(f"{MODULE_NAME}.assess_field_readiness", return_value=readiness or _go_readiness()))
    return stack


def test_go_verdict_when_everything_clean(module, db_path, finalists_path, tmp_path, capsys):
    predictions_dir = tmp_path / "neo_win_predictions" / "2026"
    predictions_dir.mkdir(parents=True)
    (predictions_dir / f"neo_win_001_{GAME_CODE}.json").write_text("{}", encoding="utf-8")

    argv = [
        "final_close_preflight.py", "--db", str(db_path), "--season", "2026", "--game-code", GAME_CODE,
        "--expected-final-round", "4", "--finalists", str(finalists_path),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
    ]
    with patch("sys.argv", argv):
        with _patched(module, snapshot_found=True):
            rc = module.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "VERDICT: GO" in out


def test_json_out_written_with_verdict_and_key_counts(module, db_path, finalists_path, tmp_path, capsys):
    import json

    predictions_dir = tmp_path / "neo_win_predictions" / "2026"
    predictions_dir.mkdir(parents=True)
    (predictions_dir / f"neo_win_001_{GAME_CODE}.json").write_text("{}", encoding="utf-8")
    json_out = tmp_path / "out" / "summary.json"

    argv = [
        "final_close_preflight.py", "--db", str(db_path), "--season", "2026", "--game-code", GAME_CODE,
        "--expected-final-round", "4", "--finalists", str(finalists_path),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
        "--json-out", str(json_out),
    ]
    with patch("sys.argv", argv):
        with _patched(module, snapshot_found=True):
            rc = module.main()

    assert rc == 0
    assert json_out.exists()
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["verdict"] == "GO"
    assert data["game_code"] == GAME_CODE
    assert data["finalist_reconciliation"]["expected_finalists"] == 1
    assert data["hard_stop_reasons"] == []


def test_hard_stop_when_canonical_snapshot_missing(module, db_path, finalists_path, tmp_path, capsys):
    argv = [
        "final_close_preflight.py", "--db", str(db_path), "--season", "2026", "--game-code", GAME_CODE,
        "--expected-final-round", "4", "--finalists", str(finalists_path),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),  # never created -- no snapshot
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
    ]
    with patch("sys.argv", argv):
        with _patched(module, snapshot_found=False):
            rc = module.main()

    out = capsys.readouterr().out
    assert rc == 6
    assert "VERDICT: HARD_STOP" in out
    assert "CANONICAL SNAPSHOT" in out


def test_hard_stop_when_unexplained_missing_finalist(module, db_path, finalists_path, tmp_path, capsys):
    predictions_dir = tmp_path / "neo_win_predictions" / "2026"
    predictions_dir.mkdir(parents=True)
    (predictions_dir / f"neo_win_001_{GAME_CODE}.json").write_text("{}", encoding="utf-8")

    bad_report = FinalistReconciliationReport(
        round_number=4, expected_finalists=1, official_round_total=0, official_round_in_roster=0,
        db_round_total=0, matched=[], missing=["1001"], extra=[], unresolved=[], wd=[], dq=[],
        anomalies=[], verdict=VERDICT_PASS, reconciliation=None,
    )
    argv = [
        "final_close_preflight.py", "--db", str(db_path), "--season", "2026", "--game-code", GAME_CODE,
        "--expected-final-round", "4", "--finalists", str(finalists_path),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
    ]
    with patch("sys.argv", argv):
        with _patched(module, snapshot_found=True, finalist_report=bad_report):
            rc = module.main()

    out = capsys.readouterr().out
    assert rc == 6
    assert "VERDICT: HARD_STOP" in out
    assert "FINALIST RECONCILIATION" in out
    assert "1001" in out


def test_module_never_imports_history_or_homepage_writers():
    """The docstring legitimately DESCRIBES docs/index.html and the
    freeze scripts in prose (explaining what this script never does) --
    what must never appear is an actual import of a module that could
    write to any of them."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "write_or_supersede_history_stage", "write_evaluation_atomic",
        "write_prediction_snapshot_atomic", "klpga.neo_win.tournament_history",
        "klpga.neo_win.r3_r4_evaluation_archive", "klpga.site",
    )
    for forbidden in forbidden_imports:
        assert forbidden not in source, f"{forbidden!r} must never be imported by this preflight script"
