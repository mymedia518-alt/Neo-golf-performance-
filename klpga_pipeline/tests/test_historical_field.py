"""Tests for klpga.backtest.historical_field — field reconstruction
from player_event, and the label/identity field separation."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.backtest.historical_field import reconstruct_historical_field

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('T1', 'T1', 'Test Open', 2026, '2026-01-04')"
    )
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('P1', '선수1')")
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('P2', '선수2')")
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('T1', 'T1', 2026, 'P1', '선수1', '1', 1, 1, 4, -10)"
    )
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('T1', 'T1', 2026, 'P2', '선수2', 'CUT', NULL, 0, 2, NULL)"
    )
    connection.commit()
    yield connection
    connection.close()


def test_field_membership_from_player_event(conn):
    result = reconstruct_historical_field(conn, "T1")
    codes = {m.player_code for m in result.members}
    assert codes == {"P1", "P2"}


def test_winner_label_derived_from_finish_position_numeric(conn):
    result = reconstruct_historical_field(conn, "T1")
    p1 = next(m for m in result.members if m.player_code == "P1")
    p2 = next(m for m in result.members if m.player_code == "P2")
    assert p1.label_is_winner is True
    assert p1.label_made_cut is True
    assert p2.label_is_winner is False
    assert p2.label_made_cut is False
    assert p2.label_finish_position_numeric is None


def test_empty_field_for_unknown_event_id_not_an_error(conn):
    result = reconstruct_historical_field(conn, "NO_SUCH_EVENT")
    assert result.members == ()


def test_source_limitation_is_documented_on_the_result(conn):
    result = reconstruct_historical_field(conn, "T1")
    assert "player_event" in result.source
    assert "not a confirmed" in result.source
