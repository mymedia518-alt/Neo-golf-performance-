"""Tests for scripts/15_collect_entry_list.py's collect_entry_list() —
no network access. Runs the real captured entry-list fixture through a
FakeClient against a real schema.sql-built temp DB, and checks both the
printed report and the actual tournament_entry rows written."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "15_collect_entry_list.py"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "entry_list_sample.html"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("collect_entry_list_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def sample_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "klpga.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


class FakeClient:
    def __init__(self, html: str):
        self.html = html

    def get_text(self, url, params=None, **kwargs):
        return self.html


def test_collects_all_120_confirmed_entrants(module, sample_html, conn, capsys):
    outcome = module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")
    out = capsys.readouterr().out

    assert outcome["status"] == "success"
    assert outcome["parsed_rows"] == 120
    assert outcome["unparsed_row_count"] == 0
    assert outcome["duplicate_player_codes"] == []
    assert outcome["rows_written"] == 120
    assert "Parsed entrant rows: 120" in out

    written = conn.execute("SELECT COUNT(*) FROM tournament_entry WHERE game_code='2026080001'").fetchone()[0]
    assert written == 120


def test_moon_jungmin_row_stored_with_confirmed_fields_only(module, sample_html, conn):
    module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")
    row = conn.execute(
        "SELECT player_name_display, nationality, qualification_category, qualification_reason, source "
        "FROM tournament_entry WHERE game_code='2026080001' AND player_code='10296'"
    ).fetchone()
    assert row == ("문정민", "KOR", "자격자", "2024 일반대회 우승자", module.config.ENTRY_LIST_ENDPOINT)


def test_matched_and_unmatched_reported_against_real_player_master(module, sample_html, conn, capsys):
    # Register every real entrant EXCEPT 문정민 (10296) as already known,
    # to exercise both the matched and unmatched-reporting paths without
    # relying on which of the 120 real players happen to already exist.
    from klpga.parsers.entry_list_parser import parse_entry_list_html

    result = parse_entry_list_html(sample_html)
    for row in result.rows:
        if row.player_code == "10296":
            continue
        conn.execute(
            "INSERT INTO player_master (player_id, player_name) VALUES (?, ?)",
            (row.player_code, row.player_name),
        )
    conn.commit()

    outcome = module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")
    out = capsys.readouterr().out

    assert outcome["matched_count"] == 119
    assert outcome["unmatched_count"] == 1
    assert "Matched against player_master: 119" in out
    assert "Unmatched against player_master: 1" in out
    assert "UNMATCHED (stored anyway): player_code=10296" in out

    # The unmatched entrant must still be stored, never dropped.
    stored = conn.execute(
        "SELECT player_code FROM tournament_entry WHERE game_code='2026080001' AND player_code='10296'"
    ).fetchone()
    assert stored is not None


def test_recollecting_is_idempotent_no_duplicate_rows(module, sample_html, conn):
    module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")
    module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")
    module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")

    total = conn.execute("SELECT COUNT(*) FROM tournament_entry WHERE game_code='2026080001'").fetchone()[0]
    assert total == 120  # not 240 or 360


def test_never_touches_other_validated_tables(module, sample_html, conn):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) VALUES (?, ?, ?, ?, ?)",
        ("2026030001", "2026030001", "미리 존재하는 대회", 2026, "2026-03-15"),
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", ("99999", "기존선수"))
    conn.commit()
    before_tournaments = conn.execute("SELECT * FROM tournament_master").fetchall()
    before_players = conn.execute("SELECT * FROM player_master WHERE player_id='99999'").fetchall()

    module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")

    assert conn.execute("SELECT * FROM tournament_master").fetchall() == before_tournaments
    assert conn.execute("SELECT * FROM player_master WHERE player_id='99999'").fetchall() == before_players


def test_collection_run_audit_log_recorded(module, sample_html, conn):
    module.collect_entry_list(conn, FakeClient(sample_html), "2026080001")
    run = conn.execute(
        "SELECT script_name, target, status, rows_written FROM collection_runs WHERE script_name='15_collect_entry_list'"
    ).fetchone()
    assert run == ("15_collect_entry_list", "2026080001", "success", 120)
