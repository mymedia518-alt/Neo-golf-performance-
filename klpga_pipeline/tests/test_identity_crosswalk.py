"""Tests for klpga.neo_win.identity_resolution.build_full_identity_
crosswalk and the AMBIGUOUS/UNMATCHED distinction in
resolve_unmatched_player_codes."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.identity_resolution import (
    REASON_AMBIGUOUS_NAME,
    REASON_NAME_NOT_FOUND,
    REASON_NO_RAW_SAMPLE,
    REASON_RESOLVED,
    STATUS_AMBIGUOUS,
    STATUS_BROKEN,
    STATUS_CLEAN,
    STATUS_PARTIAL,
    STATUS_UNMATCHED,
    build_full_identity_crosswalk,
    resolve_unmatched_player_codes,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.sqlite")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_official_metric(conn, player_code, raw_sample_path=None):
    conn.execute(
        "INSERT INTO official_metric_value (season, player_code, identity_key, menu1, menu2, official_label, "
        "field_name, value_raw, parse_status, validation_status, pit_status, source_url, raw_sample_path, "
        "acquired_at) VALUES (2025, ?, 'Tee::Tee01::010101', 'Tee', 'Tee01', 'x', 'record', '1', "
        "'PARSE_SUCCESS', 'CLEAN', 'PIT_UNVERIFIED', 'https://x', ?, '2025-01-01T00:00:00Z')",
        (player_code, raw_sample_path),
    )


# ---------------------------------------------------------------
# resolve_unmatched_player_codes — reason distinctions
# ---------------------------------------------------------------


def test_resolve_no_raw_sample_reason(conn):
    _insert_official_metric(conn, "ghost", raw_sample_path=None)
    conn.commit()
    result = resolve_unmatched_player_codes(conn, {"ghost"})
    assert result["ghost"]["reason"] == REASON_NO_RAW_SAMPLE
    assert result["ghost"]["resolved_id"] is None


def test_resolve_ambiguous_name_reason(conn, tmp_path):
    raw = tmp_path / "sample.html"
    raw.write_text(
        '<table><thead><tr><th>순위</th><th>선수명</th></tr></thead>'
        '<tbody><tr data-record=""><td class="text-start player_name">'
        '<a href="/web/profile/mainRecord?playerCode=ghost">동명이인</a></td>'
        '<td class="record" data-rank="1">1</td></tr></tbody></table>',
        encoding="utf-8",
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', '동명이인')")
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p2', '동명이인')")
    _insert_official_metric(conn, "ghost", raw_sample_path=str(raw))
    conn.commit()
    result = resolve_unmatched_player_codes(conn, {"ghost"})
    assert result["ghost"]["reason"] == REASON_AMBIGUOUS_NAME
    assert set(result["ghost"]["candidate_ids"]) == {"p1", "p2"}


def test_resolve_name_not_found_reason(conn, tmp_path):
    raw = tmp_path / "sample.html"
    raw.write_text(
        '<table><thead><tr><th>순위</th><th>선수명</th></tr></thead>'
        '<tbody><tr data-record=""><td class="text-start player_name">'
        '<a href="/web/profile/mainRecord?playerCode=ghost">누구</a></td>'
        '<td class="record" data-rank="1">1</td></tr></tbody></table>',
        encoding="utf-8",
    )
    _insert_official_metric(conn, "ghost", raw_sample_path=str(raw))
    conn.commit()
    result = resolve_unmatched_player_codes(conn, {"ghost"})
    assert result["ghost"]["reason"] == REASON_NAME_NOT_FOUND


def test_resolve_resolved_reason(conn, tmp_path):
    raw = tmp_path / "sample.html"
    raw.write_text(
        '<table><thead><tr><th>순위</th><th>선수명</th></tr></thead>'
        '<tbody><tr data-record=""><td class="text-start player_name">'
        '<a href="/web/profile/mainRecord?playerCode=ghost">진짜</a></td>'
        '<td class="record" data-rank="1">1</td></tr></tbody></table>',
        encoding="utf-8",
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', '진짜')")
    _insert_official_metric(conn, "ghost", raw_sample_path=str(raw))
    conn.commit()
    result = resolve_unmatched_player_codes(conn, {"ghost"})
    assert result["ghost"]["reason"] == REASON_RESOLVED
    assert result["ghost"]["resolved_id"] == "p1"


# ---------------------------------------------------------------
# build_full_identity_crosswalk
# ---------------------------------------------------------------


def test_crosswalk_clean_player(conn):
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'A')")
    _insert_official_metric(conn, "p1")
    conn.commit()
    rows = build_full_identity_crosswalk(conn)
    row = next(r for r in rows if r["player_code"] == "p1")
    assert row["identity_status"] == STATUS_CLEAN
    assert row["official_metric_match"] is True


def test_crosswalk_ambiguous_shared_name(conn):
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'Dup')")
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p2', 'Dup')")
    conn.commit()
    rows = build_full_identity_crosswalk(conn)
    statuses = {r["player_code"]: r["identity_status"] for r in rows}
    assert statuses["p1"] == STATUS_AMBIGUOUS
    assert statuses["p2"] == STATUS_AMBIGUOUS


def test_crosswalk_broken_orphan_tournament_entry(conn):
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('G1', 'orphan1', 'Orphan', 'test', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    rows = build_full_identity_crosswalk(conn)
    row = next(r for r in rows if r["player_code"] == "orphan1")
    assert row["identity_status"] == STATUS_BROKEN
    assert row["player_master_match"] is False


def test_crosswalk_unmatched_official_metric_code_with_no_evidence(conn):
    _insert_official_metric(conn, "no_evidence_code", raw_sample_path=None)
    conn.commit()
    rows = build_full_identity_crosswalk(conn)
    row = next(r for r in rows if r["player_code"] == "no_evidence_code")
    assert row["identity_status"] == STATUS_UNMATCHED
    assert row["player_master_match"] is False


def test_crosswalk_partial_resolved_by_name(conn, tmp_path):
    raw = tmp_path / "sample.html"
    raw.write_text(
        '<table><thead><tr><th>순위</th><th>선수명</th></tr></thead>'
        '<tbody><tr data-record=""><td class="text-start player_name">'
        '<a href="/web/profile/mainRecord?playerCode=metric_code_1">서교림</a></td>'
        '<td class="record" data-rank="1">1</td></tr></tbody></table>',
        encoding="utf-8",
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('11134', '서교림')")
    _insert_official_metric(conn, "metric_code_1", raw_sample_path=str(raw))
    conn.commit()
    rows = build_full_identity_crosswalk(conn)
    row = next(r for r in rows if r["player_code"] == "11134")
    assert row["identity_status"] == STATUS_PARTIAL
    assert row["resolution_method"] == "resolved_by_exact_name"
    assert "metric_code_1" in row["evidence"]


def test_crosswalk_every_row_has_required_columns(conn):
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'A')")
    conn.commit()
    rows = build_full_identity_crosswalk(conn)
    required = {
        "canonical_player_id", "player_code", "player_name", "player_master_match", "player_event_match",
        "player_round_match", "official_metric_match", "tournament_entry_match", "identity_status",
        "evidence", "resolution_method",
    }
    for row in rows:
        assert required.issubset(row.keys())
