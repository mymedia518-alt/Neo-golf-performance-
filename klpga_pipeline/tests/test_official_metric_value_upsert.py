"""Tests for the official_metric_value table (schema.sql section 8)
and klpga.db.upsert.upsert_official_metric_value — against a real
(temp, in-memory) klpga.sqlite built from the actual schema.sql,
never the project's real data/klpga.sqlite file."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.db.upsert import upsert_official_metric_value

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _row(**overrides):
    base = {
        "season": 2025,
        "player_code": "10112",
        "identity_key": "Approach::Approach02::020201",
        "menu1": "Approach",
        "menu2": "Approach02",
        "menu3": "020201",
        "official_label": "평균 남은 거리",
        "field_name": "record",
        "value_raw": "6.26",
        "unit": "yds",
        "response_column_label": "평균 남은 거리(yds)",
        "schema_fingerprint": "DISTANCE",
        "parse_status": "DISCOVERED_NOT_VALIDATED",
        "validation_status": "CLEAN",
        "pit_status": "PIT_UNVERIFIED",
        "source_url": "https://klpga.co.kr/load/record/loadLocationRecord",
        "raw_sample_path": "docs/discovery/raw_samples/Approach__Approach02__020201__2025.html",
        "acquired_at": "2026-08-26T20:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_upsert_inserts_a_row(conn):
    upsert_official_metric_value(conn, _row())
    conn.commit()
    result = conn.execute(
        "SELECT value_raw, unit, parse_status, validation_status, pit_status FROM official_metric_value"
    ).fetchone()
    assert result == ("6.26", "yds", "DISCOVERED_NOT_VALIDATED", "CLEAN", "PIT_UNVERIFIED")


def test_upsert_is_idempotent_by_natural_key(conn):
    upsert_official_metric_value(conn, _row())
    upsert_official_metric_value(conn, _row())
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == 1


def test_upsert_updates_changed_value_on_conflict(conn):
    upsert_official_metric_value(conn, _row(value_raw="6.26"))
    upsert_official_metric_value(conn, _row(value_raw="6.40"))
    conn.commit()
    result = conn.execute("SELECT value_raw FROM official_metric_value").fetchone()
    assert result[0] == "6.40"
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == 1


def test_two_labels_sharing_one_identity_key_are_two_distinct_rows(conn):
    """The real Approach::Approach02::020201 shape: two canonical
    labels, one physical request, two rows (one per official_label) —
    proves the natural key includes official_label, not just
    identity_key."""
    upsert_official_metric_value(conn, _row(official_label="평균 남은 거리", field_name="record"))
    upsert_official_metric_value(
        conn,
        _row(
            official_label="그린 적중 시 남은 거리",
            field_name="record",
            value_raw="6.26",
            unit="yds",
        ),
    )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == 2


def test_different_seasons_or_players_do_not_collide(conn):
    upsert_official_metric_value(conn, _row(season=2024))
    upsert_official_metric_value(conn, _row(season=2025))
    upsert_official_metric_value(conn, _row(season=2025, player_code="99999"))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == 3


def test_player_code_is_not_a_foreign_key_unmatched_player_still_stored(conn):
    """No FK to player_master — the identity-space match is
    unconfirmed, so a row for a player_code with no player_master row
    at all must still insert successfully, never rejected."""
    upsert_official_metric_value(conn, _row(player_code="no_such_player_999"))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0] == 1


def test_menu3_nullable_for_menu2_level_identities(conn):
    upsert_official_metric_value(
        conn,
        _row(identity_key="Sg::Approach", menu1="Sg", menu2="Approach", menu3=None, official_label="SG : 어프로치"),
    )
    conn.commit()
    result = conn.execute("SELECT menu3 FROM official_metric_value").fetchone()
    assert result[0] is None
