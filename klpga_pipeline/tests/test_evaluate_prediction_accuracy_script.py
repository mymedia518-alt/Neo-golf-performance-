"""Tests for scripts/43_evaluate_prediction_accuracy.py — offline,
against hand-written history files under tmp_path."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from klpga.neo_win.tournament_history import (
    STAGE_FINAL,
    STAGE_PRE,
    history_entry_from_neo_win_pre_snapshot,
    write_history_stage_atomic,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "43_evaluate_prediction_accuracy.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_prediction_accuracy_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def test_script_reports_insufficient_evidence_on_empty_history_dir(module, tmp_path, capsys):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["prog", "--history-dir", str(tmp_path / "neo_tournament_history")]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0
    out = capsys.readouterr().out
    assert "EVALUABLE TOURNAMENTS (FINAL recorded): 0" in out
    assert out.count("STATUS: INSUFFICIENT_EVIDENCE") == 4  # PRE, R1, R2, R3
    assert "LEAKAGE CHECK: 0" in out


def test_script_evaluates_when_pre_and_final_both_recorded(module, tmp_path, capsys):
    from klpga.neo_win.archive import NeoWinEntrantSnapshot, NeoWinPredictionSnapshot, RECORD_KIND
    from klpga.neo_win.tournament_history import (
        HistoryEntrant,
        HistoryStageSnapshot,
    )

    history_dir = tmp_path / "neo_tournament_history"

    pre_snapshot = NeoWinPredictionSnapshot(
        prediction_id="001", created_at_utc="2026-08-27T00:00:00Z", record_kind=RECORD_KIND,
        game_code="G1", tournament_name="T", cutoff_date="2026-08-27", cutoff_source="explicit_arg",
        model_id="NEO_WIN_V0_1", model_version="v0.1", model_features=("f",), training_tournament_count=10,
        field_size=1, entrants_predicted=1, dropped_entrants=0, probability_sum=1.0,
        minimum_probability=1.0, maximum_probability=1.0, zero_history_count=0, unmatched_count=0,
        official_metric_context={}, leakage_validation={"clean": True}, missing_data_report={},
        known_limitations=(),
        predictions=(
            NeoWinEntrantSnapshot(
                rank=1, player_code="p1", player_name="A", win_probability=0.5, prior_events_n=10,
                prior_avg_round_score_to_par=-1.0, prior_recent_form_10=-1.0, prior_recent_form_10_n=10,
                neo_consistency_stddev=2.0, neo_consistency_stddev_n=10,
            ),
        ),
    )
    pre_entry = history_entry_from_neo_win_pre_snapshot(pre_snapshot, recorded_at_utc="t1")
    write_history_stage_atomic(pre_entry, history_dir)

    final_entry = HistoryStageSnapshot(
        game_code="G1", stage=STAGE_FINAL, record_kind="neo_tournament_history_stage_v1",
        recorded_at_utc="t2", source_prediction_id="", source_model_version="actual_result",
        source_generated_at_utc="2026-08-31T00:00:00Z", tournament_name="T", field_size=1,
        entrants=(HistoryEntrant(player_code="p1", player_name="A", actual_confirmed_winner=True),),
    )
    write_history_stage_atomic(final_entry, history_dir)

    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["prog", "--history-dir", str(history_dir)]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0
    out = capsys.readouterr().out
    assert "EVALUABLE TOURNAMENTS (FINAL recorded): 1" in out
    assert "STATUS: EVALUATED" in out
    assert "SAMPLE SIZE: 1" in out
    assert "BRIER (norm):" in out
