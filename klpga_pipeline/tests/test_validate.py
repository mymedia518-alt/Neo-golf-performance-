"""Tests for scripts/03_validate.py's coverage check — catches a
tournament_master row with zero player_event rows, which a crashed or
skipped 02_collect_leaderboards.py run leaves behind silently otherwise
(row-count/FK/duplicate checks alone don't look at per-tournament
coverage at all — this was a real gap found from a live run where
02_collect_leaderboards.py crashed on tournament 1 of 5, leaving
tournaments 2-5 with zero player_event rows, and 03_validate.py still
reported PASSED)."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "03_validate.py"


def _load_validate_module():
    spec = importlib.util.spec_from_file_location("validate_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def validate_module():
    return _load_validate_module()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()
    return path


def _insert_tournament(conn, event_id):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES (?, ?, ?, 2026, '2026-08-23')",
        (event_id, event_id, f"Tournament {event_id}"),
    )


def _insert_player_event(conn, event_id, player_id):
    conn.execute(
        "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)",
        (player_id, f"Player {player_id}"),
    )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name) "
        "VALUES (?, ?, 2026, ?, ?)",
        (event_id, event_id, player_id, f"Player {player_id}"),
    )


def test_passes_when_every_tournament_has_player_event_rows(validate_module, db_path):
    conn = sqlite3.connect(db_path)
    _insert_tournament(conn, "A")
    _insert_tournament(conn, "B")
    _insert_player_event(conn, "A", "p1")
    _insert_player_event(conn, "B", "p1")
    conn.commit()
    conn.close()

    failures = validate_module.validate(db_path, target_count=2)
    assert failures == []


def test_fails_when_a_tournament_has_zero_player_event_rows(validate_module, db_path):
    """This is exactly the scenario from the real bug report: 5
    tournaments collected by 01, but 02 crashed after tournament 1 —
    tournaments 2-5 never got any player_event rows."""
    conn = sqlite3.connect(db_path)
    _insert_tournament(conn, "A")
    _insert_tournament(conn, "B")
    _insert_tournament(conn, "C")
    _insert_player_event(conn, "A", "p1")  # only A was collected
    conn.commit()
    conn.close()

    failures = validate_module.validate(db_path, target_count=3)
    assert len(failures) == 1
    assert "ZERO player_event rows" in failures[0]
    assert "B" in failures[0] and "C" in failures[0]


def test_warnings_are_informational_and_never_block_a_passing_validation(validate_module, db_path):
    """A historical error/blocked collection_runs row (e.g. from a
    since-fixed bug, or a retried tournament) must not permanently fail
    validation once coverage is actually complete — collection_runs is
    an append-only audit log, not cleared on retry."""
    conn = sqlite3.connect(db_path)
    _insert_tournament(conn, "A")
    _insert_player_event(conn, "A", "p1")
    conn.execute(
        "INSERT INTO collection_runs (script_name, target, started_at, status, error_message) "
        "VALUES ('02_collect_leaderboards', 'A', '2026-08-24T00:00:00Z', 'error', 'transient failure')"
    )
    conn.commit()
    conn.close()

    failures = validate_module.validate(db_path, target_count=1)
    assert failures == []  # coverage is complete -> not a failure

    warnings = validate_module.collect_warnings(db_path)
    assert len(warnings) == 1
    assert "error" in warnings[0]
