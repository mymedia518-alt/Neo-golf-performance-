"""Pure functions for turning a raw KLPGA rank string into structured fields.

No estimation happens here: if the source text is ambiguous, unrecognized,
or missing, the corresponding output field is left as None rather than
guessed. These are pure functions specifically so they can be unit tested
without any network access or database.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

_CUT_MARKERS = {"CUT", "MC"}
_WITHDRAWN_MARKERS = {"WD"}
_DISQUALIFIED_MARKERS = {"DQ"}
_NUMERIC_RE = re.compile(r"^T?(\d+)$")


def normalize_rank(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    text = raw.strip().upper()
    return text or None


def parse_rank(raw: Optional[str]) -> Tuple[Optional[int], Optional[bool]]:
    """Parse a raw leaderboard rank string.

    Returns (final_rank_numeric, made_cut):
      - "1", "T5"          -> (1, True), (5, True)
      - "CUT" / "MC"        -> (None, False)
      - "WD" / "DQ"          -> (None, None)  -- did not finish; whether the
                                cut was made is not knowable from rank alone
      - anything else/None   -> (None, None)
    """
    text = normalize_rank(raw)
    if text is None:
        return None, None
    if text in _CUT_MARKERS:
        return None, False
    if text in _WITHDRAWN_MARKERS or text in _DISQUALIFIED_MARKERS:
        return None, None
    match = _NUMERIC_RE.match(text)
    if match:
        return int(match.group(1)), True
    return None, None


def placement_flags(final_rank_numeric: Optional[int]) -> Tuple[bool, bool, bool, bool]:
    """Returns (win, top5, top10, top20). All False when rank is unknown."""
    if final_rank_numeric is None:
        return False, False, False, False
    return (
        final_rank_numeric == 1,
        final_rank_numeric <= 5,
        final_rank_numeric <= 10,
        final_rank_numeric <= 20,
    )


def classify_model_scope(tournament_type: Optional[str], status: Optional[str]) -> Optional[bool]:
    """Whether a tournament belongs in the regular-tour model dataset.

    Returns None when there isn't enough information to decide, rather
    than guessing True or False.
    """
    if tournament_type is None or status is None:
        return None
    is_regular = "정규" in tournament_type
    is_completed = ("완료" in status) or ("종료" in status)
    return bool(is_regular and is_completed)
