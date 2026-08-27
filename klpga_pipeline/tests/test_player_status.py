"""Tests for klpga.neo_win.player_status — the shared, evidence-only
round-aware player status classifier reused by scripts/44 and
scripts/45."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.player_status import (
    READINESS_GO,
    READINESS_HARD_STOP,
    READINESS_WARN,
    STARTED_UNDERIVABLE,
    STATUS_COLLECTION_MISSING,
    STATUS_COMPLETED,
    STATUS_CUT,
    STATUS_DQ,
    STATUS_DNS,
    STATUS_UNKNOWN,
    STATUS_WD,
    assess_field_readiness,
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


def _entry(conn, player_code):
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('G1', ?, ?, 'test', '2027-01-01T00:00:00Z')",
        (player_code, player_code),
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


# ---------------------------------------------------------------
# assess_field_readiness — status-aware readiness gate, replacing any
# numeric "N% of the field must have a score" threshold.
# Scenarios per the roadmap decision (ENTRY_FIELD != COMPLETED field).
# ---------------------------------------------------------------


def test_scenario_1_mostly_completed_plus_legitimate_wd_is_go(conn):
    for code in ["p1", "p2", "p3"]:
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-2)
    for code in ["p4", "p5"]:
        _entry(conn, code)
        _player_event(conn, code, withdrawn=1, finish_position="WD")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO
    assert readiness.field_size == 5
    assert readiness.unknown_players == ()
    assert readiness.collection_missing_players == ()


def test_scenario_2_mostly_completed_plus_legitimate_dq_is_go(conn):
    for code in ["p1", "p2", "p3", "p4"]:
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-2)
    _entry(conn, "p5")
    _player_event(conn, "p5", disqualified=1, finish_position="DQ")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO


def test_scenario_3_legitimate_dns_with_no_scoring_row_is_go(conn):
    for code in ["p1", "p2", "p3", "p4"]:
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-2)
    _entry(conn, "p5")
    _player_event(conn, "p5", finish_position="DNS")  # text-only DNS, no score row at all

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO
    statuses_by_code = {s.player_code: s for s in readiness.statuses}
    assert statuses_by_code["p5"].classification == STATUS_DNS


def test_scenario_4_unexplained_missing_player_is_warn(conn):
    for code in ["p1", "p2", "p3", "p4"]:
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-2)
    _entry(conn, "p5")  # no player_event row, no player_round row -> UNKNOWN

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_WARN
    assert readiness.unknown_players == ("p5",)
    assert readiness.collection_missing_players == ()


def test_scenario_5_confirmed_collection_failure_is_hard_stop(conn):
    for code in ["p1", "p2", "p3", "p4"]:
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-2)
    _entry(conn, "p5")
    # p5 has positive evidence of participation (rounds_played=4, no WD/DQ) but no round_number=2 row.
    _player_event(conn, "p5", made_cut=1, rounds_played=4, finish_position="T10")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_HARD_STOP
    assert readiness.collection_missing_players == ("p5",)


def test_zero_real_round_rows_at_all_is_hard_stop(conn):
    """Total non-ingestion (official round data has not arrived yet at
    all) is a distinct HARD_STOP cause from a single player's gap."""
    for code in ["p1", "p2", "p3"]:
        _entry(conn, code)
    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_HARD_STOP
    assert readiness.collection_missing_players == ()


def test_readiness_never_uses_a_numeric_percentage_threshold(conn):
    """9 of 10 players complete + 1 legitimate WD is still GO — the gate
    must never require a minimum count/percentage of the raw entry field."""
    for i in range(9):
        code = f"p{i}"
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-i)
    _entry(conn, "p9")
    _player_event(conn, "p9", withdrawn=1, finish_position="WD")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO
    assert readiness.field_size == 10


def test_readiness_reflects_every_entry_field_player_never_drops_one(conn):
    for code in ["p1", "p2", "p3"]:
        _entry(conn, code)
        _player_round(conn, code, round_number=2, round_to_par=-1)
    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert {s.player_code for s in readiness.statuses} == {"p1", "p2", "p3"}
    assert readiness.field_size == 3


