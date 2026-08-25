"""Tests for klpga.backtest.walk_forward — dataset row shape, rookie
retention with zero prior events, no silent drops, and the eligibility
trade-off sweep's math against a small hand-computable synthetic
4-tournament corpus."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.backtest.point_in_time_features import FEATURE_COLUMNS
from klpga.backtest.walk_forward import build_walk_forward_dataset, eligibility_sweep

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _tournament(conn, event_id, start_date, end_date=None, name=None):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, 2026, ?, ?)",
        (event_id, event_id, name or event_id, start_date, end_date or start_date),
    )


def _player(conn, player_id):
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))


def _event_row(conn, event_id, player_id, finish_position_numeric, made_cut=1, score_to_par=-2, rounds_played=4):
    _player(conn, player_id)
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id, event_id, player_id, player_id,
            str(finish_position_numeric), finish_position_numeric, made_cut, rounds_played, score_to_par,
        ),
    )


@pytest.fixture()
def four_tournament_corpus(conn):
    """T1 (2026-01-01): P1 wins, P2 2nd.
    T2 (2026-02-01): P1 finishes 5th, P3 (rookie) wins.
    T3 (2026-03-01): P1, P2, P3 all play.
    T4 (2026-04-01): P1, P2 play.
    prior_tournament_count: T1=0, T2=1, T3=2, T4=3."""
    _tournament(conn, "T1", "2026-01-01")
    _tournament(conn, "T2", "2026-02-01")
    _tournament(conn, "T3", "2026-03-01")
    _tournament(conn, "T4", "2026-04-01")

    _event_row(conn, "T1", "P1", 1)
    _event_row(conn, "T1", "P2", 2)

    _event_row(conn, "T2", "P1", 5)
    _event_row(conn, "T2", "P3", 1)

    _event_row(conn, "T3", "P1", 3)
    _event_row(conn, "T3", "P2", 4)
    _event_row(conn, "T3", "P3", 6)

    _event_row(conn, "T4", "P1", 2)
    _event_row(conn, "T4", "P2", 1)

    conn.commit()
    return conn


# ----------------------------------------------------------------
# build_walk_forward_dataset
# ----------------------------------------------------------------


def test_row_count_matches_sum_of_field_sizes(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    assert len(result.rows) == 2 + 2 + 3 + 2  # T1..T4 field sizes


def test_row_shape_has_every_documented_column(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    row = result.rows[0]
    expected_cols = {
        "target_game_code", "target_event_id", "target_start_date", "target_start_date_is_exact",
        "player_code", "player_name",
        "label_finish_position", "label_finish_position_numeric", "label_made_cut", "label_is_winner",
    } | set(FEATURE_COLUMNS)
    assert expected_cols.issubset(row.keys())


def test_rookie_with_zero_prior_events_is_retained_as_a_row(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    p3_t2_rows = [r for r in result.rows if r["target_event_id"] == "T2" and r["player_code"] == "P3"]
    assert len(p3_t2_rows) == 1
    row = p3_t2_rows[0]
    assert row["prior_events_n"] == 0
    assert row["prior_avg_round_score_to_par"] is None
    # She still won T2 — the label is present even though she's a rookie by features.
    assert row["label_is_winner"] is True


def test_prior_events_n_grows_across_tournaments_for_p1(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    by_target = {r["target_event_id"]: r for r in result.rows if r["player_code"] == "P1"}
    assert by_target["T1"]["prior_events_n"] == 0
    assert by_target["T2"]["prior_events_n"] == 1
    assert by_target["T3"]["prior_events_n"] == 2
    assert by_target["T4"]["prior_events_n"] == 3


def test_labels_reflect_target_tournament_outcome_only(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    t1_p1 = next(r for r in result.rows if r["target_event_id"] == "T1" and r["player_code"] == "P1")
    assert t1_p1["label_finish_position_numeric"] == 1
    assert t1_p1["label_is_winner"] is True
    assert t1_p1["label_made_cut"] is True


def test_tournament_with_no_resolvable_date_is_skipped_and_reported(conn):
    _tournament(conn, "T1", "2026-01-01")
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('BAD', 'BAD', 'Undated', 2026, NULL, 'garbage')"
    )
    _event_row(conn, "T1", "P1", 1)
    _event_row(conn, "BAD", "P1", 1)
    conn.commit()

    result = build_walk_forward_dataset(conn)
    assert "BAD" in result.skipped_no_date_event_ids
    assert all(r["target_event_id"] != "BAD" for r in result.rows)


def test_tournament_with_empty_field_is_skipped_and_reported(conn):
    _tournament(conn, "T1", "2026-01-01")
    _tournament(conn, "EMPTY", "2026-02-01")  # no player_event rows at all
    _event_row(conn, "T1", "P1", 1)
    conn.commit()

    result = build_walk_forward_dataset(conn)
    assert "EMPTY" in result.skipped_empty_field_event_ids
    assert all(r["target_event_id"] != "EMPTY" for r in result.rows)


# ----------------------------------------------------------------
# eligibility_sweep — hand-computed against the 4-tournament corpus
# ----------------------------------------------------------------


def test_eligibility_sweep_tournament_counts(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    sweep = eligibility_sweep(result, thresholds=(0, 1, 2, 3, 4))
    counts = {r["threshold"]: r["eligible_tournament_count"] for r in sweep}
    assert counts == {0: 4, 1: 3, 2: 2, 3: 1, 4: 0}


def test_eligibility_sweep_field_row_counts(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    sweep = eligibility_sweep(result, thresholds=(0, 1, 2, 3, 4))
    rows_counts = {r["threshold"]: r["eligible_field_row_count"] for r in sweep}
    assert rows_counts == {0: 9, 1: 7, 2: 5, 3: 2, 4: 0}


def test_eligibility_sweep_prior_events_n_distribution(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    sweep = eligibility_sweep(result, thresholds=(0, 3))
    by_threshold = {r["threshold"]: r for r in sweep}

    # k=0: all 9 rows, prior_events_n = [0,0,1,0,2,1,1,3,2]
    assert by_threshold[0]["mean_prior_events_n"] == round(10 / 9, 2)
    assert by_threshold[0]["median_prior_events_n"] == 1
    assert by_threshold[0]["pct_zero_prior_events"] == round(100 * 3 / 9, 1)

    # k=3: only T4's rows, prior_events_n = [3, 2]
    assert by_threshold[3]["eligible_tournament_count"] == 1
    assert by_threshold[3]["mean_prior_events_n"] == 2.5
    assert by_threshold[3]["median_prior_events_n"] == 2.5
    assert by_threshold[3]["pct_zero_prior_events"] == 0.0


def test_eligibility_sweep_handles_zero_eligible_tournaments(four_tournament_corpus):
    result = build_walk_forward_dataset(four_tournament_corpus)
    sweep = eligibility_sweep(result, thresholds=(100,))
    assert sweep[0]["eligible_tournament_count"] == 0
    assert sweep[0]["eligible_field_row_count"] == 0
    assert sweep[0]["mean_prior_events_n"] is None
    assert sweep[0]["median_prior_events_n"] is None
    assert sweep[0]["pct_zero_prior_events"] is None
