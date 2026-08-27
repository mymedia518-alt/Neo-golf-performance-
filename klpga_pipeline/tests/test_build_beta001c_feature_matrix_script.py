"""Tests for scripts/36_build_beta001c_feature_matrix.py — offline,
against a small synthetic DB. Every invocation passes --output-dir
under tmp_path so tests never write into the real repo's outputs/."""
from __future__ import annotations

import csv
import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "36_build_beta001c_feature_matrix.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
REAL_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_beta001c_feature_matrix_script", SCRIPT_PATH)
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
    for t in range(3):
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
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('LIVE', 'A', 'A', 'test', '2027-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('LIVE', 'LIVE', 'LIVE', 2027, '2027-02-01', '2027-02-01')"
    )
    conn.commit()
    conn.close()
    return path


def test_script_writes_feature_matrix_csv(module, db_path, tmp_path, capsys):
    output_dir = tmp_path / "out"
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--db", str(db_path), "--game-code", "LIVE", "--cutoff-date", "2027-01-01",
        "--taxonomy-path", str(REAL_TAXONOMY_PATH), "--raw-samples-dir", str(REAL_RAW_SAMPLES_DIR),
        "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0
    matrix_path = output_dir / "BETA001C_FEATURE_MATRIX.csv"
    assert matrix_path.exists()
    with open(matrix_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["player_code"] == "A"
    assert "neo_driving" in rows[0]
    assert "neo_scoring" in rows[0]
    assert rows[0]["neo_scoring"] == ""

    out = capsys.readouterr().out
    assert "BETA #001-C — FEATURE MATRIX" in out
    assert "DOMAIN COVERAGE" in out


def test_script_errors_on_missing_db(module, tmp_path, capsys):
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
