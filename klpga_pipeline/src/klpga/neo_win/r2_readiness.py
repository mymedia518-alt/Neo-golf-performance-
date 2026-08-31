"""Format-aware R2 completion and CUT readiness gate."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class R2Readiness:
    decision: str  # WAIT, R2_COMPLETE, HARD_STOP
    reason: str
    cut_known: bool
    cutmakers: int
    cut_players: int
    wd: int
    dq: int
    missing: int

def assess_r2(rows, expected_player_ids, *, official_page_available=True, suspended=False, cut_known=False, future_round3_rows=0, freeze_exists=False) -> R2Readiness:
    if freeze_exists:
        return R2Readiness("HARD_STOP", "R2 freeze artifact already exists; refusing overwrite", False, 0, 0, 0, 0, 0)
    if future_round3_rows:
        return R2Readiness("HARD_STOP", "future R3 rows detected before R2 checkpoint", False, 0, 0, 0, 0, future_round3_rows)
    if not official_page_available:
        return R2Readiness("WAIT", "official R2 leaderboard unavailable", False, 0, 0, 0, 0, len(expected_player_ids))
    if suspended:
        return R2Readiness("WAIT", "R2 suspension/delay; completion cannot be inferred", False, 0, 0, 0, 0, 0)
    expected = {str(x) for x in expected_player_ids}
    ids = [str(r.get("player_id") or r.get("player_code") or "") for r in rows]
    if len(ids) != len(set(ids)):
        return R2Readiness("HARD_STOP", "duplicate player identity in R2 rows", False, 0, 0, 0, 0, 0)
    if set(ids) - expected:
        return R2Readiness("HARD_STOP", "unresolved identity in R2 rows", False, 0, 0, 0, 0, len(set(ids)-expected))
    if expected - set(ids):
        return R2Readiness("HARD_STOP", "entrant absent without official WD/DQ/DNS status", False, 0, 0, 0, 0, len(expected-set(ids)))
    if not cut_known:
        return R2Readiness("WAIT", "official CUT status is not yet published; no CUT inferred", False, 0, 0, 0, 0, 0)
    counts = {"ACTIVE":0,"CUT":0,"WD":0,"DQ":0,"DNS":0}
    for row in rows:
        status = str(row.get("status") or "ACTIVE").upper()
        if status not in counts:
            return R2Readiness("HARD_STOP", f"unrecognized official status: {status}", False, 0, 0, 0, 0, 0)
        if status in {"ACTIVE", "CUT"} and str(row.get("holes_completed")) not in {"36", "F", "FINAL"}:
            return R2Readiness("WAIT", "R2 player/hole completion unresolved", False, 0, 0, 0, 0, 0)
        counts[status] += 1
    return R2Readiness("R2_COMPLETE", "official R2 and CUT states complete", True, counts["ACTIVE"], counts["CUT"], counts["WD"], counts["DQ"], 0)
