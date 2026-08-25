"""Tests for src/klpga/analytics/player_stats.py — hand-computed
expected values against a synthetic schema-based DB, so every formula
documented in that module's docstring is checked against a concrete
example, not just "it runs."""
from __future__ import annotations

import sqlite3
import statistics
from pathlib import Path

import pytest

from klpga.analytics.player_stats import compute_player_stats

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def _insert_tournament(conn, event_id, end_date, season=2026):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (event_id, event_id, f"Tournament {event_id}", season, end_date),
    )


def _insert_player(conn, player_id):
    conn.execute(
        "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)",
        (player_id, f"Player {player_id}"),
    )


def _insert_event(
    conn, event_id, player_id, made_cut, finish_position_numeric, score_to_par, rounds_played
):
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, finish_position_numeric, score_to_par, rounds_played) "
        "VALUES (?, ?, 2026, ?, ?, ?, ?, ?, ?)",
        (event_id, event_id, player_id, f"Player {player_id}", made_cut,
         finish_position_numeric, score_to_par, rounds_played),
    )


def _insert_round(conn, event_id, player_id, round_number, round_score):
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, "
        "player_name, round_score) VALUES (?, ?, 2026, ?, ?, ?, ?)",
        (event_id, event_id, round_number, player_id, f"Player {player_id}", round_score),
    )


def test_full_scenario_matches_hand_computed_values(conn):
    """One player (p1) across 3 tournaments, oldest to newest: T1
    (2026-01-01, made cut, finish 3, score_to_par -2, rounds
    [70,71,69,68]), T2 (2026-02-01, missed cut, finish 45, score_to_par
    +5, rounds [75,74]), T3 (2026-03-01, WON, finish 1, score_to_par
    -10, rounds [68,67,70,69]). All hand-computed below."""
    _insert_player(conn, "p1")
    _insert_tournament(conn, "T1", "2026-01-01")
    _insert_tournament(conn, "T2", "2026-02-01")
    _insert_tournament(conn, "T3", "2026-03-01")

    _insert_event(conn, "T1", "p1", made_cut=1, finish_position_numeric=3, score_to_par=-2, rounds_played=4)
    _insert_event(conn, "T2", "p1", made_cut=0, finish_position_numeric=45, score_to_par=5, rounds_played=2)
    _insert_event(conn, "T3", "p1", made_cut=1, finish_position_numeric=1, score_to_par=-10, rounds_played=4)

    for r, score in enumerate([70, 71, 69, 68], start=1):
        _insert_round(conn, "T1", "p1", r, score)
    for r, score in enumerate([75, 74], start=1):
        _insert_round(conn, "T2", "p1", r, score)
    for r, score in enumerate([68, 67, 70, 69], start=1):
        _insert_round(conn, "T3", "p1", r, score)
    conn.commit()

    rows = compute_player_stats(conn)
    assert len(rows) == 1
    row = rows[0]

    assert row["player_id"] == "p1"
    assert row["derived_tournaments_played"] == 3
    assert row["derived_rounds_played"] == 10
    assert row["derived_made_cuts"] == 2
    assert row["derived_cut_rate"] == round(2 / 3, 2)
    assert row["derived_wins"] == 1
    assert row["derived_top5"] == 2
    assert row["derived_top10"] == 2
    assert row["derived_best_finish"] == 1

    all_scores = [70, 71, 69, 68, 75, 74, 68, 67, 70, 69]
    assert row["derived_avg_round_score"] == round(sum(all_scores) / len(all_scores), 2)
    assert row["derived_round_scoring_stddev"] == round(statistics.stdev(all_scores), 2)

    # Event-level average: one vote per event, regardless of rounds_played.
    assert row["derived_avg_event_score_to_par"] == round((-2 + 5 - 10) / 3, 2)
    assert row["derived_avg_event_score_to_par_n"] == 3

    # Round-level rate: sum(score_to_par) / sum(rounds_played), so the
    # 4-round events weigh more than the 2-round missed cut.
    # (-2 + 5 - 10) / (4 + 2 + 4) = -7 / 10.
    assert row["derived_avg_round_score_to_par"] == round((-2 + 5 - 10) / 10, 2)
    assert row["derived_avg_round_score_to_par_n"] == 10

    # Only 3 events exist, so all three recent-form windows fall back to
    # all 3, newest-first: T3(-10), T2(5), T1(-2).
    expected_recent = round((-10 + 5 - 2) / 3, 2)
    for window in (5, 10, 20):
        assert row[f"derived_recent_event_form_{window}"] == expected_recent
        assert row[f"derived_recent_event_form_{window}_n"] == 3

    # Weighted (k=3): weights [3, 2, 1] applied newest-first to
    # [-10, 5, -2] -> (3*-10 + 2*5 + 1*-2) / 6 = -22/6.
    assert row["derived_weighted_recent_event_form"] == round(-22 / 6, 2)
    assert row["derived_weighted_recent_event_form_n"] == 3


