"""Tests for scripts/run_beta001_r3_update.py's STEP3 (reconciliation
hard-stop) and STEP4 (future-data-leakage) gates at the run_real()
level — a small, real, in-memory-shaped sqlite DB plus a monkeypatched
collect_all_rounds_for_game (no real network access). Both gates must
HARD_STOP (exit 0, "nothing written") before any prediction, CSV, or
freeze is produced.
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
    return _load(SCRIPT_PATH, "run_beta001_r3_update_gates_script")


def _row(code, name, round_number, *, round1=None, round2=None, round3=None, today_under_par=None, rank=1, status=None):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=name, player_eng_name=None, round_number=round_number,
        rank_display=(status or str(rank)), rank=(None if status else rank), tie_flag=False, status=status,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=today_under_par,
        total_strokes=None, holes_completed="18",
        round1_score=round1, round2_score=round2, round3_score=round3, round4_score=None,
    )


def _base_db(tmp_path, *, with_r4_rows=False):
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
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2026-08-25T00:00:00Z')",
            (GAME_CODE, code, name),
        )
        for rn in (1, 2):
            conn.execute(
                "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
                "round_score, round_to_par) VALUES (?, ?, 2026, ?, ?, ?, 70, -1)",
                (GAME_CODE, GAME_CODE, rn, code, name),
            )
    if with_r4_rows:
        conn.execute(
            "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
            "round_score, round_to_par) VALUES (?, ?, 2026, 4, 'p1', 'Player One', 70, -1)",
            (GAME_CODE, GAME_CODE),
        )
    conn.commit()
    conn.close()
    return db_path


class _Args:
    def __init__(self, db, game_code, cache_dir, **kw):
        self.db = str(db)
        self.game_code = game_code
        self.cache_dir = str(cache_dir)
        self.season = kw.get("season")
        self.tournament_name = kw.get("tournament_name", "Test Open")
        self.output_root = kw.get("output_root")
        self.history_dir = kw.get("history_dir")
        self.predictions_dir = kw.get("predictions_dir")
        self.c_predictions_dir = kw.get("c_predictions_dir")
        self.pre_prediction_id = kw.get("pre_prediction_id")
        self.pre_cutoff_date = kw.get("pre_cutoff_date")
        self.n_simulations = kw.get("n_simulations", 100)
        self.seed = kw.get("seed")
        self.freeze = kw.get("freeze", False)


def test_step4_future_leakage_hard_stops_before_prediction(module, tmp_path, capsys):
    db_path = _base_db(tmp_path, with_r4_rows=True)
    round3_rows = [_row("p1", "Player One", 3, round1=70, round2=69, round3=68, rank=1)]
    args = _Args(db_path, GAME_CODE, tmp_path / "cache", output_root=tmp_path / "out")

    with patch(
        "klpga.collectors.leaderboard.collect_all_rounds_for_game", return_value={3: round3_rows, 2: []}
    ):
        rc = module.run_real(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "FUTURE_DATA_LEAKAGE" in out
    assert not (tmp_path / "out").exists()


def test_step3_score_mismatch_hard_stops_before_leakage_and_prediction(module, tmp_path, capsys):
    """A player_round row already present for round 3 with a DIFFERENT
    score than the (mocked) official fetch reports must FAIL
    reconciliation and stop the run before STEP4/prediction even runs."""
    db_path = _base_db(tmp_path)
    conn = sqlite3.connect(db_path)
    # Pre-seed a round_number=3 row that will DISAGREE with the freshly "fetched" official data below.
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par, finish_position_after_round) VALUES (?, ?, 2026, 3, 'p1', 'Player One', 99, 25, '1')",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    round3_rows = [_row("p1", "Player One", 3, round1=70, round2=69, round3=68, today_under_par=-2, rank=1)]
    args = _Args(db_path, GAME_CODE, tmp_path / "cache", output_root=tmp_path / "out")

    # STEP1's own upsert will overwrite round 3 for p1 with the (mocked) fetch's real values —
    # so to genuinely exercise a DB/official disagreement, only p1's round IS refreshed by
    # STEP1 to the SAME real value as the mock (68/-2); the mismatch instead comes from a
    # second player, p2, whose DB row disagrees with what the mocked fetch reports for them.
    round3_rows_mismatch = [
        _row("p1", "Player One", 3, round1=70, round2=69, round3=68, today_under_par=-2, rank=1),
        _row("p2", "Player Two", 3, round1=72, round2=70, round3=71, today_under_par=-1, rank=2),
    ]
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par, finish_position_after_round) VALUES (?, ?, 2026, 3, 'p2', 'Player Two', "
        "999, 999, '2')",
        (GAME_CODE, GAME_CODE),
    )
    conn.commit()
    conn.close()

    with patch(
        "klpga.collectors.leaderboard.collect_all_rounds_for_game",
        return_value={3: round3_rows_mismatch, 2: []},
    ):
        with patch("klpga.db.upsert.upsert_player_round") as fake_upsert:
            # Neutralize STEP1's own upsert so the pre-seeded mismatched p2 row survives to be
            # reconciled against the mocked official fetch — isolates STEP3's own gate behavior.
            rc = module.run_real(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: HARD_STOP" in out
    assert "reconciliation" in out.lower() or "FAIL" in out
    assert not (tmp_path / "out").exists()
    assert fake_upsert.called  # STEP1 did attempt to upsert (proves we reached STEP1 for real)
