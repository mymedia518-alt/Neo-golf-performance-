"""NEO Expected Strokes -- Phase 1: shot-level transition dataset,
state-continuity validation, and lie taxonomy.

Reads ONLY from an already-open sqlite3.Connection (callers open it
however they need, e.g. read-only via `file:<path>?mode=ro`) -- this
module never opens, writes to, or migrates any database itself.

Eventual SG formula this dataset is built to support (NOT computed
anywhere in this module -- Phase 1 is data validation, not modeling):

    SG_shot = E(start_state) - 1 - E(end_state)
    E(end_state) = 0 when the shot holed out.

E() itself (Expected Strokes as a function of lie+distance+par) is a
Phase 2+ deliverable once a real model has been chosen and validated
against held-out data -- see build_expected_strokes_dataset.py's
[EXPECTED STROKES MODEL OPTIONS] output for the candidate approaches
under consideration.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------
# Task C: lie taxonomy. RAW_LIE_VALUES_FROM_PARSER is the COMPLETE set
# of strings klpga.collectors.cmpro_shots.parse_cmpro_shots can ever
# produce -- confirmed by reading its own source (not guessed):
#   end_lie: `next((x for x in ("페어웨이","러프","그린","벙커","홀인")
#             if x in text), "")` -- a literal 5-word substring scan,
#             falling back to "" for anything else.
#   start_lie: "티" hardcoded for a hole's first parsed shot
#             (`"티" if previous is None else previous.end_lie`),
#             else copied from the previous shot's own end_lie.
# The "" fallback is a REAL, CODE-CONFIRMED GAP: any lie text the
# parser doesn't recognize (e.g. a cart-path or unplayable-lie
# ruling, if cmpro ever renders one) silently collapses to "" rather
# than being preserved or raising. taxonomy_gaps() below checks a
# real collection's own distinct values against this list rather than
# assuming it is exhaustive for a specific real capture.
# ---------------------------------------------------------------
RAW_LIE_VALUES_FROM_PARSER = ("티", "페어웨이", "러프", "그린", "벙커", "홀인", "")

# 2026-09-21 red-team decision: "" is NOT a golf lie and must not be
# treated as one. Earlier this mapped "" -> RECOVERY_OTHER, implying a
# real (if unclassified) physical state. Real evidence against that:
# 641 real blank-start rows on 2026090002 span distance 0.0-567.4yd,
# include repeated-unchanged-distance chains, and every one of the 17
# real zero_distance_ambiguous rows belongs to a blank-state chain --
# a single "recovery lie" cannot explain that range. "" now maps to
# UNKNOWN: the parser's own unrecognized-text catch-all (see the block
# comment above) with no claim about what physical state it represents.
# The raw "" value itself is never discarded -- see lie_distribution()
# and TransitionRow.start_lie/end_lie, which always carry the raw text.
LIE_TAXONOMY = {
    "티": "TEE",
    "페어웨이": "FAIRWAY",
    "러프": "ROUGH",
    "벙커": "SAND",
    "그린": "GREEN",
    "홀인": "HOLED",
    "": "UNKNOWN",
}

# 2026-09-21 red-team decision: real bunker-start evidence (74 rows on
# 2026090002: par_4=46/par_5=28, shot_no 2=66/3=7/4=1) shows a distance
# range inconsistent with a simple greenside-sand assumption. SAND is
# kept as a real, distinct taxonomy bucket (not merged into UNKNOWN or
# discarded) but flagged sparse: too few observations, and too broad a
# distance range, to fit an independent SAND expected-strokes curve
# yet. Used by investigations.model_eligibility_summary's SAND_SPARSE
# flag -- never asserted as an error in the underlying data.
SPARSE_LIES = frozenset({"벙커"})


def taxonomy_gaps(conn: sqlite3.Connection, game_code: str) -> dict:
    """READ ONLY. Queries the real DB's own distinct start_lie/end_lie
    values for game_code and reports any value LIE_TAXONOMY does not
    cover -- never assumes RAW_LIE_VALUES_FROM_PARSER is exhaustive
    for a specific real collection; only the parser's own source
    guarantees that for whichever collector build actually ran."""
    distinct_start = {r[0] for r in conn.execute(
        "SELECT DISTINCT start_lie FROM shot_event WHERE game_code=?", (game_code,))}
    distinct_end = {r[0] for r in conn.execute(
        "SELECT DISTINCT end_lie FROM shot_event WHERE game_code=?", (game_code,))}
    all_values = distinct_start | distinct_end
    unmapped = sorted(v for v in all_values if v is not None and v not in LIE_TAXONOMY)
    return {
        "distinct_start_lie": sorted(v for v in distinct_start if v is not None),
        "distinct_end_lie": sorted(v for v in distinct_end if v is not None),
        "unmapped_values": unmapped,
    }


# ---------------------------------------------------------------
# Task A: transition dataset.
# ---------------------------------------------------------------

@dataclass(frozen=True)
class TransitionRow:
    game_code: str
    player_code: str
    player_name: str
    round_number: int
    hole: int
    shot_no: int
    par: Optional[int]
    start_distance_yd: Optional[float]
    start_lie: Optional[str]
    end_distance_yd: float
    end_lie: str
    holed: bool
    zero_distance_ambiguous: bool
    official_hole_score: Optional[int]


def build_transition_dataset(
    conn: sqlite3.Connection,
    game_code: str,
    *,
    par_by_round_hole: Optional[dict[tuple[int, int], int]] = None,
    official_score_by_player_round_hole: Optional[dict[tuple[str, int, int], int]] = None,
) -> list[TransitionRow]:
    """READ ONLY. Ordered by (player_code, round_number, hole, shot_no)
    -- required by check_state_continuity below. par_by_round_hole and
    official_score_by_player_round_hole are optional real evidence
    (e.g. from klpga.collectors.score_record.parse_score_record_hole_par
    / parse_score_record_hole_by_hole against a real captured page);
    without them every row's par/official_hole_score is None -- never
    guessed, per Task D's own NULL-if-no-evidence rule applied
    consistently here too."""
    rows: list[TransitionRow] = []
    cur = conn.execute(
        "SELECT game_code,player_code,player_name,round_number,hole,shot_no,"
        "start_distance_yd,start_lie,end_distance_yd,end_lie FROM shot_event "
        "WHERE game_code=? ORDER BY player_code,round_number,hole,shot_no",
        (game_code,),
    )
    for gc, pc, pn, rnd, hole, shot_no, sdist, slie, edist, elie in cur:
        par = (par_by_round_hole or {}).get((rnd, hole))
        official = (official_score_by_player_round_hole or {}).get((pn, rnd, hole))
        # STRICT: holed is determined ONLY from the real end_lie=="홀인"
        # evidence, never from end_distance_yd==0.0 alone -- a real,
        # DB-confirmed finding (17 rows on the real 2026090002 data)
        # showed end_distance_yd==0.0 with a end_lie that is NOT "홀인",
        # meaning distance-zero alone is not reliable holed evidence.
        # (klpga.collectors.cmpro_shots.CmproShot.hole_out DOES use the
        # OR-with-distance fallback -- that is a QA-gate heuristic for
        # validate_cmpro_hole's own "last shot looks holed out" check,
        # a different, looser purpose than this dataset's state model.)
        holed = (elie == "홀인")
        zero_distance_ambiguous = (edist == 0.0) and (elie != "홀인")
        rows.append(TransitionRow(
            game_code=gc, player_code=pc, player_name=pn, round_number=rnd, hole=hole,
            shot_no=shot_no, par=par, start_distance_yd=sdist, start_lie=slie,
            end_distance_yd=edist, end_lie=elie, holed=holed,
            zero_distance_ambiguous=zero_distance_ambiguous, official_hole_score=official,
        ))
    return rows


# ---------------------------------------------------------------
# Task B: state continuity.
# ---------------------------------------------------------------

@dataclass(frozen=True)
class ContinuityMismatch:
    player_code: str
    round_number: int
    hole: int
    shot_no: int
    reason: str  # "distance", "lie", or "distance+lie"
    previous_end_distance: Optional[float]
    current_start_distance: Optional[float]
    previous_end_lie: Optional[str]
    current_start_lie: Optional[str]


def check_state_continuity(rows: list[TransitionRow]) -> list[ContinuityMismatch]:
    """Shot n>1's start state must equal shot n-1's end state, WITHIN
    the same (player_code, round_number, hole). shot_no==1 is never
    checked here -- its start state is Task D's separate, still-
    unresolved problem, not a continuity violation. `rows` must
    already be ordered by (player_code,round_number,hole,shot_no) --
    build_transition_dataset's own query guarantees this."""
    mismatches: list[ContinuityMismatch] = []
    prev: Optional[TransitionRow] = None
    for row in rows:
        same_hole = (
            prev is not None
            and prev.player_code == row.player_code
            and prev.round_number == row.round_number
            and prev.hole == row.hole
        )
        if same_hole:
            reasons = []
            if row.start_distance_yd != prev.end_distance_yd:
                reasons.append("distance")
            if row.start_lie != prev.end_lie:
                reasons.append("lie")
            if reasons:
                mismatches.append(ContinuityMismatch(
                    player_code=row.player_code, round_number=row.round_number, hole=row.hole,
                    shot_no=row.shot_no, reason="+".join(reasons),
                    previous_end_distance=prev.end_distance_yd, current_start_distance=row.start_distance_yd,
                    previous_end_lie=prev.end_lie, current_start_lie=row.start_lie,
                ))
        prev = row
    return mismatches


