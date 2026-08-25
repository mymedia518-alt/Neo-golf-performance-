"""Tests for scripts/21_data_coverage_report.py — hand-computable
coverage/distribution stats against a small synthetic multi-tournament
corpus, no network."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "21_data_coverage_report.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("data_coverage_report_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def test_compute_coverage_counts_non_null_and_distribution(module):
    rows = [
        {"prior_avg_round_score_to_par": -1.5, "prior_avg_round_score_to_par_n": 4,
         "prior_avg_round_to_par": None, "prior_avg_round_to_par_n": 0,
         "prior_avg_field_relative_round_score": None, "prior_avg_field_relative_round_score_n": 0,
         "prior_recent_form_5": -1.0, "prior_recent_form_5_n": 1,
         "prior_recent_form_10": -1.0, "prior_recent_form_10_n": 1,
         "prior_recent_form_20": -1.0, "prior_recent_form_20_n": 1},
        {"prior_avg_round_score_to_par": None, "prior_avg_round_score_to_par_n": 0,
         "prior_avg_round_to_par": -2.0, "prior_avg_round_to_par_n": 2,
         "prior_avg_field_relative_round_score": None, "prior_avg_field_relative_round_score_n": 0,
         "prior_recent_form_5": None, "prior_recent_form_5_n": 0,
         "prior_recent_form_10": None, "prior_recent_form_10_n": 0,
         "prior_recent_form_20": None, "prior_recent_form_20_n": 0},
    ]
    coverage = module.compute_coverage(rows)

    assert coverage["prior_avg_round_score_to_par"]["non_null_count"] == 1
    assert coverage["prior_avg_round_score_to_par"]["non_null_pct"] == 50.0
    assert coverage["prior_avg_round_score_to_par"]["n_min"] == 0
    assert coverage["prior_avg_round_score_to_par"]["n_max"] == 4
    assert coverage["prior_avg_round_score_to_par"]["n_mean"] == 2.0

    assert coverage["prior_avg_round_to_par"]["non_null_count"] == 1
    assert coverage["prior_avg_field_relative_round_score"]["non_null_count"] == 0
    assert coverage["prior_avg_field_relative_round_score"]["non_null_pct"] == 0.0


def test_compute_coverage_handles_empty_dataset(module):
    coverage = module.compute_coverage([])
    for entry in coverage.values():
        assert entry["total_rows"] == 0
        assert entry["non_null_pct"] is None
        assert entry["n_min"] is None


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

    def event_row(event_id, player_id, finish, rounds_played=4, score_to_par=-3):
        connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, ?, ?)",
            (event_id, event_id, player_id, player_id, str(finish), finish, rounds_played, score_to_par),
        )

    for i in range(1, 4):
        tournament(f"T{i}", f"2026-0{i}-01")
        event_row(f"T{i}", "P1", i)
    connection.commit()
    yield connection
    connection.close()


def test_run_prints_coverage_report(module, conn, capsys):
    outcome = module.run(conn)
    out = capsys.readouterr().out

    assert outcome["total_rows"] > 0
    assert "prior_avg_round_score_to_par" in out
    assert "non-NULL:" in out
    assert "distribution (incl. zeros)" in out
