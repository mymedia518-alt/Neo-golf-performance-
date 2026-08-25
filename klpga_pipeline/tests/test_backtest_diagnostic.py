"""Tests for scripts/16_backtest_diagnostic.py's run() — no network,
read-only, against a real schema.sql-built temp DB."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "16_backtest_diagnostic.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("backtest_diagnostic_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "klpga.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('A', 'A', 'Prior Open', 2026, '2026-01-01', '2026-01-04')"
    )
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('T', 'T', 'Target Open', 2026, '2026-06-01', '2026-06-04')"
    )
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('P1', '선수1')")
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('A', 'A', 2026, 'P1', '선수1', '1', 1, 1, 4, -8)"
    )
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('T', 'T', 2026, 'P1', '선수1', '3', 3, 1, 4, -5)"
    )
    connection.commit()
    yield connection
    connection.close()


def test_reports_target_cutoff_and_feature_values(module, conn, capsys):
    rc = module.run(conn, "T", player_codes=None, sample=5)
    out = capsys.readouterr().out

    assert rc == 0
    assert "TARGET TOURNAMENT: 'Target Open'" in out
    assert "feature cutoff date (effective_date) = 2026-06-01" in out
    assert "exact: from confirmed start_date" in out
    assert "prior_events_n = 1" in out
    assert "LABEL (target tournament's own outcome" in out
    assert "finish_position_numeric = 3" in out
    # the label must never be printed inside the feature block above it
    feature_block = out.split("FEATURE VALUES")[1].split("LABEL")[0]
    assert "finish_position" not in feature_block


def test_unknown_game_code_reports_error_not_crash(module, conn, capsys):
    rc = module.run(conn, "NOPE", player_codes=None, sample=5)
    out = capsys.readouterr().out
    assert rc == 2
    assert "no tournament_master row for game_code" in out


def test_requested_player_not_in_field_is_reported(module, conn, capsys):
    rc = module.run(conn, "T", player_codes=["NOT_IN_FIELD"], sample=5)
    out = capsys.readouterr().out
    assert "NOT_IN_FIELD" in out
    assert "is NOT in this target's reconstructed field" in out
    assert rc == 1  # nothing selected to report on
