"""Unattended generic NEO Tournament Engine runtime.

This module is tournament-independent.

Responsibilities:
- read validated tournament state from JSON
- fetch official data only for LIVE stages
- classify whether the current round is still live or complete
- preserve factual-only publication while model readiness is false
- never infer CUT from calendar/time
- stop at the CUT confirmation gate after R2 completion
- never invoke tournament-specific legacy scripts
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from klpga.tournament_official_ingest import (
    OfficialRoundSnapshot,
    fetch_official_round,
)
from klpga.tournament_runtime_publication import (
    RuntimePublicationRequest,
    publish_runtime_snapshot,
)


TERMINAL_PLAYER_STATUSES = frozenset({
    "WD",
    "DQ",
    "DNS",
})


class RuntimeBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeState:
    game_code: str
    final_round_number: int
    current_round_number: int
    validated_stage: str
    model_ready: bool = False

    def __post_init__(self):
        if not self.game_code.strip():
            raise ValueError("game_code required")

        if self.final_round_number < 2:
            raise ValueError(
                "final_round_number must be >= 2"
            )

        if not (
            1 <= self.current_round_number
            <= self.final_round_number
        ):
            raise ValueError(
                "current_round_number outside tournament"
            )


@dataclass(frozen=True)
class RuntimeDecision:
    observed_stage: str
    publication_mode: str
    next_gate: str
    should_publish_factual: bool
    should_publish_model: bool
    should_disable_cycle: bool
    unfinished_count: int


def load_state(path: Path) -> RuntimeState:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    return RuntimeState(
        game_code=str(payload["game_code"]),
        final_round_number=int(
            payload["final_round_number"]
        ),
        current_round_number=int(
            payload["current_round_number"]
        ),
        validated_stage=str(
            payload["validated_stage"]
        ),
        model_ready=bool(
            payload.get("model_ready", False)
        ),
    )


def player_is_unfinished(player) -> bool:
    status = str(
        player.status or ""
    ).upper()

    if status in TERMINAL_PLAYER_STATUSES:
        return False

    if status == "INCOMPLETE":
        return True

    holes = player.holes_completed

    if holes is None:
        return True

    return holes < 18


def classify_live_snapshot(
    state: RuntimeState,
    snapshot: OfficialRoundSnapshot,
) -> RuntimeDecision:

    if snapshot.game_code != state.game_code:
        raise RuntimeBlocked(
            "official snapshot game_code mismatch"
        )

    if (
        snapshot.round_number
        != state.current_round_number
    ):
        raise RuntimeBlocked(
            "official snapshot round mismatch"
        )

    if snapshot.row_count <= 0:
        raise RuntimeBlocked(
            "zero-row official snapshot"
        )

    unfinished = [
        p
        for p in snapshot.players
        if player_is_unfinished(p)
    ]

    if unfinished:
        return RuntimeDecision(
            observed_stage=state.validated_stage,
            publication_mode="FACTUAL_LIVE",
            next_gate="WAIT",
            should_publish_factual=True,
            should_publish_model=False,
            should_disable_cycle=False,
            unfinished_count=len(unfinished),
        )

    # Round is observationally complete.
    #
    # R2 completion does NOT imply CUT_CONFIRMED.
    # CUT remains an independent official validation gate.
    if state.current_round_number == 2:
        return RuntimeDecision(
            observed_stage="R2_COMPLETE",
            publication_mode="FACTUAL_COMPLETE",
            next_gate="CUT_CONFIRMATION",
            should_publish_factual=True,
            should_publish_model=False,
            should_disable_cycle=True,
            unfinished_count=0,
        )

    if (
        state.current_round_number
        == state.final_round_number
    ):
        return RuntimeDecision(
            observed_stage="FINAL_COMPLETE",
            publication_mode="FACTUAL_COMPLETE",
            next_gate="FINAL_VALIDATION",
            should_publish_factual=True,
            should_publish_model=False,
            should_disable_cycle=True,
            unfinished_count=0,
        )

    return RuntimeDecision(
        observed_stage=(
            f"ROUND_{state.current_round_number}_COMPLETE"
        ),
        publication_mode="FACTUAL_COMPLETE",
        next_gate="NEXT_STAGE_VALIDATION",
        should_publish_factual=True,
        should_publish_model=False,
        should_disable_cycle=True,
        unfinished_count=0,
    )


def run_once(
    state: RuntimeState,
    *,
    cache_dir: Path,
    fetcher: Callable[..., OfficialRoundSnapshot]
        = fetch_official_round,
) -> tuple[OfficialRoundSnapshot, RuntimeDecision]:

    stage = state.validated_stage.upper()

    live_stages = {
        "R1_LIVE",
        "R2_LIVE",
        "NEXT_ROUND_LIVE",
        "R3_LIVE",
        "FINAL_LIVE",
    }

    if stage not in live_stages:
        raise RuntimeBlocked(
            "unattended runtime accepts LIVE stages only; "
            f"got {state.validated_stage}"
        )

    snapshot = fetcher(
        game_code=state.game_code,
        round_number=state.current_round_number,
        cache_dir=cache_dir,
    )

    decision = classify_live_snapshot(
        state,
        snapshot,
    )

    return snapshot, decision



def run_publication_once(
    state: RuntimeState,
    *,
    tournament_name: str,
    cache_dir: Path,
    frozen_root: Path,
    candidate_root: Path,
    target_path: Path,
    promote: bool = False,
    fetcher: Callable[..., OfficialRoundSnapshot]
        = fetch_official_round,
):
    """Fetch, validate and publish the exact same official snapshot.

    Promotion is explicit and defaults to False.
    Model publication is blocked by the factual bridge.
    """
    snapshot, decision = run_once(
        state,
        cache_dir=cache_dir,
        fetcher=fetcher,
    )

    if not decision.should_publish_factual:
        raise RuntimeBlocked(
            "runtime decision blocks factual publication"
        )

    publication = publish_runtime_snapshot(
        RuntimePublicationRequest(
            tournament_name=tournament_name,
            game_code=state.game_code,
            round_number=state.current_round_number,
            frozen_root=frozen_root,
            candidate_root=candidate_root,
            target_path=target_path,
            promote=promote,
        ),
        snapshot,
        decision,
    )

    return snapshot, decision, publication

def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--state",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--cache-dir",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    state = load_state(args.state)

    snapshot, decision = run_once(
        state,
        cache_dir=args.cache_dir,
    )

    result = {
        "game_code": state.game_code,
        "round_number": state.current_round_number,
        "official_rows": snapshot.row_count,
        "observed_stage": decision.observed_stage,
        "publication_mode": decision.publication_mode,
        "next_gate": decision.next_gate,
        "publish_factual":
            decision.should_publish_factual,
        "publish_model":
            decision.should_publish_model,
        "disable_cycle":
            decision.should_disable_cycle,
        "unfinished_count":
            decision.unfinished_count,
    }

    print(json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
    ))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