def test_zero_round_player_gets_null_score_metrics_not_zero(conn):
    """A player who appears in the field but has zero valid round
    scores and no numeric finish (the confirmed real 0-round early-exit
    pattern — see docs/SITE_STRUCTURE_TODO.md section 5) must not have
    NULLs silently coerced into misleading zeros."""
    _insert_player(conn, "p2")
    _insert_tournament(conn, "T1", "2026-01-01")
    _insert_event(conn, "T1", "p2", made_cut=0, finish_position_numeric=None, score_to_par=None, rounds_played=0)
    conn.commit()

    row = compute_player_stats(conn)[0]
    assert row["derived_tournaments_played"] == 1
    assert row["derived_rounds_played"] == 0
    assert row["derived_made_cuts"] == 0
    assert row["derived_cut_rate"] == 0.0
    assert row["derived_wins"] == 0
    assert row["derived_best_finish"] is None
    assert row["derived_avg_round_score"] is None
    assert row["derived_round_scoring_stddev"] is None
    assert row["derived_avg_event_score_to_par"] is None
    assert row["derived_avg_event_score_to_par_n"] == 0
    assert row["derived_avg_round_score_to_par"] is None
    assert row["derived_avg_round_score_to_par_n"] == 0
    assert row["derived_recent_event_form_5"] is None
    assert row["derived_recent_event_form_5_n"] == 0
    assert row["derived_weighted_recent_event_form"] is None
    assert row["derived_weighted_recent_event_form_n"] == 0


def test_scoring_stddev_requires_at_least_two_rounds(conn):
    """Sample standard deviation is undefined for n=1 — must be NULL,
    never a fabricated 0.0."""
    _insert_player(conn, "p3")
    _insert_tournament(conn, "T1", "2026-01-01")
    _insert_event(conn, "T1", "p3", made_cut=0, finish_position_numeric=50, score_to_par=3, rounds_played=1)
    _insert_round(conn, "T1", "p3", 1, 72)
    conn.commit()

    row = compute_player_stats(conn)[0]
    assert row["derived_avg_round_score"] == 72.0
    assert row["derived_round_scoring_stddev"] is None


def test_recent_form_window_caps_at_actual_available_events(conn):
    """A player with 7 events must report recent_form_5 over exactly
    their 5 most recent (n=5), and recent_form_10/_20 over all 7
    (n=7) — never padded or treated as a full window."""
    _insert_player(conn, "p4")
    for i in range(1, 8):
        event_id = f"T{i}"
        _insert_tournament(conn, event_id, f"2026-{i:02d}-01")
        _insert_event(
            conn, event_id, "p4", made_cut=1, finish_position_numeric=i,
            score_to_par=-i, rounds_played=4,
        )
    conn.commit()

    row = compute_player_stats(conn)[0]
    # Newest-first by end_date: T7(-7), T6(-6), ..., T1(-1).
    newest_five = [-7, -6, -5, -4, -3]
    assert row["derived_recent_event_form_5"] == round(sum(newest_five) / 5, 2)
    assert row["derived_recent_event_form_5_n"] == 5

    all_seven = [-7, -6, -5, -4, -3, -2, -1]
    expected_all = round(sum(all_seven) / 7, 2)
    assert row["derived_recent_event_form_10"] == expected_all
    assert row["derived_recent_event_form_10_n"] == 7
    assert row["derived_recent_event_form_20"] == expected_all
    assert row["derived_recent_event_form_20_n"] == 7


def test_wins_top5_top10_ignore_events_with_no_numeric_finish(conn):
    _insert_player(conn, "p5")
    _insert_tournament(conn, "T1", "2026-01-01")
    _insert_tournament(conn, "T2", "2026-02-01")
    # T1: a real win. T2: INCOMPLETE (999-sentinel) — no numeric finish.
    _insert_event(conn, "T1", "p5", made_cut=1, finish_position_numeric=1, score_to_par=-8, rounds_played=4)
    _insert_event(conn, "T2", "p5", made_cut=0, finish_position_numeric=None, score_to_par=None, rounds_played=0)
    conn.commit()

    row = compute_player_stats(conn)[0]
    assert row["derived_tournaments_played"] == 2
    assert row["derived_wins"] == 1
    assert row["derived_top5"] == 1
    assert row["derived_top10"] == 1
    assert row["derived_best_finish"] == 1


def test_uses_player_id_not_player_name_as_identity(conn):
    """Two different players sharing a display name must stay
    separate — player_id (the confirmed real playerCode) is the only
    identity key, never player_name."""
    _insert_player(conn, "p6")
    _insert_player(conn, "p7")
    conn.execute(
        "UPDATE player_master SET player_name = 'Same Name' WHERE player_id IN ('p6', 'p7')"
    )
    _insert_tournament(conn, "T1", "2026-01-01")
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, finish_position_numeric, score_to_par, rounds_played) "
        "VALUES ('T1', 'T1', 2026, 'p6', 'Same Name', 1, 1, -5, 4)"
    )
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, "
        "made_cut, finish_position_numeric, score_to_par, rounds_played) "
        "VALUES ('T1', 'T1', 2026, 'p7', 'Same Name', 0, 60, 8, 2)"
    )
    conn.commit()

    rows = {row["player_id"]: row for row in compute_player_stats(conn)}
    assert set(rows.keys()) == {"p6", "p7"}
    assert rows["p6"]["derived_wins"] == 1
    assert rows["p7"]["derived_wins"] == 0