# ---------------------------------------------------------------
# Real production scale (120-player field) — the exact literal
# scenarios required for the R2 status-aware readiness checkpoint.
# ---------------------------------------------------------------


def _bulk_completed(conn, codes, round_number=2):
    for i, code in enumerate(codes):
        _entry(conn, code)
        _player_round(conn, code, round_number=round_number, round_to_par=-(i % 10))


def test_120_field_118_completed_plus_2_wd_is_go(conn):
    completed = [f"p{i}" for i in range(118)]
    wd = [f"wd{i}" for i in range(2)]
    _bulk_completed(conn, completed)
    for code in wd:
        _entry(conn, code)
        _player_event(conn, code, withdrawn=1, finish_position="WD")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO
    assert readiness.field_size == 120
    assert readiness.unknown_players == ()
    assert readiness.collection_missing_players == ()
    statuses_by_code = {s.player_code: s for s in readiness.statuses}
    for code in wd:
        assert statuses_by_code[code].classification == STATUS_WD


def test_120_field_119_completed_plus_1_dq_is_go(conn):
    completed = [f"p{i}" for i in range(119)]
    _bulk_completed(conn, completed)
    _entry(conn, "dq0")
    _player_event(conn, "dq0", disqualified=1, finish_position="DQ")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO
    assert readiness.field_size == 120
    statuses_by_code = {s.player_code: s for s in readiness.statuses}
    assert statuses_by_code["dq0"].classification == STATUS_DQ


def test_120_field_dns_without_score_is_go(conn):
    completed = [f"p{i}" for i in range(119)]
    _bulk_completed(conn, completed)
    _entry(conn, "dns0")
    _player_event(conn, "dns0", finish_position="DNS")  # text-only DNS, no round_2 row, no confirmed boolean

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_GO
    assert readiness.field_size == 120
    statuses_by_code = {s.player_code: s for s in readiness.statuses}
    assert statuses_by_code["dns0"].classification == STATUS_DNS


def test_120_field_unexplained_missing_is_warn(conn):
    completed = [f"p{i}" for i in range(119)]
    _bulk_completed(conn, completed)
    _entry(conn, "unk0")  # no player_event row, no player_round row -> genuinely UNKNOWN

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_WARN
    assert readiness.field_size == 120
    assert readiness.unknown_players == ("unk0",)
    assert readiness.collection_missing_players == ()


def test_120_field_collection_failure_is_hard_stop(conn):
    completed = [f"p{i}" for i in range(119)]
    _bulk_completed(conn, completed)
    _entry(conn, "cm0")
    # positive evidence of participation (rounds_played covers round 2), no WD/DQ/DNS explanation,
    # yet no round_number=2 row exists -> a real ingestion gap, never confused with a legitimate absence.
    _player_event(conn, "cm0", made_cut=1, rounds_played=4, finish_position="T20")

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.verdict == READINESS_HARD_STOP
    assert readiness.field_size == 120
    assert readiness.collection_missing_players == ("cm0",)


def test_120_field_all_entry_field_players_always_represented(conn):
    completed = [f"p{i}" for i in range(115)]
    _bulk_completed(conn, completed)
    terminal_codes = ["wd0", "wd1", "dq0", "dns0", "unk0"]
    for code in terminal_codes:
        _entry(conn, code)
    _player_event(conn, "wd0", withdrawn=1, finish_position="WD")
    _player_event(conn, "wd1", withdrawn=1, finish_position="WD")
    _player_event(conn, "dq0", disqualified=1, finish_position="DQ")
    _player_event(conn, "dns0", finish_position="DNS")
    # unk0: no player_event row at all -> UNKNOWN, WARN, but still represented.

    readiness = assess_field_readiness(conn, "G1", round_number=2)
    assert readiness.field_size == 120
    assert len(readiness.statuses) == 120
    assert {s.player_code for s in readiness.statuses} == set(completed) | set(terminal_codes)
    assert readiness.verdict == READINESS_WARN  # unk0 is genuinely unexplained
