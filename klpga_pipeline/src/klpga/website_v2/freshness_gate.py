"""P0 incident remediation (NEO P0 PRODUCTION INCIDENT -- STALE R1 LIVE
DATA): a hard, data-state-aware release gate that refuses to promote a
build that silently presents stale in-progress round data as if it
were current/live, and refuses to promote a build whose data state
claims a round is complete while individual player rows still show
incomplete holes.

Root cause of the incident this guards against: the R1 30-minute
active cycle collector requires real klpga.co.kr network access, which
only exists on a separate operator machine (this build sandbox has
none -- confirmed repeatedly, every session). When that machine's
scheduled cycle stalls for any reason -- e.g. NEO-GOLF-R1-ACTIVE-30MIN
.ps1's ancestry-mismatch guard silently HARD_STOPping every run once
origin diverges (fixed separately) -- the last successfully collected
snapshot keeps being rebuilt and re-promoted as if it were fresh, with
nothing in the pipeline ever noticing or saying so. This module turns
that into a hard, testable, DATA-STATE check -- not merely "the HTML
is well-formed" (Playwright PASS is not sufficient on its own).

STALE_THRESHOLD_SECONDS = 3x the active cycle's own 30-minute cadence
(90 minutes): long enough that one missed cycle (a network blip, a
slow collection) never falsely trips the gate, short enough to catch
a genuinely stalled pipeline -- the incident this module was written
for had a ~3.5 hour stale snapshot.
"""
from __future__ import annotations

import datetime

STALE_THRESHOLD_SECONDS = 90 * 60
STALE_NOTICE_MARKER = "데이터 수집 지연 중"
# INCOMPLETE is klpga.parsers.leaderboard_parser's real, and only ever
# observed, did-not-complete signal (the raw "999" rank sentinel) -- the
# endpoint never actually emits a literal "WD"/"DQ" string. Treating it
# the same as WD/DQ/CUT here matches klpga.neo_win.r1_readiness.assess_r1
# (the decision gate that runs BEFORE this one): without this, a round
# assess_r1 correctly closed because it exempted an INCOMPLETE player
# would still fail THIS gate and HARD_STOP the promotion right after.
_NON_PLAYING_STATUSES = {"WD", "DQ", "CUT", "INCOMPLETE"}
_COMPLETE_HOLE_VALUES = {"18", "F"}


class FreshnessGateError(Exception):
    """Raised when the release gate finds a data-state defect that
    must never reach production: stale live data rendered without an
    honest staleness notice, or a completed round whose player rows
    still show incomplete holes."""


def snapshot_age_seconds(collected_at_iso: str, now: datetime.datetime) -> float:
    collected_at = datetime.datetime.fromisoformat(collected_at_iso.replace("Z", "+00:00"))
    return (now - collected_at).total_seconds()


def is_snapshot_stale(collected_at_iso: str | None, now: datetime.datetime, *, max_age_seconds: float = STALE_THRESHOLD_SECONDS) -> bool:
    """No collected_at at all is never treated as "stale" here -- an
    absent/pre-collection snapshot is a different condition entirely,
    already handled elsewhere (the "아직 시작 전" placeholder)."""
    if not collected_at_iso:
        return False
    return snapshot_age_seconds(collected_at_iso, now) > max_age_seconds


def assert_no_silent_staleness(
    html: str, *, collected_at_iso: str | None, now: datetime.datetime, max_age_seconds: float = STALE_THRESHOLD_SECONDS, label: str
) -> None:
    """HARD STOP: a page built from a stale snapshot (age exceeds the
    threshold) must always carry STALE_NOTICE_MARKER somewhere in its
    rendered HTML -- proof the viewer is told the data is delayed,
    rather than the page silently implying the normal 30-minute live
    cadence is still current. A fresh snapshot is exempt (nothing to
    disclose)."""
    if not is_snapshot_stale(collected_at_iso, now, max_age_seconds=max_age_seconds):
        return
    if STALE_NOTICE_MARKER in html:
        return
    age_minutes = int(snapshot_age_seconds(collected_at_iso, now) // 60)
    raise FreshnessGateError(
        f"{label}: live snapshot is {age_minutes} minutes old (collected_at={collected_at_iso}, "
        f"threshold={int(max_age_seconds // 60)}min) but the rendered page does not carry the "
        f"{STALE_NOTICE_MARKER!r} staleness notice -- refusing to promote stale data presented as current."
    )


def assert_completed_round_has_no_incomplete_holes(player_table: list, *, round_complete: bool, label: str) -> None:
    """HARD STOP: if the stage state asserts the round is complete,
    every playing (non-WD/DQ/CUT) player row must show a completed
    18-hole (or "F") result -- a completed-round claim sitting next to
    live per-hole progress data is an internally inconsistent build
    and must never be promoted."""
    if not round_complete:
        return
    incomplete = [
        row
        for row in player_table
        if str(row.get("status") or "").upper() not in _NON_PLAYING_STATUSES
        and str(row.get("holes_completed") or "") not in _COMPLETE_HOLE_VALUES
    ]
    if incomplete:
        names = [row.get("player_name") for row in incomplete]
        raise FreshnessGateError(
            f"{label}: stage state marks the round complete but {len(incomplete)} player row(s) still show "
            f"incomplete holes (not WD/DQ/CUT): {names} -- refusing to promote an inconsistent completed-round build."
        )
