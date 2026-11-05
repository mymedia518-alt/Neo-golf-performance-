"""Wiring test for scripts/306_collect_live_round_snapshot.py's collect()
-- proves the real parser chain (leaderboard parse -> group-page parse
-> round_progress resolution -> output assembly) is actually wired
correctly, using the same committed fixtures the parser unit tests
already use. No network: a fake client stands in for PoliteHttpClient.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURES = Path(__file__).parent / "fixtures"

spec = importlib.util.spec_from_file_location(
    "collect_live_round_snapshot", ROOT / "scripts" / "306_collect_live_round_snapshot.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)  # type: ignore[union-attr]


class _FakeClient:
    def __init__(self, leaderboard_html: str, group_html: str):
        self.leaderboard_html = leaderboard_html
        self.group_html = group_html
        self.post_calls = []
        self.get_calls = []

    def post_text(self, url, data=None, use_cache=True):
        self.post_calls.append((url, data, use_cache))
        return self.leaderboard_html

    def get_text_with_status(self, url, params=None):
        self.get_calls.append((url, params))
        return 200, self.group_html


def test_collect_wires_leaderboard_and_grouping_into_holes_completed():
    leaderboard_html = (FIXTURES / "round_leaderboard_sample.html").read_text(encoding="utf-8")
    group_html = (FIXTURES / "group_page_sample.html").read_text(encoding="utf-8")
    client = _FakeClient(leaderboard_html, group_html)

    snapshot = module.collect("2026110001", 1, client=client)

    assert snapshot["game_code"] == "2026110001"
    assert snapshot["round"] == 1
    assert snapshot["player_count"] > 0
    assert client.post_calls[0][2] is False, "must fetch live round leaderboard with use_cache=False"
    for player in snapshot["players"]:
        assert "holes_completed" in player
        assert isinstance(player["holes_completed"], int)
        assert 0 <= player["holes_completed"] <= 18
        # No fabrication: every row's real display fields pass through
        # unmodified from the parser (never overwritten here).
        assert player["player_code"] is not None


def test_collect_falls_back_honestly_when_round_grouping_absent():
    """Round 2 is absent from the fixture (only round-one/round-three
    tab-panes exist) -- must fall back to the documented OUT-start
    assumption and FLAG it, never fail closed or guess silently."""
    leaderboard_html = (FIXTURES / "round_leaderboard_sample.html").read_text(encoding="utf-8")
    group_html = (FIXTURES / "group_page_sample.html").read_text(encoding="utf-8")
    client = _FakeClient(leaderboard_html, group_html)

    snapshot = module.collect("2026110001", 2, client=client)

    assert snapshot["player_count"] > 0
    assert any(p["assumed_default_start"] for p in snapshot["players"])
