"""Tests for the klpga.neo_win package (NEO WIN v0.1 / BETA #001) —
consistency feature, official-metric feature, leakage validation,
model fitting/prediction, dataset row-builders, and the end-to-end
run_neo_win_inference orchestrator. All against a small synthetic
in-memory/file SQLite DB shaped like test_model_inference.py's own
fixture (never the real production DB).
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from klpga.backtest.point_in_time_features import load_corpus
from klpga.neo_win.consistency import compute_consistency_feature
from klpga.neo_win.dataset import (
    augment_rows_with_neo_features,
    build_neo_win_live_field,
    build_neo_win_live_training_rows,
    build_neo_win_training_rows,
)
from klpga.neo_win.inference import run_neo_win_inference
from klpga.neo_win.leakage import (
    validate_official_metric_temporal_safety,
    validate_pit_feature_leakage,
    validate_probability_sum,
)
from klpga.neo_win.model import BASE_FEATURES, build_feature_columns, fit_neo_win_model, predict_neo_win_model
from klpga.neo_win.official_metrics import (
    build_prior_season_official_metrics,
    oriented_value,
    select_validated_official_metrics,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
LIVE_GAME_CODE = "KG2027"
CUTOFF_DATE = "2027-01-01"


def _new_conn(db_path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_tournament(connection, event_id, game_code, season, start_date, ranked_players, round_scores_to_par=None):
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
        scores = round_scores_to_par.get(player_id) if round_scores_to_par else None
        for round_number in range(1, 5):
            rtp = scores[round_number - 1] if scores else (-5 + rank)
            connection.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                "round_score, round_to_par) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, game_code, season, round_number, player_id, player_id, 70 + rtp, rtp),
            )


def _insert_entry(connection, game_code, player_code, player_name):
    connection.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES (?, ?, ?, 'test', '2027-01-01T00:00:00Z')",
        (game_code, player_code, player_name),
    )


def _insert_official_metric(connection, season, player_code, label, value, validation_status="CLEAN"):
    connection.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, acquired_at) "
        "VALUES (?, ?, 'Tee::Tee01::010101', 'Tee', 'Tee01', ?, 'record', ?, 'PARSE_SUCCESS', ?, 'PIT_UNVERIFIED', "
        "'https://x', '2027-01-01T00:00:00Z')",
        (season, player_code, label, str(value), validation_status),
    )


@pytest.fixture()
def conn(tmp_path):
    connection = _new_conn(tmp_path / "test.sqlite")
    players = ["A", "B", "C", "D", "E"]
    for t in range(10):
        event_id = f"T{t:02d}"
        ranked = players[t % len(players):] + players[: t % len(players)]
        _insert_tournament(connection, event_id, event_id, 2026, f"2026-{(t % 12) + 1:02d}-01", ranked)

    connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('ROOKIE1', 'ROOKIE1')")

    for player_code in ["A", "B", "C", "D", "E", "ROOKIE1", "UNMATCHED1"]:
        _insert_entry(connection, LIVE_GAME_CODE, player_code, player_code)

    # Extra players purely to clear select_validated_official_metrics's
    # MIN_PLAYER_COVERAGE=20 floor. Each also gets a real player_master
    # row so klpga.neo_win.identity_resolution's alias map treats them
    # as a direct match (the realistic case — most official_metric_value.
    # player_code values DO match player_master.player_id directly;
    # this test's UNMATCHED1/UNRESOLVED-style cases are exercised
    # separately below, not via these coverage-filler players).
    for i in range(16):
        code = f"X{i}"
        connection.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (code, code))

    # 2025 official metrics (prior season for the historical 2026
    # tournaments) AND 2026 official metrics (prior season for the
    # live LIVE_GAME_CODE target, whose cutoff is 2027-01-01 and thus
    # target_season=2027 -> prior_season=2026) — both with real
    # coverage for the allowlisted "평균 티샷 거리" label, >= min_coverage.
    for season in (2025, 2026):
        for i, player_code in enumerate(["A", "B", "C", "D", "E"] + [f"X{i}" for i in range(16)]):
            _insert_official_metric(connection, season, player_code, "평균 티샷 거리", 220.0 + i)
    # One FLAGGED response for player A at 2025 — must be excluded by default.
    _insert_official_metric(connection, 2025, "A", "그린 적중률", 70.0, validation_status="FLAGGED")

    connection.commit()
    return connection


# ---------------------------------------------------------------
# consistency.py
# ---------------------------------------------------------------


def test_consistency_feature_is_none_with_fewer_than_two_prior_rounds(conn):
    corpus = load_corpus(conn)
    value, n = compute_consistency_feature(corpus, "NOT_A_REAL_EVENT", date(2020, 1, 1), "A")
    assert value is None
    assert n == 0


def test_consistency_feature_excludes_rounds_on_or_after_target_date(conn):
    corpus = load_corpus(conn)
    # Target date before ANY of player A's rounds (all in 2026) -> zero prior rounds.
    value, n = compute_consistency_feature(corpus, "future_event", date(2020, 1, 1), "A")
    assert value is None
    assert n == 0


def test_consistency_feature_computes_real_stdev_from_prior_rounds(conn):
    corpus = load_corpus(conn)
    value, n = compute_consistency_feature(corpus, "future_event", date(2027, 1, 1), "A")
    assert n > 1
    assert value is not None
    assert value >= 0


# ---------------------------------------------------------------
# official_metrics.py
# ---------------------------------------------------------------


def test_prior_season_pivot_excludes_flagged_by_default(conn):
    pivot = build_prior_season_official_metrics(conn, 2025)
    assert ("Tee::Tee01::010101", "그린 적중률") not in pivot.get("A", {})
    assert ("Tee::Tee01::010101", "평균 티샷 거리") in pivot.get("A", {})


def test_prior_season_pivot_includes_flagged_when_requested(conn):
    pivot = build_prior_season_official_metrics(conn, 2025, exclude_flagged=False)
    assert ("Tee::Tee01::010101", "그린 적중률") in pivot.get("A", {})


def test_select_validated_official_metrics_picks_driving_slot_with_coverage(conn):
    pivot = build_prior_season_official_metrics(conn, 2025)
    selection = select_validated_official_metrics(pivot)
    assert selection == {"driving": ("Tee::Tee01::010101", "평균 티샷 거리", "higher_is_better")}


def test_select_validated_official_metrics_returns_empty_when_no_coverage():
    assert select_validated_official_metrics({}) == {}
    sparse_pivot = {"p1": {"평균 티샷 거리": 220.0}}
    assert select_validated_official_metrics(sparse_pivot, min_coverage=20) == {}


def test_oriented_value_flips_sign_only_for_higher_is_better():
    assert oriented_value(250.0, "higher_is_better") == -250.0
    assert oriented_value(30.0, "lower_is_better") == 30.0


# ---------------------------------------------------------------
# leakage.py
# ---------------------------------------------------------------


def test_validate_pit_feature_leakage_clean_on_real_corpus(conn):
    corpus = load_corpus(conn)
    violations = validate_pit_feature_leakage(corpus, "future_event", date(2027, 1, 1), "A")
    assert violations == []


def test_validate_official_metric_temporal_safety_flags_wrong_season():
    rows = [{"target_event_id": "e1", "player_code": "A", "target_season": 2026, "official_metric_season": 2026}]
    violations = validate_official_metric_temporal_safety(rows)
    assert len(violations) == 1


def test_validate_official_metric_temporal_safety_clean_for_prior_season():
    rows = [{"target_event_id": "e1", "player_code": "A", "target_season": 2026, "official_metric_season": 2025}]
    assert validate_official_metric_temporal_safety(rows) == []


def test_validate_official_metric_temporal_safety_skips_omitted_feature_rows():
    rows = [{"target_event_id": "e1", "player_code": "A", "target_season": 2026, "official_metric_season": None}]
    assert validate_official_metric_temporal_safety(rows) == []


def test_validate_probability_sum_clean():
    assert validate_probability_sum({"a": 0.5, "b": 0.5}) == []


def test_validate_probability_sum_flags_bad_sum():
    violations = validate_probability_sum({"a": 0.5, "b": 0.6})
    assert len(violations) == 1


def test_validate_probability_sum_flags_empty_field():
    assert validate_probability_sum({}) != []


# ---------------------------------------------------------------
# model.py
# ---------------------------------------------------------------


def _synthetic_training_rows():
    rows = []
    for t in range(6):
        for i, player in enumerate(["p1", "p2", "p3"]):
            rows.append(
                {
                    "target_event_id": f"T{t}",
                    "player_code": player,
                    "prior_avg_round_score_to_par": -2.0 + i,
                    "prior_avg_round_score_to_par_n": 20,
                    "prior_recent_form_10": -1.0 + i,
                    "prior_recent_form_10_n": 10,
                    "neo_consistency_stddev": 2.0 + i,
                    "neo_consistency_stddev_n": 10,
                    "neo_official_metric": -1.0,
                    "neo_official_metric_n": 1,
                    "label_is_winner": i == 0,
                }
            )
    return rows


def test_fit_neo_win_model_produces_a_real_tau():
    fitted = fit_neo_win_model(_synthetic_training_rows())
    assert fitted.tau is not None
    assert fitted.tau > 0
    assert fitted.training_tournament_count == 6
    assert fitted.feature_columns == BASE_FEATURES


def test_build_feature_columns_appends_only_selected_slots():
    assert build_feature_columns({}) == BASE_FEATURES
    cols = build_feature_columns({"driving": ("평균 티샷 거리", "higher_is_better")})
    assert cols == BASE_FEATURES + ("neo_official_metric_driving",)


def test_predict_neo_win_model_sums_to_one():
    fitted = fit_neo_win_model(_synthetic_training_rows())
    field_rows = [
        {
            "player_code": "p1",
            "prior_avg_round_score_to_par": -2.0,
            "prior_avg_round_score_to_par_n": 20,
            "prior_recent_form_10": -1.0,
            "prior_recent_form_10_n": 10,
            "neo_consistency_stddev": 2.0,
            "neo_consistency_stddev_n": 10,
            "neo_official_metric": -1.0,
            "neo_official_metric_n": 1,
        },
        {
            "player_code": "p2",
            "prior_avg_round_score_to_par": None,
            "prior_avg_round_score_to_par_n": 0,
            "prior_recent_form_10": None,
            "prior_recent_form_10_n": 0,
            "neo_consistency_stddev": None,
            "neo_consistency_stddev_n": 0,
            "neo_official_metric": None,
            "neo_official_metric_n": 0,
        },
    ]
    probs = predict_neo_win_model(fitted, field_rows)
    assert set(probs) == {"p1", "p2"}
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert all(p > 0 for p in probs.values())  # zero-history player still gets a real, nonzero probability


def test_predict_neo_win_model_empty_field_returns_empty():
    fitted = fit_neo_win_model(_synthetic_training_rows())
    assert predict_neo_win_model(fitted, []) == {}


def test_fit_neo_win_model_with_no_tournaments_falls_back_to_neutral_default():
    fitted = fit_neo_win_model([])
    assert fitted.tau == 1.0
    assert fitted.training_tournament_count == 0


# ---------------------------------------------------------------
# dataset.py
# ---------------------------------------------------------------


def test_augment_rows_with_neo_features_adds_expected_keys(conn):
    corpus = load_corpus(conn)
    rows = [{"target_event_id": "T05", "target_start_date": "2026-06-01", "player_code": "A"}]
    augmented = augment_rows_with_neo_features(conn, rows, corpus)
    row = augmented[0]
    assert row["target_season"] == 2026
    assert "neo_consistency_stddev" in row
    assert "neo_official_metric_driving" in row
    assert row["official_metric_season"] in (None, 2025)


def test_build_neo_win_training_rows_covers_every_walk_forward_row(conn):
    rows, total = build_neo_win_training_rows(conn)
    assert total == 10
    assert len(rows) > 0
    assert all("neo_consistency_stddev" in r for r in rows)


def test_build_neo_win_live_training_rows_excludes_the_live_game_code(conn):
    rows, count = build_neo_win_live_training_rows(conn, LIVE_GAME_CODE, date.fromisoformat(CUTOFF_DATE))
    assert count == 10  # all 10 historical tournaments are strictly before the live cutoff
    assert all(r["target_event_id"] != LIVE_GAME_CODE for r in rows)


def test_build_neo_win_live_field_covers_every_entrant(conn):
    field_data = build_neo_win_live_field(conn, LIVE_GAME_CODE, date.fromisoformat(CUTOFF_DATE))
    codes = {row["player_code"] for row in field_data["field_rows"]}
    assert codes == {"A", "B", "C", "D", "E", "ROOKIE1", "UNMATCHED1"}
    rookie_row = next(r for r in field_data["field_rows"] if r["player_code"] == "ROOKIE1")
    assert rookie_row["prior_events_n"] == 0
    assert field_data["official_metric_context"]["selected_slots"] == {"driving": "평균 티샷 거리"}
    assert set(field_data["official_metric_context"]["omitted_slots"]) == {"overall_skill", "short_game", "putting"}
    assert "identity_resolution" in field_data["official_metric_context"]


# ---------------------------------------------------------------
# inference.py — end to end
# ---------------------------------------------------------------


def test_run_neo_win_inference_end_to_end(conn):
    result = run_neo_win_inference(conn, LIVE_GAME_CODE, CUTOFF_DATE)
    assert result.field_size == 7
    assert result.predicted_count == 7
    assert result.dropped_entrants == 0
    assert abs(result.sum_probability - 1.0) < 1e-6
    assert result.unmatched_count == 1  # UNMATCHED1
    assert result.leakage_validation["clean"] is True
    assert {p.player_code for p in result.predictions} == {"A", "B", "C", "D", "E", "ROOKIE1", "UNMATCHED1"}
    ranks = [p.rank for p in result.predictions]
    assert ranks == list(range(1, 8))


def test_run_neo_win_inference_raises_on_empty_field(conn):
    with pytest.raises(ValueError):
        run_neo_win_inference(conn, "NO_SUCH_GAME_CODE", CUTOFF_DATE)


def test_run_neo_win_inference_missing_data_report_reflects_rookie(conn):
    result = run_neo_win_inference(conn, LIVE_GAME_CODE, CUTOFF_DATE)
    assert result.missing_data_report["zero_prior_events_count"] >= 1
    assert result.missing_data_report["unmatched_player_master_count"] == 1
    assert result.missing_data_report["official_metric_slots_used"] == ["driving"]
    assert "identity_resolution" in result.missing_data_report
    assert all("driving" in p.official_metrics for p in result.predictions)
