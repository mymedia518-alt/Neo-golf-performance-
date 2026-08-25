"""Tests for scripts/12_verify_round_to_par_reliability.py — the
red-team check confirming (or refuting) that player_round.round_to_par
is reliable enough to use directly, and that
derived_avg_round_score_to_par's rate formula agrees with a direct
reconstruction from that field wherever there's full coverage."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "12_verify_round_to_par_reliability.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_round_to_par_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _insert_player(conn, player_id):
    conn.execute(
        "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)",
        (player_id, f"Player {player_id}"),
    )


def _insert_event(conn, event_id, player_id, score_to_par, rounds_played):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES (?, ?, ?, 2026, '2026-01-01')",
        (event_id, event_id, f"Tournament {event_id}"),
    )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, score_to_par, rounds_played) VALUES (?, ?, 2026, ?, ?, 1, ?, ?)",
        (event_id, event_id, player_id, f"Player {player_id}", score_to_par, rounds_played),
    )


def _insert_round(conn, event_id, player_id, round_number, round_score, round_to_par):
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, "
        "player_name, round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
        (event_id, event_id, round_number, player_id, f"Player {player_id}", round_score, round_to_par),
    )


def test_check_a_passes_when_single_round_to_par_matches_score_to_par(module, conn):
    _insert_player(conn, "p1")
    _insert_event(conn, "T1", "p1", score_to_par=-3, rounds_played=1)
    _insert_round(conn, "T1", "p1", 1, 69, round_to_par=-3)
    conn.commit()

    result = module._check_a_single_round(conn)
    assert result["checked"] == 1
    assert result["exact_matches"] == 1
    assert result["mismatches"] == []


def test_check_a_flags_a_real_mismatch(module, conn):
    _insert_player(conn, "p1")
    _insert_event(conn, "T1", "p1", score_to_par=-3, rounds_played=1)
    _insert_round(conn, "T1", "p1", 1, 69, round_to_par=-2)  # deliberately wrong
    conn.commit()

    result = module._check_a_single_round(conn)
    assert result["checked"] == 1
    assert result["exact_matches"] == 0
    assert len(result["mismatches"]) == 1


def test_check_b_passes_when_full_coverage_sums_correctly(module, conn):
    _insert_player(conn, "p2")
    _insert_event(conn, "T1", "p2", score_to_par=-3, rounds_played=2)
    _insert_round(conn, "T1", "p2", 1, 70, round_to_par=-1)
    _insert_round(conn, "T1", "p2", 2, 69, round_to_par=-2)  # -1 + -2 == -3
    conn.commit()

    result = module._check_b_full_coverage(conn)
    assert result["fully_covered_events"] == 1
    assert result["exact_matches"] == 1
    assert result["mismatches"] == []
    assert result["rate_from_totals"] == pytest.approx(-3 / 2)
    assert result["rate_from_raw_rounds"] == pytest.approx(-3 / 2)


def test_check_b_flags_a_real_mismatch(module, conn):
    _insert_player(conn, "p3")
    _insert_event(conn, "T1", "p3", score_to_par=-5, rounds_played=2)
    _insert_round(conn, "T1", "p3", 1, 70, round_to_par=-1)
    _insert_round(conn, "T1", "p3", 2, 69, round_to_par=-1)  # -1 + -1 == -2, not -5
    conn.commit()

    result = module._check_b_full_coverage(conn)
    assert result["fully_covered_events"] == 1
    assert result["exact_matches"] == 0
    assert len(result["mismatches"]) == 1
    # a real mismatch must also mean the cross-check rates disagree.
    assert round(result["rate_from_totals"], 2) != round(result["rate_from_raw_rounds"], 2)


def test_check_b_excludes_partially_covered_events(module, conn):
    """An event where round_to_par is missing for at least one round
    must NOT be included in check B — partial coverage would silently
    understate the true sum."""
    _insert_player(conn, "p4")
    _insert_event(conn, "T1", "p4", score_to_par=-3, rounds_played=2)
    _insert_round(conn, "T1", "p4", 1, 70, round_to_par=-1)
    _insert_round(conn, "T1", "p4", 2, 69, round_to_par=None)  # not directly queried
    conn.commit()

    result = module._check_b_full_coverage(conn)
    assert result["fully_covered_events"] == 0
    assert result["total_multi_round_events"] == 1  # still counted as eligible, just not covered


def test_coverage_stats_counts_null_and_non_null_round_to_par(module, conn):
    _insert_player(conn, "p5")
    _insert_event(conn, "T1", "p5", score_to_par=-3, rounds_played=2)
    _insert_round(conn, "T1", "p5", 1, 70, round_to_par=-1)
    _insert_round(conn, "T1", "p5", 2, 69, round_to_par=None)
    conn.commit()

    stats = module._coverage_stats(conn)
    assert stats["total_rounds"] == 2
    assert stats["covered_rounds"] == 1


def test_verify_never_writes_to_the_database(module, tmp_path):
    db_path = tmp_path / "test.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _insert_player(connection, "p1")
    _insert_event(connection, "T1", "p1", score_to_par=-3, rounds_played=1)
    _insert_round(connection, "T1", "p1", 1, 69, round_to_par=-3)
    connection.commit()

    before = connection.execute("SELECT COUNT(*) FROM player_round").fetchone()[0]
    connection.close()

    module.verify(db_path)

    connection = sqlite3.connect(db_path)
    after = connection.execute("SELECT COUNT(*) FROM player_round").fetchone()[0]
    connection.close()
    assert before == after
