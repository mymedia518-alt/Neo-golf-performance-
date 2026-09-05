"""Stable model boundary for the generic NEO Tournament Engine.

Tournament orchestration depends on this contract, not on a specific model
implementation. Models may be upgraded without changing tournament stage logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from klpga.tournament_engine import Stage, publication_allowed


@dataclass(frozen=True)
class ModelRequest:
    game_code: str
    stage: Stage
    artifact: str
    input_snapshot_id: str
    players: tuple[str, ...]
    feature_snapshot_id: str | None = None
    feature_snapshot_sha256: str | None = None

    def __post_init__(self):
        if not self.game_code.strip():
            raise ValueError("game_code required")
        if not self.artifact.strip():
            raise ValueError("artifact required")
        if not self.input_snapshot_id.strip():
            raise ValueError("input_snapshot_id required")


@dataclass(frozen=True)
class ModelResult:
    model_id: str
    model_version: str
    input_snapshot_id: str
    artifact: str
    payload: Mapping[str, Any]

    def __post_init__(self):
        if not self.model_id.strip():
            raise ValueError("model_id required")
        if not self.model_version.strip():
            raise ValueError("model_version required")
        if not self.input_snapshot_id.strip():
            raise ValueError("input_snapshot_id required")


class ModelBlocked(RuntimeError):
    pass


ModelRunner = Callable[[ModelRequest], ModelResult]


class TournamentModelAdapter:
    """Versioned model registry behind one publication gate."""

    def __init__(self) -> None:
        self._runners: dict[str, ModelRunner] = {}

    def register(self, artifact: str, runner: ModelRunner) -> None:
        key = artifact.strip().upper()

        if not key:
            raise ValueError("artifact required")

        if key in self._runners:
            raise ValueError(
                f"runner already registered for {key}"
            )

        self._runners[key] = runner

    def can_run(self, stage: Stage, artifact: str) -> bool:
        key = artifact.strip().upper()

        return (
            publication_allowed(stage, key)
            and key in self._runners
        )

    def run(self, request: ModelRequest) -> ModelResult:
        key = request.artifact.strip().upper()

        require_frozen_feature_snapshot(
            artifact=key,
            feature_snapshot_id=request.feature_snapshot_id,
            feature_snapshot_sha256=request.feature_snapshot_sha256,
        )

        if not publication_allowed(request.stage, key):
            raise ModelBlocked(
                f"{key} blocked at stage {request.stage.value}"
            )

        runner = self._runners.get(key)

        if runner is None:
            raise ModelBlocked(
                f"no validated model runner for {key}"
            )

        result = runner(request)

        if result.artifact.strip().upper() != key:
            raise ValueError("model artifact mismatch")

        if result.input_snapshot_id != request.input_snapshot_id:
            raise ValueError("model input snapshot mismatch")

        return result


def frozen_result_runner(
    *,
    model_id: str,
    model_version: str,
    artifact: str,
    payload_by_snapshot: Mapping[str, Mapping[str, Any]],
) -> ModelRunner:
    """Replay a frozen prediction without recalculating history."""

    artifact_key = artifact.strip().upper()

    def _run(request: ModelRequest) -> ModelResult:
        payload: Optional[Mapping[str, Any]] = (
            payload_by_snapshot.get(request.input_snapshot_id)
        )

        if payload is None:
            raise ModelBlocked(
                f"no frozen {artifact_key} result for "
                f"{request.input_snapshot_id}"
            )

        return ModelResult(
            model_id=model_id,
            model_version=model_version,
            input_snapshot_id=request.input_snapshot_id,
            artifact=artifact_key,
            payload=payload,
        )

    return _run


class FrozenFeatureSnapshotRequired(ModelBlocked):
    """Raised when a stage update lacks its immutable model-input snapshot."""


def require_frozen_feature_snapshot(
    *,
    artifact: str,
    feature_snapshot_id: str | None,
    feature_snapshot_sha256: str | None,
) -> None:
    """Prevent post-hoc reconstruction of historical model inputs.

    Stage forecasts may only be recalculated from an immutable feature
    snapshot captured before the relevant stage. A preserved probability
    output alone is evidence of the old forecast, not permission to
    reconstruct its hidden inputs after later tournament data exists.
    """
    if artifact not in {
        "NEXT_ROUND_FORECAST",
        "WIN_PROBABILITY",
    }:
        return

    if not feature_snapshot_id:
        raise FrozenFeatureSnapshotRequired(
            "immutable feature snapshot id is required"
        )

    if not feature_snapshot_sha256:
        raise FrozenFeatureSnapshotRequired(
            "immutable feature snapshot sha256 is required"
        )
