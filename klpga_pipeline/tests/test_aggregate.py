"""Tests for klpga.collectors.aggregate.resolve_winner_score — derives a
tournament's winner_score from real collected player_event rows, never
fabricated, only when unambiguous."""
from __future__ import annotations

from klpga.collectors.aggregate import resolve_winner_score


def _event_row(player_id, finish_position_numeric, total_score):
    return {
        "player_id": player_id,
        "finish_position_numeric": finish_position_numeric,
        "total_score": total_score,
    }


def test_resolves_by_winner_code_when_provided():
    rows = [
        _event_row("11134", 1, 280),
        _event_row("22222", 2, 281),
    ]
    assert resolve_winner_score(rows, winner_player_id="11134") == 280


def test_returns_none_when_winner_code_not_found_in_rows():
    rows = [_event_row("22222", 2, 281)]
    assert resolve_winner_score(rows, winner_player_id="11134") is None


def test_falls_back_to_unique_rank_one_when_no_winner_code():
    rows = [
        _event_row("11134", 1, 280),
        _event_row("22222", 2, 281),
    ]
    assert resolve_winner_score(rows, winner_player_id=None) == 280


def test_returns_none_on_tied_rank_one_without_winner_code():
    """A tie at rank 1 (e.g. unresolved playoff data) must not guess a
    winner — None, not an arbitrary pick."""
    rows = [
        _event_row("11134", 1, 280),
        _event_row("22222", 1, 280),
    ]
    assert resolve_winner_score(rows, winner_player_id=None) is None


def test_returns_none_when_no_rank_one_row_exists():
    rows = [_event_row("22222", 2, 281)]
    assert resolve_winner_score(rows, winner_player_id=None) is None
