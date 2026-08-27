"""Tests for scripts/37_beta001c_model_backtest.py — offline, against a
small synthetic DB. --output-dir always under tmp_path."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "37_beta001c_model_backtest.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("beta001c_model_backtest_script", SCRIPT_PATH)
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

    players = ["A", "B", "C", "D", "E"]
    for t in range(8):
        event_id = f"T{t:02d}"
        ranked = players[t % 5:] + players[: t % 5]
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, f"2026-{(t % 12) + 1:02d}-01", f"2026-{(t % 12) + 1:02d}-01"),
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
    conn.commit()
    conn.close()
    return path


def test_script_writes_backtest_report(module, db_path, tmp_path, capsys):
    output_dir = tmp_path / "out"
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["prog", "--db", str(db_path), "--threshold", "1", "--output-dir", str(output_dir)]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0
    md_path = output_dir / "MODEL_BACKTEST.md"
    csv_path = output_dir / "MODEL_BACKTEST.csv"
    assert md_path.exists()
    assert csv_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "MODEL_A" in text and "MODEL_B" in text and "MODEL_C" in text
    assert "Phase 8" in text and "Selected:" in text
    out = capsys.readouterr().out
    assert "PHASE 7 MODEL BACKTEST" in out
    assert "PHASE 8 SELECTED MODEL" in out


def test_script_errors_on_missing_db(module, tmp_path):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["prog", "--db", str(tmp_path / "nope.sqlite"), "--output-dir", str(tmp_path / "out")]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 3
