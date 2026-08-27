"""Tests for klpga.neo_win.beta001c_archive — the frozen PRE snapshot
writer for BETA #001-C. Same append-only/never-overwrite guarantee as
klpga.neo_win.archive (BETA #001's own), verified independently here
since this is a separate, self-contained implementation with zero code
coupling to either predictions/ or neo_win_predictions/."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from klpga.neo_win.beta001c_archive import (
    NeoWinCAlreadyArchivedError,
    NeoWinCEntrantSnapshot,
    NeoWinCPredictionSnapshot,
    RECORD_KIND,
    archive_paths,
    read_neo_win_c_snapshot,
    snapshot_to_dict,
    write_neo_win_c_snapshot_atomic,
)


def _snapshot(prediction_id="001-C", game_code="G1") -> NeoWinCPredictionSnapshot:
    entrant = NeoWinCEntrantSnapshot(
        rank=1,
        player_code="p1",
        player_name="Player One",
        win_probability=1.0,
        prior_events_n=10,
        feature_values={"prior_avg_round_score_to_par": -1.0, "neo_driving": -0.5},
        player_master_matched=True,
    )
    return NeoWinCPredictionSnapshot(
        prediction_id=prediction_id,
        created_at_utc="2027-01-01T00:00:00Z",
        record_kind=RECORD_KIND,
        game_code=game_code,
        tournament_name="Test Open",
        cutoff_date="2027-01-01",
        cutoff_source="explicit_arg",
        selected_model_id="MODEL_B",
        model_features=("prior_avg_round_score_to_par", "neo_driving"),
        selection_decision={"selected_model_id": "MODEL_B", "reasoning": ["test"]},
        training_tournament_count=10,
        field_size=1,
        entrants_predicted=1,
        probability_sum=1.0,
        minimum_probability=1.0,
        maximum_probability=1.0,
        duplicate_count=0,
        null_count=0,
        non_field_count=0,
        known_limitations=("test limitation",),
        predictions=(entrant,),
    )


def test_write_creates_json_and_csv(tmp_path):
    json_path, csv_path = write_neo_win_c_snapshot_atomic(_snapshot(), tmp_path)
    assert json_path.exists()
    assert csv_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["record_kind"] == RECORD_KIND
    assert data["predictions"][0]["player_code"] == "p1"
    assert data["selected_model_id"] == "MODEL_B"


def test_write_never_overwrites_an_existing_snapshot(tmp_path):
    write_neo_win_c_snapshot_atomic(_snapshot(), tmp_path)
    with pytest.raises(NeoWinCAlreadyArchivedError):
        write_neo_win_c_snapshot_atomic(_snapshot(), tmp_path)


def test_prediction_id_001_c_never_collides_with_beta001_own_001(tmp_path):
    # 001-C's own archive directory is entirely separate from
    # neo_win_predictions/ (BETA #001's own), so this is really just
    # confirming filename shape, not a cross-module check — but pins
    # the real requirement: 001-C must never look like a second write
    # to prediction_id "001".
    json_path, _ = write_neo_win_c_snapshot_atomic(_snapshot(prediction_id="001-C"), tmp_path)
    assert "001-C" in json_path.name
    assert json_path.name != "neo_win_c_001_G1.json"


def test_different_prediction_ids_coexist(tmp_path):
    write_neo_win_c_snapshot_atomic(_snapshot(prediction_id="001-C"), tmp_path)
    json_path, _ = write_neo_win_c_snapshot_atomic(_snapshot(prediction_id="002-C"), tmp_path)
    assert json_path.exists()


def test_archive_paths_are_under_the_cutoff_year(tmp_path):
    json_path, csv_path = archive_paths(tmp_path, "001-C", "G1", "2027-01-01")
    assert json_path.parent.name == "2027"
    assert json_path.name == "neo_win_c_001-C_G1.json"
    assert csv_path.name == "neo_win_c_001-C_G1.csv"


def test_snapshot_to_dict_is_a_pure_mapper():
    d = snapshot_to_dict(_snapshot())
    assert d["game_code"] == "G1"
    assert d["known_limitations"] == ["test limitation"]


def test_read_round_trips_written_snapshot(tmp_path):
    json_path, _ = write_neo_win_c_snapshot_atomic(_snapshot(), tmp_path)
    loaded = read_neo_win_c_snapshot(json_path)
    assert loaded.prediction_id == "001-C"
    assert loaded.predictions[0].feature_values["neo_driving"] == -0.5


def test_csv_columns_match_model_features(tmp_path):
    _, csv_path = write_neo_win_c_snapshot_atomic(_snapshot(), tmp_path)
    with open(csv_path, encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    assert "prior_avg_round_score_to_par" in header
    assert "neo_driving" in header
