"""Tests for klpga.models.inference — the read-only PRODUCTION
inference layer for an upcoming tournament's live `tournament_entry`
field under the frozen v1 model M4. Includes the 12 mandatory
adversarial tests from the production-inference stage instructions,
plus basic correctness checks, all against a small synthetic in-memory
SQLite DB (never the real production DB)."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest

from klpga.models.candidates import MODEL_FEATURES
from klpga.models.inference import (
    _detect_duplicate_player_codes,
    resolve_cutoff_date,
    resolve_tournament_name,
    run_inference,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"

LIVE_GAME_CODE = "KG2026"
CUTOFF_DATE = "2027-01-01"


def _new_conn(db_path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_tournament(connection, event_id, game_code, start_date, ranked_players):
    """ranked_players: list of player_ids in finishing order (1st..last).
    Inserts a tournament_master row + one player_event row per player,
    each played 4 rounds with a monotonically worsening score_to_par."""
    connection.execute(
        "INSERT OR IGNORE INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, 2026, ?, ?)",
        (event_id, game_code, event_id, start_date, start_date),
    )
    for rank, player_id in enumerate(ranked_players, start=1):
        connection.execute(
            "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id)
        )
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
            (event_id, game_code, player_id, player_id, str(rank), rank, -20 + rank),
        )


def _insert_entry(connection, game_code, player_code, player_name):
    connection.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES (?, ?, ?, 'test', '2026-08-25T00:00:00Z')",
        (game_code, player_code, player_name),
    )


def _base_fixture_conn(db_path):
    """10 historical tournaments (A-E rotating through finish order,
    each with a real winner), plus a live entry list at LIVE_GAME_CODE
    with 7 entrants: 5 with real history (A-E), one zero-history rookie
    who IS in player_master (ROOKIE1), and one zero-history entrant who
    is NOT in player_master at all (UNMATCHED1) — mirroring the real
    player_code=13355 case."""
    connection = _new_conn(db_path)
    players = ["A", "B", "C", "D", "E"]
    for t in range(10):
        event_id = f"T{t:02d}"
        ranked = players[t % len(players):] + players[: t % len(players)]
        _insert_tournament(connection, event_id, event_id, f"2026-{(t % 12) + 1:02d}-01", ranked)

    # ROOKIE1 exists in player_master but has never played a tournament.
    connection.execute(
        "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('ROOKIE1', 'ROOKIE1')"
    )

    for player_code in ["A", "B", "C", "D", "E", "ROOKIE1", "UNMATCHED1"]:
        _insert_entry(connection, LIVE_GAME_CODE, player_code, player_code)

    connection.commit()
    return connection


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "klpga.sqlite"
    connection = _base_fixture_conn(db_path)
    yield connection
    connection.close()


# ----------------------------------------------------------------
# Basic correctness
# ----------------------------------------------------------------


def test_all_entrants_predicted_and_sorted_descending(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    assert result.field_size == 7
    assert result.entrants_parsed == 7
    assert result.predicted_count == 7
    assert result.dropped_entrants == 0
    probs = [p.win_probability for p in result.predictions]
    assert probs == sorted(probs, reverse=True)
    assert [p.rank for p in result.predictions] == list(range(1, 8))


def test_model_id_and_features_are_frozen_m4(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    assert result.model_id == "M4"
    assert result.model_features == MODEL_FEATURES["M4"]


def test_training_tournament_count_matches_usable_history_before_cutoff(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    assert result.training_tournament_count == 10


def test_cutoff_date_resolution_prefers_explicit_arg_over_tournament_master(conn):
    date_str, source = resolve_cutoff_date(conn, LIVE_GAME_CODE, cutoff_date_arg="2030-06-15")
    assert date_str == "2030-06-15"
    assert source == "explicit_arg"


def test_cutoff_date_resolution_raises_without_any_source(conn):
    with pytest.raises(ValueError, match="No resolvable historical cutoff date"):
        resolve_cutoff_date(conn, LIVE_GAME_CODE, cutoff_date_arg=None)


def test_cutoff_date_resolution_falls_back_to_tournament_master(conn):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('KGEVT', ?, 'KG event', 2026, '2026-09-01', '2026-09-04')",
        (LIVE_GAME_CODE,),
    )
    conn.commit()
    date_str, source = resolve_cutoff_date(conn, LIVE_GAME_CODE, cutoff_date_arg=None)
    assert date_str == "2026-09-01"
    assert source == "tournament_master_fallback"


def test_tournament_name_resolution(conn):
    name, source = resolve_tournament_name(conn, LIVE_GAME_CODE, tournament_name_arg="제15회 KG 레이디스 오픈")
    assert name == "제15회 KG 레이디스 오픈"
    assert source == "explicit_arg"

    name, source = resolve_tournament_name(conn, LIVE_GAME_CODE, tournament_name_arg=None)
    assert name is None
    assert source == "unavailable"


# ----------------------------------------------------------------
# The 12 mandatory adversarial tests
# ----------------------------------------------------------------


def test_01_target_tournament_outcome_cannot_affect_its_own_predictions(conn):
    baseline = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    baseline_probs = {p.player_code: p.win_probability for p in baseline.predictions}

    # A player_event row sharing the LIVE game_code/event_id, dated
    # strictly AFTER the cutoff — as if the live tournament had since
    # been played and its own real outcome now exists in the DB. This
    # must never affect the ALREADY-COMPUTED strictly-prior prediction.
    _insert_tournament(conn, LIVE_GAME_CODE, LIVE_GAME_CODE, "2028-01-01", ["A", "B", "C", "D", "E"])
    conn.commit()

    after = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    after_probs = {p.player_code: p.win_probability for p in after.predictions}
    assert after.training_tournament_count == baseline.training_tournament_count
    for code in baseline_probs:
        assert after_probs[code] == pytest.approx(baseline_probs[code], abs=1e-12)


def test_02_future_tournament_cannot_affect_kg_predictions(conn):
    baseline = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    baseline_probs = {p.player_code: p.win_probability for p in baseline.predictions}

    # A DIFFERENT tournament, dated strictly AFTER the cutoff — must
    # never enter training.
    _insert_tournament(conn, "FUTURE01", "FUTURE01", "2027-06-01", ["A", "B", "C", "D", "E"])
    conn.commit()

    after = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    after_probs = {p.player_code: p.win_probability for p in after.predictions}
    assert after.training_tournament_count == baseline.training_tournament_count
    for code in baseline_probs:
        assert after_probs[code] == pytest.approx(baseline_probs[code], abs=1e-12)


def test_03_all_entry_players_survive_inference(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    predicted_codes = {p.player_code for p in result.predictions}
    assert predicted_codes == {"A", "B", "C", "D", "E", "ROOKIE1", "UNMATCHED1"}


def test_04_zero_history_player_receives_positive_probability(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    rookie = next(p for p in result.predictions if p.player_code == "ROOKIE1")
    assert rookie.prior_events_n == 0
    assert rookie.win_probability > 0


def test_05_unmatched_entry_survives(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    unmatched = next(p for p in result.predictions if p.player_code == "UNMATCHED1")
    assert unmatched.is_unmatched is True
    assert unmatched.win_probability > 0
    assert result.unmatched_count == 1


def test_06_duplicate_entry_player_code_is_explicitly_rejected():
    rows = [("A", "Player A"), ("B", "Player B"), ("A", "Player A duplicate")]
    dupes = _detect_duplicate_player_codes(rows)
    assert dupes == ["A"]


def test_07_probabilities_are_finite_and_non_negative(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    for p in result.predictions:
        assert math.isfinite(p.win_probability)
        assert p.win_probability >= 0


def test_08_probability_sum_equals_one_within_tolerance(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    assert abs(result.sum_probability - 1.0) <= 1e-6


def test_09_repeated_execution_is_identical(conn):
    first = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    second = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    first_probs = {p.player_code: p.win_probability for p in first.predictions}
    second_probs = {p.player_code: p.win_probability for p in second.predictions}
    assert first_probs == second_probs


def test_10_entry_row_order_does_not_change_probabilities(tmp_path):
    db_a = tmp_path / "a.sqlite"
    db_b = tmp_path / "b.sqlite"
    conn_a = _new_conn(db_a)
    conn_b = _new_conn(db_b)
    try:
        players = ["A", "B", "C", "D", "E"]
        for t in range(10):
            event_id = f"T{t:02d}"
            ranked = players[t % len(players):] + players[: t % len(players)]
            _insert_tournament(conn_a, event_id, event_id, f"2026-{(t % 12) + 1:02d}-01", ranked)
            _insert_tournament(conn_b, event_id, event_id, f"2026-{(t % 12) + 1:02d}-01", ranked)
        conn_b.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('ROOKIE1', 'ROOKIE1')")
        conn_a.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES ('ROOKIE1', 'ROOKIE1')")

        entrants = ["A", "B", "C", "D", "E", "ROOKIE1", "UNMATCHED1"]
        for player_code in entrants:
            _insert_entry(conn_a, LIVE_GAME_CODE, player_code, player_code)
        for player_code in reversed(entrants):
            _insert_entry(conn_b, LIVE_GAME_CODE, player_code, player_code)
        conn_a.commit()
        conn_b.commit()

        result_a = run_inference(conn_a, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
        result_b = run_inference(conn_b, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
        probs_a = {p.player_code: p.win_probability for p in result_a.predictions}
        probs_b = {p.player_code: p.win_probability for p in result_b.predictions}
        assert probs_a == probs_b
    finally:
        conn_a.close()
        conn_b.close()


def test_11_target_tournament_is_excluded_from_all_feature_histories(conn):
    baseline = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    baseline_n = {p.player_code: p.prior_events_n for p in baseline.predictions}

    # Insert a player_event row under the exact live game_code/event_id
    # for player A — must never be counted in A's prior_events_n.
    _insert_tournament(conn, LIVE_GAME_CODE, LIVE_GAME_CODE, "2026-06-01", ["A"])
    conn.commit()

    after = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    after_n = {p.player_code: p.prior_events_n for p in after.predictions}
    assert after_n["A"] == baseline_n["A"]


def test_12_no_feature_outside_frozen_m4_is_consumed(conn):
    result = run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)
    assert set(result.model_features) == {"prior_avg_round_score_to_par", "prior_recent_form_10"}
    assert set(result.model_features).issubset(MODEL_FEATURES["M4"])


# ----------------------------------------------------------------
# Read-only guarantee
# ----------------------------------------------------------------


def test_run_inference_never_writes_to_the_database(conn):
    before_entry = conn.execute("SELECT COUNT(*) FROM tournament_entry").fetchone()[0]
    before_master = conn.execute("SELECT COUNT(*) FROM player_master").fetchone()[0]
    before_events = conn.execute("SELECT COUNT(*) FROM player_event").fetchone()[0]

    run_inference(conn, LIVE_GAME_CODE, cutoff_date_arg=CUTOFF_DATE)

    assert conn.execute("SELECT COUNT(*) FROM tournament_entry").fetchone()[0] == before_entry
    assert conn.execute("SELECT COUNT(*) FROM player_master").fetchone()[0] == before_master
    assert conn.execute("SELECT COUNT(*) FROM player_event").fetchone()[0] == before_events


def test_run_inference_raises_on_empty_entry_list(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    connection = _new_conn(db_path)
    try:
        with pytest.raises(ValueError, match="tournament_entry has 0 rows"):
            run_inference(connection, "NOPE", cutoff_date_arg=CUTOFF_DATE)
    finally:
        connection.close()
