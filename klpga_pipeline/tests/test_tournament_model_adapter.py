import pytest

from klpga.tournament_engine import Stage
from klpga.tournament_model_adapter import (
    ModelBlocked,
    ModelRequest,
    ModelResult,
    TournamentModelAdapter,
    frozen_result_runner,
)


def test_model_cannot_bypass_stage_gate():
    adapter = TournamentModelAdapter()

    adapter.register(
        "WIN_PROBABILITY",
        lambda req: ModelResult(
            model_id="neo",
            model_version="1",
            input_snapshot_id=req.input_snapshot_id,
            artifact="WIN_PROBABILITY",
            payload={},
        ),
    )

    request = ModelRequest(
        game_code="ANY",
        stage=Stage.R2_LIVE,
        artifact="WIN_PROBABILITY",
        input_snapshot_id="snap-1",
        players=("1",),
                      feature_snapshot_id="PRE:TEST:frozen-features",
                  feature_snapshot_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)

    with pytest.raises(ModelBlocked):
        adapter.run(request)


def test_model_runs_after_validated_cut():
    adapter = TournamentModelAdapter()

    adapter.register(
        "WIN_PROBABILITY",
        lambda req: ModelResult(
            model_id="neo",
            model_version="1",
            input_snapshot_id=req.input_snapshot_id,
            artifact="WIN_PROBABILITY",
            payload={"1": 0.25},
        ),
    )

    result = adapter.run(
        ModelRequest(
            game_code="ANY",
            stage=Stage.CUT_CONFIRMED,
            artifact="WIN_PROBABILITY",
            input_snapshot_id="snap-1",
            players=("1",),
                    feature_snapshot_id="PRE:TEST:frozen-features",
            feature_snapshot_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
    )

    assert result.payload["1"] == 0.25


def test_missing_model_is_blocked_not_fabricated():
    adapter = TournamentModelAdapter()

    with pytest.raises(ModelBlocked):
        adapter.run(
            ModelRequest(
                game_code="ANY",
                stage=Stage.CUT_CONFIRMED,
                artifact="WIN_PROBABILITY",
                input_snapshot_id="snap-1",
                players=("1",),
                            feature_snapshot_id="PRE:TEST:frozen-features",
                feature_snapshot_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
        )


def test_model_must_return_same_snapshot():
    adapter = TournamentModelAdapter()

    adapter.register(
        "WIN_PROBABILITY",
        lambda req: ModelResult(
            model_id="neo",
            model_version="1",
            input_snapshot_id="WRONG",
            artifact="WIN_PROBABILITY",
            payload={},
        ),
    )

    with pytest.raises(ValueError):
        adapter.run(
            ModelRequest(
                game_code="ANY",
                stage=Stage.CUT_CONFIRMED,
                artifact="WIN_PROBABILITY",
                input_snapshot_id="snap-1",
                players=("1",),
                            feature_snapshot_id="PRE:TEST:frozen-features",
                feature_snapshot_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
        )


def test_frozen_historical_prediction_is_not_recalculated():
    adapter = TournamentModelAdapter()

    adapter.register(
        "WIN_PROBABILITY",
        frozen_result_runner(
            model_id="neo-frozen",
            model_version="historical-v1",
            artifact="WIN_PROBABILITY",
            payload_by_snapshot={
                "historical-snapshot": {
                    "p1": 0.20,
                    "p2": 0.10,
                }
            },
        ),
    )

    result = adapter.run(
        ModelRequest(
            game_code="PAST-EVENT",
            stage=Stage.CUT_CONFIRMED,
            artifact="WIN_PROBABILITY",
            input_snapshot_id="historical-snapshot",
            players=("p1", "p2"),
                    feature_snapshot_id="PRE:TEST:frozen-features",
            feature_snapshot_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
    )

    assert result.payload == {
        "p1": 0.20,
        "p2": 0.10,
    }

    assert result.model_version == "historical-v1"


def test_same_adapter_accepts_future_game_code_without_code_change():
    adapter = TournamentModelAdapter()

    adapter.register(
        "NEXT_ROUND_FORECAST",
        lambda req: ModelResult(
            model_id="neo",
            model_version="future-compatible",
            input_snapshot_id=req.input_snapshot_id,
            artifact="NEXT_ROUND_FORECAST",
            payload={
                "game_code_seen": req.game_code,
            },
        ),
    )

    for game_code in (
        "EVENT-A",
        "EVENT-B",
        "EVENT-NEXT-YEAR",
    ):
        result = adapter.run(
            ModelRequest(
                game_code=game_code,
                stage=Stage.CUT_CONFIRMED,
                artifact="NEXT_ROUND_FORECAST",
                input_snapshot_id=f"{game_code}-snapshot",
                players=("1",),
                            feature_snapshot_id="PRE:TEST:frozen-features",
                feature_snapshot_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
        )

        assert result.payload["game_code_seen"] == game_code
