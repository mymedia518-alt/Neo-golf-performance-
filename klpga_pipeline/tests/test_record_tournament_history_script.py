"""Tests for scripts/42_record_tournament_history.py — offline, against
hand-written frozen PRE/R1 JSON files under tmp_path (never the real
neo_win_predictions/ or neo_win_c_predictions/ roots)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "42_record_tournament_history.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("record_tournament_history_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _pre_json(game_code="G1"):
    return {
        "prediction_id": "001", "created_at_utc": "2026-08-27T00:00:00Z", "record_kind": "neo_win_beta_prediction_v1",
        "game_code": game_code, "tournament_name": "T", "cutoff_date": "2026-08-27", "cutoff_source": "explicit_arg",
        "model_id": "NEO_WIN_V0_1", "model_version": "v0.1", "model_features": ["f"], "training_tournament_count": 10,
        "field_size": 2, "entrants_predicted": 2, "dropped_entrants": 0, "probability_sum": 1.0,
        "minimum_probability": 0.05, "maximum_probability": 0.5, "zero_history_count": 0, "unmatched_count": 0,
        "official_metric_context": {}, "leakage_validation": {"clean": True}, "missing_data_report": {},
        "known_limitations": [],
        "predictions": [
            {"rank": 1, "player_code": "p1", "player_name": "A", "win_probability": 0.10, "prior_events_n": 10,
             "prior_avg_round_score_to_par": -1.0, "prior_recent_form_10": -1.0, "prior_recent_form_10_n": 10,
             "neo_consistency_stddev": 2.0, "neo_consistency_stddev_n": 10, "official_metrics": {},
             "player_master_matched": True},
            {"rank": 2, "player_code": "p2", "player_name": "B", "win_probability": 0.05, "prior_events_n": 8,
             "prior_avg_round_score_to_par": -0.5, "prior_recent_form_10": -0.5, "prior_recent_form_10_n": 8,
             "neo_consistency_stddev": 1.5, "neo_consistency_stddev_n": 8, "official_metrics": {},
             "player_master_matched": True},
        ],
    }


def _r1_json(game_code="G1"):
    return {
        "prediction_id": "001-R1", "created_at_utc": "2026-08-28T00:00:00Z",
        "record_kind": "neo_win_beta_round_update_v1", "game_code": game_code, "tournament_name": "T",
        "pre_prediction_id": "001", "pre_cutoff_date": "2026-08-27", "round_number": 1, "cut_fraction_used": 0.5,
        "cut_format": "single_36_hole_cut", "n_simulations": 5000, "field_size": 2, "entrants_scored": 2,
        "missing_r1_players": [], "win_probability_sum_pct": 100.0, "leakage_check": {"clean": True},
        "known_limitations": [],
        "predictions": [
            {"player_code": "p1", "player_name": "A", "pre_win_probability": 0.10, "r1_score_to_par": -3,
             "r1_position": 2, "strokes_behind_leader": 1.0, "post_r1_win_pct": 15.0, "post_r1_top5_pct": 40.0,
             "post_r1_top10_pct": 60.0, "post_r1_top20_pct": 80.0, "post_r1_make_cut_pct": 95.0,
             "probability_change_from_pre": 5.0, "missing_r1_data": False},
            {"player_code": "p2", "player_name": "B", "pre_win_probability": 0.05, "r1_score_to_par": None,
             "r1_position": None, "strokes_behind_leader": None, "post_r1_win_pct": None, "post_r1_top5_pct": None,
             "post_r1_top10_pct": None, "post_r1_top20_pct": None, "post_r1_make_cut_pct": None,
             "probability_change_from_pre": None, "missing_r1_data": True},
        ],
    }


@pytest.fixture()
def frozen_roots(tmp_path):
    predictions_dir = tmp_path / "neo_win_predictions" / "2026"
    predictions_dir.mkdir(parents=True)
    pre_path = predictions_dir / "neo_win_001_G1.json"
    r1_path = predictions_dir / "neo_win_001-R1_G1.json"
    pre_path.write_text(json.dumps(_pre_json()), encoding="utf-8")
    r1_path.write_text(json.dumps(_r1_json()), encoding="utf-8")
    return tmp_path


def test_script_records_and_verifies_pre_r1_history(module, frozen_roots, capsys):
    predictions_dir = frozen_roots / "neo_win_predictions"
    c_predictions_dir = frozen_roots / "neo_win_c_predictions"
    history_dir = frozen_roots / "neo_tournament_history"
    pre_path = predictions_dir / "2026" / "neo_win_001_G1.json"
    before_hash = hashlib.sha256(pre_path.read_bytes()).hexdigest()

    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--game-code", "G1", "--predictions-dir", str(predictions_dir),
        "--c-predictions-dir", str(c_predictions_dir), "--history-dir", str(history_dir),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv

    assert rc == 0
    assert hashlib.sha256(pre_path.read_bytes()).hexdigest() == before_hash

    out = capsys.readouterr().out
    assert "PRE COUNT: 2" in out
    assert "R1 COUNT: 2" in out
    assert "LINKED PLAYERS: 2" in out
    assert "FROZEN FILES MODIFIED: 0" in out
    assert "p1 (A): PRE 10.0 -> R1 15.0" in out


def test_script_rerun_is_idempotent_via_skip_log(module, frozen_roots):
    predictions_dir = frozen_roots / "neo_win_predictions"
    c_predictions_dir = frozen_roots / "neo_win_c_predictions"
    history_dir = frozen_roots / "neo_tournament_history"

    import sys as _sys
    old_argv = _sys.argv
    argv = [
        "prog", "--game-code", "G1", "--predictions-dir", str(predictions_dir),
        "--c-predictions-dir", str(c_predictions_dir), "--history-dir", str(history_dir),
    ]
    try:
        _sys.argv = argv
        rc1 = module.main()
        _sys.argv = argv
        rc2 = module.main()  # must not raise/crash on already-recorded stages
    finally:
        _sys.argv = old_argv
    assert rc1 == 0
    assert rc2 == 0


@pytest.fixture()
def pre_only_root(tmp_path):
    predictions_dir = tmp_path / "neo_win_predictions" / "2026"
    predictions_dir.mkdir(parents=True)
    (predictions_dir / "neo_win_001_G1.json").write_text(json.dumps(_pre_json()), encoding="utf-8")
    return tmp_path


def test_script_records_r1_as_missing_when_no_r1_artifact_exists(module, pre_only_root, capsys):
    predictions_dir = pre_only_root / "neo_win_predictions"
    c_predictions_dir = pre_only_root / "neo_win_c_predictions"
    history_dir = pre_only_root / "neo_tournament_history"
    pre_path = predictions_dir / "2026" / "neo_win_001_G1.json"
    before_hash = hashlib.sha256(pre_path.read_bytes()).hexdigest()

    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--game-code", "G1", "--predictions-dir", str(predictions_dir),
        "--c-predictions-dir", str(c_predictions_dir), "--history-dir", str(history_dir),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv

    assert rc == 0  # a confirmed-missing R1 is a successful, disclosed outcome, not a failure
    assert hashlib.sha256(pre_path.read_bytes()).hexdigest() == before_hash

    out = capsys.readouterr().out
    assert "PRE STATUS: RECORDED" in out
    assert "PRE COUNT: 2" in out
    assert "R1 STATUS: HISTORICAL_SNAPSHOT_MISSING" in out
    assert "R1 MISSING REASON:" in out
    assert "R1 COUNT: 0" in out
    assert "LINKED PLAYERS: 0" in out
    assert "N/A — R1 is HISTORICAL_SNAPSHOT_MISSING" in out
    assert "FROZEN FILES MODIFIED: 0" in out
    # never a fabricated 0% shown as a real value
    assert "PRE 10.0 -> R1 0" not in out


def test_script_rerun_after_r1_missing_is_idempotent(module, pre_only_root):
    predictions_dir = pre_only_root / "neo_win_predictions"
    c_predictions_dir = pre_only_root / "neo_win_c_predictions"
    history_dir = pre_only_root / "neo_tournament_history"

    import sys as _sys
    old_argv = _sys.argv
    argv = [
        "prog", "--game-code", "G1", "--predictions-dir", str(predictions_dir),
        "--c-predictions-dir", str(c_predictions_dir), "--history-dir", str(history_dir),
    ]
    try:
        _sys.argv = argv
        rc1 = module.main()
        _sys.argv = argv
        rc2 = module.main()
    finally:
        _sys.argv = old_argv
    assert rc1 == 0
    assert rc2 == 0


def _r1_c_json(game_code="G1"):
    data = _r1_json(game_code)
    data["prediction_id"] = "001-C-R1"
    return data


def test_script_supersedes_stale_missing_marker_once_real_r1_c_arrives(module, pre_only_root, capsys):
    """RED TEAM follow-up scenario: an earlier run recorded R1 as
    HISTORICAL_SNAPSHOT_MISSING (no frozen R1 existed yet); a real
    #001-C-R1 snapshot is later frozen — the marker must be preserved
    untouched and the real result recorded as a superseding event, not
    silently dropped."""
    predictions_dir = pre_only_root / "neo_win_predictions"
    c_predictions_dir = pre_only_root / "neo_win_c_predictions"
    history_dir = pre_only_root / "neo_tournament_history"

    import sys as _sys

    old_argv = _sys.argv
    argv = [
        "prog", "--game-code", "G1", "--predictions-dir", str(predictions_dir),
        "--c-predictions-dir", str(c_predictions_dir), "--history-dir", str(history_dir),
    ]
    try:
        _sys.argv = argv
        rc1 = module.main()
    finally:
        _sys.argv = old_argv
    assert rc1 == 0
    marker_path = history_dir / "G1" / "R1.json"
    assert marker_path.exists()
    marker_bytes_before = marker_path.read_bytes()

    # a real #001-C-R1 snapshot is now frozen (naming this script prefers)
    r1_c_path = predictions_dir / "2026" / "neo_win_001-C-R1_G1.json"
    r1_c_path.write_text(json.dumps(_r1_c_json()), encoding="utf-8")

    try:
        _sys.argv = argv
        rc2 = module.main()
    finally:
        _sys.argv = old_argv
    assert rc2 == 0

    # the original MISSING marker file is byte-for-byte unchanged
    assert marker_path.read_bytes() == marker_bytes_before

    out = capsys.readouterr().out
    assert "R1 STATUS: RECORDED" in out
    assert "write: SUPERSEDED_MISSING_MARKER" in out
    assert "R1 COUNT: 2" in out
    assert "LINKED PLAYERS: 2" in out
    assert "p1 (A): PRE 10.0 -> R1 15.0" in out

    from klpga.neo_win.tournament_history import (
        STAGE_R1,
        STATUS_HISTORICAL_SNAPSHOT_MISSING,
        STATUS_RECORDED,
        read_effective_history_stage,
        read_full_history_events,
    )

    events = read_full_history_events(history_dir, "G1", STAGE_R1)
    assert len(events) == 2
    assert events[0].status == STATUS_HISTORICAL_SNAPSHOT_MISSING
    assert events[1].status == STATUS_RECORDED
    assert read_effective_history_stage(history_dir, "G1", STAGE_R1).status == STATUS_RECORDED

    # a THIRD run (real R1 already recorded) must stay idempotent — SKIP + LOG, never a crash
    try:
        _sys.argv = argv
        rc3 = module.main()
    finally:
        _sys.argv = old_argv
    assert rc3 == 0
    out3 = capsys.readouterr().out
    assert "write: ALREADY_RECORDED" in out3


def test_script_reports_error_when_no_frozen_files_exist(module, tmp_path, capsys):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--game-code", "NOPE",
        "--predictions-dir", str(tmp_path / "neo_win_predictions"),
        "--c-predictions-dir", str(tmp_path / "neo_win_c_predictions"),
        "--history-dir", str(tmp_path / "neo_tournament_history"),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 4
    out = capsys.readouterr().out
    assert "No frozen PRE snapshot found" in out
