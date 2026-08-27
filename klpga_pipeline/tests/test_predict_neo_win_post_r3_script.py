"""Tests for scripts/46_predict_neo_win_post_r3.py — offline, against a
synthetic DB with a real frozen PRE snapshot, a real frozen R2 stage
(the correct R2->R3 movement baseline — NOT PRE), plus real
round_number=1/2/3 player_round rows and player_event.made_cut facts."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "46_predict_neo_win_post_r3.py"
R2_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "44_predict_neo_win_post_r2.py"
PREDICT_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "33_predict_neo_win.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "R3TEST"
CUTOFF_DATE = "2027-01-01"
PLAYERS = ["A", "B", "C", "D", "E"]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "predict_neo_win_post_r3_script")


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
    predict_module = _load(PREDICT_SCRIPT_PATH, "predict_neo_win_script_for_r3")
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


def _r2_freeze(db_path, predictions_dir, history_dir):
    r2_module = _load(R2_SCRIPT_PATH, "predict_neo_win_post_r2_script_for_r3")
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(predictions_dir.parent / "r2_outputs"), "--history-dir", str(history_dir),
        "--n-simulations", "200", "--seed", "5", "--freeze",
    ]
    try:
        assert r2_module.main() == 0
    finally:
        sys.argv = argv_backup


def _r1_r2_field_with_cut(conn):
    """A makes the cut (through R2); the rest are real, confirmed CUT
    players (made_cut=0, corroborated by rounds_played=2). No R3 data
    yet — callers add A's real R3 row AFTER freezing R2, so scripts/44's
    own round_number=3 leakage guard never fires during the R2 freeze."""
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
        "(?, ?, 2026, 'A', 'A', '1', 1, 1, 3, -8)",
        (GAME_CODE, GAME_CODE),
    )
    for player_id in PLAYERS[1:]:
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, 'CUT', NULL, 0, 2, -2)",
            (GAME_CODE, GAME_CODE, player_id, player_id),
        )


def _add_a_real_r3_row(conn):
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 3, 'A', 'A', 66, -6)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()


def test_warn_and_proceeds_when_unexplained_players_exist(module, tmp_path, capsys):
    """Only A and B have real R1/R2/R3 data and a real made_cut=True
    fact; C, D, E have NO player_event row and NO round data at all —
    genuinely UNKNOWN (no positive evidence either way), not a
    collection gap — so the field must WARN and still proceed."""
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS[:2]):
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
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 3, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 68 - i, -6 - i),
        )
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 3, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, str(i + 1), i + 1, -6 + i),
        )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "readiness verdict: WARN" in out
    assert "WARN:" in out
    assert (output_dir / "BETA_R3_FULL.csv").exists()
    assert (history_dir / GAME_CODE / "R3.json").exists()

    with open(output_dir / "BETA_R3_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5
    row_by_code = {r["player_code"]: r for r in rows}
    for player_id in PLAYERS[2:]:
        assert row_by_code[player_id]["player_status"] == "UNKNOWN"
        assert row_by_code[player_id]["neo_win_pct"] == "unavailable"


def test_hard_stop_when_collection_missing_evidence_exists(module, tmp_path, capsys):
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
    for i, player_id in enumerate(PLAYERS[:4]):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 3, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 68 - i, -6 - i),
        )
    # PLAYERS[4] ("E") has real evidence of playing >=3 rounds, no WD/DQ/CUT, but NO round_number=3 row.
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, 'E', 'E', 'T10', 10, 1, 4, -2)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "STATUS: HARD_STOP" in out
    assert "'E'" in out
    assert "ingestion gap" in out
    assert not (output_dir / "BETA_R3_FULL.csv").exists()
    assert not (history_dir / GAME_CODE / "R3.json").exists()


def test_hard_stop_when_zero_r3_rows_exist_at_all(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "STATUS: HARD_STOP" in out
    assert "official ingestion for this round has not happened" in out
    assert not (output_dir / "BETA_R3_FULL.csv").exists()


def test_hard_stop_on_round_4_leakage(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    _r1_r2_field_with_cut(conn)
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)

    conn = sqlite3.connect(db_path)
    _add_a_real_r3_row(conn)
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 4, 'A', 'A', 65, -7)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "STATUS: HARD_STOP" in out
    assert "round_number=4" in out
    assert "leak" in out.lower()
    assert not (output_dir / "BETA_R3_FULL.csv").exists()
    assert not (history_dir / GAME_CODE / "R3.json").exists()


def test_complete_r3_data_generates_freezes_and_records_history(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    _r1_r2_field_with_cut(conn)
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)

    conn = sqlite3.connect(db_path)
    _add_a_real_r3_row(conn)
    conn.close()

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
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

    csv_path = output_dir / "BETA_R3_FULL.csv"
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5
    codes = [r["player_code"] for r in rows]
    assert len(codes) == len(set(codes))
    # no cut/qualification-probability column of any kind — already decided by R3.
    assert "neo_cut_pct" not in rows[0]
    assert "neo_r3_pct" not in rows[0]
    assert "neo_final_pct" not in rows[0]

    row_by_code = {r["player_code"]: r for r in rows}
    assert row_by_code["A"]["neo_win_pct"] == "100.0"
    assert row_by_code["A"]["player_status"] == "ACTIVE"
    for player_id in PLAYERS[1:]:
        assert row_by_code[player_id]["neo_win_pct"] == "0.0"
        assert row_by_code[player_id]["player_status"] == "CUT"

    # R2->R3 movement is present (frozen R2 stage exists) — never "unavailable" here.
    assert row_by_code["A"]["r2_win_pct"] != "unavailable"
    assert row_by_code["A"]["r2_to_r3_win_change_pct"] != "unavailable"

    assert (history_dir / GAME_CODE / "R3.json").exists()

    # rerun is idempotent (SKIP + LOG), never a crash, never a second write.
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
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


def test_wd_player_never_receives_fabricated_probabilities(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS[:4]):
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
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 3, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 68 - i, -6 - i),
        )
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 3, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, str(i + 1), i + 1, -6 + i),
        )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, withdrawn, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, 'E', 'E', 'WD', NULL, 0, 1, 2, NULL)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0

    with open(output_dir / "BETA_R3_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    row_by_code = {r["player_code"]: r for r in rows}
    assert "E" in row_by_code  # never disappears
    assert row_by_code["E"]["player_status"] == "WD"
    for field in ("neo_win_pct", "neo_top5_pct", "neo_top10_pct", "neo_top20_pct"):
        assert row_by_code["E"][field] == "unavailable"


def test_pre_r1_r2_frozen_artifacts_remain_byte_for_byte_unchanged(module, tmp_path):
    conn, db_path = _base_db(tmp_path)
    _r1_r2_field_with_cut(conn)
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    pre_json = predictions_dir / "2027" / "neo_win_001_R3TEST.json"
    assert pre_json.exists()
    pre_hash_before = hashlib.sha256(pre_json.read_bytes()).hexdigest()

    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)
    r2_json = history_dir / GAME_CODE / "R2.json"
    assert r2_json.exists()
    r2_hash_before = hashlib.sha256(r2_json.read_bytes()).hexdigest()

    conn = sqlite3.connect(db_path)
    _add_a_real_r3_row(conn)
    conn.close()

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir), "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    assert hashlib.sha256(pre_json.read_bytes()).hexdigest() == pre_hash_before
    assert hashlib.sha256(r2_json.read_bytes()).hexdigest() == r2_hash_before


def test_r3_supersedes_a_stale_missing_marker_same_architecture_as_r2(module, tmp_path):
    from klpga.neo_win.tournament_history import (
        STAGE_R3,
        build_missing_stage_marker,
        read_effective_history_stage,
        read_full_history_events,
        write_history_stage_atomic,
    )

    conn, db_path = _base_db(tmp_path)
    _r1_r2_field_with_cut(conn)
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    history_dir = tmp_path / "neo_tournament_history"
    _r2_freeze(db_path, predictions_dir, history_dir)

    conn = sqlite3.connect(db_path)
    _add_a_real_r3_row(conn)
    conn.close()

    marker = build_missing_stage_marker(GAME_CODE, STAGE_R3, reason="stale, before real R3 existed", recorded_at_utc="2027-01-01T00:00:00Z")
    marker_path = write_history_stage_atomic(marker, history_dir)
    marker_bytes_before = marker_path.read_bytes()

    output_dir = tmp_path / "outputs" / "beta_r3"
    argv_backup = sys.argv
    sys.argv = [
        "46_predict_neo_win_post_r3.py", "--db", str(db_path), "--game-code", GAME_CODE,
        "--predictions-dir", str(predictions_dir), "--pre-cutoff-date", CUTOFF_DATE,
        "--output-dir", str(output_dir), "--history-dir", str(history_dir),
        "--n-simulations", "300", "--seed", "9", "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0

    assert marker_path.read_bytes() == marker_bytes_before  # marker untouched

    effective = read_effective_history_stage(history_dir, GAME_CODE, STAGE_R3)
    assert effective.status == "RECORDED"

    events = read_full_history_events(history_dir, GAME_CODE, STAGE_R3)
    assert len(events) == 2
    assert events[0].status == "HISTORICAL_SNAPSHOT_MISSING"
    assert events[1].status == "RECORDED"
