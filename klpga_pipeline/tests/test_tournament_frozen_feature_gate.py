import pytest

from klpga.tournament_model_adapter import (
    FrozenFeatureSnapshotRequired,
    require_frozen_feature_snapshot,
)


def test_stage_forecast_requires_frozen_feature_snapshot():
    with pytest.raises(FrozenFeatureSnapshotRequired):
        require_frozen_feature_snapshot(
            artifact="WIN_PROBABILITY",
            feature_snapshot_id=None,
            feature_snapshot_sha256=None,
        )


def test_probability_output_is_not_a_feature_snapshot():
    # A historical probability artifact cannot substitute for the
    # immutable model-input features used to create it.
    with pytest.raises(FrozenFeatureSnapshotRequired):
        require_frozen_feature_snapshot(
            artifact="NEXT_ROUND_FORECAST",
            feature_snapshot_id=None,
            feature_snapshot_sha256=None,
        )


def test_valid_frozen_feature_snapshot_unlocks_stage_model():
    require_frozen_feature_snapshot(
        artifact="WIN_PROBABILITY",
        feature_snapshot_id="PRE:GAME-X:features-v1",
        feature_snapshot_sha256="a" * 64,
    )


def test_non_forecast_artifact_does_not_require_model_features():
    require_frozen_feature_snapshot(
        artifact="FACTUAL_LEADERBOARD",
        feature_snapshot_id=None,
        feature_snapshot_sha256=None,
    )
