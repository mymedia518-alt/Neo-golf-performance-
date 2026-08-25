"""Tests for scripts/09_build_player_stats_snapshot.py's build()
orchestration: migration + compute + the full DELETE/re-INSERT
regenerate (never an incremental upsert, and never a duplicate-row
accumulation across re-runs — see that script's module docstring for
why an upsert would be wrong here: related_event_id is always NULL for
this snapshot type, and SQLite never treats two NULLs as conflicting
under a UNIQUE constraint)."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "09_build_player_stats_snapshot.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_snapshot_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def build_module():
    return _load_build_module()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('T1', 'T1', 'Tournament T1', 2026, '2026-03-01')"
    )
    conn.execute(
        "INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Player One')"
    )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, finish_position_numeric, score_to_par, rounds_played) "
        "VALUES ('T1', 'T1', 2026, 'p1', 'Player One', 1, 1, -8, 4)"
    )
    for r, score in enumerate([70, 67, 69, 74], start=1):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, "
            "player_name, round_score) VALUES ('T1', 'T1', 2026, ?, 'p1', 'Player One', ?)",
            (r, score),
        )
    conn.commit()
    conn.close()
    return path


def test_build_populates_one_row_per_player_with_the_snapshot_metadata(build_module, db_path):
    rows = build_module.build(db_path, schema_path=SCHEMA_PATH)
    assert len(rows) == 1
    assert rows[0]["player_id"] == "p1"
    assert rows[0]["derived_wins"] == 1

    conn = sqlite3.connect(db_path)
    stored = conn.execute(
        "SELECT player_id, season, as_of_date, snapshot_type, related_event_id, derived_wins, collected_at "
        "FROM player_stats_snapshot"
    ).fetchall()
    conn.close()

    assert len(stored) == 1
    player_id, season, as_of_date, snapshot_type, related_event_id, derived_wins, collected_at = stored[0]
    assert player_id == "p1"
    assert season == 2026
    assert as_of_date == "2026-03-01"
    assert snapshot_type == "derived_trailing100"
    assert related_event_id is None
    assert derived_wins == 1
    assert collected_at  # non-empty ISO timestamp


def test_rerunning_build_replaces_rows_instead_of_duplicating(build_module, db_path):
    build_module.build(db_path, schema_path=SCHEMA_PATH)
    build_module.build(db_path, schema_path=SCHEMA_PATH)  # re-run against the unchanged dataset

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM player_stats_snapshot WHERE snapshot_type = 'derived_trailing100'"
    ).fetchone()[0]
    conn.close()

    assert count == 1  # not 2 — proves the NULL-uniqueness pitfall is actually avoided


def test_leaves_official_data_center_columns_null(build_module, db_path):
    build_module.build(db_path, schema_path=SCHEMA_PATH)

    conn = sqlite3.connect(db_path)
    sg_total, gir, driving_distance = conn.execute(
        "SELECT sg_total, gir, driving_distance FROM player_stats_snapshot WHERE player_id = 'p1'"
    ).fetchone()
    conn.close()

    assert sg_total is None
    assert gir is None
    assert driving_distance is None


def test_raises_clear_error_on_empty_tournament_master(build_module, tmp_path):
    empty_db = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(empty_db)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()

    with pytest.raises(RuntimeError, match="tournament_master is empty"):
        build_module.build(empty_db, schema_path=SCHEMA_PATH)
