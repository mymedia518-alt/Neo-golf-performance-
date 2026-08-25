"""Tests for scripts/22_compare_win_probability_models.py — no
network, read-only, against a small synthetic multi-tournament DB.
Confirms the script's run() function completes, prints progress and a
full report, and never writes to the database."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "22_compare_win_probability_models.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("compare_win_probability_models_script", SCRIPT_PATH)
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

    players = ["A", "B", "C", "D", "E"]
    for t in range(10):
        event_id = f"T{t:02d}"
        connection.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, f"2026-{(t % 12) + 1:02d}-01", f"2026-{(t % 12) + 1:02d}-04"),
        )
        ranked = players[t % len(players):] + players[: t % len(players)]
        for rank, p in enumerate(ranked, start=1):
            connection.execute(
                "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (p, p)
            )
            connection.execute(
                "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
                "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
                "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
                (event_id, event_id, p, p, str(rank), rank, -rank),
            )
    connection.commit()
    yield connection, db_path
    connection.close()


def test_run_produces_report_for_every_model_and_threshold(module, conn, capsys):
    connection, db_path = conn
    results = module.run(connection, db_path, thresholds=(1, 2), model_ids=("M0", "M1"))
    out = capsys.readouterr().out

    assert set(results.keys()) == {1, 2}
    assert "REPRODUCIBILITY" in out
    assert "THRESHOLD = 1" in out
    assert "THRESHOLD = 2" in out
    assert "M0" in out and "M1" in out
    assert "TOTAL elapsed" in out
    assert "No model has been selected as a production candidate" in out


def test_run_never_writes_to_the_database(module, conn):
    connection, db_path = conn
    before_tournaments = connection.execute("SELECT COUNT(*) FROM tournament_master").fetchone()[0]
    before_events = connection.execute("SELECT COUNT(*) FROM player_event").fetchone()[0]

    module.run(connection, db_path, thresholds=(1,), model_ids=("M0", "M1", "M2"))

    after_tournaments = connection.execute("SELECT COUNT(*) FROM tournament_master").fetchone()[0]
    after_events = connection.execute("SELECT COUNT(*) FROM player_event").fetchone()[0]
    assert before_tournaments == after_tournaments
    assert before_events == after_events


def test_progress_is_printed_per_target_and_model(module, conn, capsys):
    connection, db_path = conn
    module.run(connection, db_path, thresholds=(1,), model_ids=("M0", "M1"))
    out = capsys.readouterr().out
    assert "model=M0" in out
    assert "model=M1" in out
    assert "elapsed=" in out


def test_main_rejects_unknown_model_id(module, conn, capsys, monkeypatch):
    connection, db_path = conn
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--db", str(db_path), "--thresholds", "1", "--models", "M0,NOT_A_MODEL"],
    )
    rc = module.main()
    err = capsys.readouterr().err
    assert rc == 2
    assert "unknown model id" in err
