"""Tests for klpga.neo_win.player_status — the shared, evidence-only
round-aware player status classifier reused by scripts/44 and
scripts/45."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.player_status import (
    STARTED_UNDERIVABLE,
    STATUS_COLLECTION_MISSING,
    STATUS_COMPLETED,
    STATUS_CUT,
    STATUS_DQ,
    STATUS_DNS,
    STATUS_UNKNOWN,
    STATUS_WD,
    classify_player_round_status,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "status.sqlite")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES ('E1', 'G1', 'T', 2026, '2027-01-01', '2027-01-04')"
    )
    connection.commit()
    return connection


def _player_event(conn, player_code, *, withdrawn=0, disqualified=0, made_cut=0, rounds_played=None,
                   finish_position=None):
    # made_cut is NOT NULL DEFAULT 0 in schema.sql — every real row has a 0/1 value, never NULL.
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_code, player_code))
    conn.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, withdrawn, disqualified, rounds_played, score_to_par) VALUES "
        "('E1', 'G1', 2026, ?, ?, ?, NULL, ?, ?, ?, ?, NULL)",
        (player_code, player_code, finish_position, made_cut, withdrawn, disqualified, rounds_played),
    )
    conn.commit()


def _player_round(conn, player_code, round_number, round_to_par=-1):
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_code, player_code))
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES ('E1', 'G1', 2026, ?, ?, ?, ?, ?)",
        (round_number, player_code, player_code, 70 + round_to_par, round_to_par),
    )
    conn.commit()


def test_completed_round_is_status_completed(conn):
    _player_round(conn, "p1", round_number=1, round_to_par=-3)
    result = classify_player_round_status(conn, "G1", "p1", 1)
    assert result.classification == STATUS_COMPLETED
    assert result.completed_this_round is True
    assert result.started_this_round is True


def test_wd_confirmed_by_boolean_flag(conn):
    _player_event(conn, "p2", withdrawn=1, finish_position="WD")
    result = classify_player_round_status(conn, "G1", "p2", 1)
    assert result.classification == STATUS_WD
    assert result.completed_this_round is False
    assert result.started_this_round == STARTED_UNDERIVABLE


def test_dq_confirmed_by_boolean_flag(conn):
    _player_event(conn, "p3", disqualified=1, finish_position="DQ")
    result = classify_player_round_status(conn, "G1", "p3", 1)
    assert result.classification == STATUS_DQ


def test_dns_text_only_flagged_never_asserted_as_confirmed(conn):
    _player_event(conn, "p4", finish_position="DNS")
    result = classify_player_round_status(conn, "G1", "p4", 1)
    assert result.classification == STATUS_DNS
    assert "not guessed" in result.detail


def test_no_player_event_row_is_unknown_not_assumed_dns(conn):
    result = classify_player_round_status(conn, "G1", "p5", 1)
    assert result.classification == STATUS_UNKNOWN
    assert result.event_status == "NO_PLAYER_EVENT_ROW"
    assert result.in_entry_field is False


def test_collection_missing_requires_positive_participation_evidence(conn):
    _player_event(conn, "p6", made_cut=1, rounds_played=4, finish_position="12")
    result = classify_player_round_status(conn, "G1", "p6", 1)
    assert result.classification == STATUS_COLLECTION_MISSING
    assert "pipeline gap" in result.detail


def test_no_positive_evidence_stays_unknown_never_collection_missing(conn):
    _player_event(conn, "p7", rounds_played=0)
    result = classify_player_round_status(conn, "G1", "p7", 1)
    assert result.classification == STATUS_UNKNOWN


def test_cut_player_missing_r3_is_status_cut_never_collection_missing(conn):
    """The key R2-architecture addition: once made_cut=False is a real
    fact (post-cut), a missing R3/R4 score is a real, expected outcome
    — never mistaken for a pipeline gap."""
    _player_event(conn, "p8", made_cut=0, rounds_played=2, finish_position="CUT")
    result = classify_player_round_status(conn, "G1", "p8", 3)
    assert result.classification == STATUS_CUT
    assert "expected elimination outcome" in result.detail


def test_cut_status_never_applied_at_round_1_or_2(conn):
    """The cut is only DETERMINED after Round 2 concludes — a missing
    R1 or R2 score must never be classified CUT, even if made_cut
    happens to be recorded False for some other reason."""
    _player_event(conn, "p9", made_cut=0, rounds_played=1, finish_position="CUT")
    r1 = classify_player_round_status(conn, "G1", "p9", 1)
    r2 = classify_player_round_status(conn, "G1", "p9", 2)
    assert r1.classification != STATUS_CUT
    assert r2.classification != STATUS_CUT


def test_made_cut_true_player_missing_r3_is_collection_missing_not_cut(conn):
    # made_cut=1 and rounds_played=4 (the site's own summary says they finished) — R3's
    # absence here is a real pipeline gap, never mistaken for a cut elimination.
    _player_event(conn, "p10", made_cut=1, rounds_played=4, finish_position="T5")
    result = classify_player_round_status(conn, "G1", "p10", 3)
    assert result.classification == STATUS_COLLECTION_MISSING
    assert result.made_cut is True


def test_made_cut_false_without_rounds_played_corroboration_stays_unknown(conn):
    """made_cut is NOT NULL DEFAULT 0 in schema.sql — made_cut=0 alone
    (with no rounds_played corroboration) could just mean the column
    was never updated, not a confirmed elimination. Must never be
    classified CUT without the corroborating signal."""
    _player_event(conn, "p12", made_cut=0, rounds_played=None, finish_position=None)
    result = classify_player_round_status(conn, "G1", "p12", 3)
    assert result.classification != STATUS_CUT
    assert result.classification == STATUS_UNKNOWN


def test_in_entry_field_detected_independently_of_player_event(conn):
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('G1', 'p11', 'P11', 'test', '2027-01-01T00:00:00Z')"
    )
    conn.commit()
    result = classify_player_round_status(conn, "G1", "p11", 1)
    assert result.in_entry_field is True
    assert result.classification == STATUS_UNKNOWN  # still no player_event row
