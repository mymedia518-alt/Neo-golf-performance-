"""Tests for scripts/40_redteam_beta001c_top20.py — offline, against a
small synthetic DB and a hand-written frozen snapshot JSON."""
from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "40_redteam_beta001c_top20.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("redteam_beta001c_script", SCRIPT_PATH)
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
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('LIVE', 'LIVE', 'Live', 2027, '2027-02-01', '2027-02-01')"
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'A')")
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('LIVE', 'p1', 'A', 'test', '2027-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def c_json_path(tmp_path):
    data = {
        "prediction_id": "001-C", "created_at_utc": "2027-01-01T00:00:00Z",
        "record_kind": "neo_win_beta001c_prediction_v1", "game_code": "LIVE", "tournament_name": "Live",
        "cutoff_date": "2027-01-01", "cutoff_source": "explicit_arg", "selected_model_id": "MODEL_A",
        "model_features": ["f"], "selection_decision": {}, "training_tournament_count": 5, "field_size": 1,
        "entrants_predicted": 1, "probability_sum": 1.0, "minimum_probability": 1.0, "maximum_probability": 1.0,
        "duplicate_count": 0, "null_count": 0, "non_field_count": 0, "known_limitations": [],
        "predictions": [
            {"rank": 1, "player_code": "p1", "player_name": "A", "win_probability": 1.0, "prior_events_n": 5,
             "feature_values": {}, "player_master_matched": True},
        ],
    }
    path = tmp_path / "c.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_script_writes_redteam_csv_and_summary(module, db_path, c_json_path, tmp_path, capsys):
    output_dir = tmp_path / "out"
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["prog", "--db", str(db_path), "--c-json", str(c_json_path), "--output-dir", str(output_dir)]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0
    csv_path = output_dir / "BETA001C_TOP20_REDTEAM.csv"
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["player_code"] == "p1"
    out = capsys.readouterr().out
    assert "TOP 20 RED-TEAM" in out
    assert "SUMMARY" in out


def test_script_errors_on_missing_db(module, c_json_path, tmp_path):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--db", str(tmp_path / "nope.sqlite"), "--c-json", str(c_json_path), "--output-dir", str(tmp_path / "out"),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 3
