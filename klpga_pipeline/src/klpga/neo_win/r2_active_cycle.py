"""R2 HOUSE: pure decision logic for one R2 collection cycle.

Modeled directly on klpga.neo_win.r1_active_cycle.decide_cycle's
proven action vocabulary (SKIP_WAIT / HARD_STOP / PUBLISH /
PUBLISH_AND_CLOSE) and two-gate discipline (a per-cycle SAFETY gate
distinct from the whole-round COMPLETENESS gate), reusing
klpga.neo_win.r2_readiness.assess_r2 for completeness (already
evidence-based: independent expected population, hard-stop on
duplicate/unresolved/absent-without-status, hard-stop on unrecognized
status) rather than re-deriving it.

Every function here is pure (no I/O, no network) -- fully unit-testable
without real klpga.co.kr access, exactly like its R1 analog.
scripts/112_kb_r2_active_cycle.py is the thin CLI wrapper that performs
the actual collection and calls decide_r2_cycle with the result.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from klpga.neo_win.r2_readiness import R2Readiness, assess_r2


@dataclass(frozen=True)
class R2CycleDecision:
    action: str  # "SKIP_WAIT" | "HARD_STOP" | "PUBLISH" | "PUBLISH_AND_CLOSE"
    reason: str
    retrieved_at: str
    readiness: R2Readiness | None = None


def decide_r2_cycle(
    rows: list[dict],
    expected_player_ids,
    *,
    official_page_available: bool,
    suspended: bool = False,
    cut_known: bool = False,
    future_round3_rows: int = 0,
    freeze_exists: bool = False,
    now: datetime.datetime | None = None,
) -> R2CycleDecision:
    """The one function every R2 collection cycle calls after
    collection. `freeze_exists` MUST be the real, current on-disk state
    (klpga.neo_win.r2_freeze.r2_freeze_exists) -- assess_r2 itself
    hard-stops rather than ever overwrite an existing freeze, and this
    wrapper surfaces that as a HARD_STOP action so the operator script
    never even attempts a second write."""
    retrieved_at = (now or datetime.datetime.now(datetime.timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    readiness = assess_r2(
        rows, expected_player_ids,
        official_page_available=official_page_available, suspended=suspended,
        cut_known=cut_known, future_round3_rows=future_round3_rows, freeze_exists=freeze_exists,
    )

    if readiness.decision == "WAIT":
        return R2CycleDecision("SKIP_WAIT", readiness.reason, retrieved_at, readiness)
    if readiness.decision == "HARD_STOP":
        return R2CycleDecision("HARD_STOP", readiness.reason, retrieved_at, readiness)
    # R2_COMPLETE
    return R2CycleDecision(
        "PUBLISH_AND_CLOSE",
        "official R2 and CUT states complete -- freezing, forecasting, and closing the R2 active cycle",
        retrieved_at, readiness,
    )
