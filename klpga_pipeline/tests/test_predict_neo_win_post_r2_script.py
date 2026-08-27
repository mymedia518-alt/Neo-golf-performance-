"""Tests for scripts/44_predict_neo_win_post_r2.py — offline, against a
synthetic DB with a real frozen PRE snapshot plus real round_number=1/2
player_round rows and player_event.made_cut facts."""
from __future__ import annotations

import csv
import hashlib
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


def test_warn_and_proceeds_when_unexplained_players_exist(module, tmp_path, capsys):
    """Roadmap decision: UNKNOWN players (no positive evidence either
    way) must WARN and still generate — never HARD_STOP just because
    ENTRY_FIELD != COMPLETED_R2 field. Only 2 of 5 players have a real
    round_number=2 score; the other 3 have no player_event row at all
    (no WD/DQ/DNS evidence, no positive participation evidence either)."""
    conn, db_path = _base_db(tmp_path)
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
    assert "readiness verdict: WARN" in out
    assert "WARN:" in out
    assert "3 player(s) could not be positively classified" in out
    # WARN still proceeds — output IS written, never silently blocked.
    assert (output_dir / "BETA_R2_FULL.csv").exists()
    assert (tmp_path / "neo_tournament_history" / GAME_CODE / "R2.json").exists()

    with open(output_dir / "BETA_R2_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    # every ENTRY_FIELD player still appears — never disappears just because a score is absent.
    assert len(rows) == 5
    row_by_code = {r["player_code"]: r for r in rows}
    for player_id in PLAYERS[2:]:
        assert row_by_code[player_id]["player_status"] == "UNKNOWN"
        assert row_by_code[player_id]["neo_win_pct"] == "unavailable"  # never fabricated


def test_hard_stop_when_collection_missing_evidence_exists(module, tmp_path, capsys):
    """A player with POSITIVE evidence of participation (rounds_played
    covering round 2, no WD/DQ) but no round_number=2 row is a real
    ingestion gap — HARD_STOP, nothing written, unlike a plain UNKNOWN."""
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS[:4]):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
    # PLAYERS[4] ("E") has real evidence of playing >=2 rounds, no WD/DQ, but NO round_number=2 row.
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

    output_dir = tmp_path / "outputs" / "beta_r2"
    history_dir = tmp_path / "neo_tournament_history"
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
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
    assert not (output_dir / "BETA_R2_FULL.csv").exists()
    assert not (history_dir / GAME_CODE / "R2.json").exists()


def test_hard_stop_when_zero_r2_rows_exist_at_all(module, tmp_path, capsys):
    conn, db_path = _base_db(tmp_path)
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)

    output_dir = tmp_path / "outputs" / "beta_r2"
    history_dir = tmp_path / "neo_tournament_history"
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
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
    assert not (output_dir / "BETA_R2_FULL.csv").exists()


def test_hard_stop_on_round_3_leakage(module, tmp_path, capsys):
    """Future-data leakage guard: any round_number=3 row already
    existing must HARD STOP a POST-R2 generation — same discipline as
    scripts/35's round_number=2 guard."""
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 3, 'A', 'A', 68, -4)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)

    output_dir = tmp_path / "outputs" / "beta_r2"
    history_dir = tmp_path / "neo_tournament_history"
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
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
    assert "round_number=3" in out
    assert "leak" in out.lower()
    assert not (output_dir / "BETA_R2_FULL.csv").exists()
    assert not (history_dir / GAME_CODE / "R2.json").exists()


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

    # every entrant has a real round_number=2 score here -> ACTIVE status, never fabricated.
    for player_id in PLAYERS:
        assert row_by_code[player_id]["player_status"] == "ACTIVE"

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


