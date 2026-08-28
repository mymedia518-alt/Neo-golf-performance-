"""End-to-end test for scripts/generate_r2_frozen_forecast.py — the R2
FROZEN FORECAST (TOP20/TOP10/TOP5/WIN for the real, double-verified
Round 3 continuers only), reusing klpga.neo_win.round_update_r2.
simulate_post_round2 verbatim (no new model logic).

Fully synthetic: a frozen R1 history fixture, a fake frozen PRE
snapshot (duck-typed `.predictions`), and monkeypatched real-data
functions (collect_all_rounds_for_game, fetch_group_page_html,
parse_round_grouping) — no network, no real DB.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.neo_win.archive import NeoWinEntrantSnapshot
from klpga.neo_win.tournament_history import (
    STAGE_R1,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    write_history_stage_atomic,
)
from klpga.parsers.group_page_parser import GroupingRow
from klpga.parsers.leaderboard_parser import PlayerRoundRow

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_r2_frozen_forecast.py"
GAME_CODE = "2026080099"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "generate_r2_frozen_forecast_script")


class _FakeSnapshot:
    def __init__(self, predictions):
        self.predictions = predictions


def _entrant(code, name, prior_avg, consistency):
    return NeoWinEntrantSnapshot(
        rank=1, player_code=code, player_name=name, win_probability=0.1,
        prior_events_n=10, prior_avg_round_score_to_par=prior_avg, prior_recent_form_10=prior_avg,
        prior_recent_form_10_n=10, neo_consistency_stddev=consistency, neo_consistency_stddev_n=10,
        official_metrics={}, player_master_matched=True,
    )


def _seed_frozen_r1_history(history_dir, codes_and_cut_pct):
    entrants = tuple(
        HistoryEntrant(
            player_code=code, player_name=f"Player_{code}", win_pct=5.0,
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


def _r2_row(code, round2=68, total_strokes=140, rank=1):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=f"Player_{code}", player_eng_name=None, round_number=2,
        rank_display=str(rank), rank=rank, tie_flag=False, status=None,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=-2, holes_completed="18",
        total_strokes=total_strokes,
        round1_score=None, round2_score=round2, round3_score=None, round4_score=None,
    )


def _r1_row(code, round1=70, rank=1):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=f"Player_{code}", player_eng_name=None, round_number=1,
        rank_display=str(rank), rank=rank, tie_flag=False, status=None,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=-2, holes_completed="18",
        total_strokes=round1,
        round1_score=round1, round2_score=None, round3_score=None, round4_score=None,
    )


def _run(module, tmp_path, argv_extra=()):
    output_dir = tmp_path / "out"
    argv = [
        "generate_r2_frozen_forecast.py",
        "--game-code", GAME_CODE,
        "--pre-cutoff-date", "2026-08-27",
        "--tournament-name", "Test Open",
        "--cache-dir", str(tmp_path / "cache"),
        "--output-dir", str(output_dir),
        "--history-dir", str(tmp_path / "neo_tournament_history"),
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
        "--outputs-csv-path", str(tmp_path / "BETA001_R1_FULL.csv"),
        "--n-simulations", "200",
        *argv_extra,
    ]
    with patch("sys.argv", argv):
        exit_code = module.main()
    return exit_code, output_dir


def test_end_to_end_forecast_population_is_exactly_confirmed_continuers(module, tmp_path, capsys):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir, [("p1", 80.0), ("p2", 70.0), ("p3", 30.0)])

    pre_snapshot = _FakeSnapshot(
        [_entrant("p1", "Player_p1", -1.0, 2.0), _entrant("p2", "Player_p2", -0.5, 2.5), _entrant("p3", "Player_p3", 0.0, 2.0)]
    )
    r1_rows = [_r1_row("p1", round1=70, rank=1), _r1_row("p2", round1=72, rank=2), _r1_row("p3", round1=75, rank=3)]
    r2_rows = [
        _r2_row("p1", round2=68, total_strokes=140, rank=1),  # confirmed continuer
        _r2_row("p2", round2=70, total_strokes=142, rank=2),  # confirmed continuer
        _r2_row("p3", round2=78, total_strokes=150, rank=3),  # absent from R3, missed cut
    ]
    parsed_r3 = [
        GroupingRow(player_code="p1", player_name="Player_p1", starting_tee="1", tee_time="09:10", group=None),
        GroupingRow(player_code="p2", player_name="Player_p2", starting_tee="1", tee_time="09:10", group=None),
    ]

    with patch.object(module, "_load_pre_snapshot", return_value=pre_snapshot):
        with patch.object(module, "collect_all_rounds_for_game", return_value={2: r2_rows, 1: r1_rows}):
            with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>x</html>")):
                with patch.object(module, "parse_round_grouping", return_value=parsed_r3):
                    exit_code, output_dir = _run(module, tmp_path)

    captured = capsys.readouterr().out
    assert exit_code == 0, captured
    assert "Simulation population count: 2" in captured
    assert "ALL_PASSED: True" in captured
    assert "DO NOT PUBLISH" in captured

    csv_path = output_dir / GAME_CODE / f"BETA001_R2_FORECAST_{GAME_CODE}.csv"
    assert csv_path.is_file()
    with open(csv_path, encoding="utf-8") as f:
        rows = {r["player_code"]: r for r in csv.DictReader(f)}
    assert set(rows) == {"p1", "p2"}  # p3 (missed cut) never enters
    assert float(rows["p1"]["win_pct"]) + float(rows["p2"]["win_pct"]) == pytest.approx(100.0, abs=2.0)

    html_path = output_dir / GAME_CODE / f"r2_forecast_{GAME_CODE}.html"
    assert html_path.is_file()
    html = html_path.read_text(encoding="utf-8")
    assert "NEO 첫 실전 검증" in html
    assert "2R 종료 후 우승 경쟁 예측" in html
    assert "Player_p1" in html and "Player_p2" in html
    assert "Player_p3" not in html  # missed-cut player never enters the forecast table or cards


def test_no_frozen_r1_source_fails_loudly(module, tmp_path, capsys):
    pre_snapshot = _FakeSnapshot([_entrant("p1", "Player_p1", -1.0, 2.0)])
    with patch.object(module, "_load_pre_snapshot", return_value=pre_snapshot):
        exit_code, _output_dir = _run(module, tmp_path)
    assert exit_code == 2
    assert "FATAL: no frozen R1 source" in capsys.readouterr().out


def test_no_pre_snapshot_fails_loudly(module, tmp_path, capsys):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir, [("p1", 80.0)])
    with patch.object(module, "_load_pre_snapshot", return_value=None):
        exit_code, _output_dir = _run(module, tmp_path)
    assert exit_code == 2
    assert "FATAL: no frozen PRE snapshot" in capsys.readouterr().out


def test_missing_real_score_for_confirmed_continuer_aborts_rather_than_fabricating(module, tmp_path, capsys):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir, [("p1", 80.0)])
    pre_snapshot = _FakeSnapshot([_entrant("p1", "Player_p1", -1.0, 2.0)])
    # Round 2 has no row for p1 at all (no real score) even though R3 grouping confirms them --
    # this must never be papered over with a fabricated score.
    r2_rows = [_r2_row("p2", round2=68, total_strokes=140, rank=1)]
    parsed_r3 = [GroupingRow(player_code="p1", player_name="Player_p1", starting_tee="1", tee_time="09:10", group=None)]

    with patch.object(module, "_load_pre_snapshot", return_value=pre_snapshot):
        with patch.object(module, "collect_all_rounds_for_game", return_value={2: r2_rows, 1: []}):
            with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>x</html>")):
                with patch.object(module, "parse_round_grouping", return_value=parsed_r3):
                    exit_code, output_dir = _run(module, tmp_path)

    captured = capsys.readouterr().out
    assert exit_code == 6, captured
    assert "FATAL" in captured
    assert "p1" in captured
    assert not (output_dir / GAME_CODE / f"BETA001_R2_FORECAST_{GAME_CODE}.csv").exists()
