"""Tests for scripts/07_inspect_status_markup.py's find_row_context —
the diagnostic helper used to inspect raw HTML around a player's row
when investigating the CUT/WD/DQ classification question."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "07_inspect_status_markup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("inspect_status_markup", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_find_row_context_returns_surrounding_markup_when_present():
    mod = _load_module()
    html = (
        '<div class="leaderboardList">'
        '<ul class="lb-row" data-rank="999" data-name="테스트">'
        '<li class="player-detail wd-status" _gamecode="G1" _playercode="999999" '
        '_playername="테스트" _round="1" title="기권">'
        '<span class="name">테스트</span></li></ul></div>'
    )
    context = mod.find_row_context(html, "999999")
    assert context is not None
    assert "999999" in context
    assert "wd-status" in context  # any extra class/attribute in the row is preserved


def test_find_row_context_returns_none_when_player_absent():
    mod = _load_module()
    html = '<ul class="lb-row" data-rank="1"><li _playercode="111"></li></ul>'
    assert mod.find_row_context(html, "does-not-exist") is None
