"""Tests for scripts/17_eligibility_report.py — no network, against a
small hand-computable synthetic corpus (same shape as
tests/test_walk_forward.py's four_tournament_corpus)."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "17_eligibility_report.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("eligibility_report_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tournament(event_id, start_date):
        connection.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, start_date, start_date),
        )

    def player(player_id):
        connection.execute(
            "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id)
        )

    def event_row(event_id, player_id, finish):
        player(player_id)
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 4, -2)",
            (event_id, event_id, player_id, player_id, str(finish), finish),
        )

    tournament("T1", "2026-01-01")
    tournament("T2", "2026-02-01")
    tournament("T3", "2026-03-01")
    event_row("T1", "P1", 1)
    event_row("T1", "P2", 2)
    event_row("T2", "P1", 1)
    event_row("T3", "P1", 1)
    event_row("T3", "P2", 2)
    connection.commit()
    yield connection
    connection.close()


def test_run_prints_report_and_does_not_choose_a_threshold(module, conn, capsys):
    report = module.run(conn, thresholds=(0, 1, 2))
    out = capsys.readouterr().out

    assert "Corpus: 3 tournament_master row(s)." in out
    assert "No threshold is chosen by this script" in out
    assert "min prior" in report


def test_report_values_match_hand_computed_sweep(module, conn):
    from klpga.backtest.walk_forward import build_walk_forward_dataset, eligibility_sweep

    result = build_walk_forward_dataset(conn)
    expected = eligibility_sweep(result, thresholds=(0, 1, 2))
    report = module.run(conn, thresholds=(0, 1, 2))

    for row in expected:
        assert str(row["threshold"]) in report
        if row["earliest_eligible_target_game_code"]:
            assert row["earliest_eligible_target_game_code"] in report


def test_run_reports_skipped_undated_tournament(module, conn, capsys):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('BAD', 'BAD', 'Undated', 2026, NULL, 'garbage')"
    )
    conn.commit()
    module.run(conn, thresholds=(0,))
    out = capsys.readouterr().out
    assert "skipped entirely" in out
    assert "BAD" in out
