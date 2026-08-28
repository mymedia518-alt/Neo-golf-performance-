"""BETA #001 R1 -> R2 ground-truth CUT-status diagnostic (double-
verification phase). Builds a per-player comparison table from real,
already-collected official Round 1 / Round 2 leaderboard rows plus —
when available — a real official Round 3 grouping/tee-time list.

This module NEVER infers a MISSED_CUT status from a player being
absent from a round's response, or from rank/position. A real Windows
run already disproved that inference (see klpga.neo_win.
r1_to_r2_reconciliation's own docstring): it produced an implausibly
high made-cut rate, meaning "absent from Round 2" is not, by itself,
reliable evidence of a missed cut on the real site. This module exists
to gather stronger, independent evidence — Round 3's real grouping/
tee-time list is a second, structurally different signal ("this player
was assigned a tee time to continue playing") that a status-text-only
approach cannot fake or guess.

======================================================================
NO CONFIRMED ROUND 3 GROUPING/TEE-TIME ENDPOINT EXISTS YET
======================================================================
Every other endpoint this project uses (getGameList, roundLeaderboard,
entry, loadLocationRecord — see klpga.config) was discovered from a
real, human-captured browser Network-tab request and documented in
docs/SITE_STRUCTURE_TODO.md before any collector was written against
it. No such capture exists yet for a Round 3 grouping/tee-time page,
so this module never constructs or guesses a URL for one.
`r3_grouping_rows` is a plain parameter this module accepts from an
ALREADY-collected real source (see scripts/diagnose_r2_r3_ground_
truth.py's --r3-grouping-json) — an empty list is the real, honest
"not collected yet" state, never treated as "confirmed no groupings
exist."

======================================================================
PROPOSED_CUT_STATUS — evidence tiers, weakest claim wins when tied
======================================================================
  1. Found in the real Round 3 grouping/tee-time list -> CONFIRMED
     CONTINUING (the strongest, most direct real signal: they were
     assigned a tee time to keep playing).
  2. An explicit WD/DQ status text on their Round 2 (preferred) or
     Round 1 row -> that status (real, direct site evidence).
  3. Neither of the above -> UNRESOLVED_NEEDS_MORE_EVIDENCE, with a
     `reason` that says exactly what evidence is still missing. This
     is the DIAGNOSTIC's entire point: surface exactly this population
     with their full real evidence, never assert MISSED_CUT for them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

STATUS_WD = "WD"
STATUS_DQ = "DQ"
STATUS_CONFIRMED_CONTINUING = "CONFIRMED_CONTINUING"
STATUS_UNRESOLVED = "UNRESOLVED_NEEDS_MORE_EVIDENCE"

_KNOWN_EXCEPTIONAL_STATUS = {"WD": STATUS_WD, "DQ": STATUS_DQ}


@dataclass(frozen=True)
class R3GroupingRow:
    """One player's real Round 3 grouping/tee-time entry — from an
    ALREADY-collected real source (see module docstring); this
    dataclass never fetches or parses anything itself."""

    player_code: str
    player_name: Optional[str]
    group: Optional[str]
    tee_time: Optional[str]
    starting_tee: Optional[str] = None


@dataclass(frozen=True)
class GroundTruthRow:
    player_code: str
    official_name: str
    r1_present: bool
    r2_present: bool
    r2_raw_rank: Optional[str]
    r2_raw_status: Optional[str]
    r2_round_score: Optional[int]
    r2_total_score: Optional[int]
    r3_grouping_present: bool
    r3_group: Optional[str]
    r3_tee_time: Optional[str]
    proposed_cut_status: str
    reason: str


def build_ground_truth_table(
    r1_rows: list, r2_rows: list, r3_grouping_rows: list[R3GroupingRow]
) -> tuple[list[GroundTruthRow], dict]:
    """Pure function — no I/O, no fabrication. `r1_rows`/`r2_rows` are
    real klpga.parsers.leaderboard_parser.PlayerRoundRow lists (from an
    already-completed live fetch, e.g. klpga.collectors.leaderboard.
    collect_all_rounds_for_game). `player_code` is the ONLY join key
    across all three sources."""
    r1_by_code = {r.player_code: r for r in r1_rows if r.player_code}
    r2_by_code = {r.player_code: r for r in r2_rows if r.player_code}
    r3_by_code = {r.player_code: r for r in r3_grouping_rows if r.player_code}

    all_codes = set(r1_by_code) | set(r2_by_code) | set(r3_by_code)
    r3_available = len(r3_grouping_rows) > 0

    rows: list[GroundTruthRow] = []
    for code in sorted(all_codes):
        r1 = r1_by_code.get(code)
        r2 = r2_by_code.get(code)
        r3 = r3_by_code.get(code)

        official_name = (
            (r2.player_name if r2 else None)
            or (r1.player_name if r1 else None)
            or (r3.player_name if r3 else None)
            or ""
        )
        r2_status = r2.status if r2 else None

        if r3 is not None:
            proposed = STATUS_CONFIRMED_CONTINUING
            reason = "found in the real official Round 3 grouping/tee-time list"
        elif r2_status in _KNOWN_EXCEPTIONAL_STATUS:
            proposed = _KNOWN_EXCEPTIONAL_STATUS[r2_status]
            reason = f"official Round 2 status text = {r2_status!r}"
        elif r1 is not None and r1.status in _KNOWN_EXCEPTIONAL_STATUS:
            proposed = _KNOWN_EXCEPTIONAL_STATUS[r1.status]
            reason = f"official Round 1 status text = {r1.status!r}"
        elif r3_available:
            proposed = STATUS_UNRESOLVED
            reason = (
                "absent from the real Round 3 grouping/tee-time list, no explicit WD/DQ status found — "
                "evidence insufficient to assert MISSED_CUT without further site verification"
            )
        else:
            proposed = STATUS_UNRESOLVED
            reason = "Round 3 grouping/tee-time data not collected yet — cannot determine status"

        rows.append(
            GroundTruthRow(
                player_code=code,
                official_name=official_name,
                r1_present=r1 is not None,
                r2_present=r2 is not None,
                r2_raw_rank=r2.rank_display if r2 else None,
                r2_raw_status=r2_status,
                r2_round_score=r2.round2_score if r2 else None,
                r2_total_score=r2.total_strokes if r2 else None,
                r3_grouping_present=r3 is not None,
                r3_group=r3.group if r3 else None,
                r3_tee_time=r3.tee_time if r3 else None,
                proposed_cut_status=proposed,
                reason=reason,
            )
        )

    summary = {
        "total_tournament_players": len(all_codes),
        "r3_grouping_player_count": len(r3_by_code),
        "r3_absent_count": sum(1 for r in rows if not r.r3_grouping_present),
        "explicit_wd_count": sum(1 for r in rows if r.proposed_cut_status == STATUS_WD),
        "explicit_dq_count": sum(1 for r in rows if r.proposed_cut_status == STATUS_DQ),
        "unexplained_count": sum(1 for r in rows if r.proposed_cut_status == STATUS_UNRESOLVED),
    }
    return rows, summary


_RAW_ROUND_ROW_FIELDNAMES: tuple[str, ...] = (
    "game_code", "player_code", "player_name", "player_eng_name", "round_number",
    "rank_display", "rank", "tie_flag", "status",
    "total_under_par_display", "total_under_par",
    "today_under_par_display", "today_under_par",
    "total_strokes", "holes_completed",
    "round1_score", "round2_score", "round3_score", "round4_score",
)


def raw_round_row_to_dict(row) -> dict:
    """Every real PlayerRoundRow field, preserved as-is — the "every
    raw status/rank field available from the endpoint" requirement
    (GROUND TRUTH CHECK A) — never a trimmed subset."""
    return {name: getattr(row, name) for name in _RAW_ROUND_ROW_FIELDNAMES}
