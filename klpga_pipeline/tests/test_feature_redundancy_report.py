"""Tests for scripts/20_feature_redundancy_report.py — the hand-rolled
Pearson implementation against known values, pairwise-deletion sample
sizing, and the report's no-decision framing (no feature removed, no
weight chosen)."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "20_feature_redundancy_report.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("feature_redundancy_report_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def test_pearson_perfect_positive_correlation(module):
    pairs = [(1, 2), (2, 4), (3, 6), (4, 8)]
    assert module._pearson_r(pairs) == pytest.approx(1.0)


def test_pearson_perfect_negative_correlation(module):
    pairs = [(1, 8), (2, 6), (3, 4), (4, 2)]
    assert module._pearson_r(pairs) == pytest.approx(-1.0)


def test_pearson_no_correlation_with_constant_y(module):
    pairs = [(1, 5), (2, 5), (3, 5)]
    assert module._pearson_r(pairs) is None  # zero variance in y -> undefined


def test_pearson_needs_at_least_two_points(module):
    assert module._pearson_r([(1, 2)]) is None
    assert module._pearson_r([]) is None


def test_compute_pairwise_correlations_uses_pairwise_deletion(module):
    rows = [
        {"a": 1, "b": 2, "c": None},
        {"a": 2, "b": 4, "c": 10},
        {"a": 3, "b": 6, "c": 20},
    ]
    result = module.compute_pairwise_correlations(rows, columns=("a", "b", "c"))
    assert result[("a", "b")]["n"] == 3
    assert result[("a", "b")]["r"] == pytest.approx(1.0)
    assert result[("a", "c")]["n"] == 2  # row 1's c=None dropped for this pair only


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tournament(event_id, start_date):
        connection.execute(
            "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
            "VALUES (?, ?, ?, 2026, ?, ?)",
            (event_id, event_id, event_id, start_date, start_date),
        )

    def event_row(event_id, player_id, finish):
        connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
            (event_id, event_id, player_id, player_id, str(finish), finish, -finish),
        )

    # A player who consistently finishes near the top builds up
    # correlated wins/top5/top10 across several target tournaments.
    for i in range(1, 6):
        tournament(f"T{i}", f"2026-0{i}-01")
        event_row(f"T{i}", "P1", 1)
    connection.commit()
    yield connection
    connection.close()


def test_run_prints_report_without_choosing_anything(module, conn, capsys):
    outcome = module.run(conn, min_n=1, notable_threshold=0.5)
    out = capsys.readouterr().out

    assert outcome["row_count"] > 0
    assert "No feature is removed and no weight is chosen" in out
    assert "Legend:" in out
    assert "Notable pairs" in out
