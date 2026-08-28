"""End-to-end test for scripts/evaluate_r1_cut_ground_truth.py — the
final step bridging klpga.neo_win.ground_truth_diagnostic's real R2 x
R3 double-verified ground truth into the existing R1 MAKE-CUT
evaluation pipeline (klpga.neo_win.cut_evaluation /
klpga.neo_win.r1_r2_evaluation_report).

Fully synthetic: a frozen R1 history fixture (klpga.neo_win.
tournament_history) plus monkeypatched real-data functions
(collect_all_rounds_for_game, fetch_group_page_html,
parse_round_grouping) — no network, no real DB. This IS this
project's Section L "dry run" for the ground-truth evaluation stage.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.neo_win.tournament_history import (
    STAGE_R1,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    write_history_stage_atomic,
)
from klpga.parsers.group_page_parser import GroupingRow
from klpga.parsers.leaderboard_parser import PlayerRoundRow

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_r1_cut_ground_truth.py"
GAME_CODE = "2026080099"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "evaluate_r1_cut_ground_truth_script")


def _seed_frozen_r1_history(history_dir, codes_and_cut_pct):
    entrants = tuple(
        HistoryEntrant(
            player_code=code, player_name=f"Player_{code}", win_pct=1.0,
            make_cut_pct=cut_pct, position=i, score_to_par=float(-i),
        )
        for i, (code, cut_pct) in enumerate(codes_and_cut_pct, start=1)
    )
    entry = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R1, record_kind=RECORD_KIND, recorded_at_utc="2026-08-27T00:00:00Z",
        source_prediction_id="001-C-R1", source_model_version="round_update", source_generated_at_utc="2026-08-27T00:00:00Z",
        tournament_name="Test Open", field_size=len(entrants), entrants=entrants,
    )
    write_history_stage_atomic(entry, history_dir)


def _r2_row(code, round2=68, total_strokes=140, status=None, rank=1):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=f"Player_{code}", player_eng_name=None, round_number=2,
        rank_display=(status or str(rank)), rank=(None if status else rank), tie_flag=False, status=status,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=None,
        total_strokes=total_strokes, holes_completed="18",
        round1_score=None, round2_score=round2, round3_score=None, round4_score=None,
    )


def _run(module, tmp_path, argv_extra=()):
    output_dir = tmp_path / "out"
    argv = [
        "evaluate_r1_cut_ground_truth.py",
        "--game-code", GAME_CODE,
        "--cache-dir", str(tmp_path / "cache"),
        "--output-dir", str(output_dir),
        "--history-dir", str(tmp_path / "neo_tournament_history"),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--outputs-csv-path", str(tmp_path / "BETA001_R1_FULL.csv"),
        *argv_extra,
    ]
    with patch("sys.argv", argv):
        exit_code = module.main()
    return exit_code, output_dir


def test_end_to_end_made_cut_missed_cut_and_explicit_wd_override(module, tmp_path, capsys):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir, [("p1", 80.0), ("p2", 30.0), ("p3", 60.0)])

    r2_rows = [
        _r2_row("p1", round2=68, total_strokes=140, rank=1),  # confirmed continuer -> MADE_CUT
        _r2_row("p2", round2=75, total_strokes=150, rank=50),  # absent from R3, worse score -> MISSED_CUT
        _r2_row("p3", status="INCOMPLETE", total_strokes=None, rank=None),  # ambiguous -> overridden to WD
    ]
    parsed_r3 = [GroupingRow(player_code="p1", player_name="Player_p1", starting_tee="1", tee_time="09:10", group=None)]

    override_path = tmp_path / "explicit_status.json"
    override_path.write_text('[{"player_code": "p3", "status": "WD"}]', encoding="utf-8")

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: r2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>real group page</html>")):
            with patch.object(module, "parse_round_grouping", return_value=parsed_r3):
                exit_code, output_dir = _run(module, tmp_path, argv_extra=["--explicit-status-json", str(override_path)])

    captured = capsys.readouterr().out
    assert exit_code == 0, captured
    assert "ALL_PASSED: True" in captured
    assert "DO NOT PUBLISH" in captured
    assert "INTERIM CHECK — NOT FINAL WIN PROBABILITY EVALUATION" in captured

    eval_csv = output_dir / "player_cut_evaluation.csv"
    assert eval_csv.is_file()
    with open(eval_csv, encoding="utf-8") as f:
        rows = {r["player_code"]: r for r in csv.DictReader(f)}
    assert rows["p1"]["actual_r2_status"] == "MADE_CUT"
    assert rows["p2"]["actual_r2_status"] == "MISSED_CUT"
    assert rows["p3"]["actual_r2_status"] == "WD_AFTER_R1_START"
    assert rows["p3"]["actual_cut"] == ""  # excluded from scoring


def test_no_frozen_r1_source_fails_loudly(module, tmp_path, capsys):
    with patch.object(module, "collect_all_rounds_for_game", return_value={2: [_r2_row("p1")], 1: []}):
        exit_code, _output_dir = _run(module, tmp_path)
    assert exit_code == 2
    assert "FATAL: no frozen R1 source" in capsys.readouterr().out


def test_group_page_fetch_failure_aborts_loudly(module, tmp_path, capsys):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir, [("p1", 80.0)])

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: [_r2_row("p1")], 1: []}):
        with patch.object(module, "fetch_group_page_html", side_effect=ConnectionError("simulated failure")):
            exit_code, output_dir = _run(module, tmp_path)

    assert exit_code == 4
    assert not (output_dir / "player_cut_evaluation.csv").exists()
    assert "FATAL" in capsys.readouterr().out


def test_override_conflicting_with_real_r3_presence_is_reported_not_silently_resolved(module, tmp_path, capsys):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir, [("p1", 80.0)])
    r2_rows = [_r2_row("p1", round2=68, total_strokes=140, rank=1)]
    parsed_r3 = [GroupingRow(player_code="p1", player_name="Player_p1", starting_tee="1", tee_time="09:10", group=None)]
    override_path = tmp_path / "explicit_status.json"
    override_path.write_text('[{"player_code": "p1", "status": "WD"}]', encoding="utf-8")

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: r2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>x</html>")):
            with patch.object(module, "parse_round_grouping", return_value=parsed_r3):
                exit_code, _output_dir = _run(module, tmp_path, argv_extra=["--explicit-status-json", str(override_path)])

    captured = capsys.readouterr().out
    assert "OVERRIDE CONFLICTS" in captured
    assert "p1" in captured
