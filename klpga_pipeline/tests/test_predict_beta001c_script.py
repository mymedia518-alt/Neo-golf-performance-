"""Tests for scripts/38_predict_beta001c.py — offline, against a small
synthetic DB. Every invocation passes --output-dir/--predictions-dir
under tmp_path so tests never write into the real repo's outputs/ or
neo_win_c_predictions/."""
from __future__ import annotations

import csv
import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "38_predict_beta001c.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("predict_beta001c_script", SCRIPT_PATH)
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
        for player_id in ranked:
            conn.execute(
                "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
                "VALUES (?, ?, ?, 'test', '2026-01-01T00:00:00Z')",
                (event_id, player_id, player_id),
            )
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('LIVE', 'LIVE', 'Live Test Open', 2027, '2027-02-01', '2027-02-01')"
    )
    for player_id in players:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES ('LIVE', ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (player_id, player_id),
        )
    conn.commit()
    conn.close()
    return path


def test_script_writes_prediction_and_freezes(module, db_path, tmp_path, capsys):
    output_dir = tmp_path / "out"
    predictions_dir = tmp_path / "frozen"
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--db", str(db_path), "--game-code", "LIVE", "--cutoff-date", "2027-01-01",
        "--threshold", "1", "--output-dir", str(output_dir), "--predictions-dir", str(predictions_dir),
        "--freeze", "--prediction-id", "001-C",
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0

    full_path = output_dir / "BETA001C_WIN_FULL.csv"
    top20_path = output_dir / "BETA001C_WIN_TOP20.csv"
    report_path = output_dir / "BETA001C_MODEL_REPORT.md"
    freeze_path = output_dir / "BETA001C_FREEZE.json"
    for p in (full_path, top20_path, report_path, freeze_path):
        assert p.exists()

    with open(full_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5
    codes = [r["player_code"] for r in rows]
    assert len(codes) == len(set(codes))
    total = sum(float(r["win_probability_pct"]) for r in rows)
    assert abs(total - 100.0) < 1e-3

    out = capsys.readouterr().out
    assert "NEO GOLF BETA #001-C" in out
    assert "FROZEN" in out


def test_script_refuses_prediction_id_001(module, db_path, tmp_path):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--db", str(db_path), "--game-code", "LIVE", "--cutoff-date", "2027-01-01",
        "--freeze", "--prediction-id", "001", "--output-dir", str(tmp_path / "out"),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 2


def test_script_second_freeze_of_same_prediction_id_fails(module, db_path, tmp_path):
    output_dir = tmp_path / "out"
    predictions_dir = tmp_path / "frozen"
    import sys as _sys
    old_argv = _sys.argv
    argv = [
        "prog", "--db", str(db_path), "--game-code", "LIVE", "--cutoff-date", "2027-01-01",
        "--threshold", "1", "--output-dir", str(output_dir), "--predictions-dir", str(predictions_dir),
        "--freeze", "--prediction-id", "001-C",
    ]
    try:
        _sys.argv = argv
        rc1 = module.main()
        _sys.argv = argv
        rc2 = module.main()
    finally:
        _sys.argv = old_argv
    assert rc1 == 0
    assert rc2 == 4


def test_script_errors_on_missing_db(module, tmp_path):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--db", str(tmp_path / "nope.sqlite"), "--game-code", "LIVE", "--cutoff-date", "2027-01-01",
        "--output-dir", str(tmp_path / "out"),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 3