def test_missing_player_reported_with_evidence_only_classification(module, tmp_path, capsys):
    """R2-architecture player-state model: a player excluded from the
    simulation (here, because player_event.made_cut was never
    recorded) must be reported with a real, evidence-only
    classification from klpga.neo_win.player_status — never a bare,
    unexplained player_code."""
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
    # Every player except E gets a real player_event row (made_cut known).
    # E has REAL r1+r2 scores but no player_event row at all -> made_cut
    # lookup is None -> excluded from the simulation despite complete round data.
    for player_id in PLAYERS:
        if player_id == "E":
            continue
        conn.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, '1', 1, 1, 4, -6)",
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
        "--n-simulations", "300", "--seed", "3", "--freeze",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "Missing r1/r2/cut data" in out
    assert "'E'" in out
    assert "Evidence-only classification" in out
    # E DOES have a real R2 score — the classifier honestly reports that, revealing the
    # actual exclusion cause (missing made_cut fact) was separate from R2 score availability.
    assert "  - E: COMPLETED —" in out


def test_wd_player_never_receives_fabricated_probabilities(module, tmp_path, capsys):
    """A real WD player has zero round data — the output must show
    them (never disappear) with an explicit status and 'unavailable'
    probabilities, never a fabricated number of any kind (not even 0)."""
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS[:4]):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, withdrawn, rounds_played, score_to_par) VALUES "
        "(?, ?, 2026, 'E', 'E', 'WD', NULL, 0, 1, 1, NULL)",
        (GAME_CODE, GAME_CODE),
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

    with open(output_dir / "BETA_R2_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    row_by_code = {r["player_code"]: r for r in rows}
    assert "E" in row_by_code  # never disappears
    assert row_by_code["E"]["player_status"] == "WD"
    for field in ("neo_win_pct", "neo_cut_pct", "neo_r3_pct", "neo_final_pct", "neo_top10_pct"):
        assert row_by_code["E"][field] == "unavailable"


def test_pre_and_r1_frozen_artifacts_remain_byte_for_byte_unchanged(module, tmp_path):
    conn, db_path = _base_db(tmp_path)
    for i, player_id in enumerate(PLAYERS):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 2, ?, ?, ?, ?)",
            (GAME_CODE, GAME_CODE, player_id, player_id, 70 - i, -i),
        )
    conn.commit()
    conn.close()

    predictions_dir = tmp_path / "neo_win_predictions"
    _pre_freeze(db_path, predictions_dir)
    pre_json = predictions_dir / "2027" / "neo_win_001_R2TEST.json"
    assert pre_json.exists()
    before_hash = hashlib.sha256(pre_json.read_bytes()).hexdigest()

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
    assert hashlib.sha256(pre_json.read_bytes()).hexdigest() == before_hash


def test_r2_supersedes_a_stale_missing_marker_same_architecture_as_r1(module, tmp_path):
    """The same append-only correction mechanism scripts/35 uses for
    R1 must also protect R2: a stale HISTORICAL_SNAPSHOT_MISSING marker
    from an earlier run must not permanently block a later real R2
    result — it stays preserved, and the real result is recorded as a
    superseding event."""
    from klpga.neo_win.tournament_history import (
        STAGE_R2,
        build_missing_stage_marker,
        read_effective_history_stage,
        read_full_history_events,
        write_history_stage_atomic,
    )

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
    marker = build_missing_stage_marker(GAME_CODE, STAGE_R2, reason="stale, before real R2 existed", recorded_at_utc="2027-01-01T00:00:00Z")
    marker_path = write_history_stage_atomic(marker, history_dir)
    marker_bytes_before = marker_path.read_bytes()

    output_dir = tmp_path / "outputs" / "beta_r2"
    argv_backup = sys.argv
    sys.argv = [
        "44_predict_neo_win_post_r2.py", "--db", str(db_path), "--game-code", GAME_CODE,
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

    effective = read_effective_history_stage(history_dir, GAME_CODE, STAGE_R2)
    assert effective.status == "RECORDED"

    events = read_full_history_events(history_dir, GAME_CODE, STAGE_R2)
    assert len(events) == 2
    assert events[0].status == "HISTORICAL_SNAPSHOT_MISSING"
    assert events[1].status == "RECORDED"
