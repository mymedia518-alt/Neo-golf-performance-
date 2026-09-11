"""Format-aware R3 completion readiness gate. Mirrors
klpga.neo_win.r2_readiness exactly, minus the cut-known check (there is
no new cut event at R3 -- see round_update_r3.py's own module
docstring)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class R3Readiness:
    decision: str  # WAIT, R3_COMPLETE, HARD_STOP
    reason: str
    active: int
    wd: int
    dq: int
    dns: int
    missing: int


def assess_r3(rows, expected_player_ids, *, official_page_available=True, suspended=False, future_round4_rows=0, freeze_exists=False) -> R3Readiness:
    if freeze_exists:
        return R3Readiness("HARD_STOP", "R3 freeze artifact already exists; refusing overwrite", 0, 0, 0, 0, 0)
    if future_round4_rows:
        return R3Readiness("HARD_STOP", "future R4/FINAL rows detected before R3 checkpoint", 0, 0, 0, 0, future_round4_rows)
    if not official_page_available:
        return R3Readiness("WAIT", "official R3 leaderboard unavailable", 0, 0, 0, 0, len(expected_player_ids))
    if suspended:
        return R3Readiness("WAIT", "R3 suspension/delay; completion cannot be inferred", 0, 0, 0, 0, 0)
    expected = {str(x) for x in expected_player_ids}
    ids = [str(r.get("player_id") or r.get("player_code") or "") for r in rows]
    if len(ids) != len(set(ids)):
        return R3Readiness("HARD_STOP", "duplicate player identity in R3 rows", 0, 0, 0, 0, 0)
    if set(ids) - expected:
        return R3Readiness("HARD_STOP", "unresolved identity in R3 rows", 0, 0, 0, 0, len(set(ids) - expected))
    if expected - set(ids):
        return R3Readiness("HARD_STOP", "entrant absent without official WD/DQ/DNS status", 0, 0, 0, 0, len(expected - set(ids)))
    counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0}
    for row in rows:
        status = str(row.get("status") or "ACTIVE").upper()
        if status not in counts:
            return R3Readiness("HARD_STOP", f"unrecognized official status: {status}", 0, 0, 0, 0, 0)
        if status == "ACTIVE" and str(row.get("holes_completed")) not in {"54", "F", "FINAL"}:
            return R3Readiness("WAIT", "R3 player/hole completion unresolved", 0, 0, 0, 0, 0)
        counts[status] += 1
    return R3Readiness("R3_COMPLETE", "official R3 states complete", counts["ACTIVE"], counts["WD"], counts["DQ"], counts["DNS"], 0)