# ---------------------------------------------------------------
# Task E: distribution.
# ---------------------------------------------------------------

def _percentile(sorted_values: list[float], p: float) -> Optional[float]:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def distance_stats(values: list[float]) -> dict:
    if not values:
        return {"shots": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    s = sorted(values)
    return {
        "shots": len(s), "min": s[0],
        "p25": _percentile(s, 0.25), "median": _percentile(s, 0.5), "p75": _percentile(s, 0.75),
        "max": s[-1],
    }


def lie_distribution(rows: list[TransitionRow]) -> dict[str, dict]:
    """shots/distance stats grouped by the ORIGINAL raw start_lie value
    (never the mapped taxonomy label alone -- the raw value is always
    preserved per Task C's own requirement)."""
    by_lie: dict[str, list[float]] = {}
    for row in rows:
        if row.start_distance_yd is None:
            continue
        by_lie.setdefault(row.start_lie or "", []).append(row.start_distance_yd)
    return {lie: distance_stats(vals) for lie, vals in sorted(by_lie.items())}


def par_distribution(rows: list[TransitionRow]) -> dict:
    """Shot-count distribution by par (3/4/5/other), and BLOCKED for
    any hole whose par is unknown (par_by_round_hole was not supplied
    to build_transition_dataset) -- never assumed from hole number or
    guessed from shot count."""
    by_par: dict[str, int] = {}
    unknown = 0
    for row in rows:
        if row.par is None:
            unknown += 1
            continue
        key = f"par_{row.par}" if row.par in (3, 4, 5) else f"par_other_{row.par}"
        by_par[key] = by_par.get(key, 0) + 1
    return {"by_par": dict(sorted(by_par.items())), "par_unknown_shots": unknown}
