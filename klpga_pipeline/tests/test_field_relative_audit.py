"""Tests for scripts/19_field_relative_audit.py — no network, against a
real schema.sql-built temp DB with hand-computable round scores."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "19_field_relative_audit.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("field_relative_audit_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('A', 'A', 'Open', 2026, '2026-01-04')"
    )
    # Round 1 field: P1=68, P2=72, P3=70 -> total=210, n=3.
    for player_id, score in [("P1", 68), ("P2", 72), ("P3", 70)]:
        connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
        connection.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_score) "
            "VALUES ('A', 'A', 2026, 1, ?, ?, ?)",
            (player_id, player_id, score),
        )
    connection.commit()
    yield connection
    connection.close()


def test_leave_one_out_benchmark_excludes_own_score(module, conn, capsys):
    outcome = module.run(conn, "A", 1, player_codes=["P1"], sample=5)
    out = capsys.readouterr().out

    assert outcome["status"] == "success"
    example = outcome["examples"][0]
    # leave_one_out for P1 = (210-68)/(3-1) = 142/2 = 71.0
    assert example["leave_one_out"] == 71.0
    assert example["field_avg_including_self"] == round(210 / 3, 2)
    # field_relative = 68 - 71 = -3.0
    assert example["field_relative"] == -3.0
    assert example["proof_ok"] is True
    assert "PASS" in out
    assert "NOT Strokes Gained" in out


def test_never_labeled_sg(module, conn, capsys):
    module.run(conn, "A", 1, player_codes=None, sample=5)
    out = capsys.readouterr().out
    assert "Strokes Gained" in out  # only in the explicit disclaimer
    assert "SG" not in out.replace("Strokes Gained", "")


def test_auto_select_round_picks_largest_field(module, conn, capsys):
    # Add a smaller field on a different event/round — auto-select must
    # still pick event A round 1 (n=3), not this n=1 round.
    conn.execute("INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) VALUES ('B', 'B', 'Small', 2026, '2026-02-04')")
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('P4', 'P4')")
    conn.execute("INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_score) VALUES ('B', 'B', 2026, 1, 'P4', 'P4', 70)")
    conn.commit()

    outcome = module.run(conn, None, None, player_codes=None, sample=5)
    out = capsys.readouterr().out
    assert outcome["event_id"] == "A"
    assert outcome["n"] == 3
    assert "auto-selected" in out


def test_unknown_game_code_reports_error(module, conn, capsys):
    outcome = module.run(conn, "NOPE", 1, player_codes=None, sample=5)
    assert outcome["status"] == "error"
    out = capsys.readouterr().out
    assert "no tournament_master row" in out


def test_field_of_one_has_no_leave_one_out(module, conn, capsys):
    conn.execute("INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) VALUES ('C', 'C', 'Solo', 2026, '2026-03-04')")
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('P5', 'P5')")
    conn.execute("INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, round_score) VALUES ('C', 'C', 2026, 1, 'P5', 'P5', 70)")
    conn.commit()

    outcome = module.run(conn, "C", 1, player_codes=None, sample=5)
    out = capsys.readouterr().out
    assert "no leave-one-out benchmark is possible" in out
    assert outcome["examples"] == []
