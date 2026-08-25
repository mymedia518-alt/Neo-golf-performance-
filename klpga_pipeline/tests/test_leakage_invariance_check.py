"""Tests for scripts/18_leakage_invariance_check.py — no network,
against a small synthetic multi-tournament corpus with a real player who
has events on both sides of a mid-corpus target."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "18_leakage_invariance_check.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("leakage_invariance_check_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _tournament(conn, event_id, start_date):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, 2026, ?, ?)",
        (event_id, event_id, event_id, start_date, start_date),
    )


def _event_row(conn, event_id, player_id, finish=1):
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, ?, ?, ?, ?, 1, 4, -2)",
        (event_id, event_id, player_id, player_id, str(finish), finish),
    )


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # 5 tournaments, T3 in the middle. P1 (prolific) plays all 5. P2
    # only plays T1 (nothing to demonstrate exclusion against).
    for i, month in enumerate(["01", "02", "03", "04", "05"], start=1):
        _tournament(connection, f"T{i}", f"2026-{month}-01")
        _event_row(connection, f"T{i}", "P1", finish=i)
    _event_row(connection, "T1", "P2", finish=2)
    connection.commit()
    yield connection
    connection.close()


def test_auto_selects_middle_target_and_prolific_player(module, conn, capsys):
    outcome = module.run(conn, game_code=None, player_code=None)
    out = capsys.readouterr().out

    assert outcome["status"] == "success"
    assert outcome["passed"] is True
    assert outcome["target_event_id"] == "T3"  # middle of 5
    assert outcome["player_code"] == "P1"
    assert "PASS" in out
    assert "FAIL" not in out


def test_explicit_target_and_player(module, conn, capsys):
    outcome = module.run(conn, game_code="T4", player_code="P1")
    out = capsys.readouterr().out
    assert outcome["status"] == "success"
    assert outcome["used_count"] == 3  # T1, T2, T3
    assert outcome["excluded_count"] == 2  # T4 (itself), T5
    assert "T5" in out
    assert outcome["passed"] is True


def test_unknown_game_code_reports_error(module, conn, capsys):
    outcome = module.run(conn, game_code="NOPE", player_code=None)
    assert outcome["status"] == "error"
    out = capsys.readouterr().out
    assert "not a usable target tournament" in out


def test_explicit_player_with_zero_prior_events_still_runs_trivially(module, conn):
    # T1 is the earliest tournament — even P1 (prolific) has zero real
    # "before" events for it. Passing an explicit player still computes
    # (trivially: nothing used, nothing leaked), it just isn't a very
    # interesting demonstration.
    outcome = module.run(conn, game_code="T1", player_code="P2")
    assert outcome["status"] == "success"
    assert outcome["used_count"] == 0
    assert outcome["passed"] is True


def test_auto_select_reports_error_when_no_player_qualifies(module, conn, capsys):
    # No player in this corpus has a real event BEFORE T1 (the earliest
    # tournament) — auto-selection must report this clearly, not crash.
    outcome = module.run(conn, game_code="T1", player_code=None)
    assert outcome["status"] == "error"
    out = capsys.readouterr().out
    assert "cannot" in out.lower()
