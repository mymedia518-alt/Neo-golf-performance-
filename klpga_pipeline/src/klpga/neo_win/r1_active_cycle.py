"""OK Open R1 ACTIVE MODE: the pure decision logic for one 30-minute
collection cycle. Every function here is a plain function over already-
fetched data (or, for the fetch step, over an injected client) so the
full decision tree is unit-testable without any real network access --
the sandbox this was written in has none (confirmed, repeatedly,
against klpga.co.kr all session). scripts/96_ok_open_r1_active_cycle.py
is the thin CLI wrapper that actually calls klpga.co.kr with --live,
run somewhere that has real access.

Two distinct gates, not one, because they answer different questions:

  - assess_r1_snapshot_safety(): "is THIS collected snapshot internally
    trustworthy enough to publish as a live, in-progress R1 view" --
    duplicate/unknown identities are a hard stop, but mid-round players
    (holes_completed < 18) are exactly what an in-progress snapshot
    looks like, not a defect.

  - klpga.neo_win.r1_readiness.assess_r1(): "is R1 AS A WHOLE finished"
    (WAIT while any active player has incomplete holes) -- the R1->R2
    lifecycle transition gate, reused unchanged from the existing
    codebase. Only its R1_COMPLETE outcome triggers the R1-close
    workflow and the active cycle's own stop signal.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from klpga.neo_win.r1_readiness import assess_r1


@dataclass(frozen=True)
class SnapshotSafety:
    safe: bool
    reason: str
    row_count: int


def assess_r1_snapshot_safety(rows: list[dict], expected_player_ids: list[str]) -> SnapshotSafety:
    """A per-cycle gate for "can this specific collected snapshot be
    shown at all" -- distinct from (and looser than) assess_r1's full-
    round-completion gate. Refuses only real corruption signals:
    duplicate identity, an unresolved/unknown player_id, or an empty
    collection (the official page returned nothing usable). A mixed
    field of in-progress and finished players is exactly what a
    legitimate mid-round snapshot looks like and is never refused here."""
    if not rows:
        return SnapshotSafety(False, "empty collection -- official leaderboard returned no rows", 0)
    ids = [str(r.get("player_id") or r.get("player_code") or "") for r in rows]
    if any(not pid for pid in ids):
        return SnapshotSafety(False, "row with no resolvable player identity", len(rows))
    if len(ids) != len(set(ids)):
        return SnapshotSafety(False, "duplicate player identity in official rows", len(rows))
    expected = {str(x) for x in expected_player_ids}
    unknown = set(ids) - expected
    if unknown:
        return SnapshotSafety(False, f"{len(unknown)} row(s) with unresolved/unexpected player identity", len(rows))
    return SnapshotSafety(True, "internally consistent snapshot", len(rows))


@dataclass(frozen=True)
class CycleDecision:
    action: str  # "SKIP_WAIT" | "HARD_STOP" | "PUBLISH" | "PUBLISH_AND_CLOSE"
    reason: str
    retrieved_at: str
    row_count: int = 0
    r1_status: str | None = None  # None | "WAIT" | "R1_COMPLETE"


def decide_cycle(
    rows: list[dict],
    expected_player_ids: list[str],
    *,
    official_page_available: bool,
    tournament_finished: bool,
    now: datetime.datetime | None = None,
) -> CycleDecision:
    """The one function every 30-minute cycle calls after collection.
    Pure: no I/O, no side effects, fully exercised by tests without a
    network. Never infers a stage or completion from `now` -- it is
    used only to stamp the decision's own retrieved_at, never as an
    input to any WAIT/COMPLETE/HARD_STOP judgment."""
    retrieved_at = (now or datetime.datetime.now(datetime.timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if not official_page_available:
        return CycleDecision("SKIP_WAIT", "official R1 leaderboard unavailable this cycle", retrieved_at)
    safety = assess_r1_snapshot_safety(rows, expected_player_ids)
    if not safety.safe:
        return CycleDecision("HARD_STOP", safety.reason, retrieved_at, safety.row_count)
    completion = assess_r1(rows, expected_player_ids, official_page_available=True, expected_holes=18)
    if completion.decision == "HARD_STOP":
        return CycleDecision("HARD_STOP", f"R1 completeness gate: {completion.reason}", retrieved_at, safety.row_count, "HARD_STOP")
    if completion.decision == "R1_COMPLETE":
        return CycleDecision("PUBLISH_AND_CLOSE", "official R1 complete -- publishing final snapshot and closing the active cycle", retrieved_at, safety.row_count, "R1_COMPLETE")
    # WAIT from the completion gate just means "round still in progress"
    # -- the snapshot itself is still safe to publish as a live view.
    return CycleDecision("PUBLISH", "in-progress snapshot passed the safety gate", retrieved_at, safety.row_count, "WAIT")
