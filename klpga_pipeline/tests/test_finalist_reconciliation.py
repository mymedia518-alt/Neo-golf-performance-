"""Tests for klpga.neo_win.finalist_reconciliation — roster vs. official
round fetch vs. DB, with evidence-backed WD/DQ classification."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.finalist_reconciliation import (
    build_roster_normalized,
    load_roster_csv,
    query_wd_dq_status,
    reconcile_finalists,
)
from klpga.neo_win.round_reconciliation import VERDICT_FAIL, NormalizedPlayer

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "G1"


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def test_load_roster_csv(tmp_path):
    path = tmp_path / "roster.csv"
    path.write_text("player_code,player_name\n1001,가\n1002,나\n", encoding="utf-8")
    rows = load_roster_csv(path)
    assert rows == [("1001", "가"), ("1002", "나")]


def test_build_roster_normalized():
    normalized = build_roster_normalized([("1001", "가")])
    assert normalized["1001"].player_name == "가"
    assert normalized["1001"].round_score is None


def _official(code, name, score):
    return NormalizedPlayer(
        player_code=code, player_name=name, position_display="1", position=1,
        round_score=score, score_to_par=score, status=None,
    )


def _db_player(code, name, score):
    return NormalizedPlayer(
        player_code=code, player_name=name, position_display="1", position=1,
        round_score=score, score_to_par=score, status=None,
    )


def test_all_matched(db):
    roster = [("1001", "가"), ("1002", "나")]
    official = {"1001": _official("1001", "가", -3), "1002": _official("1002", "나", -1)}
    db_rows = {"1001": _db_player("1001", "가", -3), "1002": _db_player("1002", "나", -1)}
    report = reconcile_finalists(db, GAME_CODE, 4, roster, official, db_rows)
    assert report.expected_finalists == 2
    assert sorted(report.matched) == ["1001", "1002"]
    assert report.missing == []
    assert report.extra == []
    assert report.unresolved == []
    assert report.verdict != VERDICT_FAIL


def test_missing_finalist_without_wd_dq_evidence(db):
    """A roster player entirely absent from official + DB, with no
    player_event row at all -- must be MISSING, not silently ignored."""
    roster = [("1001", "가")]
    report = reconcile_finalists(db, GAME_CODE, 4, roster, official_normalized={}, db_normalized={})
    assert report.missing == ["1001"]
    assert report.wd == []
    assert report.dq == []


def test_missing_finalist_with_real_wd_evidence(db):
    """A roster player absent from official R4 + DB, but with a REAL
    player_event.withdrawn=1 row -- must show up in `wd`, not just
    `missing`, so a caller can tell the difference between an
    unexplained gap and a real, evidence-backed withdrawal."""
    db.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES (?, ?, 'Test', 2026, '2026-08-30')", (GAME_CODE, GAME_CODE),
    )
    db.execute("INSERT INTO player_master (player_id, player_name) VALUES ('1001', '가')")
    db.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, withdrawn) "
        "VALUES (?, ?, 2026, '1001', '가', 1)", (GAME_CODE, GAME_CODE),
    )
    db.commit()

    roster = [("1001", "가")]
    report = reconcile_finalists(db, GAME_CODE, 4, roster, official_normalized={}, db_normalized={})

    assert report.missing == ["1001"]
    assert report.wd == ["1001"]
    assert report.dq == []


def test_extra_player_in_official_not_in_roster(db):
    roster = [("1001", "가")]
    official = {"1001": _official("1001", "가", -3), "9999": _official("9999", "다른선수", -1)}
    db_rows = {"1001": _db_player("1001", "가", -3)}
    report = reconcile_finalists(db, GAME_CODE, 4, roster, official, db_rows)
    assert report.extra == ["9999"]


def test_unresolved_when_official_has_score_but_db_missing(db):
    """The exact live scenario: official R4 shows a real completed
    score for a roster finalist, but the DB has zero R4 rows yet."""
    roster = [("1001", "가")]
    official = {"1001": _official("1001", "가", -3)}
    report = reconcile_finalists(db, GAME_CODE, 4, roster, official, db_normalized={})
    assert report.unresolved == ["1001"]
    assert report.verdict == VERDICT_FAIL


def test_query_wd_dq_status_reads_real_columns_only(db):
    db.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES (?, ?, 'Test', 2026, '2026-08-30')", (GAME_CODE, GAME_CODE),
    )
    for code in ("1001", "1002", "1003"):
        db.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (code, code))
    db.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, withdrawn, disqualified) "
        "VALUES (?, ?, 2026, '1001', '1001', 1, 0)", (GAME_CODE, GAME_CODE),
    )
    db.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, withdrawn, disqualified) "
        "VALUES (?, ?, 2026, '1002', '1002', 0, 1)", (GAME_CODE, GAME_CODE),
    )
    db.commit()

    status = query_wd_dq_status(db, GAME_CODE, ["1001", "1002", "1003"])
    assert status["1001"]["withdrawn"] is True
    assert status["1002"]["disqualified"] is True
    assert "1003" not in status  # no player_event row at all -> not fabricated as False
