"""Tests for klpga.analytics.neo_performance_dataset — the read-only
join of tournament_master + player_event + official_metric_value +
player_master."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.analytics.neo_performance_dataset import build_neo_performance_dataset

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.sqlite")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('E1', 'G1', 'Test Open', 2026, '2026-01-01')"
    )
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Player One')")
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('E1', 'G1', 2026, 'p1', 'Player One', '1', 1, 1, 4, -10)"
    )
    connection.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) VALUES "
        "(2026, 'p1', 'Tee::Tee01::010101', 'Tee', 'Tee01', '평균 티샷 거리', 'record', '250.5', 'PARSE_SUCCESS', "
        "'CLEAN', 'PIT_UNVERIFIED', 'https://x', '2026-01-01T00:00:00Z')"
    )
    # An official metric row whose player_code has no player_master match.
    connection.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) VALUES "
        "(2026, 'ghost', 'Tee::Tee01::010101', 'Tee', 'Tee01', '평균 티샷 거리', 'record', '200.0', 'PARSE_SUCCESS', "
        "'CLEAN', 'PIT_UNVERIFIED', 'https://x', '2026-01-01T00:00:00Z')"
    )
    connection.commit()
    return connection


def test_dataset_joins_official_metrics_onto_the_matched_player(conn):
    dataset = build_neo_performance_dataset(conn)
    assert dataset["row_count"] == 1
    row = dataset["rows"][0]
    assert row["player_id"] == "p1"
    assert row["official_metrics"] == {"평균 티샷 거리": 250.5}
    assert row["official_metrics_available"] is True


def test_dataset_reports_unmatched_official_metric_codes_without_dropping_results(conn):
    dataset = build_neo_performance_dataset(conn)
    assert dataset["unmatched_official_metric_player_codes"] == ["ghost"]
    assert dataset["unmatched_official_metric_player_code_count"] == 1
    assert dataset["row_count"] == 1  # the real player_event row is unaffected


def test_dataset_reports_seasons_available(conn):
    dataset = build_neo_performance_dataset(conn)
    assert dataset["official_metric_seasons_available"] == [2026]


def test_dataset_empty_db_returns_empty_rows(tmp_path):
    connection = sqlite3.connect(tmp_path / "empty.sqlite")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    dataset = build_neo_performance_dataset(connection)
    assert dataset["row_count"] == 0
    assert dataset["rows"] == []
