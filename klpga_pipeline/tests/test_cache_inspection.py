"""Tests for klpga.collectors.cache_inspection — read-only inspection
of a roundLeaderboard HTTP cache entry, never deletes/modifies it."""
from __future__ import annotations

import json

import pytest

from klpga import config
from klpga.collectors.cache_inspection import inspect_round_leaderboard_cache
from klpga.http_client import PoliteHttpClient

GAME_CODE = "2026080001"


@pytest.fixture()
def client(tmp_path):
    return PoliteHttpClient(cache_dir=tmp_path / "cache")


def test_no_cache_entry_reports_does_not_exist(client):
    result = inspect_round_leaderboard_cache(client, GAME_CODE, 4)
    assert result.exists is False
    assert result.is_empty is None
    assert result.mtime_utc is None


def test_stale_empty_cache_entry_is_classified_as_stale(client):
    payload = {"gameCode": GAME_CODE, "round": "4"}
    cache_path = client.post_cache_path(config.ROUND_LEADERBOARD_ENDPOINT, data=payload)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"url": config.ROUND_LEADERBOARD_ENDPOINT, "params": {"data": payload}, "body_text": ""}),
        encoding="utf-8",
    )

    result = inspect_round_leaderboard_cache(client, GAME_CODE, 4)

    assert result.exists is True
    assert result.is_empty is True
    assert result.player_row_count == 0
    assert result.body_length == 0
    assert result.mtime_utc is not None
    # never modified/deleted by the inspection itself
    assert cache_path.exists()


def test_real_cache_entry_with_player_rows_is_not_empty(client):
    html = (
        '<ul class="lb-row" data-rank="1" data-name="박혜준" data-totunderpar="-9" data-inghole="18" '
        'data-todayunderpar="0" data-score="279" data-round1score="-6" data-round2score="-3" '
        'data-round3score="0" data-round4score="0">'
        '<li class="player-detail" _gamecode="2026080001" _playercode="9788" _playername="박혜준" '
        '_playerengname="Park" _round="4" _hole="18"></li></ul>'
    )
    payload = {"gameCode": GAME_CODE, "round": "4"}
    cache_path = client.post_cache_path(config.ROUND_LEADERBOARD_ENDPOINT, data=payload)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"url": config.ROUND_LEADERBOARD_ENDPOINT, "params": {"data": payload}, "body_text": html}),
        encoding="utf-8",
    )

    result = inspect_round_leaderboard_cache(client, GAME_CODE, 4)

    assert result.exists is True
    assert result.is_empty is False
    assert result.player_row_count == 1
