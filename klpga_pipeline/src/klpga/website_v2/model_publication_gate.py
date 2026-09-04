"""P0 MODEL SAFETY PATCH -- LIVE PROBABILITY PUBLICATION BLOCK.

A hard, promotion-time gate proving no output derived from the
blocked R1 live probability simulation (klpga.neo_win.
r1_live_probability.LIVE_PROBABILITY_MODEL_STATUS) can reach
production. Defense in depth alongside the generator-level omission in
scripts/84_build_ok_open_pre_website_candidate.py -- that script
already never emits these markers while blocked, but this gate checks
the actual PROMOTED HTML itself, not merely the generator's intent, so
a future edit that reintroduces one of these columns/sections without
first flipping the model status to "VALIDATED" fails promotion instead
of silently shipping."""
from __future__ import annotations

FORBIDDEN_MARKERS_WHEN_BLOCKED = (
    "<th>Cut%</th>",
    "<th>Top20%</th>",
    "<th>Top10%</th>",
    "<th>Top5%</th>",
    "<th>Win%</th>",
    "<th>PRE 대비 Win Δ</th>",
    "<h2>NEO Movers",
    "NEO 예상 컷 (분포)",
)


class ModelPublicationGateError(Exception):
    """Raised when probability-derived output is found in a public page
    while the LIVE probability model is not validated for publication."""


def assert_no_blocked_probability_output(html: str, *, model_validated: bool, label: str) -> None:
    if model_validated:
        return
    found = [marker for marker in FORBIDDEN_MARKERS_WHEN_BLOCKED if marker in html]
    if found:
        raise ModelPublicationGateError(
            f"{label}: LIVE probability model is not validated for publication but the page still "
            f"contains blocked output: {found} -- refusing to promote."
        )
