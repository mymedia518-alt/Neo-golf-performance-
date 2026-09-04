"""R1 FINAL reconciliation against the official scoreRecord source.

Pure decision logic over already-fetched, already-parsed rows -- no
I/O, fully unit-testable without any real network access, matching the
klpga.neo_win.r1_active_cycle.decide_cycle / assess_r1 precedent this
mirrors deliberately.

WHY THIS EXISTS (separate from the live in-progress collector): the
30-minute active cycle (klpga.neo_win.r1_active_cycle, scripts/96) only
ever sees the roundLeaderboard endpoint's raw "999" rank sentinel for a
player who did not complete a round -- parsed as status="INCOMPLETE"
(klpga.parsers.leaderboard_parser). That endpoint has NEVER been
observed distinguishing WD from DQ from DNS from anything else, so the
live collector's own completion gate (klpga.neo_win.r1_readiness.
assess_r1) can only ever treat INCOMPLETE as "exempt from the 18-hole
requirement," never as a confirmed official determination of WHY a
player didn't finish.

scoreRecord ("대회기록" -- tournament record) is a DIFFERENT, dedicated
official-record endpoint that may carry KLPGA's own real WD/DQ/DNS
determination directly (not yet confirmed against real markup -- see
klpga.collectors.score_record). This module is written against the
CLEAN INTERMEDIATE CONTRACT that a real parser for that page will
eventually produce, so the reconciliation policy itself -- normal
players require a real final score, WD/DQ/DNS are exempt but ONLY on
the official source's own say-so, never inferred from INCOMPLETE or
any other live-collector signal -- can be written, tested, and
reviewed today, entirely independent of when that parser gets
finished.

STATUS TAXONOMY IS DELIBERATELY DIFFERENT FROM r1_readiness.assess_r1:
that module's recognized set includes "INCOMPLETE" (the live
collector's own internal label). This module's recognized set does
NOT -- "INCOMPLETE" is not a real official status, it is what the live
collector calls "I don't know why this player stopped." A scoreRecord
row reporting a status this module doesn't recognize (including the
literal string "INCOMPLETE", if a caller ever mistakenly fed live-
collector data into this function) is treated exactly like any other
unrecognized status: FAIL, never guessed into WD.
"""
from __future__ import annotations

from dataclasses import dataclass

OFFICIAL_NON_PLAYING_STATUSES = {"WD", "DQ", "DNS"}


@dataclass(frozen=True)
class ReconciliationResult:
    passed: bool
    reason: str
    active_confirmed: int = 0
    wd: int = 0
    dq: int = 0
    dns: int = 0


def reconcile_r1_final(score_record_rows: list[dict], expected_player_ids: list[str]) -> ReconciliationResult:
    """`score_record_rows`: the clean, already-parsed contract a real
    klpga.collectors.score_record.parse_score_record_html() will
    eventually produce -- {"player_id": str, "official_status": str |
    None, "final_score": <value> | None, "rank_display": str | None}
    per row. Identity is matched by player_id ONLY, exactly like every
    other reconciliation in this project -- never a name-based fallback.

    PASSES only if every expected entrant has an official row, every
    row's identity and status are recognized, and every ACTIVE
    (non-WD/DQ/DNS) player has a real, non-None final_score. WD/DQ/DNS
    players are exempt from the final-score requirement -- but only
    because THIS official source itself reported that status, never
    because the live collector's INCOMPLETE label suggested it."""
    ids = [str(r.get("player_id") or "") for r in score_record_rows]
    if any(not pid for pid in ids):
        return ReconciliationResult(False, "official scoreRecord row with no resolvable player_id")
    if len(ids) != len(set(ids)):
        return ReconciliationResult(False, "duplicate player_id in official scoreRecord rows")
    expected = {str(x) for x in expected_player_ids}
    unknown = set(ids) - expected
    if unknown:
        return ReconciliationResult(False, f"{len(unknown)} official scoreRecord row(s) with unresolved/unexpected player_id")
    missing = expected - set(ids)
    if missing:
        return ReconciliationResult(False, f"{len(missing)} expected entrant(s) have no official scoreRecord row at all")

    counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0}
    for row in score_record_rows:
        status = str(row.get("official_status") or "ACTIVE").upper()
        if status not in counts:
            return ReconciliationResult(False, f"unrecognized official scoreRecord status: {status!r} -- never inferred, refusing to guess")
        if status == "ACTIVE" and row.get("final_score") is None:
            return ReconciliationResult(
                False,
                f"player_id={row.get('player_id')}: official status is ACTIVE but no final_score is present -- "
                "a normal player is not complete without a real final score",
            )
        counts[status] += 1

    return ReconciliationResult(
        True, "every expected entrant has an official row; every ACTIVE player has a final score",
        active_confirmed=counts["ACTIVE"], wd=counts["WD"], dq=counts["DQ"], dns=counts["DNS"],
    )
