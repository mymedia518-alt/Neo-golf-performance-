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
    # Register in sys.modules BEFORE exec: scripts/35 now defines its own
    # @dataclass classes under `from __future__ import annotations` —
    # dataclasses' string-annotation resolution needs sys.modules[name]
    # to already point at this module, or it fails with an AttributeError.
    sys.modules[name] = module
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


def test_hard_stop_when_round_2_data_already_exists(module, db_path, tmp_path, capsys):
    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze_pre(db_path, predictions_dir)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 2, 'A', 'A', 68, -2)",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

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
    assert rc == 7
    out = capsys.readouterr().out
    assert "HARD STOP" in out
    assert "round_number=2" in out
    assert not output_dir.exists() or not any(output_dir.iterdir())


def test_neo_r3_and_final_pct_are_aliases_of_make_cut_pct(module, db_path, tmp_path):
    import csv as csv_module

    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze_pre(db_path, predictions_dir)
    output_dir = tmp_path / "outputs" / "beta001_r1"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--predictions-dir", str(predictions_dir),
        "--pre-prediction-id", "001", "--pre-cutoff-date", CUTOFF_DATE,
        "--n-simulations", "300", "--seed", "9", "--output-dir", str(output_dir),
    ]
    try:
        assert module.main() == 0
    finally:
        sys.argv = argv_backup

    with open(output_dir / "BETA001_R1_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv_module.DictReader(f))
    assert rows
    for row in rows:
        assert row["neo_r3_pct"] == row["post_r1_make_cut_pct"]
        assert row["neo_final_pct"] == row["post_r1_make_cut_pct"]


def test_r2_absence_reported_in_console_output(module, db_path, tmp_path, capsys):
    predictions_dir = tmp_path / "neo_win_predictions"
    _freeze_pre(db_path, predictions_dir)
    output_dir = tmp_path / "outputs" / "beta001_r1"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--predictions-dir", str(predictions_dir),
        "--pre-prediction-id", "001", "--pre-cutoff-date", CUTOFF_DATE,
        "--n-simulations", "300", "--seed", "3", "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "R2 DATA: 0 round_number=2 rows found" in out


PLAYERS = ["A", "B", "C", "D", "E"]


def _freeze_pre_c(c_predictions_dir):
    """Freezes a synthetic BETA #001-C PRE snapshot directly (not via
    scripts/38, which needs a full taxonomy/backtest pipeline) — same
    shape scripts/38 itself writes: feature_values holds RAW
    prior_avg_round_score_to_par / neo_consistency_stddev, exactly as
    verified in scripts/38 (feature_values={f: row_by_code[code].get(f)
    ...}, read straight off the live-field row before standardization)."""
    from klpga.neo_win.beta001c_archive import (
        NeoWinCEntrantSnapshot,
        NeoWinCPredictionSnapshot,
        RECORD_KIND as C_RECORD_KIND,
        write_neo_win_c_snapshot_atomic,
    )

    entrants = tuple(
        NeoWinCEntrantSnapshot(
            rank=i + 1, player_code=p, player_name=p, win_probability=1.0 / len(PLAYERS),
            prior_events_n=10,
            feature_values={
                "prior_avg_round_score_to_par": -1.0 - i * 0.2,
                "prior_recent_form_10": -1.0,
                "neo_consistency_stddev": 2.0,
            },
        )
        for i, p in enumerate(PLAYERS)
    )
    snapshot = NeoWinCPredictionSnapshot(
        prediction_id="001-C-FINAL", created_at_utc="2027-01-01T00:00:00Z", record_kind=C_RECORD_KIND,
        game_code=GAME_CODE, tournament_name="Live Test Open", cutoff_date=CUTOFF_DATE,
        cutoff_source="explicit_arg", selected_model_id="MODEL_A",
        model_features=("prior_avg_round_score_to_par", "prior_recent_form_10", "neo_consistency_stddev"),
        selection_decision={"selected_model_id": "MODEL_A"}, training_tournament_count=8,
        field_size=len(PLAYERS), entrants_predicted=len(PLAYERS), probability_sum=1.0,
        minimum_probability=1.0 / len(PLAYERS), maximum_probability=1.0 / len(PLAYERS),
        duplicate_count=0, null_count=0, non_field_count=0, known_limitations=(),
        predictions=entrants,
    )
    write_neo_win_c_snapshot_atomic(snapshot, c_predictions_dir)
    return snapshot


def test_adapt_beta001c_snapshot_maps_feature_values_to_raw_attrs(module):
    from klpga.neo_win.beta001c_archive import (
        NeoWinCEntrantSnapshot,
        NeoWinCPredictionSnapshot,
        RECORD_KIND as C_RECORD_KIND,
    )

    c_snapshot = NeoWinCPredictionSnapshot(
        prediction_id="001-C-FINAL", created_at_utc="t", record_kind=C_RECORD_KIND, game_code="G",
        tournament_name="T", cutoff_date="2027-01-01", cutoff_source="explicit_arg", selected_model_id="MODEL_A",
        model_features=("prior_avg_round_score_to_par", "neo_consistency_stddev"), selection_decision={},
        training_tournament_count=5, field_size=1, entrants_predicted=1, probability_sum=0.3,
        minimum_probability=0.3, maximum_probability=0.3, duplicate_count=0, null_count=0, non_field_count=0,
        known_limitations=(),
        predictions=(
            NeoWinCEntrantSnapshot(
                rank=1, player_code="p1", player_name="A", win_probability=0.3, prior_events_n=5,
                feature_values={"prior_avg_round_score_to_par": -1.2, "neo_consistency_stddev": 2.5},
            ),
        ),
    )
    adapted = module._adapt_beta001c_snapshot(c_snapshot)
    assert adapted.prediction_id == "001-C-FINAL"
    assert adapted.tournament_name == "T"
    assert adapted.cutoff_date == "2027-01-01"
    e = adapted.predictions[0]
    assert e.player_code == "p1" and e.player_name == "A"
    assert e.win_probability == 0.3
    assert e.prior_avg_round_score_to_par == -1.2
    assert e.neo_consistency_stddev == 2.5


def test_pre_family_beta001c_accepts_frozen_c_pre_and_records_history(module, db_path, tmp_path, capsys):
    import csv as csv_module

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    _freeze_pre_c(c_predictions_dir)

    predictions_dir = tmp_path / "neo_win_predictions"
    history_dir = tmp_path / "neo_tournament_history"
    output_dir = tmp_path / "outputs" / "beta001_r1_c"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE,
        "--pre-family", "beta001c", "--c-predictions-dir", str(c_predictions_dir),
        "--pre-prediction-id", "001-C-FINAL", "--pre-cutoff-date", CUTOFF_DATE,
        "--predictions-dir", str(predictions_dir), "--history-dir", str(history_dir),
        "--n-simulations", "400", "--seed", "11", "--output-dir", str(output_dir),
        "--freeze", "--prediction-id", "001-C-R1",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0
    out = capsys.readouterr().out
    assert "Tournament history (PRE->R1): RECORDED at" in out

    with open(output_dir / "BETA001_R1_FULL.csv", encoding="utf-8-sig") as f:
        rows = list(csv_module.DictReader(f))
    assert len(rows) == len(PLAYERS)
    total_win = sum(float(r["post_r1_win_pct"]) for r in rows if r["post_r1_win_pct"])
    assert total_win == pytest.approx(100.0, abs=1.0)
    codes = [r["player_code"] for r in rows]
    assert len(codes) == len(set(codes))

    round_update_json = predictions_dir / "2027" / "neo_win_001-C-R1_R1TEST.json"
    assert round_update_json.exists()
    data = json.loads(round_update_json.read_text(encoding="utf-8"))
    assert data["pre_prediction_id"] == "001-C-FINAL"

    from klpga.neo_win.tournament_history import history_stage_path, read_history_stage

    history_path = history_stage_path(history_dir, GAME_CODE, "R1")
    assert history_path.exists()
    recorded = read_history_stage(history_path)
    assert recorded.status == "RECORDED"
    assert recorded.source_prediction_id == "001-C-R1"
    assert len(recorded.entrants) == len(PLAYERS)


def test_pre_family_beta001c_history_write_is_skip_log_when_r1_already_marked_missing(module, db_path, tmp_path, capsys):
    from klpga.neo_win.tournament_history import (
        build_missing_stage_marker,
        history_stage_path,
        read_history_stage,
        write_history_stage_atomic,
    )

    history_dir = tmp_path / "neo_tournament_history"
    marker = build_missing_stage_marker(
        GAME_CODE, "R1", reason="test: pre-existing missing marker", recorded_at_utc="2027-01-01T00:00:00Z"
    )
    write_history_stage_atomic(marker, history_dir)

    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    _freeze_pre_c(c_predictions_dir)
    predictions_dir = tmp_path / "neo_win_predictions"
    output_dir = tmp_path / "outputs" / "beta001_r1_c2"
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(db_path), "--game-code", GAME_CODE,
        "--pre-family", "beta001c", "--c-predictions-dir", str(c_predictions_dir),
        "--pre-prediction-id", "001-C-FINAL", "--pre-cutoff-date", CUTOFF_DATE,
        "--predictions-dir", str(predictions_dir), "--history-dir", str(history_dir),
        "--n-simulations", "300", "--seed", "12", "--output-dir", str(output_dir),
        "--freeze", "--prediction-id", "001-C-R1",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0  # the round-update snapshot itself still freezes successfully
    out = capsys.readouterr().out
    assert "SKIP + LOG" in out

    round_update_json = predictions_dir / "2027" / "neo_win_001-C-R1_R1TEST.json"
    assert round_update_json.exists()

    # the pre-existing MISSING marker must remain untouched — never silently overwritten.
    still = read_history_stage(history_stage_path(history_dir, GAME_CODE, "R1"))
    assert still.status == "HISTORICAL_SNAPSHOT_MISSING"


def test_pre_family_beta001c_rejects_prediction_id_001(module, tmp_path):
    argv_backup = sys.argv
    sys.argv = [
        "35_predict_neo_win_post_r1.py",
        "--db", str(tmp_path / "nope.sqlite"), "--game-code", GAME_CODE,
        "--pre-family", "beta001c", "--pre-cutoff-date", CUTOFF_DATE,
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == 2


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
