"""Tests for klpga.neo_win.feature_matrix — BETA #001-C Phase 5's
domain-aggregate feature matrix. Mostly offline against a small
synthetic in-memory/file SQLite DB (same shape as test_neo_win.py's
fixture); domain classification/usable gating is checked against the
REAL, committed docs/discovery/ taxonomy evidence for the strongest
regression pin."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from klpga.neo_win.feature_matrix import (
    DOMAIN_FEATURE_NAMES,
    build_beta001c_feature_matrix,
    compute_domain_aggregate_features,
    usable_metrics_by_domain,
)
from klpga.neo_win.metric_domain_map import DOMAIN_DRIVING, DOMAIN_SCORING

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
REAL_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"
LIVE_GAME_CODE = "KG2027"


def _new_conn(db_path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_tournament(connection, event_id, game_code, season, start_date, ranked_players):
    connection.execute(
        "INSERT OR IGNORE INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, game_code, event_id, season, start_date, start_date),
    )
    for rank, player_id in enumerate(ranked_players, start=1):
        connection.execute(
            "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id)
        )
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, 1, 4, ?)",
            (event_id, game_code, season, player_id, player_id, str(rank), rank, -20 + rank),
        )
        for round_number in range(1, 5):
            connection.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                "round_score, round_to_par) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, game_code, season, round_number, player_id, player_id, 70 - rank, -5 + rank),
            )


def _insert_entry(connection, game_code, player_code, player_name):
    connection.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
        (game_code, player_code, player_name),
    )


def _insert_official_metric(connection, season, player_code, identity_key, menu1, label, value, validation_status="CLEAN"):
    connection.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) "
        "VALUES (?, ?, ?, ?, 'x', ?, 'record', ?, 'PARSE_SUCCESS', ?, 'PIT_UNVERIFIED', 'https://x', "
        "'2027-01-01T00:00:00Z')",
        (season, player_code, identity_key, menu1, label, str(value), validation_status),
    )


@pytest.fixture()
def conn(tmp_path):
    connection = _new_conn(tmp_path / "test.sqlite")
    players = ["A", "B", "C", "D", "E"]
    for t in range(3):
        event_id = f"T{t:02d}"
        ranked = players[t % len(players):] + players[: t % len(players)]
        _insert_tournament(connection, event_id, event_id, 2026, f"2026-{(t % 12) + 1:02d}-01", ranked)

    connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('ROOKIE1', 'ROOKIE1')")
    for player_code in ["A", "B", "C", "D", "E", "ROOKIE1"]:
        _insert_entry(connection, LIVE_GAME_CODE, player_code, player_code)

    # 20+ players with real, allowlisted DRIVING-domain coverage
    # (Tee::Tee01::010101 / 평균 티샷 거리) for the live target's prior
    # season (2026, since LIVE cutoff 2027-01-01 -> target_season=2027).
    for i in range(20):
        code = f"X{i}"
        connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (code, code))
        _insert_official_metric(connection, 2026, code, "Tee::Tee01::010101", "Tee", "평균 티샷 거리", 220.0 + i)
    # ROOKIE1 gets NO official metric rows at all -> must stay None/0, never fabricated.

    connection.commit()
    return connection


# ---------------------------------------------------------------
# compute_domain_aggregate_features — pure, synthetic
# ---------------------------------------------------------------


def test_domain_average_of_two_metrics_for_one_player():
    pivot = {
        "p1": {("Sg::Tee", "SG : 티샷"): 2.0, ("Tee::Tee01::010101", "평균 티샷 거리"): 240.0},
    }
    by_domain = {
        DOMAIN_DRIVING: [
            ("Sg::Tee", "SG : 티샷", "higher_is_better"),
            ("Tee::Tee01::010101", "평균 티샷 거리", "higher_is_better"),
        ]
    }
    out = compute_domain_aggregate_features(pivot, by_domain, min_metric_coverage=1)
    assert out["p1"]["neo_driving_n"] == 2
    assert out["p1"]["neo_driving"] == (-2.0 + -240.0) / 2


def test_thinly_covered_metric_dropped_from_domain_average():
    pivot = {
        "p1": {("Sg::Tee", "SG : 티샷"): 2.0},
        "p2": {("Tee::Tee01::010101", "평균 티샷 거리"): 210.0},
    }
    by_domain = {
        DOMAIN_DRIVING: [
            ("Sg::Tee", "SG : 티샷", "higher_is_better"),  # coverage 1, below floor
            ("Tee::Tee01::010101", "평균 티샷 거리", "higher_is_better"),  # coverage 1, below floor
        ]
    }
    out = compute_domain_aggregate_features(pivot, by_domain, min_metric_coverage=2)
    assert out["p1"]["neo_driving"] is None
    assert out["p1"]["neo_driving_n"] == 0


def test_player_with_no_metrics_in_domain_gets_none_never_fabricated():
    pivot = {"p1": {}}
    by_domain = {DOMAIN_DRIVING: [("Sg::Tee", "SG : 티샷", "higher_is_better")]}
    out = compute_domain_aggregate_features(pivot, by_domain, min_metric_coverage=0)
    assert out["p1"]["neo_driving"] is None
    assert out["p1"]["neo_driving_n"] == 0


def test_scoring_domain_is_always_none_duplicate_representation_guard():
    pivot = {"p1": {("All::x", "평균 타수"): 70.0}}
    by_domain = {DOMAIN_SCORING: [("All::x", "평균 타수", "lower_is_better")]}
    out = compute_domain_aggregate_features(pivot, by_domain, min_metric_coverage=0)
    assert out["p1"]["neo_scoring"] is None
    assert out["p1"]["neo_scoring_n"] == 0


def test_every_domain_feature_name_present_for_every_player_even_with_empty_candidates():
    out = compute_domain_aggregate_features({"p1": {}}, {}, min_metric_coverage=0)
    for feature_name in DOMAIN_FEATURE_NAMES.values():
        assert out["p1"][feature_name] is None
        assert out["p1"][f"{feature_name}_n"] == 0


# ---------------------------------------------------------------
# usable_metrics_by_domain — real taxonomy evidence
# ---------------------------------------------------------------


def test_usable_metrics_by_domain_against_real_taxonomy():
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    by_domain = usable_metrics_by_domain(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    assert DOMAIN_SCORING not in by_domain  # never usable, so never populated
    assert ("Tee::Tee01::010101", "평균 티샷 거리", "higher_is_better") in by_domain.get(DOMAIN_DRIVING, [])


# ---------------------------------------------------------------
# build_beta001c_feature_matrix — end to end against the synthetic DB
# ---------------------------------------------------------------


def test_feature_matrix_end_to_end_driving_domain_has_coverage(conn):
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    result = build_beta001c_feature_matrix(
        conn, LIVE_GAME_CODE, date.fromisoformat("2027-01-01"),
        taxonomy=taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR,
    )
    assert result["prior_season"] == 2026
    field_rows = {row["player_code"]: row for row in result["field_rows"]}
    assert set(field_rows) == {"A", "B", "C", "D", "E", "ROOKIE1"}
    for feature_name in DOMAIN_FEATURE_NAMES.values():
        for row in field_rows.values():
            assert feature_name in row
            assert f"{feature_name}_n" in row
    assert field_rows["ROOKIE1"]["neo_driving"] is None
    assert field_rows["ROOKIE1"]["neo_driving_n"] == 0
    assert result["coverage"][DOMAIN_DRIVING]["field_size"] == 6


def test_feature_matrix_neo_scoring_always_none_across_field(conn):
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    result = build_beta001c_feature_matrix(
        conn, LIVE_GAME_CODE, date.fromisoformat("2027-01-01"),
        taxonomy=taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR,
    )
    for row in result["field_rows"]:
        assert row["neo_scoring"] is None
        assert row["neo_scoring_n"] == 0
    assert result["coverage"][DOMAIN_SCORING]["metrics_used"] == []


def test_feature_matrix_preserves_base_features_from_live_field(conn):
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    result = build_beta001c_feature_matrix(
        conn, LIVE_GAME_CODE, date.fromisoformat("2027-01-01"),
        taxonomy=taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR,
    )
    for row in result["field_rows"]:
        assert "prior_avg_round_score_to_par" in row
        assert "prior_recent_form_10" in row
        assert "neo_consistency_stddev" in row
