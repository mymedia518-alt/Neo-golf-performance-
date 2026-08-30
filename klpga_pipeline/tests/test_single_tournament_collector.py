"""Tests for klpga.collectors.single_tournament.collect_and_persist_tournament
— the shared core scripts/04_collect_single_tournament.py and
scripts/final_close_preflight.py both now call, covering:
  - the stale-cached-empty-round -> expected_final_round HARD STOP path
  - force_refresh_rounds passed through unchanged
  - real partial data (R1..N-1) still persisted on a HARD STOP
  - fully backward-compatible legacy behavior (no new args)
  - never touches any frozen history/prediction artifact or docs/index.html
    (proven structurally: the module never imports those write paths)

No real network access: fetch_game_list and collect_all_rounds_for_game
are monkeypatched to return real-shaped data standing in for the live
site response — the same convention
tests/test_run_beta001_r3_update_step1_collection.py already uses.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.collectors.single_tournament import (
    STATUS_GAME_CODE_NOT_FOUND,
    STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND,
    STATUS_SUCCESS,
    collect_and_persist_tournament,
)
from klpga.collectors.tournaments import TournamentListing
from klpga.http_client import PoliteHttpClient
from klpga.parsers.leaderboard_parser import PlayerRoundRow

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "2026080001"


def _row(code, name, round_number, *, score=None, rank=1):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=name, player_eng_name=None, round_number=round_number,
        rank_display=str(rank), rank=rank, tie_flag=False, status=None,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=score,
        total_strokes=None, holes_completed="18",
        round1_score=score if round_number == 1 else None,
        round2_score=score if round_number == 2 else None,
        round3_score=score if round_number == 3 else None,
        round4_score=score if round_number == 4 else None,
    )


def _listing(game_code=GAME_CODE, season=2026):
    return TournamentListing(
        game_code=game_code, game_title="Test Open", game_eng_title=None, tour_type="RE",
        course_text=None, course_eng_text=None, out_course_text=None, in_course_text=None,
        start_date=date(2026, 8, 27), start_date_raw="20260827", end_date=date(2026, 8, 30), end_date_raw="20260830",
        game_finish="F", prize_money=None, winner_code="p1", winner_name="Player One", game_method="0",
        season=season, raw={"gameCode": game_code},
    )


@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return conn


@pytest.fixture()
def client(tmp_path):
    return PoliteHttpClient(cache_dir=tmp_path / "cache")


def test_normal_success_no_new_flags_is_backward_compatible(db, client):
    rounds = {1: [_row("p1", "Player One", 1, score=-2)], 2: [_row("p1", "Player One", 2, score=-1)]}
    with patch("klpga.collectors.single_tournament.fetch_game_list", return_value=[_listing()]):
        with patch("klpga.collectors.single_tournament.collect_all_rounds_for_game", return_value=rounds) as fake:
            result = collect_and_persist_tournament(db, client, 2026, GAME_CODE)

    assert result.status == STATUS_SUCCESS
    assert result.final_round == 2
    fake.assert_called_once()
    assert fake.call_args.kwargs["force_refresh_rounds"] == frozenset()
    written = db.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ?", (GAME_CODE,)
    ).fetchone()[0]
    assert written == 2


def test_force_refresh_rounds_passed_through_unchanged(db, client):
    rounds = {1: [_row("p1", "Player One", 1, score=-2)]}
    with patch("klpga.collectors.single_tournament.fetch_game_list", return_value=[_listing()]):
        with patch("klpga.collectors.single_tournament.collect_all_rounds_for_game", return_value=rounds) as fake:
            collect_and_persist_tournament(db, client, 2026, GAME_CODE, force_refresh_rounds=frozenset({4}))

    assert fake.call_args.kwargs["force_refresh_rounds"] == frozenset({4})


def test_expected_final_round_hard_stop_when_discovery_falls_short(db, client):
    """The exact real-world scenario: discover_final_round silently
    fell back to round 3 because round 4 was cached empty. Real R1-3
    data must still be persisted; the status must NOT be SUCCESS."""
    rounds = {
        1: [_row("p1", "Player One", 1, score=-2)],
        2: [_row("p1", "Player One", 2, score=-1)],
        3: [_row("p1", "Player One", 3, score=-3)],
    }
    with patch("klpga.collectors.single_tournament.fetch_game_list", return_value=[_listing()]):
        with patch("klpga.collectors.single_tournament.collect_all_rounds_for_game", return_value=rounds):
            result = collect_and_persist_tournament(
                db, client, 2026, GAME_CODE, expected_final_round=4,
            )

    assert result.status == STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND
    assert result.final_round == 3
    assert "4" in result.reason and "3" in result.reason

    # real R1-3 data was NOT withheld
    round_counts = dict(db.execute(
        "SELECT round_number, COUNT(*) FROM player_round WHERE game_code = ? GROUP BY round_number",
        (GAME_CODE,),
    ).fetchall())
    assert round_counts == {1: 1, 2: 1, 3: 1}
    assert 4 not in round_counts


def test_expected_final_round_success_when_reached(db, client):
    rounds = {n: [_row("p1", "Player One", n, score=-1)] for n in (1, 2, 3, 4)}
    with patch("klpga.collectors.single_tournament.fetch_game_list", return_value=[_listing()]):
        with patch("klpga.collectors.single_tournament.collect_all_rounds_for_game", return_value=rounds):
            result = collect_and_persist_tournament(
                db, client, 2026, GAME_CODE, expected_final_round=4,
            )

    assert result.status == STATUS_SUCCESS
    assert result.final_round == 4


def test_game_code_not_found_writes_nothing(db, client):
    with patch("klpga.collectors.single_tournament.fetch_game_list", return_value=[_listing(game_code="OTHER")]):
        result = collect_and_persist_tournament(db, client, 2026, GAME_CODE)

    assert result.status == STATUS_GAME_CODE_NOT_FOUND
    assert GAME_CODE in result.reason
    tm_count = db.execute("SELECT COUNT(*) FROM tournament_master WHERE game_code = ?", (GAME_CODE,)).fetchone()[0]
    assert tm_count == 0


def test_module_never_imports_any_frozen_artifact_or_homepage_writer():
    """Structural guarantee: this module cannot touch
    neo_tournament_history/, neo_r3_r4_evaluation/, or docs/index.html
    because it never imports the modules that write to them."""
    import klpga.collectors.single_tournament as m

    forbidden_names = (
        "write_or_supersede_history_stage", "write_evaluation_atomic",
        "write_prediction_snapshot_atomic",
    )
    for name in forbidden_names:
        assert name not in vars(m)

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "docs/index.html" not in source
    assert "tournament_history" not in source
    assert "r3_r4_evaluation" not in source
