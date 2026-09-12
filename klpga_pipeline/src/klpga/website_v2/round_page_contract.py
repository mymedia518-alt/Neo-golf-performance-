"""NEO_EXECUTABLE_CONTRACT_V1 -- PUBLIC_ROUND_PAGE_001.

A round page (R1/R2/R3/FR) MAY display a cumulative "합계" column.
Correct invariant: 합계, when present, means the cumulative score
RELATIVE TO PAR through that round (e.g. "-5", "E", "+2") -- a raw
cumulative stroke count (e.g. "211") must never be substituted for it.

This is a SEMANTIC contract, not a column-name contract: the same
defect (a raw stroke total silently standing in for a to-par value)
could reappear under a different column name or a data-source change,
so this module inspects the actual DISPLAYED VALUE, not merely
whether a column called "합계" exists or is absent.

HARD STOP code: ROUND_PAGE_CUMULATIVE_SCORE_SEMANTICS_INVALID.
"""
from __future__ import annotations

import re

EMPTY_MARK = "—"

PUBLIC_ROUND_PAGE_001 = (
    "A round page's cumulative (합계) column, when present, must display "
    "the cumulative score relative to par through that round -- never a "
    "raw cumulative stroke count. R1/R2/R3/FR may all show 합계; only its "
    "VALUE is constrained. Raw cumulative totals belong on FINAL."
)

# A real to-par notation is always "E" (even) or a signed 1-2 digit
# integer -- no realistic cumulative relative-to-par score through a
# single golf round or a handful of rounds falls outside +/-99, and a
# genuine to-par value is never unsigned (a raw stroke count, by
# contrast, is always unsigned and typically 3+ digits once summed
# across rounds).
_VALID_TO_PAR_DISPLAY = re.compile(r"^(E|[+-]\d{1,2})$")


class RoundPageContractError(RuntimeError):
    """PUBLIC_ROUND_PAGE_001 violated -- HARD STOP. The caller must
    never write/publish this HTML."""


def assert_cumulative_score_is_relative_to_par(display_value: str, *, label: str = "합계", player: str | None = None) -> None:
    """Raises RoundPageContractError, message-tagged
    ROUND_PAGE_CUMULATIVE_SCORE_SEMANTICS_INVALID, if `display_value`
    is not a real to-par notation and is not EMPTY_MARK (a genuine
    "no data yet" state, never a contract violation)."""
    if display_value == EMPTY_MARK:
        return
    if _VALID_TO_PAR_DISPLAY.match(display_value):
        return
    who = f" for {player}" if player else ""
    raise RoundPageContractError(
        f"ROUND_PAGE_CUMULATIVE_SCORE_SEMANTICS_INVALID: {label}{who} displayed "
        f"{display_value!r}, which is not a valid to-par notation (E / +N / -N) -- "
        f"a raw cumulative stroke count appears to have been substituted. {PUBLIC_ROUND_PAGE_001}"
    )
