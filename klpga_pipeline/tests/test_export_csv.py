"""Tests for src/klpga/db/export_csv.py.

Covers the real bug: a Windows run of this script exited with no error
and no output directory at all — see the module docstring in
export_csv.py for the root-cause reasoning (a pandas import-time
failure, before export_all's first line, mkdir, could even run). The
rewrite drops pandas entirely (stdlib csv + sqlite3 only) and raises a
clear FileNotFoundError instead of silently creating an empty database
at a wrong/missing --db path. These tests exercise the actual CSV
content (headers, boolean TRUE/FALSE mapping, NULL -> empty string) and
the row-count return value the CLI prints for verification."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from klpga.db.export_csv import TABLE_TO_COLUMNS, export_all

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()
    return path


def _insert_sample_rows(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date, winner_score) "
        "VALUES ('e1', 'g1', 'Test Championship', 2026, '2026-08-23', '-8')"
    )
    conn.execute(
        "INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Player One')"
    )
    conn.execute(
        "INSERT INTO player_master (player_id, player_name) VALUES ('p2', 'Player Two')"
    )
    # p1: made the cut (made_cut=1), p2: missed the cut (made_cut=0) — one
    # of each boolean value, plus a NULL prize_money to check NULL -> "".
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, withdrawn, disqualified, tie_flag, rounds_played, prize_money) "
        "VALUES ('e1', 'g1', 2026, 'p1', 'Player One', 1, 0, 0, 0, 4, 50000000)"
    )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, withdrawn, disqualified, tie_flag, rounds_played) "
        "VALUES ('e1', 'g1', 2026, 'p2', 'Player Two', 0, 0, 0, 0, 2)"
    )
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_score) "
        "VALUES ('e1', 'g1', 2026, 1, 'p1', 'Player One', 70)"
    )
    conn.commit()
    conn.close()


def test_export_all_writes_one_csv_per_table_with_correct_row_counts(db_path, tmp_path):
    _insert_sample_rows(db_path)
    out_dir = tmp_path / "csv"

    row_counts = export_all(db_path, out_dir)

    assert row_counts == {
        "tournament_master": 1,
        "player_master": 2,
        "player_event": 2,
        "player_round": 1,
        "player_stats_snapshot": 0,
    }
    for table in TABLE_TO_COLUMNS:
        assert (out_dir / f"{table}.csv").exists()


def test_export_all_creates_out_dir_even_when_every_table_is_empty(db_path, tmp_path):
    """The exact symptom of the real bug report: no rows anywhere should
    still leave a real csv/ directory with header-only CSVs, never a
    silent no-op."""
    out_dir = tmp_path / "csv"

    row_counts = export_all(db_path, out_dir)

    assert out_dir.is_dir()
    assert all(count == 0 for count in row_counts.values())
    with (out_dir / "tournament_master.csv").open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [TABLE_TO_COLUMNS["tournament_master"]]


def test_export_all_raises_clear_error_instead_of_creating_empty_db(tmp_path):
    """A nonexistent --db path must fail loudly, not have sqlite3
    silently create a fresh empty database there (which would then fail
    per-table with a confusing 'no such table' error, or worse, appear
    to "work" with all-empty CSVs)."""
    missing_db = tmp_path / "does_not_exist.sqlite"
    out_dir = tmp_path / "csv"

    with pytest.raises(FileNotFoundError):
        export_all(missing_db, out_dir)

    assert not missing_db.exists()
    assert not out_dir.exists()


def test_player_event_booleans_export_as_true_false_strings(db_path, tmp_path):
    _insert_sample_rows(db_path)
    out_dir = tmp_path / "csv"
    export_all(db_path, out_dir)

    with (out_dir / "player_event.csv").open(encoding="utf-8") as f:
        rows = {row["player_id"]: row for row in csv.DictReader(f)}

    assert rows["p1"]["made_cut"] == "TRUE"
    assert rows["p1"]["withdrawn"] == "FALSE"
    assert rows["p1"]["disqualified"] == "FALSE"
    assert rows["p2"]["made_cut"] == "FALSE"


def test_null_columns_export_as_empty_string_not_the_word_none(db_path, tmp_path):
    _insert_sample_rows(db_path)
    out_dir = tmp_path / "csv"
    export_all(db_path, out_dir)

    with (out_dir / "player_event.csv").open(encoding="utf-8") as f:
        rows = {row["player_id"]: row for row in csv.DictReader(f)}

    # p2 was inserted with no prize_money -> real SQL NULL.
    assert rows["p2"]["prize_money"] == ""
    assert rows["p1"]["prize_money"] == "50000000"
