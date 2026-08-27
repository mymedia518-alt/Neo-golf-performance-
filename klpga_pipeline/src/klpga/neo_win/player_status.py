"""klpga.neo_win.player_status — round-aware, evidence-only player
status classification. Shared by the R1 audit (scripts/45) and the R2
prediction script (scripts/44), reusable by any future R3/R4 stage.
Never guesses: every non-COMPLETED classification is grounded in a
real DB flag (player_event.withdrawn/disqualified/made_cut) or a real
absence, never inferred from silence alone.

======================================================================
STATUS VALUES
======================================================================
STATUS_COMPLETED — a real player_round row with a score exists for
  this round_number.
STATUS_WD / STATUS_DQ — player_event's own confirmed withdrawn/
  disqualified boolean is set.
STATUS_DNS — ONLY when finish_position's raw text literally says so
  and no confirmed boolean contradicts it (the record still flags this
  as text-only evidence, never silently upgraded to certain).
STATUS_CUT — round_number is after the single 36-hole cut (verified
  real evidence, klpga.neo_win.round_update's own docstring /
  docs/SITE_STRUCTURE_TODO.md: exactly one cut, after Round 2, no
  subsequent cut) AND player_event.made_cut=0 is CORROBORATED by
  rounds_played<=2. made_cut is `NOT NULL DEFAULT 0` in schema.sql, so
  made_cut=0 alone can mean "confirmed missed cut" OR simply "never
  updated" — rounds_played<=2 is the real, independent signal (sourced
  from the site's own tournament summary, not our own player_round
  collection) that confirms the player's tournament actually ended at
  or before Round 2. Without that corroboration this falls through to
  UNKNOWN, never a guessed CUT. Never applied to round_number<=2 at
  all, since the cut has not yet been determined at that point.
STATUS_COLLECTION_MISSING — POSITIVE evidence of participation
  (rounds_played >= round_number, no WD/DQ/CUT explanation) yet this
  round's own player_round row is absent — a pipeline gap, not a
  tournament-status case. Never assigned without that positive
  evidence (a legitimate WD/DNS/DQ/CUT is never reported as this).
STATUS_UNKNOWN — none of the above could be positively established.

ENTRY FIELD (tournament_entry membership) and STARTED (whether the
player teed off) are tracked as separate fields on PlayerRoundStatus,
never folded into the single `classification` value:
  - `in_entry_field`: real tournament_entry membership, always
    determinable.
  - `started_this_round`: True when completed_this_round is True (a
    score can only exist if the round was started); otherwise the
    literal STARTED_UNDERIVABLE string — the schema has no separate
    "teed off, no result captured" field, so this is never guessed
    True/False in that case.

======================================================================
FIELD READINESS — a semantic, evidence-based replacement for any
numeric "N% of the field must have a score" gate
======================================================================
`assess_field_readiness` classifies EVERY tournament_entry player for
`game_code` at `round_number` (via classify_player_round_status — no
round-specific duplicated logic) and reduces the whole field to one of
three verdicts:

  READINESS_GO — every player is accounted for by a legitimate,
    evidence-backed state (COMPLETED/WD/DQ/DNS/CUT). Safe to generate.
  READINESS_WARN — no ingestion failure, but at least one player is
    STATUS_UNKNOWN (no positive evidence either way). Still safe to
    generate — the caller must report the UNKNOWN players explicitly,
    never silently drop them.
  READINESS_HARD_STOP — either at least one player is
    STATUS_COLLECTION_MISSING (positive evidence of a real pipeline
    gap), or zero real round_number rows exist for this game_code at
    all (official ingestion for this round has not happened). Never
    generate a prediction.

Deliberately NO numeric/percentage threshold anywhere in this
function — "120/120", "95%", or any other arbitrary minimum would
conflate ENTRY_FIELD size with COMPLETED_ROUND field size, which this
whole module exists to keep separate.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Union

STATUS_COMPLETED = "COMPLETED"
STATUS_WD = "WD"
STATUS_DQ = "DQ"
STATUS_DNS = "DNS"
STATUS_CUT = "CUT"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_COLLECTION_MISSING = "COLLECTION_MISSING"

READINESS_GO = "GO"
READINESS_WARN = "WARN"
READINESS_HARD_STOP = "HARD_STOP"

STARTED_UNDERIVABLE = (
    "UNKNOWN (not derivable from current schema — player_round only records a COMPLETED round's "
    "score; there is no separate 'started but result not captured' field anywhere in schema.sql)"
)

SINGLE_CUT_AFTER_ROUND = 2
"""Verified real evidence: exactly one 36-hole cut, after Round 2, no
subsequent cut — see klpga.neo_win.round_update's own docstring."""


