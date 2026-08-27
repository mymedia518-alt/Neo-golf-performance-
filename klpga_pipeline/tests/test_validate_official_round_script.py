"""Tests for scripts/50_validate_official_round.py — end-to-end through
real fetch/parse adapters (via a FakeClient, no real network) plus a
real sqlite DB, proving the whole gate wires together correctly. Core
classification logic itself is tested exhaustively in
tests/test_round_reconciliation.py; these tests only prove the I/O
plumbing (script -> collectors/parsers -> klpga.neo_win.
round_reconciliation -> stdout) is correct."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "50_validate_official_round.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "2026080001"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "validate_official_round_script")


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient — supports both
    get_text (entry list) and post_text (round leaderboard), mirroring
    the FakeClient pattern already used by the other collector tests."""

    def __init__(self, entry_html: str, leaderboard_html: str):
        self.entry_html = entry_html
        self.leaderboard_html = leaderboard_html

    def get_text(self, url, params=None, **kwargs):
        return self.entry_html

    def post_text(self, url, data=None, **kwargs):
        return self.leaderboard_html


def _entry_html(codes_and_names):
    rows = "".join(
        f'<tr><td><a class="col-7" href="/x?playerCode={code}">{name}</a></td><td></td></tr>'
        for code, name in codes_and_names
    )
    return f"<html><body><h2>전체 선수</h2><table><tbody>{rows}</tbody></table></body></html>"


def _leaderboard_row(code, name, *, rank="1", round_score="69", to_par="-3"):
    return (
        f'<div data-rank="{rank}" data-name="{name}" data-totunderpar="{to_par}" '
        f'data-todayunderpar="{to_par}" data-score="{round_score}" data-inghole="18" '
        f'data-round1score="{round_score}" _playercode="{code}" _playername="{name}" '
        f'_gamecode="{GAME_CODE}" _round="1"></div>'
    )


def _leaderboard_html(rows):
    return f"<html><body>{''.join(rows)}</body></html>"


def _db(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return path


def _run(module, client, argv_extra, monkeypatch):
    monkeypatch.setattr(module, "PoliteHttpClient", lambda cache_dir: client)
    argv_backup = sys.argv
    sys.argv = ["50_validate_official_round.py", "--game-code", GAME_CODE, "--round", "1"] + argv_extra
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    return rc


def test_fully_matched_field_passes(module, tmp_path, capsys, monkeypatch):
    db_path = _db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par, finish_position_after_round) VALUES ('E', ?, 2026, 1, '9431', '박보겸', 69, -3, '1')",
        (GAME_CODE,),
    )
    conn.commit()
    conn.close()

    client = FakeClient(
        entry_html=_entry_html([("9431", "박보겸")]),
        leaderboard_html=_leaderboard_html([_leaderboard_row("9431", "박보겸")]),
    )
    rc = _run(module, client, ["--db", str(db_path), "--cache-dir", str(tmp_path / "cache")], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "ENTRY COUNT: 1" in out
    assert "OFFICIAL ROUND COUNT: 1" in out
    assert "DB ROUND COUNT: 1" in out
    assert "VERDICT: PASS" in out
    assert "PERMITTED: no anomalies detected." in out


def test_official_complete_missing_in_db_fails_and_blocks(module, tmp_path, capsys, monkeypatch):
    """Reproduces the real 2026080001 R1 control case: 박보겸 has a real
    official round result but no DB row for it."""
    db_path = _db(tmp_path)  # no player_round rows at all

    client = FakeClient(
        entry_html=_entry_html([("9431", "박보겸")]),
        leaderboard_html=_leaderboard_html([_leaderboard_row("9431", "박보겸", rank="T27", round_score="69", to_par="-3")]),
    )
    rc = _run(module, client, ["--db", str(db_path), "--cache-dir", str(tmp_path / "cache")], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "VERDICT: FAIL" in out
    assert "9431" in out
    assert "OFFICIAL_COMPLETE_MISSING_IN_DB" in out
    assert "BLOCKED: FAIL verdict" in out
    assert "PREDICTION ELIGIBLE: 0" in out
