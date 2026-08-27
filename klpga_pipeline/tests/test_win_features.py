"""Tests for klpga.neo_win.win_features — BETA #001-C Phase 6's win
feature candidates. Same fixture shape as test_point_in_time_features.py
(the module this one directly reuses `Corpus`/`is_strictly_before`
from)."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from klpga.backtest.point_in_time_features import load_corpus
from klpga.neo_win.win_features import WIN_FEATURE_CANDIDATE_NAMES, compute_win_feature_candidates, season_by_event

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _tournament(conn, event_id, start_date, season=2026):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, event_id, event_id, season, start_date, start_date),
    )


def _player(conn, player_id):
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id))


def _event_row(conn, event_id, player_id, finish_position_numeric, season=2026):
    _player(conn, player_id)
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 4, -5)",
        (event_id, event_id, season, player_id, player_id, str(finish_position_numeric), finish_position_numeric),
    )


def test_no_prior_events_everything_none_or_zero(conn):
    _tournament(conn, "T", "2026-06-01")
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2026, 6, 1), 2026, "P1", season_by_event(conn))
    for name in WIN_FEATURE_CANDIDATE_NAMES:
        assert out[name] is None
        assert out[f"{name}_n"] == 0


def test_win_within_52_weeks_counted(conn):
    _tournament(conn, "A", "2026-01-01")
    _tournament(conn, "T", "2026-06-01")
    _event_row(conn, "A", "P1", finish_position_numeric=1)
    conn.commit()
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2026, 6, 1), 2026, "P1", season_by_event(conn))
    assert out["wins_last_52_weeks"] == 1.0
    assert out["wins_last_52_weeks_n"] == 1


def test_win_outside_52_weeks_excluded(conn):
    _tournament(conn, "A", "2020-01-01")
    _tournament(conn, "T", "2026-06-01")
    _event_row(conn, "A", "P1", finish_position_numeric=1)
    conn.commit()
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2026, 6, 1), 2026, "P1", season_by_event(conn))
    assert out["wins_last_52_weeks_n"] == 0
    assert out["wins_last_52_weeks"] is None


def test_wins_current_season_only_counts_matching_season(conn):
    _tournament(conn, "A", "2025-01-01", season=2025)
    _tournament(conn, "B", "2026-01-01", season=2026)
    _tournament(conn, "T", "2026-06-01", season=2026)
    _event_row(conn, "A", "P1", finish_position_numeric=1, season=2025)
    _event_row(conn, "B", "P1", finish_position_numeric=1, season=2026)
    conn.commit()
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2026, 6, 1), 2026, "P1", season_by_event(conn))
    assert out["wins_current_season"] == 1.0
    assert out["wins_current_season_n"] == 1


def test_wins_last_10_starts_caps_at_ten_most_recent(conn):
    for i in range(12):
        event_id = f"E{i:02d}"
        _tournament(conn, event_id, f"2026-{(i % 12) + 1:02d}-01")
        # Win only on the OLDEST event (would be excluded from a
        # last-10 window if ordering/truncation is correct).
        _event_row(conn, event_id, "P1", finish_position_numeric=1 if i == 0 else 5)
    _tournament(conn, "T", "2027-01-01")
    conn.commit()
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2027, 1, 1), 2027, "P1", season_by_event(conn))
    assert out["wins_last_10_starts_n"] == 10
    assert out["wins_last_10_starts"] == 0.0  # the win was in event 0, the 12th-most-recent -> excluded


def test_top3_and_top10_rate(conn):
    _tournament(conn, "A", "2026-01-01")
    _tournament(conn, "B", "2026-02-01")
    _tournament(conn, "C", "2026-03-01")
    _tournament(conn, "D", "2026-04-01")
    _tournament(conn, "T", "2026-06-01")
    _event_row(conn, "A", "P1", finish_position_numeric=1)  # top3 + top10
    _event_row(conn, "B", "P1", finish_position_numeric=7)  # top10 only
    _event_row(conn, "C", "P1", finish_position_numeric=25)  # neither
    _event_row(conn, "D", "P1", finish_position_numeric=3)  # top3 + top10
    conn.commit()
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2026, 6, 1), 2026, "P1", season_by_event(conn))
    assert out["top3_rate_n"] == 4
    assert out["top3_rate"] == 0.5
    assert out["top10_rate_n"] == 4
    assert out["top10_rate"] == 0.75


def test_target_event_and_future_events_never_leak_into_any_candidate(conn):
    _tournament(conn, "T", "2026-06-01")
    _tournament(conn, "FUTURE", "2027-01-01")
    _event_row(conn, "T", "P1", finish_position_numeric=1)  # target itself — must never count
    _event_row(conn, "FUTURE", "P1", finish_position_numeric=1)  # future win — must never count
    conn.commit()
    corpus = load_corpus(conn)
    out = compute_win_feature_candidates(corpus, "T", date(2026, 6, 1), 2026, "P1", season_by_event(conn))
    for name in WIN_FEATURE_CANDIDATE_NAMES:
        assert out[name] is None
        assert out[f"{name}_n"] == 0
