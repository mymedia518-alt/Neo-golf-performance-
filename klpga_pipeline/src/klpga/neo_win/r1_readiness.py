"""Deterministic R1 completeness and status-delta gate.

STATUS TAXONOMY -- kept in sync with klpga.parsers.leaderboard_parser and
scripts/84's _UNRESOLVED_STATUSES: the official KLPGA leaderboard endpoint
has only ever been observed emitting a bare "999" rank sentinel for a
did-not-complete player -- parsed as status="INCOMPLETE" -- never a
literal "WD" or "DQ" string (those are defined in the parser defensively,
for if the endpoint ever does emit one, but never yet observed live).

"INCOMPLETE" is a KNOWN status here (never hits the "unrecognized
official status" HARD_STOP branch), but it is NOT treated as exempt from
completion the way WD/DQ/DNS are: a bare "999" sentinel is not itself
official evidence of WD/DQ/DNS (klpga.neo_win.r1_final_reconciliation's
own OFFICIAL_NON_PLAYING_STATUSES deliberately excludes it for exactly
this reason -- see that module). Letting INCOMPLETE count toward
R1_COMPLETE would let the live 30-minute cycle (klpga.neo_win.
r1_active_cycle.decide_cycle) fire PUBLISH_AND_CLOSE -- which disables
the Task Scheduler job that runs it -- while two players' true status is
still unconfirmed, permanently freezing their stale mid-round data with
no further collection ever happening. So an INCOMPLETE row instead
returns WAIT: the round stays open and polling continues until either
those rows resolve to a real official score, or
scripts/98_ok_open_r1_final_reconciliation.py's scoreRecord-based check
(the only real authority for r1_complete/r2_ready) confirms a real
WD/DQ/DNS. This still fixes the original bug this module's history
records: a genuinely-withdrawn player's row no longer HARD_STOPs the
gate every cycle -- it now returns a quiet WAIT instead of an error."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class R1Readiness:
    decision: str  # WAIT, R1_COMPLETE, HARD_STOP
    reason: str
    active: int
    wd: int
    dq: int
    dns: int
    missing: int
    incomplete: int = 0

def assess_r1(rows, expected_player_ids, *, suspended=False, official_page_available=True, expected_holes=18) -> R1Readiness:
    if not official_page_available:
        return R1Readiness("WAIT", "official leaderboard unavailable", 0, 0, 0, 0, len(expected_player_ids))
    ids = [str(r.get("player_id") or r.get("player_code") or "") for r in rows]
    if len(ids) != len(set(ids)):
        return R1Readiness("HARD_STOP", "duplicate player identity in official rows", 0, 0, 0, 0, 0)
    expected = {str(x) for x in expected_player_ids}
    unknown = set(ids) - expected
    if unknown:
        return R1Readiness("HARD_STOP", "official row contains unresolved player identity", 0, 0, 0, 0, len(unknown))
    missing = expected - set(ids)
    if missing:
        return R1Readiness("HARD_STOP", "expected entrant absent without an official status", 0, 0, 0, 0, len(missing))
    if suspended:
        return R1Readiness("WAIT", "round suspension/delay; completion cannot be inferred", 0, 0, 0, 0, 0)
    counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0, "INCOMPLETE": 0}
    for row in rows:
        status = str(row.get("status") or "ACTIVE").upper()
        if status not in counts:
            return R1Readiness("HARD_STOP", f"unrecognized official status: {status}", 0, 0, 0, 0, 0)
        if status == "INCOMPLETE":
            # A bare "999" sentinel is not official WD/DQ/DNS evidence --
            # never treated as a non-playing exception that lets the
            # round close. Keep polling (WAIT), never HARD_STOP, never
            # R1_COMPLETE, until real evidence resolves it elsewhere.
            return R1Readiness(
                "WAIT", "one or more players have an unresolved INCOMPLETE status (no confirmed WD/DQ/DNS)",
                counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0, counts["INCOMPLETE"],
            )
        if status == "ACTIVE":
            holes = row.get("holes_completed")
            if str(holes) not in {str(expected_holes), "F", "FINAL"}:
                return R1Readiness(
                    "WAIT", "one or more active players have incomplete holes",
                    counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0, counts["INCOMPLETE"],
                )
            if row.get("rank") is None and not row.get("rank_display"):
                return R1Readiness(
                    "HARD_STOP", "active player has no official rank",
                    counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0, counts["INCOMPLETE"],
                )
        counts[status] += 1
    return R1Readiness(
        "R1_COMPLETE", "all official rows complete; statuses preserved",
        counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0, counts["INCOMPLETE"],
    )
