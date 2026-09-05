"""Immutable model-feature freeze for NEO Tournament Engine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from klpga.neo_win.archive import (
    NeoWinPredictionSnapshot,
    archive_paths,
    snapshot_to_json_text,
    write_neo_win_snapshot_atomic,
)


@dataclass(frozen=True)
class FrozenFeatureRef:
    snapshot_id: str
    sha256: str
    path: str
    game_code: str
    stage: str
    model_id: str
    model_version: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze_pre_model_features(
    snapshot: NeoWinPredictionSnapshot,
    *,
    predictions_root: Path,
) -> FrozenFeatureRef:
    """Freeze the exact PRE model inputs used by the prediction.

    The existing NeoWinPredictionSnapshot is the feature snapshot:
    each entrant already contains the historical mean, recent form,
    consistency spread and the generated probability.

    Existing archives are never overwritten.
    """
    if not snapshot.predictions:
        raise ValueError("PRE feature snapshot has no entrants")

    if snapshot.entrants_predicted != len(snapshot.predictions):
        raise ValueError(
            "entrants_predicted does not match frozen entrant rows"
        )

    if snapshot.game_code == "":
        raise ValueError("game_code is required")

    required_feature_names = {
        "prior_avg_round_score_to_par",
        "prior_recent_form_10",
    }

    if not required_feature_names.issubset(
        set(snapshot.model_features)
    ):
        raise ValueError(
            "PRE snapshot is missing required model feature declaration"
        )

    json_path, _ = write_neo_win_snapshot_atomic(
        snapshot,
        predictions_root,
    )

    digest = _sha256(json_path)

    return FrozenFeatureRef(
        snapshot_id=(
            f"PRE:{snapshot.game_code}:"
            f"{snapshot.prediction_id}"
        ),
        sha256=digest,
        path=str(json_path),
        game_code=snapshot.game_code,
        stage="PRE",
        model_id=snapshot.model_id,
        model_version=snapshot.model_version,
    )


def verify_frozen_pre_features(
    snapshot: NeoWinPredictionSnapshot,
    *,
    predictions_root: Path,
    expected_sha256: str,
) -> FrozenFeatureRef:
    """Verify an existing immutable PRE archive without recalculation."""
    json_path, _ = archive_paths(
        predictions_root,
        snapshot.prediction_id,
        snapshot.game_code,
        snapshot.cutoff_date,
    )

    if not json_path.exists():
        raise FileNotFoundError(
            f"frozen PRE feature snapshot not found: {json_path}"
        )

    actual = _sha256(json_path)

    if actual != expected_sha256:
        raise ValueError(
            "frozen PRE feature snapshot sha256 mismatch"
        )

    # Also ensure the caller's in-memory snapshot is exactly the
    # canonical JSON representation expected for this archive.
    expected_bytes = snapshot_to_json_text(snapshot).encode("utf-8")

    if hashlib.sha256(expected_bytes).hexdigest() != actual:
        raise ValueError(
            "in-memory PRE snapshot differs from frozen archive"
        )

    return FrozenFeatureRef(
        snapshot_id=(
            f"PRE:{snapshot.game_code}:"
            f"{snapshot.prediction_id}"
        ),
        sha256=actual,
        path=str(json_path),
        game_code=snapshot.game_code,
        stage="PRE",
        model_id=snapshot.model_id,
        model_version=snapshot.model_version,
    )
