"""Tests for scripts/run_beta001_r3_update.py's STEP1 real official R3
collection — mirrors tests/test_run_beta001_r2_update_step1_collection.py
exactly, one round later. `_collect_and_upsert_round3` reuses the SAME
collect_all_rounds_for_game + build_rows + klpga.db.upsert path
scripts/run_beta001_r2_update.py's own STEP1 uses.

No real network access: `collect_all_rounds_for_game` is monkeypatched
to return real-shaped PlayerRoundRow data standing in for the live
site response.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.parsers.leaderboard_parser import PlayerRoundRow

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_beta001_r3_update.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "2026080001"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "run_beta001_r3_update_script")


def _row(code, name, round_number, *, round1=None, round2=None, round3=None, today_under_par=None, rank=1, status=None):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=name, player_eng_name=None, round_number=round_number,
        rank_display=(status or str(rank)), rank=(None if status else rank), tie_flag=False, status=status,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=today_under_par,
        total_strokes=None, holes_completed="18",
        round1_score=round1, round2_score=round2, round3_score=round3, round4_score=None,
    )


def _base_db(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Test Open', 2026, '2026-08-27', '2026-08-30')",
        (GAME_CODE, GAME_CODE),
    )
    for code, name in (("p1", "Player One"), ("p2", "Player Two")):
        conn.execute("INSERT INTO player_master (player_id, player_name) VALUES (?, ?)", (code, name))
        for rn in (1, 2):
            conn.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                "round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, 70, -1)",
                (GAME_CODE, GAME_CODE, rn, code, name),
            )
    conn.commit()
    return conn, db_path


class _Args:
    def __init__(self, game_code, cache_dir, season=None):
        self.game_code = game_code
        self.cache_dir = str(cache_dir)
        self.season = season


def test_step1_fetches_and_upserts_real_round3_data(module, tmp_path):
    conn, _db_path = _base_db(tmp_path)
    round3_rows = [
        _row("p1", "Player One", 3, round1=70, round2=69, round3=68, today_under_par=-2, rank=1),
        _row("p2", "Player Two", 3, round1=72, round2=70, round3=71, today_under_par=-1, rank=2),
    ]
    args = _Args(GAME_CODE, tmp_path / "cache")

    with patch(
        "klpga.collectors.leaderboard.collect_all_rounds_for_game", return_value={3: round3_rows, 2: []}
    ) as fake:
        official_round3_rows, official_round2_rows, final_round_collected = module._collect_and_upsert_round3(conn, args)

    assert final_round_collected == 3
    assert official_round3_rows == round3_rows
    assert official_round2_rows == []
    fake.assert_called_once()
    assert fake.call_args.kwargs["force_refresh_rounds"] == frozenset({3})

    written = dict(conn.execute(
        "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = 3", (GAME_CODE,)
    ).fetchall())
    assert written == {"p1": -2, "p2": -1}

    seasons = {s for (s,) in conn.execute("SELECT season FROM player_round WHERE game_code = ? AND round_number = 3", (GAME_CODE,))}
    assert seasons == {2026}


def test_step1_never_fabricates_when_round3_still_genuinely_empty(module, tmp_path):
    """If the live (mocked) fetch still returns nothing for Round 3 —
    e.g. it really hasn't been played yet — this must raise, not write
    fabricated data or silently proceed."""
    conn, _db_path = _base_db(tmp_path)
    args = _Args(GAME_CODE, tmp_path / "cache")

    with patch("klpga.collectors.leaderboard.collect_all_rounds_for_game", return_value={3: [], 2: []}):
        with pytest.raises(RuntimeError, match="still empty"):
            module._collect_and_upsert_round3(conn, args)

    count = conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 3", (GAME_CODE,)
    ).fetchone()[0]
    assert count == 0


def test_step1_explicit_season_override_is_respected(module, tmp_path):
    conn, _db_path = _base_db(tmp_path)
    round3_rows = [_row("p1", "Player One", 3, round1=70, round2=69, round3=68, today_under_par=-2, rank=1)]
    args = _Args(GAME_CODE, tmp_path / "cache", season=2099)

    with patch("klpga.collectors.leaderboard.collect_all_rounds_for_game", return_value={3: round3_rows, 2: []}):
        module._collect_and_upsert_round3(conn, args)

    seasons = {s for (s,) in conn.execute("SELECT season FROM player_round WHERE game_code = ? AND round_number = 3", (GAME_CODE,))}
    assert seasons == {2099}


def test_step1_detects_a_real_cut_player_absent_from_round3(module, tmp_path):
    """A player present on Round 2 but genuinely absent from Round 3
    (a real CUT/WD/DQ dropout — structurally expected for a CUT player,
    see round_update_r3.py's own docstring) must not silently vanish
    from player_round — collect_all_rounds_for_game's own dropped-player
    detection (reused here) is what feeds this."""
    conn, _db_path = _base_db(tmp_path)
    round3_rows = [_row("p1", "Player One", 3, round1=70, round2=69, round3=68, today_under_par=-2, rank=1)]
    round2_rows = [
        _row("p1", "Player One", 2, round1=70, round2=69, today_under_par=-1, rank=1),
        _row("p2", "Player Two", 2, round1=75, round2=80, today_under_par=5, rank=60, status="CUT"),
    ]
    args = _Args(GAME_CODE, tmp_path / "cache")

    with patch(
        "klpga.collectors.leaderboard.collect_all_rounds_for_game",
        return_value={3: round3_rows, 2: round2_rows},
    ):
        official_round3_rows, official_round2_rows, _final = module._collect_and_upsert_round3(conn, args)

    assert {r.player_code for r in official_round3_rows} == {"p1"}
    assert {r.player_code for r in official_round2_rows} == {"p1", "p2"}
