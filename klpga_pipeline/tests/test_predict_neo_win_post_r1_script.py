"""Tests for scripts/35_predict_neo_win_post_r1.py — offline, against
a synthetic DB with a real frozen PRE snapshot (built the same way
scripts/33 does) plus real round_number=1 player_round rows."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "35_predict_neo_win_post_r1.py"
PREDICT_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "33_predict_neo_win.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "R1TEST"
CUTOFF_DATE = "2027-01-01"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "predict_neo_win_post_r1_script")


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

    for player_id in players:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (GAME_CODE, player_id, player_id),
        )

    # scripts/04_collect_single_tournament.py always upserts a
    # tournament_master row (from getGameList) before any player_round
    # row can be inserted (player_round.event_id has a real FK to
    # tournament_master.event_id) — mirror that here for the LIVE,
    # in-progress tournament (end_date is a placeholder pending
    # completion, same as a real in-progress event would have).
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04')",
        (GAME_CODE, GAME_CODE),
    )

    # Real Round-1 data for the LIVE, not-yet-completed tournament.
    for i, player_id in enumerate(players):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 1, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )

    conn.commit()
    conn.close()
    return path


def _freeze_pre(db_path, predictions_dir):
    predict_module = _load(PREDICT_SCRIPT_PATH, "predict_neo_win_script_for_r1")
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


def test_main_produces_r1_report_and_files(module, db_path, tmp_path, capsys):
    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze_pre(db_path, predictions_dir)

    output_dir = tmp_path / "outputs" / "beta001_r1"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--predictions-dir", str(predictions_dir),
        "--pre-prediction-id", "001", "--pre-cutoff-date", CUTOFF_DATE,
        "--n-simulations", "300", "--seed", "42", "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "NEO GOLF BETA #001 — AFTER R1" in out
    assert "WIN % TOP 20" in out
    assert "SEO GYO-RIM TRACK" in out
    assert "MODEL CHECK" in out
    assert "NOT FROZEN" in out

    assert (output_dir / "BETA001_R1_FULL.csv").exists()
    assert (output_dir / "BETA001_R1_TOP20.csv").exists()
    assert (output_dir / "BETA001_R1_MODEL_REPORT.md").exists()
    assert (output_dir / "BETA001_R1_THREADS.txt").exists()
    assert not (output_dir / "BETA001_R1_FREEZE.json").exists()


def test_full_csv_win_sum_is_100_within_tolerance(module, db_path, tmp_path):
    import csv as csv_module

    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze_pre(db_path, predictions_dir)
    output_dir = tmp_path / "outputs" / "beta001_r1"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--predictions-dir", str(predictions_dir),
        "--pre-prediction-id", "001", "--pre-cutoff-date", CUTOFF_DATE,
        "--n-simulations", "500", "--seed", "1", "--output-dir", str(output_dir),
    ]
    try:
        assert module.main() == 0
    finally:
        sys.argv = argv_backup

    with open(output_dir / "BETA001_R1_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv_module.DictReader(f))
    total_win = sum(float(r["post_r1_win_pct"]) for r in rows if r["post_r1_win_pct"])
    assert total_win == pytest.approx(100.0, abs=1.0)
    codes = [r["player_code"] for r in rows]
    assert len(codes) == len(set(codes))


def test_main_freeze_writes_immutable_snapshot(module, db_path, tmp_path):
    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze_pre(db_path, predictions_dir)
    output_dir = tmp_path / "outputs" / "beta001_r1"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--predictions-dir", str(predictions_dir),
        "--pre-prediction-id", "001", "--pre-cutoff-date", CUTOFF_DATE,
        "--n-simulations", "200", "--seed", "5", "--output-dir", str(output_dir),
        "--freeze", "--prediction-id", "001-R1",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0

    json_path = predictions_dir / "2027" / "neo_win_001-R1_R1TEST.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["prediction_id"] == "001-R1"
    assert data["pre_prediction_id"] == "001"

    # The PRE snapshot must remain untouched.
    pre_json_path = predictions_dir / "2027" / "neo_win_001_R1TEST.json"
    pre_data = json.loads(pre_json_path.read_text(encoding="utf-8"))
    assert pre_data["prediction_id"] == "001"


def test_main_fails_cleanly_when_no_r1_data(module, tmp_path):
    path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(path), "--game-code", "NOPE", "--predictions-dir", str(predictions_dir),
        "--pre-cutoff-date", CUTOFF_DATE, "--output-dir", str(tmp_path / "out"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 5  # no PRE snapshot found first
