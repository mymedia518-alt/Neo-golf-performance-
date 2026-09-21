"""Tests for klpga.expected_strokes.course_yardage -- the design-only
official yardage ingestion contract (2026-09-21 red-team decision
item 4). No real yardage data exists anywhere yet; these tests only
prove the schema/loader mechanics are correct, using synthetic rows
never asserted to represent any real tournament."""
from __future__ import annotations

import sqlite3

from klpga.expected_strokes.course_yardage import (
    SCHEMA,
    CourseYardageRecord,
    load_course_yardage,
)


def test_load_course_yardage_empty_dict_when_table_missing():
    conn = sqlite3.connect(":memory:")  # no course_yardage table at all
    result = load_course_yardage(conn, "G")
    assert result == {}


def test_load_course_yardage_empty_dict_when_table_exists_but_no_rows_for_game():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO course_yardage VALUES(?,?,?,?,?,?,?)",
        ("OTHER_GAME", 1, 1, 4, 380.0, "synthetic_test_source", "abc123"),
    )
    conn.commit()
    result = load_course_yardage(conn, "G")
    assert result == {}


def test_load_course_yardage_returns_records_keyed_by_round_hole():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO course_yardage VALUES(?,?,?,?,?,?,?)",
        ("G", 1, 1, 4, 380.0, "synthetic_test_source", "abc123"),
    )
    conn.execute(
        "INSERT INTO course_yardage VALUES(?,?,?,?,?,?,?)",
        ("G", 1, 2, 3, 165.5, "synthetic_test_source", "def456"),
    )
    conn.commit()
    result = load_course_yardage(conn, "G")
    assert set(result.keys()) == {(1, 1), (1, 2)}
    rec = result[(1, 1)]
    assert isinstance(rec, CourseYardageRecord)
    assert rec.game_code == "G"
    assert rec.par == 4
    assert rec.yardage_yd == 380.0
    assert rec.source == "synthetic_test_source"
    assert rec.source_hash == "abc123"


def test_load_course_yardage_never_fabricates_missing_par_or_yardage():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO course_yardage VALUES(?,?,?,?,?,?,?)",
        ("G", 1, 1, None, None, "synthetic_test_source", "abc123"),
    )
    conn.commit()
    result = load_course_yardage(conn, "G")
    assert result[(1, 1)].par is None
    assert result[(1, 1)].yardage_yd is None
