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
The official round-2 leaderboard's own `data-rank` text is the single
source of truth (klpga.parsers.leaderboard_parser.parse_rank already
extracts this into NormalizedPlayer.status):
  status == "CUT"                              -> CUT_OUTCOME_MISSED
  status == "WD"                               -> CUT_OUTCOME_WD
  status == "DQ"                               -> CUT_OUTCOME_DQ
  status == "INCOMPLETE" (the real 999 sentinel) -> CUT_OUTCOME_UNRESOLVED
  status is None AND a real round_score exists  -> CUT_OUTCOME_MADE
  status is None AND no round_score at all      -> CUT_OUTCOME_UNRESOLVED
    (present in the frozen R1 field but genuinely no R2 row yet —
    never guessed as WD/DQ/CUT; docs/SITE_STRUCTURE_TODO.md's own
    documented finding is that the site gives no way to distinguish an
    unresolved 999/INCOMPLETE row from a real WD/DQ, so this module
    never tries to.)
No other mapping is ever applied; an unrecognized status string is
also reported as CUT_OUTCOME_UNRESOLVED rather than crashing, since a
new, previously-unseen status text on the real site is a real
possibility this evaluation must survive (SKIP + LOG, never HARD STOP,
per this project's own local-failure discipline).
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


def outcome_from_official_r2(o: Optional[NormalizedPlayer]) -> str:
    """See module docstring's STATUS -> CUT OUTCOME MAPPING. `o` is
    None when this player has no row at all in the official R2
    leaderboard fetch."""
    if o is None:
        return CUT_OUTCOME_UNRESOLVED
    if o.status in _KNOWN_STATUS_OUTCOMES:
        return _KNOWN_STATUS_OUTCOMES[o.status]
    if o.status is None and o.round_score is not None:
        return CUT_OUTCOME_MADE
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


def reconcile_r1_to_r2(
    frozen_r1: list[PlayerR1Frozen], official_r2: dict[str, NormalizedPlayer]
) -> tuple[list[PlayerR2Reconciled], dict]:
    """Pure function — no I/O, no fabrication. `player_code` is the
    ONLY join key (project-wide identity rule); a code present on only
    one side still appears, with the other side's fields None/False,
    never dropped and never merged by name."""
    frozen_by_code = {r.player_code: r for r in frozen_r1}
    all_codes = set(frozen_by_code) | set(official_r2)

    rows: list[PlayerR2Reconciled] = []
    for code in sorted(all_codes):
        f = frozen_by_code.get(code)
        o = official_r2.get(code)
        outcome = outcome_from_official_r2(o)
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
            )
        )

    only_in_frozen_r1 = sorted(set(frozen_by_code) - set(official_r2))
    only_in_official_r2 = sorted(set(official_r2) - set(frozen_by_code))

    summary = {
        "r1_players": len(frozen_by_code),
        "r2_players": len(official_r2),
        "new_wd": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_WD),
        "new_dq": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_DQ),
        "cut": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_MISSED),
        "made_cut": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_MADE),
        "missing": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_UNRESOLVED),
        "unmatched_player_codes": {
            "only_in_frozen_r1": only_in_frozen_r1,
            "only_in_official_r2": only_in_official_r2,
        },
    }
    return rows, summary
