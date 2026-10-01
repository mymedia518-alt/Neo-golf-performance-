"""RED TEAM (2026-09-25): the shared tournament-chronology utility.
Every module that orders tournaments in time must go through this --
these tests pin down the exact bug it fixes (game_code is not a date)
and the exact, disclosed limits of its real-date coverage."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_ordering import load_schedule_end_dates, sort_tournaments, tournament_sort_key  # noqa: E402

pytestmark = pytest.mark.round_pipeline


def test_real_schedule_overrides_the_game_code_proxy_within_a_season():
    """The exact bug RED TEAM found: KB (2026090003) really ended
    2026-09-13, Hana (2026090002) really ended 2026-09-20 (later), but
    game_code order (090002 < 090003) sorts them backwards."""
    end_dates = {"2026090002": "2026-09-20", "2026090003": "2026-09-13"}
    events = [
        {"game_code": "2026090003", "season": 2026, "tournament": "KB"},
        {"game_code": "2026090002", "season": 2026, "tournament": "Hana"},
    ]
    ordered = sort_tournaments(events, schedule_end_dates=end_dates)
    assert [e["tournament"] for e in ordered] == ["KB", "Hana"]


def test_proxy_only_events_never_get_pulled_after_a_real_dated_event_from_an_earlier_season():
    """Season is always a real fact, never a proxy -- a real end_date in
    season 2026 must never outrank a proxy-only event from season 2025,
    regardless of what the date string says."""
    end_dates = {"2026010001": "2026-01-05"}
    events = [
        {"game_code": "2025120009", "season": 2025, "tournament": "old-proxy"},
        {"game_code": "2026010001", "season": 2026, "tournament": "new-real"},
    ]
    ordered = sort_tournaments(events, schedule_end_dates=end_dates)
    assert [e["tournament"] for e in ordered] == ["old-proxy", "new-real"]


def test_proxy_fallback_matches_the_original_game_code_ordering_when_no_real_date_exists():
    """Never regresses events this repository has no real date for --
    same (season, game_code) tail order as before this utility existed."""
    events = [
        {"game_code": "2026070003", "season": 2026, "tournament": "b"},
        {"game_code": "2026070002", "season": 2026, "tournament": "a"},
    ]
    ordered = sort_tournaments(events, schedule_end_dates={})
    assert [e["tournament"] for e in ordered] == ["a", "b"]


def test_tiebreak_only_breaks_ties_within_one_tournament_never_reorders_across_tournaments():
    end_dates = {}
    rows = [
        {"game_code": "2026090003", "season": 2026, "round": 2},
        {"game_code": "2026090002", "season": 2026, "round": 1},
        {"game_code": "2026090003", "season": 2026, "round": 1},
    ]
    ordered = sort_tournaments(rows, tiebreak_key="round", schedule_end_dates=end_dates)
    assert [(r["game_code"], r["round"]) for r in ordered] == [
        ("2026090002", 1), ("2026090003", 1), ("2026090003", 2),
    ]


def test_load_schedule_end_dates_matches_the_real_official_schedule_artifact():
    """The real, currently-known 2026 tail -- confirms this utility
    reads the SAME file the RED TEAM investigation used, not a copy."""
    end_dates = load_schedule_end_dates()
    assert end_dates.get("2026090002") == "2026-09-20"  # Hana
    assert end_dates.get("2026090003") == "2026-09-13"  # KB
    assert end_dates.get("2026120001") == "2026-09-06"  # OK Open


def test_missing_schedule_file_degrades_to_pure_proxy_never_raises():
    key_kb = tournament_sort_key("2026090003", 2026, {})
    key_hana = tournament_sort_key("2026090002", 2026, {})
    assert key_hana < key_kb  # falls back to plain game_code order when no real date is known