@dataclass(frozen=True)
class PlayerRoundStatus:
    player_code: str
    round_number: int
    in_entry_field: bool
    completed_this_round: bool
    started_this_round: Union[bool, str]
    rounds_played_total: Optional[int]
    made_cut: Optional[bool]
    event_status: str
    """One of 'DQ' / 'WD' / 'NO_FLAG_SET' / 'NO_PLAYER_EVENT_ROW' /
    'NOT_CHECKED' (the last only when completed_this_round is already
    True and player_event was never consulted) — read straight from
    player_event's own confirmed booleans, never inferred otherwise."""
    finish_position: Optional[str]
    classification: str
    """One of the STATUS_* constants above — the single, mutually
    exclusive final decision."""
    detail: str
    """Human-readable evidence trail behind `classification`."""


def _in_entry_field(conn: sqlite3.Connection, game_code: str, player_code: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM tournament_entry WHERE game_code = ? AND player_code = ?", (game_code, player_code)
        ).fetchone()
        is not None
    )


def _completed_this_round(conn: sqlite3.Connection, game_code: str, player_code: str, round_number: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM player_round WHERE game_code = ? AND round_number = ? AND player_id = ? "
            "AND round_to_par IS NOT NULL",
            (game_code, round_number, player_code),
        ).fetchone()
        is not None
    )


def classify_player_round_status(
    conn: sqlite3.Connection, game_code: str, player_code: str, round_number: int
) -> PlayerRoundStatus:
    """The single, reusable entry point every caller (scripts/44,
    scripts/45, any future R3/R4 script) should use instead of
    re-deriving WD/DQ/CUT/COLLECTION_MISSING logic itself."""
    in_entry = _in_entry_field(conn, game_code, player_code)

    if _completed_this_round(conn, game_code, player_code, round_number):
        return PlayerRoundStatus(
            player_code=player_code, round_number=round_number, in_entry_field=in_entry,
            completed_this_round=True, started_this_round=True, rounds_played_total=None, made_cut=None,
            event_status="NOT_CHECKED", finish_position=None, classification=STATUS_COMPLETED,
            detail=f"real round_number={round_number} player_round row with a score exists",
        )

    row = conn.execute(
        "SELECT withdrawn, disqualified, made_cut, rounds_played, finish_position "
        "FROM player_event WHERE game_code = ? AND player_id = ?",
        (game_code, player_code),
    ).fetchone()

    if row is None:
        return PlayerRoundStatus(
            player_code=player_code, round_number=round_number, in_entry_field=in_entry,
            completed_this_round=False, started_this_round=STARTED_UNDERIVABLE, rounds_played_total=None,
            made_cut=None, event_status="NO_PLAYER_EVENT_ROW", finish_position=None,
            classification=STATUS_UNKNOWN,
            detail=(
                "no player_event row exists for this game_code at all "
                f"({'in tournament_entry' if in_entry else 'NOT in tournament_entry either'}); consistent "
                "with DNS (never started, so no event row was ever created) but not positively confirmed "
                "— never assumed"
            ),
        )

    withdrawn, disqualified, made_cut_raw, rounds_played, finish_position = row
    made_cut = None if made_cut_raw is None else bool(made_cut_raw)

    if disqualified:
        event_status = "DQ"
    elif withdrawn:
        event_status = "WD"
    else:
        event_status = "NO_FLAG_SET"

    if event_status == "DQ":
        classification = STATUS_DQ
        detail = f"player_event.disqualified=1 (finish_position={finish_position!r})"
    elif event_status == "WD":
        classification = STATUS_WD
        detail = f"player_event.withdrawn=1 (finish_position={finish_position!r})"
    elif finish_position in (STATUS_WD, STATUS_DQ, STATUS_DNS):
        classification = finish_position
        detail = (
            f"finish_position text says {finish_position!r} but the confirmed withdrawn/disqualified boolean "
            "flag is NOT set; inconsistent evidence, flagged for manual review, not guessed"
        )
    elif (
        round_number > SINGLE_CUT_AFTER_ROUND
        and made_cut is False
        and rounds_played is not None
        and rounds_played <= SINGLE_CUT_AFTER_ROUND
    ):
        classification = STATUS_CUT
        detail = (
            f"made_cut=False, corroborated by rounds_played={rounds_played}<=SINGLE_CUT_AFTER_ROUND "
            f"(single 36-hole cut after Round {SINGLE_CUT_AFTER_ROUND}) — this round's absence is a real, "
            "expected elimination outcome, not a data-quality issue"
        )
    elif rounds_played is not None and rounds_played >= round_number:
        classification = STATUS_COLLECTION_MISSING
        detail = (
            f"rounds_played={rounds_played} >= round_number={round_number} with no WD/DQ/CUT explanation "
            f"(positive evidence round {round_number} was played), but no player_round row exists for it "
            "— a pipeline gap, not a tournament-status case"
        )
    else:
        classification = STATUS_UNKNOWN
        detail = (
            f"player_event row exists (made_cut={made_cut!r}, finish_position={finish_position!r}) but "
            f"rounds_played={rounds_played!r} — no positive evidence either way, not classified as "
            f"{STATUS_COLLECTION_MISSING} without it"
        )

    return PlayerRoundStatus(
        player_code=player_code, round_number=round_number, in_entry_field=in_entry, completed_this_round=False,
        started_this_round=STARTED_UNDERIVABLE, rounds_played_total=rounds_played, made_cut=made_cut,
        event_status=event_status, finish_position=finish_position, classification=classification, detail=detail,
    )


