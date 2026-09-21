"""NEO Expected Strokes -- official course/hole yardage ingestion
contract (design only, per 2026-09-21 red-team decision item 4).

This module does NOT populate any real yardage data. It does NOT
fetch anything over the network. It does NOT back-calculate a first
shot's start_distance_yd from shot_distance_yd + end_distance_yd, and
it does NOT propose TEE+PAR+HOLE_ID as a substitute Expected Strokes
state -- that proposal was explicitly rejected this round.

What it defines: the schema a REAL, evidence-backed official
yardage source must populate before any first-shot start_distance_yd
can be filled in. Until such a source exists and is ingested, every
first-shot row's start_distance_yd stays exactly what
build_transition_dataset() already leaves it: None.

Schema fields (per explicit instruction):
    game_code, round, hole, par, yardage, source, source_hash

Repo-search finding for "what official KLPGA source should populate
this" (2026-09-21, this QA branch's own reachable tree -- see caveat
below): no such source currently exists ANYWHERE in the files reachable
from this branch's history. Checked:
  - klpga.collectors.score_record (parse_score_record_html /
    parse_score_record_hole_by_hole / parse_score_record_hole_par):
    the real scoreRecord page carries per-hole PAR (see
    parse_score_record_hole_par, already used by this Phase 1 pipeline)
    but no yardage row anywhere in its real, captured markup.
  - klpga.discovery.response_schema: has a KIND_DISTANCE field-kind
    classifier (matches "거리"/"야드" in a label), but this classifies
    generic per-round statistical fields (e.g. driving distance
    averages) discovered during site exploration -- it is not a
    per-hole course yardage source and never has been.
  - klpga.collectors.cmpro_shots (the shot-level source this whole
    Phase 1 dataset is built from): carries no course/hole yardage
    field at all -- only per-shot start/end distance and lie.
  - No TOURNAMENT_SITE_REGISTRY.json-style course/venue artifact, and
    no course_deep_dive-style artifact, exists anywhere in this
    branch's reachable tree for game_code 2026090002.

CAVEAT (evidentiary correction, 2026-09-21): an earlier report in this
review cited `klpga.neo_win.final_course_deep_dive`'s own "BLOCKED"
contract and `klpga.official_tournament_warehouse.build_round_exposure()`
as evidence. Both modules are REAL and exist in this GitHub repository,
but on OTHER branches (e.g. neo-website-v2 and several
feat/hana-2026090002-* branches) that are NOT ancestors of this QA
branch (`cmpro-qa-review-*`) -- `git merge-base --is-ancestor` confirms
neither commit that introduced them is reachable from this branch's
HEAD. final_course_deep_dive's BLOCKED result is additionally scoped to
a different tournament (game_code 2026090003) and to course-level
aggregate stats (field average score, birdie/bogey rate, danger-zone
holes, hole difficulty) -- it does not even have a "yardage" field in
its REQUIRED_FIELDS. official_tournament_warehouse.build_round_exposure()
does have a real `"yardage": r.get("yardage")` pass-through line, but it
was not re-verified this round whether any real caller on that other
branch ever populates a real value through it. Citing cross-branch
files as if they were verified within this QA branch's own search was
imprecise and is corrected here. The conclusion itself (no populated
per-hole yardage source currently reachable from this branch) still
holds for everything actually searched above; it is not re-asserted as
a repo-wide fact across every branch without further verification.

Investigation, not implementation, per explicit instruction: identifying
which real KLPGA-operated endpoint (if any) could someday serve
per-hole yardage -- e.g. a hypothetical course/tee-info page separate
from scoreRecord/cmpro -- has not been attempted; no such endpoint has
been observed anywhere in this collection's real HTTP traffic capture.
A future collection cycle would need to discover and evidence one
before this table can be populated for real.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

SCHEMA = """CREATE TABLE IF NOT EXISTS course_yardage(
    game_code TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    hole INTEGER NOT NULL,
    par INTEGER,
    yardage_yd REAL,
    source TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    PRIMARY KEY(game_code, round_number, hole)
);"""


@dataclass(frozen=True)
class CourseYardageRecord:
    game_code: str
    round_number: int
    hole: int
    par: Optional[int]
    yardage_yd: Optional[float]
    source: str
    source_hash: str


def load_course_yardage(
    conn: sqlite3.Connection, game_code: str
) -> dict[tuple[int, int], CourseYardageRecord]:
    """READ ONLY. Returns {} if the course_yardage table does not exist
    or has no rows for game_code -- this is the expected, current state
    for every real collection today (no real ingestion has ever
    populated this table). Never fabricates a record; never falls back
    to a computed/estimated yardage."""
    try:
        cur = conn.execute(
            "SELECT round_number,hole,par,yardage_yd,source,source_hash "
            "FROM course_yardage WHERE game_code=?",
            (game_code,),
        )
    except sqlite3.OperationalError:
        return {}
    out: dict[tuple[int, int], CourseYardageRecord] = {}
    for rnd, hole, par, yardage_yd, source, source_hash in cur:
        out[(rnd, hole)] = CourseYardageRecord(
            game_code=game_code, round_number=rnd, hole=hole, par=par,
            yardage_yd=yardage_yd, source=source, source_hash=source_hash,
        )
    return out
