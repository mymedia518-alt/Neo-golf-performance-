"""Tests for scripts/34_audit_neo_win_player.py — offline, against a
real frozen snapshot built in-process over a synthetic DB (mirrors
tests/test_neo_win_audit.py's fixture)."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "34_audit_neo_win_player.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
LIVE_GAME_CODE = "AUDIT1"
CUTOFF_DATE = "2027-01-01"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_neo_win_player_script", SCRIPT_PATH)
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

    players = [("seo", "서교림"), ("park", "박현경"), ("other", "기타")]
    for t in range(8):
        event_id = f"T{t:02d}"
        ranked = players[t % 3:] + players[: t % 3]
        winner_name = ranked[0][1]
        conn.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date, winner) "
            "VALUES (?, ?, ?, 2026, ?, ?, ?)",
            (event_id, event_id, event_id, f"2026-{(t % 9) + 1:02d}-01", f"2026-{(t % 9) + 1:02d}-01", winner_name),
        )
        for rank, (player_id, player_name) in enumerate(ranked, start=1):
            conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_name))
            conn.execute(
                "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
                "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
                "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
                (event_id, event_id, player_id, player_name, str(rank), rank, -20 + rank),
            )
            for rn in range(1, 5):
                conn.execute(
                    "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                    "round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
                    (event_id, event_id, rn, player_id, player_name, 70 - rank, -rank),
                )

    for player_id, player_name in players:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
            (LIVE_GAME_CODE, player_id, player_name),
        )
    conn.commit()
    conn.close()
    return path


def _freeze(db_path, predictions_dir):
    import importlib.util as ilu

    predict_script_path = Path(__file__).resolve().parents[1] / "scripts" / "33_predict_neo_win.py"
    spec = ilu.spec_from_file_location("predict_neo_win_script_for_audit", predict_script_path)
    predict_module = ilu.module_from_spec(spec)
    spec.loader.exec_module(predict_module)

    argv_backup = sys.argv
    sys.argv = [
        "33_predict_neo_win.py", "--db", str(db_path), "--game-code", LIVE_GAME_CODE,
        "--cutoff-date", CUTOFF_DATE, "--freeze", "--prediction-id", "001",
        "--predictions-dir", str(predictions_dir), "--output-dir", str(predictions_dir.parent / "outputs"),
    ]
    try:
        rc = predict_module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0


def test_main_produces_audit_report_and_files(module, db_path, tmp_path, capsys):
    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze(db_path, predictions_dir)

    output_dir = tmp_path / "audit_outputs"
    argv_backup = sys.argv
    sys.argv = [
        "34_audit_neo_win_player.py",
        "--db", str(db_path),
        "--predictions-dir", str(predictions_dir),
        "--prediction-id", "001",
        "--game-code", LIVE_GAME_CODE,
        "--cutoff-date", CUTOFF_DATE,
        "--player-a-name", "서교림",
        "--player-b-name", "박현경",
        "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "SEO GYO-RIM AUDIT" in out
    assert "PARK vs SEO" in out
    assert "WIN TREATMENT" in out
    assert "VERDICT" in out
    assert "BETA #001 INTEGRITY" in out
    assert "Frozen artifact modified: NO" in out

    assert (output_dir / "BETA001_SEOGYORIM_AUDIT.md").exists()
    assert (output_dir / "BETA001_TOP10_AUDIT.csv").exists()


def test_main_fails_cleanly_when_snapshot_missing(module, db_path, tmp_path):
    argv_backup = sys.argv
    sys.argv = [
        "34_audit_neo_win_player.py",
        "--db", str(db_path),
        "--predictions-dir", str(tmp_path / "no_such_dir"),
        "--prediction-id", "001",
        "--game-code", LIVE_GAME_CODE,
        "--cutoff-date", CUTOFF_DATE,
        "--output-dir", str(tmp_path / "audit_outputs"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 5


def test_main_fails_cleanly_when_db_missing(module, tmp_path):
    argv_backup = sys.argv
    sys.argv = [
        "34_audit_neo_win_player.py",
        "--db", str(tmp_path / "nope.sqlite"),
        "--game-code", LIVE_GAME_CODE,
        "--cutoff-date", CUTOFF_DATE,
        "--output-dir", str(tmp_path / "audit_outputs"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 3
