"""4R FINAL PRE-BUILD Phase 6: course Deep Dive connection.

HONEST RESULT OF THIS PHASE, recorded in code rather than only in a
chat report: a full repository search (file names, JSON contents, HTML
evidence captures, and TOURNAMENT_SITE_REGISTRY.json's own venue field
for game_code 2026090003) found ZERO existing "Blackstone Icheon"
(블랙스톤 이천) Deep Dive data anywhere in this repository --
TOURNAMENT_SITE_REGISTRY.json's entry for 2026090003 has venue=null,
holes=null, format=null, and no course-level artifact (field average
score, birdie+/bogey+ rate, Danger Zone, hole difficulty) exists for
ANY game_code yet. `previews/website-v2-phase1/deep-dive/` is a
fixture-only page shell for a fictional 2027 tournament, not real
course data.

Per the mission's own hard rule ("근거가 없으면 PASS 처리하지 않는다"),
this module does NOT fabricate a connection. It defines the lookup
contract a real course Deep Dive artifact would need to satisfy
(so a future real ingestion just has to write that file, no code
change here), and reports BLOCKED with the exact missing artifact path
when -- as today -- none exists.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from klpga.tournament_context import TournamentContext, CONTENT_DIR

COURSE_DEEP_DIVE_ARTIFACT_TYPE = "course_deep_dive"

REQUIRED_FIELDS = (
    "field_average_relative_score",
    "birdie_plus_rate",
    "bogey_plus_rate",
    "attacking_holes",
    "defensive_holes",
    "danger_zone_holes",
    "hole_difficulty",
)


@dataclass(frozen=True)
class CourseDeepDiveConnection:
    status: str  # "CONNECTED" or "BLOCKED"
    game_code: str
    expected_artifact_path: str
    reason: Optional[str] = None
    data: Optional[dict] = None


def _deep_dive_path(context: TournamentContext) -> Path:
    return context.artifact_path(COURSE_DEEP_DIVE_ARTIFACT_TYPE)


def connect_course_deep_dive(context: TournamentContext) -> CourseDeepDiveConnection:
    """Never invents course data. Looks ONLY for a real, already-sourced
    artifact at the generic artifact_path -- if absent, or missing any
    REQUIRED_FIELDS, returns BLOCKED with the exact reason rather than
    a partial/guessed connection."""
    path = _deep_dive_path(context)
    if not path.is_file():
        return CourseDeepDiveConnection(
            status="BLOCKED",
            game_code=context.game_code,
            expected_artifact_path=str(path),
            reason=(
                f"no course Deep Dive artifact found at {path} -- no venue/course data "
                f"is recorded for game_code={context.game_code!r} anywhere in this repository "
                "(TOURNAMENT_SITE_REGISTRY.json venue/holes/format are all null); a real "
                "Deep Dive connection requires this artifact to exist first, never a guess"
            ),
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        return CourseDeepDiveConnection(
            status="BLOCKED",
            game_code=context.game_code,
            expected_artifact_path=str(path),
            reason=f"course Deep Dive artifact at {path} is missing required field(s): {missing}",
        )
    return CourseDeepDiveConnection(
        status="CONNECTED",
        game_code=context.game_code,
        expected_artifact_path=str(path),
        data=data,
    )
