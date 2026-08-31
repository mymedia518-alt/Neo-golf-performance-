"""Deterministic R1 completeness and status-delta gate."""
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
    counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0}
    for row in rows:
        status = str(row.get("status") or "ACTIVE").upper()
        if status not in counts:
            return R1Readiness("HARD_STOP", f"unrecognized official status: {status}", 0, 0, 0, 0, 0)
        if status == "ACTIVE":
            holes = row.get("holes_completed")
            if str(holes) not in {str(expected_holes), "F", "FINAL"}:
                return R1Readiness("WAIT", "one or more active players have incomplete holes", counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0)
            if row.get("rank") is None and not row.get("rank_display"):
                return R1Readiness("HARD_STOP", "active player has no official rank", counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0)
        counts[status] += 1
    return R1Readiness("R1_COMPLETE", "all official rows complete; statuses preserved", counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0)
