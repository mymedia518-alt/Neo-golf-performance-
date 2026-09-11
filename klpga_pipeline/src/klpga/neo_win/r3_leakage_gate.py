"""R3 HOUSE: hard runtime future-leakage gate.

Allowed inputs to anything downstream of the R3 freeze: PRE frozen
information, R1 information available at R1 close, R2 information
available at R2 close, R3 information available at R3 close. Forbidden:
R4, FINAL, post-event statistics/records, or any future K-Ranking/
player-stat update. Mirrors klpga.neo_win.r2_leakage_gate exactly, one
stage later.
"""
from __future__ import annotations

from klpga.evidence.manifest import FORBIDDEN_RESULT_FIELDS

ALLOWED_STAGES = frozenset({"pre", "r1", "r2", "r3"})
FORBIDDEN_STAGES = frozenset({"r4", "final", "postmortem", "post_event"})


class FutureLeakageError(RuntimeError):
    """Raised whenever code downstream of the R3 freeze is about to
    consume a stage/field that could only be known after R3 -- always a
    hard stop, never a soft warning."""


def assert_stage_allowed(stage: str, *, context: str = "") -> None:
    normalized = stage.strip().lower()
    if normalized in FORBIDDEN_STAGES or normalized not in ALLOWED_STAGES:
        raise FutureLeakageError(
            f"FUTURE LEAKAGE: stage {stage!r} is not allowed as an R3-house input "
            f"(allowed: {sorted(ALLOWED_STAGES)}){f' [{context}]' if context else ''}"
        )


def assert_artifact_type_allowed(artifact_type: str, *, context: str = "") -> None:
    """artifact_type strings in this codebase are free-form
    (TournamentContext.artifact_path), so this checks for any forbidden
    stage token appearing in the name (e.g. "r4_live_snapshot",
    "final_result", "post_r4_forecast") rather than requiring an exact
    stage match."""
    lowered = artifact_type.strip().lower()
    for forbidden in FORBIDDEN_STAGES:
        if forbidden in lowered:
            raise FutureLeakageError(
                f"FUTURE LEAKAGE: artifact_type {artifact_type!r} references forbidden stage "
                f"{forbidden!r}{f' [{context}]' if context else ''}"
            )


def assert_no_forbidden_result_fields(payload: dict, *, context: str = "") -> None:
    found = sorted(FORBIDDEN_RESULT_FIELDS & set(payload.keys()))
    if found:
        raise FutureLeakageError(
            f"FUTURE LEAKAGE: forbidden result field(s) {found} present in payload"
            f"{f' [{context}]' if context else ''} -- post-event data must never reach the R3 house"
        )
