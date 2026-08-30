"""Minimal point-in-time freeze gate for the reusable NEO stage lifecycle.

The gate is intentionally pure: callers collect/validate official data and
then provide the immutable artifact state.  It prevents a stage transition
from being treated as publishable when its required checkpoint is absent.
"""
from __future__ import annotations

from dataclasses import dataclass

REQUIRED_PREDICTION = {"PRE": "001", "R1": "002", "R2": "003", "R3": "004"}
STAGE_SEQUENCE = ("PRE", "R1", "R2", "R3", "FINAL")


class StageFreezeGateError(RuntimeError):
    """A stage cannot advance without an immutable, validated checkpoint."""


@dataclass(frozen=True)
class StageTransitionDecision:
    allowed: bool
    stage: str
    required_prediction_id: str | None
    expected_rounds: int
    reason: str


def expected_rounds(total_holes: int) -> int:
    """Return rounds from official tournament format metadata, not UI labels."""
    if total_holes <= 0 or total_holes % 18:
        raise StageFreezeGateError("official total_holes must be a positive multiple of 18")
    return total_holes // 18


def validate_stage_transition(
    stage: str,
    *,
    artifact_frozen: bool,
    total_holes: int,
    official_complete: bool,
    playoff_resolved: bool = True,
    weather_complete: bool = True,
) -> StageTransitionDecision:
    """Validate the minimum freeze contract before publishing ``stage``.

    FINAL is review-only: it requires the preceding R3 prediction artifact
    and official completion, but never creates prediction #005.  Playoff and
    weather gates are explicit so calendar/date alone cannot advance a stage.
    """
    if stage not in STAGE_SEQUENCE:
        raise StageFreezeGateError(f"unknown stage: {stage}")
    rounds = expected_rounds(total_holes)
    required = REQUIRED_PREDICTION.get(stage)
    if not artifact_frozen:
        return StageTransitionDecision(False, stage, required, rounds, "required immutable checkpoint is missing")
    if not weather_complete:
        return StageTransitionDecision(False, stage, required, rounds, "official player/hole completion is unresolved")
    if stage == "FINAL" and not playoff_resolved:
        return StageTransitionDecision(False, stage, None, rounds, "playoff result is unresolved")
    if stage == "FINAL" and not official_complete:
        return StageTransitionDecision(False, stage, None, rounds, "official FINAL result is incomplete")
    return StageTransitionDecision(True, stage, required, rounds, "freeze gate passed")

