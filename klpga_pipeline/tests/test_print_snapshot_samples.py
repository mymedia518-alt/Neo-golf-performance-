"""Tests for scripts/10_print_snapshot_samples.py — read-only, must
never write anything, and must format REAL/None values to 2dp / '-'."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "10_print_snapshot_samples.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("print_samples_script", SCRIPT_PATH)
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
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Player One')")
    conn.execute(
        "INSERT INTO player_stats_snapshot "
        "(player_id, season, as_of_date, snapshot_type, related_event_id, "
        "derived_tournaments_played, derived_wins, derived_avg_round_score, collected_at) "
        "VALUES ('p1', 2026, '2026-08-25', 'derived_trailing100', NULL, 3, 1, 71.5, '2026-08-25T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    return path


def test_print_samples_formats_floats_to_two_decimals_and_none_as_dash(module, db_path, capsys):
    exit_code = module.print_samples(db_path, limit=10)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Player One" in out
    assert "71.50" in out  # not "71.5"
    assert " - " in out or out.strip().endswith("-")  # unset derived_* columns


def test_print_samples_reports_error_when_no_rows_yet(module, tmp_path, capsys):
    empty_db = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(empty_db)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()

    exit_code = module.print_samples(empty_db, limit=10)
    assert exit_code == 1


def test_print_samples_never_writes_to_the_database(module, db_path):
    before = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM player_stats_snapshot").fetchone()[0]
    module.print_samples(db_path, limit=10)
    after = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM player_stats_snapshot").fetchone()[0]
    assert before == after
