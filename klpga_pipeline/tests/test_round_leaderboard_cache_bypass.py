"""Tests for the round-leaderboard cache-bypass mechanism (Task 3 of
the official-leaderboard validation gate hardening): round-leaderboard
data is mutable while a round is in progress — a player can move from
the confirmed rank=999/INCOMPLETE sentinel to a real completed score
between two fetches — so klpga.collectors.leaderboard.
fetch_round_leaderboard_html/fetch_round_leaderboard now accept
`use_cache`, defaulting to True (unchanged behavior for bulk/
historical collection), with `use_cache=False` forcing a real fetch
that overwrites any stale cached response. No real network access —
PoliteHttpClient._do_request is monkeypatched per test."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga import config
from klpga.collectors.leaderboard import fetch_round_leaderboard_html
from klpga.http_client import PoliteHttpClient

GAME_CODE = "2026080001"


class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


def _client(tmp_path):
    return PoliteHttpClient(cache_dir=tmp_path / "cache", min_interval_sec=0, jitter_sec=0)


# ---------------------------------------------------------------
# A. first response = 999/INCOMPLETE, later official response = a real
#    completed score -> use_cache=False (the active-round path) sees
#    the new completed score, not the stale cached one.
# ---------------------------------------------------------------
def test_use_cache_false_bypasses_a_stale_incomplete_cached_response(tmp_path, monkeypatch):
    client = _client(tmp_path)
    responses = iter([
        _FakeResponse("<html>INCOMPLETE_999_SNAPSHOT</html>"),
        _FakeResponse("<html>REAL_COMPLETED_SCORE</html>"),
    ])
    monkeypatch.setattr(client, "_do_request", lambda method, url, **kwargs: next(responses))

    # First fetch (use_cache=True implicitly via a normal call) writes the stale snapshot to disk.
    first = fetch_round_leaderboard_html(client, GAME_CODE, 1, use_cache=True)
    assert first == "<html>INCOMPLETE_999_SNAPSHOT</html>"

    # A later use_cache=False call must NOT replay the stale cache — it must hit _do_request again
    # and return the fresh, real response.
    second = fetch_round_leaderboard_html(client, GAME_CODE, 1, use_cache=False)
    assert second == "<html>REAL_COMPLETED_SCORE</html>"

    # And the cache file on disk is now updated to the fresh content — a subsequent normal
    # (cached) read returns the REAL data too, not the original stale snapshot.
    third = fetch_round_leaderboard_html(client, GAME_CODE, 1, use_cache=True)
    assert third == "<html>REAL_COMPLETED_SCORE</html>"


# ---------------------------------------------------------------
# B. A genuinely completed historical round: the cached response can
#    still be reused normally (use_cache=True, the default) — no
#    forced real request every time.
# ---------------------------------------------------------------
def test_use_cache_true_default_reuses_cache_for_completed_round(tmp_path, monkeypatch):
    client = _client(tmp_path)
    call_count = {"n": 0}

    def _do_request(method, url, **kwargs):
        call_count["n"] += 1
        return _FakeResponse("<html>FINAL_COMPLETED_LEADERBOARD</html>")

    monkeypatch.setattr(client, "_do_request", _do_request)

    first = fetch_round_leaderboard_html(client, GAME_CODE, 4)  # default use_cache=True
    second = fetch_round_leaderboard_html(client, GAME_CODE, 4)  # default use_cache=True

    assert first == second == "<html>FINAL_COMPLETED_LEADERBOARD</html>"
    assert call_count["n"] == 1  # only the first call ever hit the network; the second was a real cache hit
