"""BETA #001 R1 -> R2 evaluation pipeline, Section B: reconciles the
frozen R1 field (klpga.neo_win.r1_frozen_snapshot.PlayerR1Frozen)
against the REAL official Round-2 leaderboard.

Reuses `klpga.neo_win.round_reconciliation.normalize_official_round` /
`NormalizedPlayer` verbatim — the SAME already-validated official-round
normalization every other round transition in this project uses
(reusing `klpga.collectors.aggregate.merge_player_rows` underneath) —
rather than re-deriving official-leaderboard parsing here. The
`official_r2` dict this module consumes IS that function's own return
value for round_number=2; collecting the real official R2 leaderboard
itself is the caller's job (klpga.collectors.leaderboard.
fetch_round_leaderboard), never this module's.

======================================================================
STATUS -> CUT OUTCOME MAPPING — real, observed evidence only
======================================================================
The official round-2 leaderboard's own `data-rank` text is the primary
source of truth (klpga.parsers.leaderboard_parser.parse_rank already
extracts this into NormalizedPlayer.status):
  status == "CUT"                              -> CUT_OUTCOME_MISSED
  status == "WD"                               -> CUT_OUTCOME_WD
  status == "DQ"                               -> CUT_OUTCOME_DQ
  status == "INCOMPLETE" (the real 999 sentinel) -> CUT_OUTCOME_UNRESOLVED
  status is None AND a real round_score exists  -> CUT_OUTCOME_MADE
No other mapping is ever applied to a player who DOES have a Round 2
row; an unrecognized status string on that row is also reported as
CUT_OUTCOME_UNRESOLVED rather than crashing, since a new, previously-
unseen status text on the real site is a real possibility this
evaluation must survive (SKIP + LOG, never HARD STOP, per this
project's own local-failure discipline).

======================================================================
A PLAYER WITH NO ROUND 2 ROW AT ALL — evidence is NOT yet conclusive
======================================================================
A first hypothesis (since reverted) treated "present with a real score
in official Round 1, but entirely absent from the official Round 2
fetch" as sufficient evidence of a missed cut on its own. A real
Windows run disproved this being a *complete* explanation: after that
rule was applied, `cut` (missed-cut count) stayed at 0 even though the
evaluated field was ~92% "made cut" — implausibly high for a real
36-hole cut — meaning genuine cut-line dropouts were NOT reliably
producing "R1-present, R2-absent" at all. The real KLPGA round=2
endpoint's actual behavior for an eliminated player (a normal-looking
row with a lower rank? the INCOMPLETE/999 sentinel? something else?)
has not been directly confirmed by inspecting the live site, so this
module no longer infers CUT_OUTCOME_MISSED from R1-presence/R2-absence
alone — that would be exactly the kind of unproven, rank-adjacent
guess this project's identity/evidence discipline forbids.

So when a player has NO Round 2 row (`o is None`), this module
consults their OFFICIAL Round 1 row (`r1`, optional, backward
compatible — omitting it preserves the original UNRESOLVED result)
ONLY for explicit, already-proven evidence:
  r1 shows an explicit WD/DQ status -> that status (a real, direct
    site signal, wherever it appears — never guessed).
  Anything else (including "r1 shows a real round_score but Round 2
    is simply absent") -> CUT_OUTCOME_UNRESOLVED. This is deliberately
    conservative: every such player is still surfaced via
    `missing_player_diagnostics` (see reconcile_r1_to_r2) with their
    real official_r1_status/official_r1_round_score, so a human with
    real site access can determine the actual missed-cut signal by
    inspecting one of these players directly — once that's confirmed,
    the real rule can be added here with real evidence behind it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD,
)
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.round_reconciliation import NormalizedPlayer

_KNOWN_STATUS_OUTCOMES = {"CUT": CUT_OUTCOME_MISSED, "WD": CUT_OUTCOME_WD, "DQ": CUT_OUTCOME_DQ}


def outcome_from_official_r2(o: Optional[NormalizedPlayer], r1: Optional[NormalizedPlayer] = None) -> str:
    """See module docstring's STATUS -> CUT OUTCOME MAPPING and "A
    PLAYER WITH NO ROUND 2 ROW AT ALL" sections. `o` is None when this
    player has no row at all in the official R2 leaderboard fetch;
    `r1` (optional, default None) is that same player's official Round
    1 row, consulted ONLY when `o` is None."""
    if o is not None:
        if o.status in _KNOWN_STATUS_OUTCOMES:
            return _KNOWN_STATUS_OUTCOMES[o.status]
        if o.status is None and o.round_score is not None:
            return CUT_OUTCOME_MADE
        return CUT_OUTCOME_UNRESOLVED  # a Round 2 row exists but is ambiguous (e.g. INCOMPLETE/999) — never guessed further
    if r1 is not None and r1.status in _KNOWN_STATUS_OUTCOMES:
        return _KNOWN_STATUS_OUTCOMES[r1.status]  # a real, direct WD/DQ signal — never guessed
    # r1 present with a real round_score but no explicit status, and o is
    # entirely absent: NOT treated as CUT_OUTCOME_MISSED — see module
    # docstring's "A PLAYER WITH NO ROUND 2 ROW AT ALL" section. This was
    # tried and disproven against a real Windows run (missed-cut count
    # stayed 0 for an implausibly-high-made-cut-rate field), so
    # presence/absence alone is not treated as sufficient evidence.
    return CUT_OUTCOME_UNRESOLVED


@dataclass(frozen=True)
class PlayerR2Reconciled:
    player_code: str
    player_name: str
    r2_position: Optional[int]
    r2_score_to_par: Optional[int]
    r2_outcome: str
    """One of klpga.neo_win.cut_evaluation.CUT_OUTCOME_*."""
    in_frozen_r1: bool
    in_official_r2: bool
    in_official_r1: bool = False
    official_r1_status: Optional[str] = None
    official_r1_round_score: Optional[int] = None


def reconcile_r1_to_r2(
    frozen_r1: list[PlayerR1Frozen], official_r2: dict[str, NormalizedPlayer],
    official_r1: Optional[dict[str, NormalizedPlayer]] = None,
) -> tuple[list[PlayerR2Reconciled], dict]:
    """Pure function — no I/O, no fabrication. `player_code` is the
    ONLY join key (project-wide identity rule); a code present on only
    one side still appears, with the other side's fields None/False,
    never dropped and never merged by name.

    `official_r1` (optional, default None — fully backward compatible)
    is the official Round 1 leaderboard, normalized the same way as
    `official_r2`; see module docstring's "A PLAYER WITH NO ROUND 2
    ROW AT ALL" section for why this is needed."""
    official_r1 = official_r1 or {}
    frozen_by_code = {r.player_code: r for r in frozen_r1}
    all_codes = set(frozen_by_code) | set(official_r2)

    rows: list[PlayerR2Reconciled] = []
    for code in sorted(all_codes):
        f = frozen_by_code.get(code)
        o = official_r2.get(code)
        r1o = official_r1.get(code)
        outcome = outcome_from_official_r2(o, r1o)
        name = (o.player_name if o else None) or (f.player_name if f else None) or ""
        rows.append(
            PlayerR2Reconciled(
                player_code=code,
                player_name=name,
                r2_position=o.position if o else None,
                r2_score_to_par=o.score_to_par if o else None,
                r2_outcome=outcome,
                in_frozen_r1=f is not None,
                in_official_r2=o is not None,
                in_official_r1=r1o is not None,
                official_r1_status=r1o.status if r1o else None,
                official_r1_round_score=r1o.round_score if r1o else None,
            )
        )

    only_in_frozen_r1 = sorted(set(frozen_by_code) - set(official_r2))
    only_in_official_r2 = sorted(set(official_r2) - set(frozen_by_code))

    missing_rows = [r for r in rows if r.r2_outcome == CUT_OUTCOME_UNRESOLVED]
    missing_player_diagnostics = [
        {
            "player_code": r.player_code,
            "player_name": r.player_name,
            "in_frozen_r1": r.in_frozen_r1,
            "in_official_r1": r.in_official_r1,
            "official_r1_status": r.official_r1_status,
            "official_r1_round_score": r.official_r1_round_score,
            "in_official_r2": r.in_official_r2,
        }
        for r in missing_rows
    ]
    """Real, per-player forensic detail for every UNRESOLVED player —
    exactly why each one is unresolved (absent from official_r1 too?
    present in official_r1 but with no real round_score? found under a
    player_code that simply never matched anything?) is visible here,
    rather than requiring a second investigation pass to discover."""

    summary = {
        "r1_players": len(frozen_by_code),
        "r2_players": len(official_r2),
        "new_wd": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_WD),
        "new_dq": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_DQ),
        "cut": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_MISSED),
        "made_cut": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_MADE),
        "missing": len(missing_rows),
        "missing_player_diagnostics": missing_player_diagnostics,
        "unmatched_player_codes": {
            "only_in_frozen_r1": only_in_frozen_r1,
            "only_in_official_r2": only_in_official_r2,
        },
    }
    return rows, summary
