"""Tests for the tournament_entry storage layer:
  - src/klpga/db/migrate.py's ensure_tournament_entry_schema (additive,
    never touches tournament_master/player_master/player_event/
    player_round)
  - src/klpga/db/upsert.py's upsert_tournament_entry (idempotent by
    (game_code, player_code))
  - src/klpga/collectors/entry_list.py's build_tournament_entry_rows
    (pure row-shaping, no DB access, no fabricated fields)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.collectors.entry_list import build_tournament_entry_rows
from klpga.db.migrate import ensure_tournament_entry_schema
from klpga.db.upsert import (
    upsert_player,
    upsert_player_event,
    upsert_tournament,
    upsert_tournament_entry,
)
from klpga.parsers.entry_list_parser import EntryRow

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"

# A production-like DB shape from BEFORE tournament_entry existed —
# only the 4 validated tables, matching schema.sql's DDL for them
# exactly as of this table's introduction.
_PRE_ENTRY_TABLE_SHAPE_SQL = """
CREATE TABLE tournament_master (
    event_id TEXT PRIMARY KEY, game_code TEXT NOT NULL UNIQUE,
    event_name TEXT NOT NULL, season INTEGER NOT NULL,
    start_date TEXT, end_date TEXT NOT NULL
);
CREATE TABLE player_master (
    player_id TEXT PRIMARY KEY, player_name TEXT NOT NULL
);
CREATE TABLE player_event (
    event_id TEXT NOT NULL, game_code TEXT NOT NULL, season INTEGER NOT NULL,
    player_id TEXT NOT NULL, player_name TEXT NOT NULL,
    PRIMARY KEY (event_id, player_id)
);
CREATE TABLE player_round (
    event_id TEXT NOT NULL, game_code TEXT NOT NULL, season INTEGER NOT NULL,
    round_number INTEGER NOT NULL, player_id TEXT NOT NULL, player_name TEXT NOT NULL,
    PRIMARY KEY (event_id, player_id, round_number)
);
"""


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


@pytest.fixture()
def full_conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


# ---------------------------------------------------------------
# ensure_tournament_entry_schema — migration tests
# ---------------------------------------------------------------


def test_creates_table_fresh_when_it_does_not_exist_yet(conn):
    ensure_tournament_entry_schema(conn, SCHEMA_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tournament_entry)")}
    assert cols == {
        "game_code",
        "player_code",
        "player_name_display",
        "nationality",
        "qualification_category",
        "qualification_reason",
        "source",
        "collected_at",
    }


def test_is_a_noop_once_the_table_already_exists(full_conn):
    # full_conn already has tournament_entry from schema.sql — calling
    # again must not error or alter anything.
    ensure_tournament_entry_schema(full_conn, SCHEMA_PATH)
    cols = {row[1] for row in full_conn.execute("PRAGMA table_info(tournament_entry)")}
    assert "player_code" in cols


def test_additive_migration_never_touches_existing_validated_tables(conn):
    """The core safety requirement: adding tournament_entry to a real,
    already-populated production DB must not modify or reset
    tournament_master / player_master / player_event / player_round."""
    conn.executescript(_PRE_ENTRY_TABLE_SHAPE_SQL)
    upsert_tournament(
        conn,
        {
            "event_id": "2026030001",
            "game_code": "2026030001",
            "event_name": "테스트 대회",
            "season": 2026,
            "start_date": None,
            "end_date": "2026-03-15",
        },
    )
    upsert_player(conn, {"player_id": "10296", "player_name": "문정민"})
    upsert_player_event(
        conn,
        {
            "event_id": "2026030001",
            "game_code": "2026030001",
            "season": 2026,
            "player_id": "10296",
            "player_name": "문정민",
        },
    )
    conn.commit()

    before_tournaments = conn.execute("SELECT * FROM tournament_master").fetchall()
    before_players = conn.execute("SELECT * FROM player_master").fetchall()
    before_events = conn.execute("SELECT * FROM player_event").fetchall()

    ensure_tournament_entry_schema(conn, SCHEMA_PATH)

    assert conn.execute("SELECT * FROM tournament_master").fetchall() == before_tournaments
    assert conn.execute("SELECT * FROM player_master").fetchall() == before_players
    assert conn.execute("SELECT * FROM player_event").fetchall() == before_events
    # ...and the new table now exists.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tournament_entry)")}
    assert "player_code" in cols


# ---------------------------------------------------------------
# upsert_tournament_entry — idempotency tests
# ---------------------------------------------------------------


def _row(game_code="2026080001", player_code="10296", **overrides):
    row = {
        "game_code": game_code,
        "player_code": player_code,
        "player_name_display": "문정민",
        "nationality": "KOR",
        "qualification_category": "자격자",
        "qualification_reason": "2024 일반대회 우승자",
        "source": "https://klpga.co.kr/web/tourInfo/entry",
        "collected_at": "2026-08-25T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_upsert_inserts_a_new_row(full_conn):
    upsert_tournament_entry(full_conn, _row())
    full_conn.commit()
    rows = full_conn.execute("SELECT game_code, player_code, player_name_display FROM tournament_entry").fetchall()
    assert rows == [("2026080001", "10296", "문정민")]


def test_reupserting_the_same_entrant_does_not_duplicate(full_conn):
    """The core idempotency requirement: re-running collection for the
    same gameCode must never create duplicate tournament_entry rows."""
    upsert_tournament_entry(full_conn, _row())
    upsert_tournament_entry(full_conn, _row())
    upsert_tournament_entry(full_conn, _row(collected_at="2026-08-26T00:00:00+00:00"))
    full_conn.commit()

    count = full_conn.execute(
        "SELECT COUNT(*) FROM tournament_entry WHERE game_code=? AND player_code=?",
        ("2026080001", "10296"),
    ).fetchone()[0]
    assert count == 1

    collected_at = full_conn.execute(
        "SELECT collected_at FROM tournament_entry WHERE game_code=? AND player_code=?",
        ("2026080001", "10296"),
    ).fetchone()[0]
    assert collected_at == "2026-08-26T00:00:00+00:00"  # latest write wins


def test_different_game_codes_for_the_same_player_do_not_collide(full_conn):
    upsert_tournament_entry(full_conn, _row(game_code="2026080001"))
    upsert_tournament_entry(full_conn, _row(game_code="2026090001"))
    full_conn.commit()
    count = full_conn.execute(
        "SELECT COUNT(*) FROM tournament_entry WHERE player_code='10296'"
    ).fetchone()[0]
    assert count == 2


def test_unmatched_rookie_entrant_is_stored_without_a_player_master_row(full_conn):
    """Confirmed live 2026-08-25: player_code=13355 (배윤철 0908(A)) had
    no player_master row (119/120 matched) yet must still be stored —
    tournament_entry deliberately has no FK to player_master for
    exactly this reason."""
    upsert_tournament_entry(
        full_conn,
        _row(player_code="13355", player_name_display="배윤철 0908(A)", qualification_reason=None),
    )
    full_conn.commit()

    row = full_conn.execute(
        "SELECT player_code, player_name_display, qualification_reason FROM tournament_entry WHERE player_code='13355'"
    ).fetchone()
    assert row == ("13355", "배윤철 0908(A)", None)

    matched = full_conn.execute(
        "SELECT COUNT(*) FROM player_master WHERE player_id='13355'"
    ).fetchone()[0]
    assert matched == 0  # confirms this really is an unmatched entrant, not silently linked


def test_upsert_never_writes_an_entry_status_or_other_unconfirmed_column(full_conn):
    """No entry_status/WD/DNS/SG/GIR/course-par column exists on
    tournament_entry at all — assert the schema itself, not just this
    one row, to guard against it being added back speculatively."""
    cols = {row[1] for row in full_conn.execute("PRAGMA table_info(tournament_entry)")}
    for forbidden in ("entry_status", "wd", "dns", "sg_total", "gir", "course_par"):
        assert forbidden not in cols


# ---------------------------------------------------------------
# build_tournament_entry_rows — pure row-shaping
# ---------------------------------------------------------------


def test_build_tournament_entry_rows_shapes_confirmed_fields_only():
    entry_rows = [
        EntryRow(
            player_code="10296",
            player_name="문정민",
            nationality="KOR",
            qualification_category="자격자",
            qualification_reason="2024 일반대회 우승자",
        ),
        EntryRow(
            player_code="13355",
            player_name="배윤철 0908(A)",
            nationality="KOR",
            qualification_category="추천자",
            qualification_reason=None,
        ),
    ]
    rows = build_tournament_entry_rows(
        game_code="2026080001",
        entry_rows=entry_rows,
        source="https://klpga.co.kr/web/tourInfo/entry",
        collected_at="2026-08-25T00:00:00+00:00",
    )
    assert rows == [
        {
            "game_code": "2026080001",
            "player_code": "10296",
            "player_name_display": "문정민",
            "nationality": "KOR",
            "qualification_category": "자격자",
            "qualification_reason": "2024 일반대회 우승자",
            "source": "https://klpga.co.kr/web/tourInfo/entry",
            "collected_at": "2026-08-25T00:00:00+00:00",
        },
        {
            "game_code": "2026080001",
            "player_code": "13355",
            "player_name_display": "배윤철 0908(A)",
            "nationality": "KOR",
            "qualification_category": "추천자",
            "qualification_reason": None,
            "source": "https://klpga.co.kr/web/tourInfo/entry",
            "collected_at": "2026-08-25T00:00:00+00:00",
        },
    ]
    for row in rows:
        assert "entry_status" not in row


def test_build_tournament_entry_rows_is_directly_upsertable(full_conn):
    """End-to-end sanity: the shape build_tournament_entry_rows produces
    is exactly what upsert_tournament_entry accepts."""
    entry_rows = [
        EntryRow(
            player_code="10296",
            player_name="문정민",
            nationality="KOR",
            qualification_category="자격자",
            qualification_reason="2024 일반대회 우승자",
        )
    ]
    rows = build_tournament_entry_rows(
        game_code="2026080001",
        entry_rows=entry_rows,
        source="https://klpga.co.kr/web/tourInfo/entry",
        collected_at="2026-08-25T00:00:00+00:00",
    )
    for row in rows:
        upsert_tournament_entry(full_conn, row)
    full_conn.commit()
    count = full_conn.execute("SELECT COUNT(*) FROM tournament_entry").fetchone()[0]
    assert count == 1
