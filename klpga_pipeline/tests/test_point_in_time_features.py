"""Tests for klpga.backtest.point_in_time_features — including the
MANDATORY adversarial leakage tests (red-team requirement #6): insert
future tournaments, target-tournament rows, and extreme future scores/
wins, and prove the target tournament's point-in-time features do not
change. This is a hard gate — every test in the "LEAKAGE" section below
must pass before this layer can be considered safe to build a
walk-forward dataset on top of."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.backtest.point_in_time_features import (
    Corpus,
    compute_point_in_time_features,
    load_corpus,
)
from klpga.backtest.temporal import effective_tournament_date

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _tournament(conn, event_id, start_date=None, end_date="2026-01-01", name=None):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, event_id, name or event_id, 2026, start_date, end_date),
    )


def _player(conn, player_id, name=None):
    conn.execute(
        "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)",
        (player_id, name or player_id),
    )


def _event_row(
    conn,
    event_id,
    player_id,
    player_name=None,
    finish_position_numeric=None,
    score_to_par=None,
    rounds_played=4,
    made_cut=1,
):
    _player(conn, player_id, player_name)
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "finish_position, finish_position_numeric, made_cut, rounds_played, score_to_par) "
        "VALUES (?, ?, 2026, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id,
            event_id,
            player_id,
            player_name or player_id,
            str(finish_position_numeric) if finish_position_numeric is not None else None,
            finish_position_numeric,
            made_cut,
            rounds_played,
            score_to_par,
        ),
    )


def _round_row(conn, event_id, player_id, round_number, round_score, round_to_par=None, player_name=None):
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, ?, ?)",
        (event_id, event_id, round_number, player_id, player_name or player_id, round_score, round_to_par),
    )


def _baseline_scenario(conn):
    """Target T (2026-06-01), player P1 with two REAL prior events:
    A (2026-01-01, made cut, T3, score_to_par=-5) and B (2026-03-01, WIN,
    score_to_par=-10). Returns (target_event_id, target_effective_date)."""
    _tournament(conn, "T", start_date="2026-06-01", end_date="2026-06-04")
    _tournament(conn, "A", start_date="2026-01-01", end_date="2026-01-04")
    _tournament(conn, "B", start_date="2026-03-01", end_date="2026-03-04")

    _event_row(conn, "A", "P1", finish_position_numeric=3, score_to_par=-5, rounds_played=4)
    _round_row(conn, "A", "P1", 1, 68, round_to_par=-4)
    _round_row(conn, "A", "P1", 2, 70)
    _round_row(conn, "A", "P1", 3, 70)
    _round_row(conn, "A", "P1", 4, 68, round_to_par=-4)
    # A second player in event A's round 1, so the field-relative
    # benchmark has something to compare P1 against.
    _event_row(conn, "A", "P2", finish_position_numeric=10, score_to_par=2, rounds_played=4)
    _round_row(conn, "A", "P2", 1, 72)
    _round_row(conn, "A", "P2", 2, 74)
    _round_row(conn, "A", "P2", 3, 71)
    _round_row(conn, "A", "P2", 4, 73)

    _event_row(conn, "B", "P1", finish_position_numeric=1, score_to_par=-10, rounds_played=4)
    _round_row(conn, "B", "P1", 1, 66)
    _round_row(conn, "B", "P1", 2, 68)
    _round_row(conn, "B", "P1", 3, 69)
    _round_row(conn, "B", "P1", 4, 65)

    conn.commit()

    target_eff = effective_tournament_date("2026-06-01", "2026-06-04")
    return "T", target_eff.value


def _features_for_p1(conn, target_event_id, target_effective_date):
    corpus = load_corpus(conn)
    return compute_point_in_time_features(corpus, target_event_id, target_effective_date, "P1", "선수P1")


# ----------------------------------------------------------------
# Baseline correctness
# ----------------------------------------------------------------


def test_prior_events_n_and_win_top_counts(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    features = _features_for_p1(conn, target_event_id, target_date)

    assert features.prior_events_n == 2
    assert features.prior_wins == 1
    assert features.prior_top5 == 2
    assert features.prior_top10 == 2
    assert features.prior_made_cuts == 2
    assert features.prior_cut_rate == 1.0
    assert set(features.prior_event_ids_used) == {"A", "B"}


def test_prior_avg_round_score_to_par_rate_formula(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    features = _features_for_p1(conn, target_event_id, target_date)
    # sum(score_to_par) = -5 + -10 = -15, sum(rounds_played) = 4 + 4 = 8
    assert features.prior_avg_round_score_to_par == -1.88  # round(-15/8, 2)
    assert features.prior_avg_round_score_to_par_n == 8


def test_recent_form_windows_never_padded(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    features = _features_for_p1(conn, target_event_id, target_date)

    # Only 2 prior events exist — every window (5/10/20) must report
    # n=2, not be padded toward the window size.
    assert features.prior_recent_form_5 == -7.5  # mean(-10, -5), newest first
    assert features.prior_recent_form_5_n == 2
    assert features.prior_recent_form_10_n == 2
    assert features.prior_recent_form_20_n == 2
    assert features.recent_form_event_ids_used[5] == ("B", "A")  # newest (B) first


def test_prior_avg_round_to_par_sparse_field(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    features = _features_for_p1(conn, target_event_id, target_date)
    # Only round 1 and 4 of event A had round_to_par populated (-4, -4);
    # event B has none at all in this fixture.
    assert features.prior_avg_round_to_par == -4.0
    assert features.prior_avg_round_to_par_n == 2


def test_field_relative_round_score_leave_one_out(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    features = _features_for_p1(conn, target_event_id, target_date)
    # Event A round 1: P1=68, P2=72 -> P1's leave-one-out field avg = 72,
    # deviation = 68-72 = -4. Round 2: P1=70, P2=74 -> -4. Round 3:
    # P1=70, P2=71 -> -1. Round 4: P1=68, P2=73 -> -5.
    # Event B has no second player -> every round skipped (n<2 field).
    assert features.prior_avg_field_relative_round_score == -3.5  # mean(-4,-4,-1,-5)
    assert features.prior_avg_field_relative_round_score_n == 4


def test_rookie_with_zero_prior_events_gets_none_not_padded(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    corpus = load_corpus(conn)
    features = compute_point_in_time_features(corpus, target_event_id, target_date, "ROOKIE", "신인선수")

    assert features.prior_events_n == 0
    assert features.prior_wins == 0
    assert features.prior_cut_rate is None
    assert features.prior_avg_round_score_to_par is None
    assert features.prior_avg_round_score_to_par_n == 0
    assert features.prior_recent_form_5 is None
    assert features.prior_recent_form_5_n == 0
    assert features.prior_avg_round_to_par is None
    assert features.prior_avg_field_relative_round_score is None
    # Never a fabricated 0% win probability at this layer — this module
    # emits no probability field at all.
    assert not hasattr(features, "win_probability")


# ----------------------------------------------------------------
# Same-day / missing-date fail-safe (requirement #1)
# ----------------------------------------------------------------


def test_same_day_tournament_excluded_fail_safe(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    # A same-calendar-day sibling tournament S, with a real win for P1 —
    # must NOT be treated as prior, since it is not STRICTLY before T.
    _tournament(conn, "S", start_date="2026-06-01", end_date="2026-06-01")
    _event_row(conn, "S", "P1", finish_position_numeric=1, score_to_par=-20, rounds_played=4)
    conn.commit()

    features = _features_for_p1(conn, target_event_id, target_date)
    assert features.prior_events_n == 2  # still just A and B
    assert "S" not in features.prior_event_ids_used


def test_tournament_with_no_resolvable_date_excluded_fail_safe(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    # A tournament with neither start_date nor a parseable end_date —
    # must be excluded rather than guessed as "earlier."
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('U', 'U', 'Undated', 2026, NULL, 'not-a-date')"
    )
    _event_row(conn, "U", "P1", finish_position_numeric=1, score_to_par=-30, rounds_played=4)
    conn.commit()

    features = _features_for_p1(conn, target_event_id, target_date)
    assert features.prior_events_n == 2
    assert "U" not in features.prior_event_ids_used


# ----------------------------------------------------------------
# LEAKAGE — mandatory adversarial tests (requirement #6, hard gate)
# ----------------------------------------------------------------


def test_leakage_future_tournament_does_not_change_target_features(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    before = _features_for_p1(conn, target_event_id, target_date)

    _tournament(conn, "FUTURE", start_date="2026-09-01", end_date="2026-09-04")
    _event_row(conn, "FUTURE", "P1", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    _round_row(conn, "FUTURE", "P1", 1, 40)
    conn.commit()

    after = _features_for_p1(conn, target_event_id, target_date)
    assert after == before


def test_leakage_target_tournament_own_rows_do_not_change_target_features(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    before = _features_for_p1(conn, target_event_id, target_date)

    # Insert P1's OWN result row for the target tournament T itself —
    # an extreme win. Must never be counted as "prior" to itself.
    _event_row(conn, target_event_id, "P1", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    _round_row(conn, target_event_id, "P1", 1, 40)
    conn.commit()

    after = _features_for_p1(conn, target_event_id, target_date)
    assert after == before


def test_leakage_extreme_future_scores_and_wins_do_not_change_target_features(conn):
    target_event_id, target_date = _baseline_scenario(conn)
    before = _features_for_p1(conn, target_event_id, target_date)

    # A deliberately implausible canary: a "future" event dated after T,
    # with a physically-impossible score and a win — if ANY of this
    # leaks in, the assertion below fails loudly rather than drifting
    # by a small, easy-to-miss amount.
    _tournament(conn, "CANARY", start_date="2026-12-25", end_date="2026-12-28")
    _event_row(conn, "CANARY", "P1", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    for round_number in (1, 2, 3, 4):
        _round_row(conn, "CANARY", "P1", round_number, 1, round_to_par=-70)
    conn.commit()

    after = _features_for_p1(conn, target_event_id, target_date)
    assert after == before


def test_leakage_future_event_round_field_benchmark_not_used(conn):
    """The field-relative benchmark is keyed by (event_id, round_number)
    — confirm that a FUTURE event sharing the same round_number as a
    real prior event does not contaminate the prior event's own
    benchmark (they're different event_ids, so different keys)."""
    target_event_id, target_date = _baseline_scenario(conn)
    before = _features_for_p1(conn, target_event_id, target_date)

    _tournament(conn, "FUTURE2", start_date="2026-10-01", end_date="2026-10-04")
    _event_row(conn, "FUTURE2", "P3", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    _round_row(conn, "FUTURE2", "P3", 1, 30)  # same round_number=1 as event A's round 1

    after = _features_for_p1(conn, target_event_id, target_date)
    assert after == before


def test_leakage_multiple_adversarial_insertions_combined(conn):
    """All three adversarial insertion types at once, per requirement
    #6's literal wording — belt-and-suspenders on top of the individual
    tests above."""
    target_event_id, target_date = _baseline_scenario(conn)
    before = _features_for_p1(conn, target_event_id, target_date)

    _tournament(conn, "FUTURE3", start_date="2026-11-01", end_date="2026-11-04")
    _event_row(conn, "FUTURE3", "P1", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    _round_row(conn, "FUTURE3", "P1", 1, 20, round_to_par=-50)

    _event_row(conn, target_event_id, "P1", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    _round_row(conn, target_event_id, "P1", 2, 20, round_to_par=-50)

    _tournament(conn, "SAMEDAY2", start_date=target_date.isoformat(), end_date=target_date.isoformat())
    _event_row(conn, "SAMEDAY2", "P1", finish_position_numeric=1, score_to_par=-999, rounds_played=4)
    conn.commit()

    after = _features_for_p1(conn, target_event_id, target_date)
    assert after == before
