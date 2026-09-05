import pytest

from klpga.tournament_engine import Stage
from klpga.tournament_model_adapter import (
    FrozenFeatureSnapshotRequired,
    ModelRequest,
    ModelResult,
    TournamentModelAdapter,
)


def _runner(request):
    return ModelResult(
        model_id="M4",
        model_version="M4",
        input_snapshot_id=request.input_snapshot_id,
        artifact=request.artifact,
        payload={"ok": True},
    )


def test_forecast_request_requires_frozen_feature_binding():
    adapter = TournamentModelAdapter()
    adapter.register("WIN_PROBABILITY", _runner)

    request = ModelRequest(
        game_code="GAME-X",
        stage=Stage.CUT_CONFIRMED,
        artifact="WIN_PROBABILITY",
        input_snapshot_id="R2:GAME-X:facts",
        players=("P1",),
    )

    with pytest.raises(FrozenFeatureSnapshotRequired):
        adapter.run(request)


def test_forecast_request_runs_with_snapshot_id_and_sha():
    adapter = TournamentModelAdapter()
    adapter.register("WIN_PROBABILITY", _runner)

    request = ModelRequest(
        game_code="GAME-X",
        stage=Stage.CUT_CONFIRMED,
        artifact="WIN_PROBABILITY",
        input_snapshot_id="R2:GAME-X:facts",
        players=("P1",),
        feature_snapshot_id="PRE:GAME-X:001",
        feature_snapshot_sha256="a" * 64,
    )

    result = adapter.run(request)

    assert result.model_id == "M4"
    assert result.input_snapshot_id == "R2:GAME-X:facts"


def test_factual_artifact_does_not_require_feature_binding():
    adapter = TournamentModelAdapter()
    adapter.register("FACTUAL_LEADERBOARD", _runner)

    request = ModelRequest(
        game_code="GAME-X",
        stage=Stage.R2_LIVE,
        artifact="FACTUAL_LEADERBOARD",
        input_snapshot_id="R2:GAME-X:facts",
        players=("P1",),
    )

    result = adapter.run(request)

    assert result.payload["ok"] is True
