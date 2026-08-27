"""Tests for klpga.neo_win.archive — the frozen PRE snapshot writer.
Same append-only/never-overwrite guarantee as klpga.archive.
prediction_archive, verified independently here since this is a
separate, self-contained implementation (zero code coupling to
predictions/'s own archive, by design)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.neo_win.archive import (
    NeoWinAlreadyArchivedError,
    NeoWinEntrantSnapshot,
    NeoWinPredictionSnapshot,
    RECORD_KIND,
    archive_paths,
    snapshot_to_dict,
    write_neo_win_snapshot_atomic,
)


def _snapshot(prediction_id="001", game_code="G1") -> NeoWinPredictionSnapshot:
    entrant = NeoWinEntrantSnapshot(
        rank=1,
        player_code="p1",
        player_name="Player One",
        win_probability=1.0,
        prior_events_n=10,
        prior_avg_round_score_to_par=-1.0,
        prior_recent_form_10=-1.0,
        prior_recent_form_10_n=10,
        neo_consistency_stddev=2.0,
        neo_consistency_stddev_n=10,
        neo_official_metric=-220.0,
        neo_official_metric_n=1,
        player_master_matched=True,
    )
    return NeoWinPredictionSnapshot(
        prediction_id=prediction_id,
        created_at_utc="2027-01-01T00:00:00Z",
        record_kind=RECORD_KIND,
        game_code=game_code,
        tournament_name="Test Open",
        cutoff_date="2027-01-01",
        cutoff_source="explicit_arg",
        model_id="NEO_WIN_V0_1",
        model_version="v0.1",
        model_features=("prior_avg_round_score_to_par",),
        training_tournament_count=10,
        field_size=1,
        entrants_predicted=1,
        dropped_entrants=0,
        probability_sum=1.0,
        minimum_probability=1.0,
        maximum_probability=1.0,
        zero_history_count=0,
        unmatched_count=0,
        official_metric_context={"official_metric_label": "평균 티샷 거리"},
        leakage_validation={"clean": True, "violations": []},
        missing_data_report={"zero_prior_events_count": 0},
        known_limitations=("test limitation",),
        predictions=(entrant,),
    )


def test_write_creates_json_and_csv(tmp_path):
    json_path, csv_path = write_neo_win_snapshot_atomic(_snapshot(), tmp_path)
    assert json_path.exists()
    assert csv_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["record_kind"] == RECORD_KIND
    assert data["predictions"][0]["player_code"] == "p1"


def test_write_never_overwrites_an_existing_snapshot(tmp_path):
    write_neo_win_snapshot_atomic(_snapshot(), tmp_path)
    with pytest.raises(NeoWinAlreadyArchivedError):
        write_neo_win_snapshot_atomic(_snapshot(), tmp_path)


def test_different_prediction_ids_coexist(tmp_path):
    write_neo_win_snapshot_atomic(_snapshot(prediction_id="001"), tmp_path)
    json_path, _ = write_neo_win_snapshot_atomic(_snapshot(prediction_id="002"), tmp_path)
    assert json_path.exists()


def test_archive_paths_are_under_the_cutoff_year(tmp_path):
    json_path, csv_path = archive_paths(tmp_path, "001", "G1", "2027-01-01")
    assert json_path.parent.name == "2027"
    assert json_path.name == "neo_win_001_G1.json"
    assert csv_path.name == "neo_win_001_G1.csv"


def test_snapshot_to_dict_is_a_pure_mapper():
    d = snapshot_to_dict(_snapshot())
    assert d["game_code"] == "G1"
    assert d["known_limitations"] == ["test limitation"]
