"""Deterministic R1 completeness and status-delta gate.

STATUS TAXONOMY -- kept in sync with klpga.parsers.leaderboard_parser and
scripts/84's _UNRESOLVED_STATUSES: the official KLPGA leaderboard endpoint
has only ever been observed emitting a bare "999" rank sentinel for a
did-not-complete player -- parsed as status="INCOMPLETE" -- never a
literal "WD" or "DQ" string (those are defined in the parser defensively,
for if the endpoint ever does emit one, but never yet observed live).
"INCOMPLETE" is therefore treated exactly like WD/DQ/DNS here: exempt
from the 18-hole completion requirement, never blocking R1_COMPLETE.
Before this was added, a genuinely-withdrawn player whose row still (and,
per the parser's own documented behavior, permanently) carries
status="INCOMPLETE" would hit the "unrecognized official status" branch
below and HARD_STOP the round-close decision the moment every other
player actually finished -- discovered live against the real R1 snapshot
during the P0 round-close-gate audit, not a hypothetical."""
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
