"""SHARED ROUND-PAGE SCORE CONTRACT (VISUAL-ARTIFACT-001 remediation,
research/official-tournament-warehouse-v1-20260912): every competitive
round page (R1/R2/R3/FR) must show THAT round's own official strokes
together with its score relative to par, in ONE reusable formatter --
never a cumulative tournament stroke total (that belongs on FINAL
only, see klpga.neo_win.r3_real_page's own module docstring), and never
a second, round-specific reinvention of the same to-par notation.

format_to_par mirrors the exact notation every round page already used
independently (E / +N / -N) -- consolidated here so it is defined once.
format_round_score composes it with the round's real official strokes:
"68 (-4)". Never partially fabricated: EMPTY_MARK unless the round's
real strokes are known; the parenthetical is included only when the
real to-par is ALSO known, otherwise the bare strokes render alone
(never inventing a to-par value the evidence doesn't support)."""
from __future__ import annotations

EMPTY_MARK = "—"


def format_to_par(raw) -> str:
    if raw is None:
        return EMPTY_MARK
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return EMPTY_MARK
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def format_round_score(strokes, score_to_par) -> str:
    """'{strokes} ({to_par})', e.g. '68 (-4)'. Falls back to bare
    strokes ('68') if the to-par side is not real evidence yet, and to
    EMPTY_MARK only when the round's own official strokes are unknown
    (e.g. a WD player)."""
    if strokes is None:
        return EMPTY_MARK
    try:
        strokes_int = int(strokes)
    except (TypeError, ValueError):
        return EMPTY_MARK
    to_par = format_to_par(score_to_par)
    if to_par == EMPTY_MARK:
        return str(strokes_int)
    return f"{strokes_int} ({to_par})"
