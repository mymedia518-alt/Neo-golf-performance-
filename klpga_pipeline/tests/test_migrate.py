"""Tests for src/klpga/db/migrate.py's player_stats_snapshot migration
— must never silently drop real data, and must be a no-op once the
schema already has every derived_* column."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.db.migrate import EXPECTED_DERIVED_COLUMNS, ensure_player_stats_snapshot_schema

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"

_OLD_SHAPE_SQL = """
CREATE TABLE player_stats_snapshot (
    snapshot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id      TEXT NOT NULL,
    season         INTEGER NOT NULL,
    as_of_date     TEXT NOT NULL,
    snapshot_type  TEXT NOT NULL CHECK (snapshot_type IN ('pre_event', 'season_to_date', 'season_final')),
    related_event_id TEXT,
    scoring_average REAL,
    collected_at   TEXT NOT NULL,
    UNIQUE (player_id, season, as_of_date, snapshot_type, related_event_id)
);
"""


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def test_creates_table_fresh_when_it_does_not_exist_yet(conn):
    ensure_player_stats_snapshot_schema(conn, SCHEMA_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(player_stats_snapshot)")}
    assert EXPECTED_DERIVED_COLUMNS.issubset(cols)


def test_migrates_old_shape_when_table_is_empty(conn):
    conn.executescript(_OLD_SHAPE_SQL)
    conn.commit()

    ensure_player_stats_snapshot_schema(conn, SCHEMA_PATH)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(player_stats_snapshot)")}
    assert EXPECTED_DERIVED_COLUMNS.issubset(cols)


def test_is_a_noop_when_schema_already_current(conn):
    ensure_player_stats_snapshot_schema(conn, SCHEMA_PATH)
    conn.execute(
        "INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Player One')"
    )
    conn.execute(
        "INSERT INTO player_stats_snapshot (player_id, season, as_of_date, snapshot_type, "
        "related_event_id, derived_wins, collected_at) "
        "VALUES ('p1', 2026, '2026-08-25', 'derived_trailing100', NULL, 3, '2026-08-25T00:00:00Z')"
    )
    conn.commit()

    ensure_player_stats_snapshot_schema(conn, SCHEMA_PATH)  # must not touch existing rows

    row = conn.execute("SELECT derived_wins FROM player_stats_snapshot WHERE player_id = 'p1'").fetchone()
    assert row[0] == 3


def test_refuses_to_drop_populated_old_shape_table(conn):
    conn.executescript(_OLD_SHAPE_SQL)
    conn.execute(
        "INSERT INTO player_stats_snapshot "
        "(player_id, season, as_of_date, snapshot_type, related_event_id, scoring_average, collected_at) "
        "VALUES ('p1', 2026, '2026-08-25', 'season_final', NULL, 70.5, '2026-08-25T00:00:00Z')"
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="refusing to drop"):
        ensure_player_stats_snapshot_schema(conn, SCHEMA_PATH)

    # The old row must still be exactly where it was.
    row = conn.execute("SELECT scoring_average FROM player_stats_snapshot WHERE player_id = 'p1'").fetchone()
    assert row[0] == 70.5
