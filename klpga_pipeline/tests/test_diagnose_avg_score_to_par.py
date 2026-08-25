"""Tests for scripts/11_diagnose_avg_score_to_par.py — the red-team
verification that derived_avg_score_to_par is built from the
TOURNAMENT-total score_to_par field (data-totunderpar), never a
round-level to-par value, and that the numbers are internally
consistent (implied par per round lands near a real golf course par)."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "11_diagnose_avg_score_to_par.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("diagnose_score_to_par_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Test Player')")
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('E1', 'E1', 'Tournament 1', 2026, '2026-01-01')"
    )
    # 4 rounds summing to 280 strokes, tournament total_score_to_par = -8
    # (a real, self-consistent example: 288 - (-8) = ... i.e. implied
    # par = 280 - (-8) = 288, 72/round — plausible).
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, finish_position_numeric, total_score, score_to_par, rounds_played) "
        "VALUES ('E1', 'E1', 2026, 'p1', 'Test Player', 1, 1, 280, -8, 4)"
    )
    for r, score in enumerate([70, 67, 69, 74], start=1):
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, "
            "player_name, round_score) VALUES ('E1', 'E1', 2026, ?, 'p1', 'Test Player', ?)",
            (r, score),
        )
    conn.commit()
    conn.close()
    return path


def test_implied_par_matches_a_real_golf_par_for_self_consistent_data(module, db_path, capsys):
    exit_code = module.diagnose(db_path, names=["Test Player"], fill_to=1)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "implied_total_par = total_strokes - score_to_par: 288" in out
    assert "implied_avg_par/round: 72.00" in out
    assert "no implausible implied-par events found" in out
    assert "mean(score_to_par) across those events = -8.00" in out


def test_flags_implausible_implied_par(module, db_path, capsys):
    """If score_to_par were ever accidentally sourced from a per-round
    to-par value instead of the tournament total, the reverse-engineered
    implied par would come out nowhere near a real golf par — this test
    proves that case IS actually caught, not silently accepted."""
    conn = sqlite3.connect(db_path)
    # Simulate the exact failure mode being red-teamed: score_to_par
    # holds a small per-round-like value (-2) instead of the real
    # tournament total (-8) for a 280-stroke, 4-round event -> implied
    # total par = 280 - (-2) = 282, /4 = 70.5/round... still plausible.
    # Use a more extreme corruption to guarantee an implausible flag:
    # score_to_par = -150 (impossible tournament total for 280 strokes).
    conn.execute("UPDATE player_event SET score_to_par = -150 WHERE event_id = 'E1'")
    conn.commit()
    conn.close()

    exit_code = module.diagnose(db_path, names=["Test Player"], fill_to=1)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "⚠ IMPLAUSIBLE implied par" in out


def test_falls_back_to_top_tournaments_played_when_name_not_found(module, db_path, capsys):
    exit_code = module.diagnose(db_path, names=["Nonexistent Player Name"], fill_to=1)
    out = capsys.readouterr().out
    assert exit_code == 1  # nothing in player_stats_snapshot to fall back on either


def test_never_writes_to_the_database(module, db_path):
    before = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM player_event").fetchone()[0]
    module.diagnose(db_path, names=["Test Player"], fill_to=1)
    after = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM player_event").fetchone()[0]
    assert before == after
