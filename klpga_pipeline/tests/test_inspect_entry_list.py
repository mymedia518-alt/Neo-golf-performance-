"""Tests for scripts/14_inspect_entry_list.py's report logic — no
network access. Runs the real captured entry-list fixture through a
FakeClient (same duck-typed pattern as tests/test_discover_entry_list.py
and the other collector tests) and checks the printed report."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "14_inspect_entry_list.py"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "entry_list_sample.html"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _load_module():
    spec = importlib.util.spec_from_file_location("inspect_entry_list_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def sample_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, html: str):
        self.html = html

    def get_text(self, url, params=None, **kwargs):
        return self.html


def test_reports_matching_summary_and_no_unparsed_rows(module, sample_html, capsys):
    client = FakeClient(sample_html)
    rc = module.inspect_entry_list(client, "2026080001")
    out = capsys.readouterr().out

    assert rc == 0
    assert "Parsed entrant rows: 120" in out
    assert "OK: parsed row count matches the page's own 총 참가자 figure (120)" in out
    assert "Unparseable rows (looked like an entrant, no extractable player_code): 0" in out
    assert "Duplicate player_codes within this entry list: 0" in out
    assert "강가율" in out  # first real entrant, confirms sample-entrant printing works
    assert "--db not provided" in out


def test_reports_matched_and_unmatched_against_real_db(module, sample_html, tmp_path, capsys):
    db_path = tmp_path / "klpga.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # Only register 문정민 (10296) as known — every other real entrant in
    # the fixture is deliberately left unmatched to exercise the
    # unmatched-reporting path against a real schema.
    conn.execute(
        "INSERT INTO player_master (player_id, player_name) VALUES (?, ?)",
        ("10296", "문정민"),
    )
    conn.commit()
    conn.close()

    client = FakeClient(sample_html)
    rc = module.inspect_entry_list(client, "2026080001", db_path=str(db_path))
    out = capsys.readouterr().out

    assert rc == 0
    assert "Matched against player_master" in out
    assert "Matched against player_master" in out and ": 1" in out
    assert "Unmatched against player_master: 119" in out


def test_missing_db_path_is_reported_not_crashed(module, sample_html, capsys):
    client = FakeClient(sample_html)
    rc = module.inspect_entry_list(client, "2026080001", db_path="/nonexistent/path.sqlite")
    out = capsys.readouterr().out
    assert rc == 0
    assert "does not exist — skipping player_master matching" in out
