"""Tests for klpga.neo_win.redteam — BETA #001-C Phase 11's TOP20
red-team audit. Against a small synthetic DB (schema.sql) plus
hand-built NeoWinCPredictionSnapshot objects."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.beta001c_archive import NeoWinCEntrantSnapshot, NeoWinCPredictionSnapshot, RECORD_KIND
from klpga.neo_win.redteam import STATUS_CLEAN, STATUS_DATA_WARNING, STATUS_IDENTITY_WARNING, STATUS_MODEL_WARNING, red_team_top20

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.sqlite")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('LIVE', 'LIVE', 'Live', 2027, '2027-02-01', '2027-02-01')"
    )
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'A')")
    connection.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('LIVE', 'p1', 'A', 'test', '2027-01-01T00:00:00Z')"
    )
    # p1 has a DIRECT official_metric_value match (player_code == player_master.player_id)
    # so the identity crosswalk classifies it STATUS_CLEAN, not PARTIAL.
    connection.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) "
        "VALUES (2026, 'p1', 'Tee::Tee01::010101', 'Tee', 'x', 'x', 'record', '220', 'PARSE_SUCCESS', 'CLEAN', "
        "'PIT_UNVERIFIED', 'https://x', '2027-01-01T00:00:00Z')"
    )
    connection.commit()
    return connection


def _entrant(rank, code, name, prob, prior_events_n=10, feature_values=None) -> NeoWinCEntrantSnapshot:
    return NeoWinCEntrantSnapshot(
        rank=rank, player_code=code, player_name=name, win_probability=prob, prior_events_n=prior_events_n,
        feature_values=feature_values or {},
    )


def _snapshot(entrants, cutoff_date="2027-01-01", game_code="LIVE") -> NeoWinCPredictionSnapshot:
    return NeoWinCPredictionSnapshot(
        prediction_id="001-C", created_at_utc="2027-01-01T00:00:00Z", record_kind=RECORD_KIND,
        game_code=game_code, tournament_name="Live", cutoff_date=cutoff_date, cutoff_source="explicit_arg",
        selected_model_id="MODEL_A", model_features=("f",), selection_decision={},
        training_tournament_count=5, field_size=len(entrants), entrants_predicted=len(entrants),
        probability_sum=1.0, minimum_probability=0.01, maximum_probability=0.9,
        duplicate_count=0, null_count=0, non_field_count=0, known_limitations=(), predictions=tuple(entrants),
    )


def test_clean_field_player_reports_clean(conn):
    snapshot = _snapshot([_entrant(1, "p1", "A", 0.5)])
    reports = red_team_top20(snapshot, conn)
    assert reports[0]["status"] == STATUS_CLEAN
    assert reports[0]["flags"] == []


def test_unmatched_identity_flags_identity_warning(conn):
    # "ghost" has no player_master row and no evidence -> UNMATCHED in the crosswalk.
    conn.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) "
        "VALUES (2026, 'ghost', 'Tee::Tee01::010101', 'Tee', 'x', 'x', 'record', '1', 'PARSE_SUCCESS', 'CLEAN', "
        "'PIT_UNVERIFIED', 'https://x', '2027-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('LIVE', 'ghost', 'Ghost', 'test', '2027-01-01T00:00:00Z')"
    )
    conn.commit()
    snapshot = _snapshot([_entrant(1, "ghost", "Ghost", 0.5)])
    reports = red_team_top20(snapshot, conn)
    assert reports[0]["status"] == STATUS_IDENTITY_WARNING


def test_player_not_in_tournament_entry_flags_data_warning(conn):
    # This code is also genuinely UNMATCHED in the identity crosswalk
    # (no player_master/official_metric_value evidence at all), so the
    # overall status escalates past DATA_WARNING to IDENTITY_WARNING —
    # what this test actually pins is that the tournament_entry check
    # itself still fires its own flag regardless of overall severity.
    snapshot = _snapshot([_entrant(1, "not_in_field", "X", 0.5)])
    reports = red_team_top20(snapshot, conn)
    assert any("tournament_entry" in f for f in reports[0]["flags"])


def test_zero_prior_events_flags_data_warning(conn):
    snapshot = _snapshot([_entrant(1, "p1", "A", 0.5, prior_events_n=0)])
    reports = red_team_top20(snapshot, conn)
    assert reports[0]["status"] == STATUS_DATA_WARNING


def test_win_count_exceeding_sample_size_flags_model_warning(conn):
    snapshot = _snapshot([
        _entrant(1, "p1", "A", 0.5, feature_values={"wins_current_season": 5.0, "wins_current_season_n": 2})
    ])
    reports = red_team_top20(snapshot, conn)
    assert reports[0]["status"] == STATUS_MODEL_WARNING


def test_probability_out_of_range_flags_model_warning(conn):
    snapshot = _snapshot([_entrant(1, "p1", "A", 1.5)])
    reports = red_team_top20(snapshot, conn)
    assert reports[0]["status"] == STATUS_MODEL_WARNING


def test_target_before_cutoff_flags_model_warning(conn):
    snapshot = _snapshot([_entrant(1, "p1", "A", 0.5)], cutoff_date="2027-03-01")
    reports = red_team_top20(snapshot, conn)
    assert reports[0]["status"] == STATUS_MODEL_WARNING


def test_extreme_feature_value_flagged_against_field_population(conn):
    # A large, tightly-clustered "normal" population (small real
    # variance) plus one wild outlier — the outlier's z-score stays
    # far past 4 even though it is itself part of the population the
    # mean/stdev are computed from.
    entrants = [
        _entrant(i + 2, f"px{i}", "A", 0.01, feature_values={"neo_driving": 1.0 + (i % 3) * 0.01})
        for i in range(29)
    ]
    entrants.insert(0, _entrant(1, "p1", "A", 0.5, feature_values={"neo_driving": 1000.0}))
    snapshot = _snapshot(entrants)
    snapshot = NeoWinCPredictionSnapshot(**{**snapshot.__dict__, "model_features": ("neo_driving",)})
    reports = red_team_top20(snapshot, conn, top_n=1)
    assert reports[0]["status"] == STATUS_MODEL_WARNING
    assert any("extreme value" in f for f in reports[0]["flags"])


def test_duplicate_player_code_flags_data_warning(conn):
    snapshot = _snapshot([_entrant(1, "p1", "A", 0.5), _entrant(2, "p1", "A", 0.3)])
    reports = red_team_top20(snapshot, conn, top_n=2)
    assert reports[1]["status"] == STATUS_DATA_WARNING
