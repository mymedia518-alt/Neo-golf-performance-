"""Tests for scripts/33_predict_neo_win.py — offline, against a small
synthetic DB (mirrors tests/test_neo_win.py's fixture shape)."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "33_predict_neo_win.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("predict_neo_win_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    players = ["A", "B", "C"]
    for t in range(6):
        event_id = f"T{t:02d}"
        ranked = players[t % 3:] + players[: t % 3]
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, f"2026-0{(t % 9) + 1}-01", f"2026-0{(t % 9) + 1}-01"),
        )
        for rank, player_id in enumerate(ranked, start=1):
            conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
            conn.execute(
                "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
                "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
                "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
                (event_id, event_id, player_id, player_id, str(rank), rank, -10 + rank),
            )
            for rn in range(1, 5):
                conn.execute(
                    "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                    "round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
                    (event_id, event_id, rn, player_id, player_id, 70 - rank, -rank),
                )

    for player_code in ["A", "B", "C"]:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES ('LIVE1', ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (player_code, player_code),
        )

    conn.commit()
    conn.close()
    return path


def test_main_prints_report_without_freezing(module, db_path, tmp_path, capsys):
    argv_backup = sys.argv
    sys.argv = ["33_predict_neo_win.py", "--db", str(db_path), "--game-code", "LIVE1", "--cutoff-date", "2027-01-01"]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "NEO WIN % v0.1 (BETA #001)" in out
    assert "TOP 10 NEO WIN %" in out


def test_main_freeze_writes_snapshot(module, db_path, tmp_path):
    predictions_dir = tmp_path / "neo_win_predictions"
    argv_backup = sys.argv
    sys.argv = [
        "33_predict_neo_win.py",
        "--db", str(db_path),
        "--game-code", "LIVE1",
        "--cutoff-date", "2027-01-01",
        "--freeze",
        "--prediction-id", "001",
        "--predictions-dir", str(predictions_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    json_path = predictions_dir / "2027" / "neo_win_001_LIVE1.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["game_code"] == "LIVE1"
    assert len(data["predictions"]) == 3


def test_main_freeze_without_prediction_id_fails_cleanly(module, db_path):
    argv_backup = sys.argv
    sys.argv = ["33_predict_neo_win.py", "--db", str(db_path), "--game-code", "LIVE1", "--freeze"]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 2


def test_main_db_not_found_fails_cleanly(module, tmp_path):
    argv_backup = sys.argv
    sys.argv = ["33_predict_neo_win.py", "--db", str(tmp_path / "nope.sqlite"), "--game-code", "LIVE1"]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 3


def test_main_refuses_to_reopen_an_already_frozen_snapshot(module, db_path, tmp_path):
    predictions_dir = tmp_path / "neo_win_predictions"
    argv = [
        "33_predict_neo_win.py",
        "--db", str(db_path),
        "--game-code", "LIVE1",
        "--cutoff-date", "2027-01-01",
        "--freeze",
        "--prediction-id", "001",
        "--predictions-dir", str(predictions_dir),
    ]
    argv_backup = sys.argv
    try:
        sys.argv = argv
        assert module.main() == 0
        sys.argv = argv
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 4