@dataclass(frozen=True)
class FieldReadiness:
    round_number: int
    field_size: int
    statuses: tuple  # tuple[PlayerRoundStatus, ...], one per ENTRY_FIELD player
    verdict: str  # one of READINESS_GO / READINESS_WARN / READINESS_HARD_STOP
    unknown_players: tuple
    collection_missing_players: tuple
    reason: str


def _entry_field_codes(conn: sqlite3.Connection, game_code: str) -> list:
    return [
        code
        for (code,) in conn.execute(
            "SELECT player_code FROM tournament_entry WHERE game_code = ? ORDER BY player_code", (game_code,)
        )
    ]


def assess_field_readiness(conn: sqlite3.Connection, game_code: str, round_number: int) -> FieldReadiness:
    """The semantic, evidence-based replacement for any numeric
    coverage gate. Classifies the WHOLE tournament_entry field (never
    just the players who happen to have a score) and reduces it to one
    verdict — see the module docstring's FIELD READINESS section for
    the exact GO/WARN/HARD_STOP rules. No arbitrary percentage
    threshold anywhere in this function."""
    field_codes = _entry_field_codes(conn, game_code)
    statuses = tuple(
        classify_player_round_status(conn, game_code, code, round_number) for code in field_codes
    )

    collection_missing = tuple(s.player_code for s in statuses if s.classification == STATUS_COLLECTION_MISSING)
    unknown = tuple(s.player_code for s in statuses if s.classification == STATUS_UNKNOWN)

    real_round_rows = conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = ? AND round_to_par IS NOT NULL",
        (game_code, round_number),
    ).fetchone()[0]

    if collection_missing:
        verdict = READINESS_HARD_STOP
        reason = (
            f"{len(collection_missing)} player(s) show positive evidence of participation "
            f"(rounds_played >= round_number) but no round_number={round_number} row exists: "
            f"{collection_missing} — a real ingestion gap, not a tournament-status case."
        )
    elif field_codes and real_round_rows == 0:
        verdict = READINESS_HARD_STOP
        reason = (
            f"zero real round_number={round_number} rows exist for game_code={game_code!r} at all — "
            "official ingestion for this round has not happened yet."
        )
    elif unknown:
        verdict = READINESS_WARN
        reason = (
            f"{len(unknown)} player(s) could not be positively classified (no player_event row, or no round "
            f"score and no positive participation evidence either): {unknown}. No ingestion-failure evidence "
            "exists, so generation may proceed — these players must be reported explicitly, never silently dropped."
        )
    else:
        verdict = READINESS_GO
        reason = f"every one of {len(field_codes)} entry-field player(s) is accounted for by a legitimate, evidence-backed state."

    return FieldReadiness(
        round_number=round_number, field_size=len(field_codes), statuses=statuses, verdict=verdict,
        unknown_players=unknown, collection_missing_players=collection_missing, reason=reason,
    )
