"""R3 HOUSE: pure decision logic for one R3 collection cycle.

Modeled directly on klpga.neo_win.r2_active_cycle.decide_r2_cycle,
reusing klpga.neo_win.r3_readiness.assess_r3 for completeness. Every
function here is pure (no I/O, no network) -- fully unit-testable
without real klpga.co.kr access, exactly like its R2 analog. The R3
operator script is the thin CLI wrapper that performs the actual
collection and calls decide_r3_cycle with the result.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from klpga.neo_win.r3_readiness import R3Readiness, assess_r3


@dataclass(frozen=True)
class R3CycleDecision:
    action: str  # "SKIP_WAIT" | "HARD_STOP" | "PUBLISH_AND_CLOSE"
    reason: str
    retrieved_at: str
    readiness: R3Readiness | None = None


def decide_r3_cycle(
    rows: list[dict],
    expected_player_ids,
    *,
    official_page_available: bool,
    suspended: bool = False,
    future_round4_rows: int = 0,
    freeze_exists: bool = False,
    now: datetime.datetime | None = None,
) -> R3CycleDecision:
    """The one function every R3 collection cycle calls after
    collection. `freeze_exists` MUST be the real, current on-disk state
    (klpga.neo_win.r3_freeze.r3_freeze_exists) -- assess_r3 itself
    hard-stops rather than ever overwrite an existing freeze, and this
    wrapper surfaces that as a HARD_STOP action so the operator script
    never even attempts a second write."""
    retrieved_at = (now or datetime.datetime.now(datetime.timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    readiness = assess_r3(
        rows, expected_player_ids,
        official_page_available=official_page_available, suspended=suspended,
        future_round4_rows=future_round4_rows, freeze_exists=freeze_exists,
    )

    if readiness.decision == "WAIT":
        return R3CycleDecision("SKIP_WAIT", readiness.reason, retrieved_at, readiness)
    if readiness.decision == "HARD_STOP":
        return R3CycleDecision("HARD_STOP", readiness.reason, retrieved_at, readiness)
    # R3_COMPLETE
    return R3CycleDecision(
        "PUBLISH_AND_CLOSE",
        "official R3 state complete -- freezing, forecasting, and closing the R3 active cycle",
        retrieved_at, readiness,
    )
