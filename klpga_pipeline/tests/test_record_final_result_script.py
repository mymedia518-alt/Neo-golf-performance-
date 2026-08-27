"""Tests for scripts/47_record_final_result.py — a thin CLI wrapper
around the already-existing klpga.neo_win.tournament_history.
build_final_stage_entry. This script performs NO simulation and NO
probability computation — it only reads the REAL, already-decided
result from tournament_master.winner / player_event and freezes it."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "47_record_final_result.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "FINALTEST"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "record_final_result_script")


def _base_db(tmp_path, *, winner=None):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date, winner, field_size) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04', ?, 5)",
        (GAME_CODE, GAME_CODE, winner),
    )
    conn.commit()
    return conn, path


def test_not_yet_final_when_winner_is_null(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path, winner=None)
    conn.close()

    history_dir = tmp_path / "neo_tournament_history"
    argv_backup = sys.argv
    sys.argv = [
        "47_record_final_result.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "STATUS: NOT_YET_FINAL" in out
    assert not (history_dir / GAME_CODE / "FINAL.json").exists()


def test_confirmed_winner_generates_freezes_and_records_history(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path, winner="A")
    for i, player_id in enumerate(["A", "B", "C", "D", "E"]):
        conn.execute(
            "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id)
        )
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, str(i + 1), i + 1, -10 + i),
        )
    conn.commit()
    conn.close()

    history_dir = tmp_path / "neo_tournament_history"
    argv_backup = sys.argv
    sys.argv = [
        "47_record_final_result.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "STATUS: FINAL_CONFIRMED" in out
    assert "WINNER (tournament_master.winner): A" in out
    assert "CONFIRMED WINNER PLAYER(S)" in out
    assert "['A']" in out
    assert "FROZEN" in out

    from klpga.neo_win.tournament_history import STAGE_FINAL, read_effective_history_stage

    effective = read_effective_history_stage(history_dir, GAME_CODE, STAGE_FINAL)
    assert effective is not None
    assert effective.status == "RECORDED"
    assert len(effective.entrants) == 5
    a_entry = next(e for e in effective.entrants if e.player_code == "A")
    assert a_entry.actual_confirmed_winner is True
    assert a_entry.actual_finish_position_numeric == 1

    # rerun is idempotent (SKIP + LOG), never a crash, never a second write.
    argv_backup = sys.argv
    sys.argv = [
        "47_record_final_result.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc2 = module.main()
    finally:
        sys.argv = argv_backup
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "SKIP + LOG" in out2


def test_winner_set_but_no_matching_player_row_is_disclosed_not_fabricated(module, tmp_path, capsys):
    """tournament_master.winner names someone with no player_event
    finish_position_numeric==1 match — a real, disclosed discrepancy,
    never silently treated as a confirmed win."""
    conn, db_path = _base_db(tmp_path, winner="Nobody Real")
    conn.execute(
        "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('A', 'A')"
    )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, 'A', 'A', '1', 1, 1, 4, -10)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    history_dir = tmp_path / "neo_tournament_history"
    argv_backup = sys.argv
    sys.argv = [
        "47_record_final_result.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "CONFIRMED WINNER PLAYER(S) (finish_position_numeric==1 AND name match): NONE" in out
    assert "real, disclosed discrepancy, not fabricated" in out


def test_no_db_writes_read_only(module, tmp_path):
    """This script only ever opens the DB in read-only mode."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "mode=ro" in source
