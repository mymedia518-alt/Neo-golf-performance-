"""Tests for scripts/44_predict_neo_win_post_r2.py — offline, against a
synthetic DB with a real frozen PRE snapshot plus real round_number=1/2
player_round rows and player_event.made_cut facts."""
from __future__ import annotations

import csv
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "44_predict_neo_win_post_r2.py"
PREDICT_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "33_predict_neo_win.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "R2TEST"
CUTOFF_DATE = "2027-01-01"
PLAYERS = ["A", "B", "C", "D", "E"]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "predict_neo_win_post_r2_script")


def _base_db(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    for t in range(8):
        event_id = f"T{t:02d}"
        ranked = PLAYERS[t % 5:] + PLAYERS[: t % 5]
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, f"2026-0{(t % 9) + 1:01d}-01", f"2026-0{(t % 9) + 1:01d}-01"),
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
    for player_id in PLAYERS:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (GAME_CODE, player_id, player_id),
        )
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04')",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    return conn, path


def _pre_freeze(db_path, predictions_dir):
    predict_module = _load(PREDICT_SCRIPT_PATH, "predict_neo_win_script_for_r2")
    argv_backup = sys.argv
    sys.argv = [
        "33_predict_neo_win.py", "--db", str(db_path), "--game-code", GAME_CODE, "--cutoff-date", CUTOFF_DATE,
        "--freeze", "--prediction-id", "001", "--predictions-dir", str(predictions_dir),
        "--output-dir", str(predictions_dir.parent / "pre_outputs"),
    ]
    try:
        assert predict_module.main() == 0
    finally:
        sys.argv = argv_backup


def test_incomplete_r2_data_stops_at_ready_for_r2(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    # Only 2 of 5 players have round_number=2 data -> incomplete.
    for i, player_id in enumerate(PLAYERS[:2]):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)

    output_dir = tmp_path / "outputs" / "beta_r2"
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(tmp_path / "neo_tournament_history"), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "READY_FOR_R2" in out
    assert "INCOMPLETE" in out
    assert not (output_dir / "BETA_R2_FULL.csv").exists()
    assert not (tmp_path / "neo_tournament_history" / GAME_CODE / "R2.json").exists()


def test_complete_r2_data_generates_freezes_and_records_history(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 1, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 71 - i, -i - 1),
        )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, 'A', 'A', '1', 1, 1, 2, -6)",
        (GAME_CODE, GAME_CODE),
    )
    for player_id in PLAYERS[1:]:
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, 'CUT', NULL, 0, 2, -2)",
            (GAME_CODE, GAME_CODE, player_id, player_id),
        )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)

    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta_r2"
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir),
        "--n-simulations", "300", "--seed", "7", "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "DATA_COMPLETE" in out
    assert "FROZEN" in out

    csv_path = output_dir / "BETA_R2_FULL.csv"
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5
    codes = [r["player_code"] for r in rows]
    assert len(codes) == len(set(codes))

    row_by_code = {r["player_code"]: r for r in rows}
    assert row_by_code["A"]["neo_cut_pct"] == "100.0"
    assert row_by_code["A"]["neo_r3_pct"] == row_by_code["A"]["neo_cut_pct"]
    assert row_by_code["A"]["neo_final_pct"] == row_by_code["A"]["neo_cut_pct"]
    for player_id in PLAYERS[1:]:
        assert row_by_code[player_id]["neo_cut_pct"] == "0.0"
        assert row_by_code[player_id]["neo_win_pct"] == "0.0"

    assert (history_dir / GAME_CODE / "R2.json").exists()

    # rerun is idempotent (SKIP + LOG), never a crash, never a second write.
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir),
        "--n-simulations", "300", "--seed", "7", "--freeze",
    ]
    try:
        rc2 = module.main()
    finally:
        sys.argv = argv_backup
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "SKIP + LOG" in out2
