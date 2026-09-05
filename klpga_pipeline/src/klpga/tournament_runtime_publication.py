"""Bridge validated runtime snapshots into factual publication."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from klpga.tournament_official_ingest import OfficialRoundSnapshot
from klpga.tournament_publication_runner import (
    PublicationRunRequest,
    PublicationRunResult,
    run_factual_publication,
)


class RuntimePublicationBlocked(RuntimeError):
    pass


class RuntimeDecisionLike(Protocol):
    should_publish_factual: bool
    should_publish_model: bool


@dataclass(frozen=True)
class RuntimePublicationRequest:
    tournament_name: str
    game_code: str
    round_number: int
    frozen_root: Path
    candidate_root: Path
    target_path: Path
    promote: bool = False


def publish_runtime_snapshot(
    request: RuntimePublicationRequest,
    snapshot: OfficialRoundSnapshot,
    decision: RuntimeDecisionLike,
    *,
    collected_at: str | None = None,
) -> PublicationRunResult:

    if not decision.should_publish_factual:
        raise RuntimePublicationBlocked(
            "runtime decision blocks factual publication"
        )

    if decision.should_publish_model:
        raise RuntimePublicationBlocked(
            "model publication must not pass factual bridge"
        )

    if snapshot.game_code != request.game_code:
        raise RuntimePublicationBlocked(
            "snapshot/request game_code mismatch"
        )

    if snapshot.round_number != request.round_number:
        raise RuntimePublicationBlocked(
            "snapshot/request round mismatch"
        )

    return run_factual_publication(
        PublicationRunRequest(
            tournament_name=request.tournament_name,
            game_code=request.game_code,
            round_number=request.round_number,
            frozen_root=request.frozen_root,
            candidate_root=request.candidate_root,
            target_path=request.target_path,
            promote=request.promote,
        ),
        snapshot,
        collected_at=collected_at,
    )
