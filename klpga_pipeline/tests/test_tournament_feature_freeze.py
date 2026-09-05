from pathlib import Path

import pytest

from klpga.neo_win.archive import (
    NeoWinEntrantSnapshot,
    NeoWinPredictionSnapshot,
)
from klpga.tournament_feature_freeze import (
    freeze_pre_model_features,
    verify_frozen_pre_features,
)


def _snapshot(game_code="GAME-X"):
    entrant = NeoWinEntrantSnapshot(
        rank=1,
        player_code="P1",
        player_name="Player 1",
        win_probability=1.0,
        prior_events_n=10,
        prior_avg_round_score_to_par=-1.2,
        prior_recent_form_10=-4.0,
        prior_recent_form_10_n=10,
        neo_consistency_stddev=2.1,
        neo_consistency_stddev_n=20,
        official_metrics={},
        player_master_matched=True,
    )

    return NeoWinPredictionSnapshot(
        prediction_id="001",
        created_at_utc="2026-01-01T00:00:00Z",
        record_kind="neo_win_beta_prediction_v1",
        game_code=game_code,
        tournament_name="Generic Event",
        cutoff_date="2026-01-01",
        cutoff_source="entry freeze",
        model_id="M4",
        model_version="M4",
        model_features=(
            "prior_avg_round_score_to_par",
            "prior_recent_form_10",
        ),
        training_tournament_count=100,
        field_size=1,
        entrants_predicted=1,
        dropped_entrants=0,
        probability_sum=1.0,
        minimum_probability=1.0,
        maximum_probability=1.0,
        zero_history_count=0,
        unmatched_count=0,
        official_metric_context={},
        leakage_validation={"future_data_excluded": True},
        missing_data_report={},
        known_limitations=(),
        predictions=(entrant,),
    )


def test_pre_freeze_creates_immutable_feature_archive(tmp_path):
    ref = freeze_pre_model_features(
        _snapshot(),
        predictions_root=tmp_path,
    )

    assert ref.stage == "PRE"
    assert ref.game_code == "GAME-X"
    assert len(ref.sha256) == 64
    assert Path(ref.path).exists()


def test_same_pre_snapshot_cannot_be_overwritten(tmp_path):
    snapshot = _snapshot()

    freeze_pre_model_features(
        snapshot,
        predictions_root=tmp_path,
    )

    with pytest.raises(Exception):
        freeze_pre_model_features(
            snapshot,
            predictions_root=tmp_path,
        )


def test_existing_freeze_verifies_by_sha(tmp_path):
    snapshot = _snapshot()

    ref = freeze_pre_model_features(
        snapshot,
        predictions_root=tmp_path,
    )

    verified = verify_frozen_pre_features(
        snapshot,
        predictions_root=tmp_path,
        expected_sha256=ref.sha256,
    )

    assert verified.sha256 == ref.sha256
    assert verified.snapshot_id == ref.snapshot_id


def test_wrong_sha_hard_stops(tmp_path):
    snapshot = _snapshot()

    freeze_pre_model_features(
        snapshot,
        predictions_root=tmp_path,
    )

    with pytest.raises(ValueError):
        verify_frozen_pre_features(
            snapshot,
            predictions_root=tmp_path,
            expected_sha256="0" * 64,
        )


def test_game_code_is_data_not_tournament_specific_code(tmp_path):
    a = freeze_pre_model_features(
        _snapshot("GAME-A"),
        predictions_root=tmp_path / "a",
    )

    b = freeze_pre_model_features(
        _snapshot("GAME-B"),
        predictions_root=tmp_path / "b",
    )

    assert a.game_code == "GAME-A"
    assert b.game_code == "GAME-B"
