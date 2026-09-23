"""Tournament DNA Generator (Sprint 4).

Writes tournament_dna.generate_tournament_dna()'s output to
content/website_v2/knowledge_engine/tournament_dna/<game_code>/TournamentDNA.json.
Never computes anything itself -- assembly and validation only, the
same division of labor Sprint 2's player_intelligence_generator.py
uses over the frozen knowledge_engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR, load_tournament_context

from . import tournament_dna as tdna

OUTPUT_ROOT = CONTENT_DIR / "knowledge_engine" / "tournament_dna"
OUTPUT_FILENAME = "TournamentDNA.json"

REQUIRED_SECTIONS = (
    "identity",
    "course_dna",
    "winning_profile",
    "field_composition",
    "best_fits",
    "danger_holes",
    "opportunity_holes",
    "story",
    "watch_list",
    "verdict",
)


def validate_tournament_dna_document(doc: dict) -> list:
    problems = []
    for section in REQUIRED_SECTIONS:
        if section not in doc:
            problems.append(f"missing required section: {section}")

    identity = doc.get("identity") or {}
    if not identity.get("game_code"):
        problems.append("identity.game_code is missing")
    if not identity.get("tournament_name"):
        problems.append("identity.tournament_name is missing")

    for i, fact in enumerate(doc.get("story", [])):
        if not isinstance(fact, str) or not fact.strip():
            problems.append(f"story[{i}] is not a real sentence")

    verdict = (doc.get("verdict") or {}).get("summary", "")
    if verdict and verdict.count(".") > 2:
        problems.append("verdict has more than 2 sentences")

    return problems


@dataclass(frozen=True)
class GenerationResult:
    game_code: str
    status: str  # "written" | "skipped" | "error"
    path: Optional[Path] = None
    error: Optional[str] = None


def output_path(game_code: str) -> Path:
    return OUTPUT_ROOT / str(game_code) / OUTPUT_FILENAME


def generate_one(game_code: str, *, force: bool = False) -> GenerationResult:
    try:
        context = load_tournament_context(game_code)
        path = output_path(context.game_code)

        result = tdna.generate_tournament_dna(context)
        doc = tdna.to_json_dict(result)

        problems = validate_tournament_dna_document(doc)
        if problems:
            return GenerationResult(game_code=game_code, status="error", error="; ".join(problems))

        if not force and path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing_no_ts = {k: v for k, v in existing.items() if k != "generated_at"}
            new_no_ts = {k: v for k, v in doc.items() if k != "generated_at"}
            if existing_no_ts == new_no_ts:
                return GenerationResult(game_code=game_code, status="skipped", path=path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return GenerationResult(game_code=game_code, status="written", path=path)
    except Exception as exc:  # one tournament's failure must not raise past the caller
        return GenerationResult(game_code=game_code, status="error", error=str(exc))


def main(argv: Optional[list] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a tournament's TournamentDNA.json.")
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    result = generate_one(args.game_code, force=args.force)
    print(f"{result.game_code}: {result.status}" + (f" ({result.error})" if result.error else f" ({result.path})" if result.path else ""))
    return 0 if result.status != "error" else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
