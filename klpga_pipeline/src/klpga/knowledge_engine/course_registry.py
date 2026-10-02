"""Phase 0 of the Knowledge Engine course/tournament split (2026-10-02
mission): resolves a game_code to a course_id via the real,
operator-curated COURSE_REGISTRY.json. Purely additive -- nothing in
this repository imports this module yet (confirmed: it is wired into
no consumer). See content/website_v2/knowledge_engine/MIGRATION_PLAN.md
for the phased plan to actually have Player Intelligence/PRE/Deep Dive
prefer the course_id-keyed Course Warehouse this enables.

Never guesses a course_id for a game_code the registry doesn't cover --
returns None, same "never fabricate" discipline as every other reader
in this project.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # klpga_pipeline/
_REGISTRY_PATH = _ROOT / "content" / "website_v2" / "knowledge_engine" / "course" / "COURSE_REGISTRY.json"


def course_registry() -> list[dict]:
    """The real registry's 'entries' list, or [] if the registry file
    doesn't exist yet (never fabricated)."""
    if not _REGISTRY_PATH.is_file():
        return []
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8")).get("entries", [])


def resolve_course_id(game_code: str) -> str | None:
    """The real course_id for this game_code per COURSE_REGISTRY.json,
    or None if this game_code isn't in the registry yet -- never a
    guessed/derived course_id."""
    for entry in course_registry():
        if game_code in entry.get("game_codes", []):
            return entry["course_id"]
    return None


def course_warehouse_dir(course_id: str) -> Path:
    """Where this course_id's Course Warehouse files
    (course_layout.json, hole_layout.json, landing_distribution.json,
    course_dna.json, pin_history.json) live."""
    return _ROOT / "content" / "website_v2" / "knowledge_engine" / "course" / course_id


def tournament_warehouse_dir(game_code: str) -> Path:
    """Where this game_code's Tournament Warehouse files
    (leaderboard.json, sg.json, pin_position.json, hole_difficulty.json)
    live."""
    return _ROOT / "content" / "website_v2" / "knowledge_engine" / "tournament" / game_code
