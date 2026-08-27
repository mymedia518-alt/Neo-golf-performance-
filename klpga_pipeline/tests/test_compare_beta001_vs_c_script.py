"""Tests for scripts/39_compare_beta001_vs_c.py — offline, against
hand-written snapshot JSON files under tmp_path."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "39_compare_beta001_vs_c.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("compare_beta001_vs_c_script", SCRIPT_PATH)
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
            {"rank": 1, "player_code": "p1", "player_name": "서교림", "win_probability": 0.10, "prior_events_n": 10,
             "prior_avg_round_score_to_par": -1.0, "prior_recent_form_10": -1.0, "prior_recent_form_10_n": 10,
             "neo_consistency_stddev": 2.0, "neo_consistency_stddev_n": 10, "official_metrics": {},
             "player_master_matched": True},
            {"rank": 2, "player_code": "p2", "player_name": "박현경", "win_probability": 0.08, "prior_events_n": 10,
             "prior_avg_round_score_to_par": -1.0, "prior_recent_form_10": -1.0, "prior_recent_form_10_n": 10,
             "neo_consistency_stddev": 2.0, "neo_consistency_stddev_n": 10, "official_metrics": {},
             "player_master_matched": True},
        ],
    }


def _c_json(game_code="G1"):
    return {
        "prediction_id": "001-C", "created_at_utc": "2026-08-27T00:00:00Z",
        "record_kind": "neo_win_beta001c_prediction_v1", "game_code": game_code, "tournament_name": "T",
        "cutoff_date": "2026-08-27", "cutoff_source": "explicit_arg", "selected_model_id": "MODEL_B",
        "model_features": ["f"], "selection_decision": {}, "training_tournament_count": 10, "field_size": 2,
        "entrants_predicted": 2, "probability_sum": 1.0, "minimum_probability": 0.05, "maximum_probability": 0.5,
        "duplicate_count": 0, "null_count": 0, "non_field_count": 0, "known_limitations": [],
        "predictions": [
            {"rank": 2, "player_code": "p1", "player_name": "서교림", "win_probability": 0.06, "prior_events_n": 10,
             "feature_values": {}, "player_master_matched": True},
            {"rank": 1, "player_code": "p2", "player_name": "박현경", "win_probability": 0.15, "prior_events_n": 10,
             "feature_values": {}, "player_master_matched": True},
        ],
    }


def test_script_writes_comparison_csv_and_highlights(module, tmp_path, capsys):
    pre_path = tmp_path / "pre.json"
    c_path = tmp_path / "c.json"
    pre_path.write_text(json.dumps(_pre_json()), encoding="utf-8")
    c_path.write_text(json.dumps(_c_json()), encoding="utf-8")
    output_dir = tmp_path / "out"

    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--pre-001-json", str(pre_path), "--c-json", str(c_path),
        "--highlight", "서교림", "박현경", "--output-dir", str(output_dir),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0

    csv_path = output_dir / "BETA001_VS_001C_COMPARISON.csv"
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = {r["player_code"]: r for r in csv.DictReader(f)}
    assert rows["p1"]["old_rank"] == "1"
    assert rows["p1"]["new_rank"] == "2"

    out = capsys.readouterr().out
    assert "HIGHLIGHTED PLAYERS" in out
    assert "서교림" in out


def test_script_refuses_mismatched_game_codes(module, tmp_path):
    pre_path = tmp_path / "pre.json"
    c_path = tmp_path / "c.json"
    pre_path.write_text(json.dumps(_pre_json(game_code="G1")), encoding="utf-8")
    c_path.write_text(json.dumps(_c_json(game_code="G2")), encoding="utf-8")

    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["prog", "--pre-001-json", str(pre_path), "--c-json", str(c_path), "--output-dir", str(tmp_path / "out")]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 5


def test_script_errors_on_missing_file(module, tmp_path):
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = [
        "prog", "--pre-001-json", str(tmp_path / "nope.json"), "--c-json", str(tmp_path / "nope2.json"),
        "--output-dir", str(tmp_path / "out"),
    ]
    try:
        rc = module.main()
    finally:
        _sys.argv = old_argv
    assert rc == 3
