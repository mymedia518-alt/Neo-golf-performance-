"""Tests for klpga.db.upsert against a real (temp, in-memory-backed)
klpga.sqlite built from the actual schema.sql — never the project's real
data/klpga.sqlite file."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.db.upsert import (
    finish_collection_run,
    start_collection_run,
    upsert_player,
    upsert_player_event,
    upsert_player_round,
    upsert_tournament,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def test_upsert_tournament_then_player_then_event_then_round_is_idempotent(conn):
    tournament = {
        "event_id": "2026030001",
        "game_code": "2026030001",
        "event_name": "리쥬란 챔피언십",
        "season": 2026,
        "start_date": None,
        "end_date": "2026-03-15",
        "course_name": "아마타스프링",
        "course_location": None,
        "par": None,
        "course_yards": None,
        "rounds_scheduled": None,
        "rounds_completed": None,
        "field_size": None,
        "winner": None,
        "winner_score": None,
        "official_url": None,
    }
    player = {
        "player_id": "11134",
        "player_name": "서고린",
        "birth_year": None,
        "nationality": None,
        "team_or_sponsor": None,
        "official_player_url": None,
    }
    event = {
        "event_id": "2026030001",
        "game_code": "2026030001",
        "season": 2026,
        "player_id": "11134",
        "player_name": "서고린",
        "finish_position": "1",
        "finish_position_numeric": 1,
        "tie_flag": 0,
        "made_cut": 1,
        "withdrawn": 0,
        "disqualified": 0,
        "rounds_played": 2,
        "r1_score": 70,
        "r2_score": 67,
        "r3_score": None,
        "r4_score": None,
        "total_score": 137,
        "score_to_par": -7,
        "prize_money": None,
        "avg_score_event": 68.5,
        "official_url": None,
    }
    rnd = {
        "event_id": "2026030001",
        "game_code": "2026030001",
        "season": 2026,
        "round_number": 1,
        "player_id": "11134",
        "player_name": "서고린",
        "round_score": 70,
        "round_to_par": None,
        "finish_position_after_round": None,
        "course_name": None,
        "course_par": None,
        "front9_score": None,
        "back9_score": None,
        "birdies": None,
        "eagles": None,
        "pars": None,
        "bogeys": None,
        "double_bogey_plus": None,
        "official_url": None,
    }

    for _ in range(2):  # run twice — must not duplicate or error
        upsert_tournament(conn, tournament)
        upsert_player(conn, player)
        upsert_player_event(conn, event)
        upsert_player_round(conn, rnd)
    conn.commit()

    assert conn.execute("SELECT COUNT(*) FROM tournament_master").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM player_master").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM player_event").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM player_round").fetchone()[0] == 1

    row = conn.execute("SELECT total_score FROM player_event WHERE player_id='11134'").fetchone()
    assert row[0] == 137


def test_upsert_updates_changed_values_on_conflict(conn):
    row = {
        "player_id": "999",
        "player_name": "Old Name",
        "birth_year": None,
        "nationality": None,
        "team_or_sponsor": None,
        "official_player_url": None,
    }
    upsert_player(conn, row)
    row["player_name"] = "New Name"
    upsert_player(conn, row)
    conn.commit()

    result = conn.execute("SELECT player_name FROM player_master WHERE player_id='999'").fetchone()
    assert result[0] == "New Name"
    assert conn.execute("SELECT COUNT(*) FROM player_master").fetchone()[0] == 1


def test_collection_run_lifecycle(conn):
    run_id = start_collection_run(conn, "test_script", target="season=2026", started_at="2026-08-24T00:00:00+00:00")
    conn.commit()

    running = conn.execute("SELECT status FROM collection_runs WHERE run_id=?", (run_id,)).fetchone()
    assert running[0] == "running"

    finish_collection_run(conn, run_id, status="success", finished_at="2026-08-24T00:05:00+00:00", rows_written=100)
    conn.commit()

    finished = conn.execute(
        "SELECT status, rows_written, error_message FROM collection_runs WHERE run_id=?", (run_id,)
    ).fetchone()
    assert finished == ("success", 100, None)


def test_finish_collection_run_rejects_invalid_status(conn):
    run_id = start_collection_run(conn, "test_script", target=None, started_at="2026-08-24T00:00:00+00:00")
    conn.commit()
    with pytest.raises(ValueError):
        finish_collection_run(conn, run_id, status="not-a-real-status", finished_at="2026-08-24T00:05:00+00:00")
