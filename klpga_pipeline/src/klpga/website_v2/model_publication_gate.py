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
    # PRODUCT RECOVERY V1: the PRE page's own probability-distribution
    # column headers (scripts/84's _PROBABILITY_COLUMNS) -- a distinct
    # set of literal strings from the R1 live table's markers above,
    # so they need their own entries for this gate to actually catch a
    # PRE-side regression, not just an R1-side one.
    "<th>컷 통과확률</th>",
    "<th>TOP20</th>",
    "<th>TOP10</th>",
    "<th>TOP5</th>",
    "<th>우승확률</th>",
)


class ModelPublicationGateError(Exception):
    """Raised when probability-derived output is found in a public page
    while the LIVE probability model is not validated for publication."""


# REFERENCE_ESTIMATE escape (operator-directed, 2026100003): a third,
# explicit publication state between BLOCKED and VALIDATED for a PRE
# round's own probability candidate -- real stored values shown, never
# as a confirmed/operational number, only together with a disclosure
# that walk-forward validation and probability calibration are still
# in progress. assert_reference_estimate_disclosed() is the one check
# that makes this an honest, gated escape rather than a silent bypass:
# it fails promotion if a later edit keeps the numbers but drops the
# disclosure text from the SAME page. 2026-10-16 (operator instruction):
# shrunk from a full sentence in a notice box to a short label-chip
# badge next to the table title -- the gate's own required substring
# shrunk to match exactly, so the check still enforces the same
# invariant (numbers never shown without SOME visible "not confirmed"
# marker), just against the new, more compact UI.
REFERENCE_ESTIMATE_DISCLOSURE = "참고 예상"


def assert_no_blocked_probability_output(
    html: str, *, model_validated: bool, label: str, reference_estimate: bool = False
) -> None:
    if model_validated or reference_estimate:
        return
    found = [marker for marker in FORBIDDEN_MARKERS_WHEN_BLOCKED if marker in html]
    if found:
        raise ModelPublicationGateError(
            f"{label}: LIVE probability model is not validated for publication but the page still "
            f"contains blocked output: {found} -- refusing to promote."
        )


def assert_reference_estimate_disclosed(html: str, *, label: str) -> None:
    """Companion check for assert_no_blocked_probability_output's
    reference_estimate=True escape: probability-derived numbers may
    only be published under that status together with the exact
    disclosure text, checked in the same promoted HTML, not merely
    assumed from the generator's intent."""
    if REFERENCE_ESTIMATE_DISCLOSURE not in html:
        raise ModelPublicationGateError(
            f"{label}: probability-derived output is published under REFERENCE_ESTIMATE status "
            f"but the required disclosure text ({REFERENCE_ESTIMATE_DISCLOSURE!r}) is missing -- "
            f"refusing to promote."
        )


# CUT RULE CONFIRMATION gate (operator-directed, 2026100003): separate
# from REFERENCE_ESTIMATE above -- a tournament's own official cut
# application/threshold not being confirmed from an official source is
# a DIFFERENT, narrower fact than "the model overall is unvalidated".
# The other 4 probability columns can still show their real disclosed
# estimate; the cut column specifically must never render as a percentage
# (which would read as a confirmed cut condition) until that one fact is
# confirmed -- it shows CUT_RULE_UNCONFIRMED_LABEL instead.
import re as _re  # noqa: E402

CUT_RULE_UNCONFIRMED_LABEL = "공식 기준 확인 중"


def assert_cut_probability_not_published_as_number(
    html: str, *, cut_rule_confirmed: bool, label: str
) -> None:
    if cut_rule_confirmed:
        return
    cells = _re.findall(r"data-label='컷 통과확률'>(.*?)</td>", html, _re.S)
    numeric = [c for c in cells if _re.search(r"\d+(\.\d+)?%", c)]
    if numeric:
        raise ModelPublicationGateError(
            f"{label}: the official cut rule is not confirmed but the 컷 통과확률 column still shows "
            f"a numeric percentage in {len(numeric)} row(s) -- refusing to promote."
        )
