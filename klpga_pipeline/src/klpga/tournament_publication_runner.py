"""Generic end-to-end factual publication runner.

Official validated snapshot
    -> immutable freeze
    -> factual publication candidate
    -> HTML candidate
    -> pre-publish validation
    -> optional atomic promotion

Promotion is explicit. Dry-run is the default architectural contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from klpga.tournament_atomic_promotion import (
    PromotionResult,
    atomic_promote,
    validate_candidate_for_promotion,
)
from klpga.tournament_factual_publication import (
    FrozenFactualRef,
    build_publication_candidate,
    freeze_factual_snapshot,
    verify_factual_snapshot,
)
from klpga.tournament_factual_site import (
    build_factual_site_candidate,
    candidate_sha256,
)
from klpga.tournament_official_ingest import OfficialRoundSnapshot


class PublicationRunBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicationRunRequest:
    tournament_name: str
    game_code: str
    round_number: int
    frozen_root: Path
    candidate_root: Path
    target_path: Path
    promote: bool = False

    def __post_init__(self):
        if not self.tournament_name.strip():
            raise ValueError("tournament_name required")
        if not self.game_code.strip():
            raise ValueError("game_code required")
        if self.round_number < 1:
            raise ValueError("round_number must be >= 1")


@dataclass(frozen=True)
class PublicationRunResult:
    game_code: str
    round_number: int
    factual_ref: FrozenFactualRef
    candidate_path: Path
    candidate_sha256: str
    promoted: bool
    promotion: PromotionResult | None


def run_factual_publication(
    request: PublicationRunRequest,
    snapshot: OfficialRoundSnapshot,
    *,
    collected_at: str | None = None,
) -> PublicationRunResult:
    if snapshot.game_code != request.game_code:
        raise PublicationRunBlocked(
            "snapshot/request game_code mismatch"
        )

    if snapshot.round_number != request.round_number:
        raise PublicationRunBlocked(
            "snapshot/request round mismatch"
        )

    if snapshot.row_count <= 0:
        raise PublicationRunBlocked(
            "zero-row snapshot cannot publish"
        )

    ref = freeze_factual_snapshot(
        snapshot,
        output_root=request.frozen_root,
        collected_at=collected_at,
    )

    payload = verify_factual_snapshot(ref)

    if payload["game_code"] != request.game_code:
        raise PublicationRunBlocked(
            "frozen game_code mismatch"
        )

    if payload["round_number"] != request.round_number:
        raise PublicationRunBlocked(
            "frozen round mismatch"
        )

    if payload["row_count"] != snapshot.row_count:
        raise PublicationRunBlocked(
            "frozen row_count mismatch"
        )

    candidate = build_publication_candidate(ref)

    candidate_path = build_factual_site_candidate(
        tournament_name=request.tournament_name,
        candidate=candidate,
        ref=ref,
        output_root=request.candidate_root,
    )

    html_sha = candidate_sha256(candidate_path)

    validate_candidate_for_promotion(
        candidate_path,
        expected_game_code=request.game_code,
        expected_round_number=request.round_number,
        expected_factual_sha256=ref.sha256,
    )

    if not request.promote:
        return PublicationRunResult(
            game_code=request.game_code,
            round_number=request.round_number,
            factual_ref=ref,
            candidate_path=candidate_path,
            candidate_sha256=html_sha,
            promoted=False,
            promotion=None,
        )

    promotion = atomic_promote(
        candidate_path,
        request.target_path,
        expected_game_code=request.game_code,
        expected_round_number=request.round_number,
        expected_factual_sha256=ref.sha256,
    )

    if promotion.after_sha256 != html_sha:
        raise PublicationRunBlocked(
            "promoted HTML SHA mismatch"
        )

    return PublicationRunResult(
        game_code=request.game_code,
        round_number=request.round_number,
        factual_ref=ref,
        candidate_path=candidate_path,
        candidate_sha256=html_sha,
        promoted=True,
        promotion=promotion,
    )
