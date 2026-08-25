"""Tests for klpga.collectors.entry_list — fetch/match/cross-check logic
against a fake HTTP client and a real (temp, in-memory-backed) schema.sql
database, never the project's real data/klpga.sqlite file."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from klpga.collectors.entry_list import (
    cross_check_against_player_event,
    fetch_entry_list,
    match_entries_to_player_master,
)
from klpga.db.upsert import upsert_player, upsert_player_event, upsert_tournament
from klpga.parsers.entry_list_parser import EntryRow

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield connection
    connection.close()


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient.get_text — mirrors the
    FakeClient pattern used across the other collector tests."""

    def __init__(self, html_by_key: dict[tuple, str]):
        self.html_by_key = html_by_key
        self.calls: list[tuple] = []

    def get_text(self, url, params=None, **kwargs):
        key = (url, params.get("gameCode") if params else None)
        self.calls.append(key)
        return self.html_by_key[key]


def test_fetch_entry_list_calls_confirmed_endpoint_with_game_code():
    from klpga import config

    client = FakeClient({(config.ENTRY_LIST_ENDPOINT, "2026080001"): "<html>ok</html>"})
    html = fetch_entry_list(client, "2026080001")
    assert html == "<html>ok</html>"
    assert client.calls == [(config.ENTRY_LIST_ENDPOINT, "2026080001")]


def _row(code, name="선수", category="자격자", reason=None):
    return EntryRow(
        player_code=code,
        player_name=name,
        nationality="KOR",
        qualification_category=category,
        qualification_reason=reason,
    )


def test_match_entries_reports_matched_and_unmatched_explicitly(conn):
    upsert_player(conn, {"player_id": "10296", "player_name": "문정민"})
    upsert_player(conn, {"player_id": "9174", "player_name": "강가율"})

    entries = [_row("10296"), _row("9174"), _row("99999", name="미등록선수")]
    result = match_entries_to_player_master(conn, entries)

    assert result.matched_count == 2
    assert result.unmatched_count == 1
    assert {r.player_code for r in result.matched} == {"10296", "9174"}
    assert {r.player_code for r in result.unmatched} == {"99999"}
    # Nothing silently discarded: matched + unmatched == total input.
    assert result.matched_count + result.unmatched_count == len(entries)


def test_match_entries_detects_duplicate_player_codes(conn):
    upsert_player(conn, {"player_id": "10296", "player_name": "문정민"})
    entries = [_row("10296"), _row("10296")]
    result = match_entries_to_player_master(conn, entries)
    assert result.duplicate_player_codes == ["10296"]


def test_match_entries_handles_empty_list(conn):
    result = match_entries_to_player_master(conn, [])
    assert result.matched == []
    assert result.unmatched == []
    assert result.duplicate_player_codes == []


def test_cross_check_against_player_event_reports_differences_without_erroring(conn):
    upsert_tournament(
        conn,
        {
            "event_id": "2026030001",
            "game_code": "2026030001",
            "event_name": "테스트 대회",
            "season": 2026,
            "end_date": "2026-03-15",
        },
    )
    upsert_player(conn, {"player_id": "A", "player_name": "선수A"})
    upsert_player(conn, {"player_id": "B", "player_name": "선수B"})
    upsert_player_event(
        conn,
        {
            "event_id": "2026030001",
            "game_code": "2026030001",
            "season": 2026,
            "player_id": "A",
            "player_name": "선수A",
        },
    )
    upsert_player_event(
        conn,
        {
            "event_id": "2026030001",
            "game_code": "2026030001",
            "season": 2026,
            "player_id": "B",
            "player_name": "선수B",
        },
    )

    # Entry list has A and C (a withdrawal-before-result scenario) — B
    # played in the result but wasn't in the (later-fetched, fictional)
    # entry snapshot. Neither is treated as an error.
    entries = [_row("A"), _row("C")]
    check = cross_check_against_player_event(conn, "2026030001", entries)

    assert check.entry_count == 2
    assert check.player_event_count == 2
    assert check.intersection_count == 1
    assert check.entry_only == ["C"]
    assert check.result_only == ["B"]
