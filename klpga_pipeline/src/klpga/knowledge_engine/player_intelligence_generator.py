"""Automatic Player Intelligence Generator.

Input: Knowledge Engine -> every player -> Player Intelligence JSON.
Output: content/website_v2/knowledge_engine/player_intelligence/<id>/latest.json
        content/website_v2/knowledge_engine/player_intelligence/<id>/history/<game_code>.json

Every player is generated automatically from knowledge_engine.py. No
handwritten content, no player-specific exceptions. This module never
computes a new statistic or reason itself -- it only assembles the
Knowledge Engine's own output into the document schema and writes it.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR, TournamentContext, load_tournament_context

from . import knowledge_engine as ke

SCHEMA_VERSION = "player_intelligence_generator_v2"
OUTPUT_ROOT = ke.PLAYER_INTELLIGENCE_DIR
POPULATION_FILE = "HOME_REGULAR_TOUR_PLAYER_MASTER.json"

MAX_STRENGTHS = 5
MAX_WEAKNESSES = 5

REQUIRED_SECTIONS = (
    "hero",
    "player_type",
    "player_dna",
    "current_form",
    "shot_profile",
    "course_fit",
    "strengths",
    "weaknesses",
    "why_wins",
    "why_loses",
    "evolution",
    "neo_verdict",
)

_WEAK_PERCENTILE_CEILING = 100.0 - ke.rules.STRONG_PERCENTILE  # 25.0


# ---------------------------------------------------------------------------
# Section builders (each one only assembles already-computed Evidence /
# rule output -- never a new calculation)
# ---------------------------------------------------------------------------


def build_hero(player_id: str, evidence: ke.Evidence) -> dict:
    return {
        "player_id": player_id,
        "player_name": evidence.player_name,
        "current_season": evidence.current_season,
        "sample_count": evidence.sample_count,
    }


def _percentile_label_pairs(evidence: ke.Evidence):
    for key, pctl in evidence.field_percentiles.items():
        label = ke.rules.FIELD_METRIC_LABELS.get(key, key)
        yield key, label, pctl


def build_player_dna(evidence: ke.Evidence) -> dict:
    axes = []
    for key in ("sg_ott", "sg_app", "sg_arg", "sg_putt"):
        pctl = evidence.field_percentiles.get(key)
        if pctl is None:
            continue
        axes.append({"key": key, "label": ke.rules.SG_COMPONENT_LABELS.get(f"avg_{key.split('_')[1]}", key), "percentile": pctl})
    return {"axes": axes}


def build_current_form(evidence: ke.Evidence) -> dict:
    return {
        "recent_5_sg": evidence.recent_5_sg,
        "recent_10_sg": evidence.recent_10_sg,
        "long_term_sg": evidence.long_term_sg,
        "volatility": evidence.volatility,
        "rate_stats": dict(evidence.current_season_rate_stats),
    }


def build_shot_profile(evidence: ke.Evidence, *, existing_doc: Optional[dict] = None) -> dict:
    current = evidence.current_season_components
    return {
        "season": evidence.current_season,
        "avg_total": current.get("avg_total"),
        "avg_ott": current.get("avg_ott"),
        "avg_app": current.get("avg_app"),
        "avg_arg": current.get("avg_arg"),
        "avg_putt": current.get("avg_putt"),
    }


def build_course_fit(evidence: ke.Evidence, *, existing_doc: Optional[dict] = None) -> dict:
    return {"history": list(evidence.course_history)}


def build_strengths(evidence: ke.Evidence, max_strengths: int = MAX_STRENGTHS) -> list:
    items = [
        {"metric": key, "label": label, "percentile": pctl}
        for key, label, pctl in _percentile_label_pairs(evidence)
        if pctl is not None and pctl >= ke.rules.STRONG_PERCENTILE
    ]
    items.sort(key=lambda i: -i["percentile"])
    return items[:max_strengths]


def build_weaknesses(evidence: ke.Evidence, max_weaknesses: int = MAX_WEAKNESSES) -> list:
    items = [
        {"metric": key, "label": label, "percentile": pctl}
        for key, label, pctl in _percentile_label_pairs(evidence)
        if pctl is not None and pctl <= _WEAK_PERCENTILE_CEILING
    ]
    items.sort(key=lambda i: i["percentile"])
    return items[:max_weaknesses]


def build_neo_verdict(player_name: str, player_type: ke.PlayerTypeResult, why_wins: tuple, why_loses: tuple, evolution: ke.EvolutionResult) -> dict:
    """Exactly 2 sentences: FACT (who this player is) + INTERPRETATION
    (the single most relevant already-generated observation). Never a
    prediction -- every candidate sentence here is a present-tense
    description of already-computed evidence, the same sentences
    why_wins/why_loses/evolution already produce, never new wording."""
    fact = f"{player_name}은(는) {player_type.label_ko}({player_type.label_en}) 유형입니다."
    if why_wins:
        interpretation = why_wins[0].text
    elif why_loses:
        interpretation = why_loses[0].text
    else:
        interpretation = evolution.narrative
    return {"summary": f"{fact} {interpretation}"}


def _citation_dict(citation: ke.rules.Citation) -> dict:
    return ke._citation_to_dict(citation)


def _reason_dict(reason: ke.Reason) -> dict:
    return ke._reason_to_dict(reason)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def assemble_document(
    player_id: str,
    evidence: ke.Evidence,
    *,
    existing_doc: Optional[dict] = None,
    tournament_context: Optional[dict] = None,
    generated_at: Optional[str] = None,
) -> dict:
    player_type = ke.classify_player_type(evidence)
    why_wins = ke.generate_why_wins(evidence)
    why_loses = ke.generate_why_loses(evidence)
    evolution = ke.generate_evolution(evidence)

    doc = {
        "schema_version": SCHEMA_VERSION,
        "hero": build_hero(player_id, evidence),
        "player_type": {
            "key": player_type.key,
            "label_ko": player_type.label_ko,
            "label_en": player_type.label_en,
            "evidence_text": player_type.evidence_text,
            "citations": [_citation_dict(c) for c in player_type.citations],
        },
        "player_dna": build_player_dna(evidence),
        "current_form": build_current_form(evidence),
        "shot_profile": build_shot_profile(evidence, existing_doc=existing_doc),
        "course_fit": build_course_fit(evidence, existing_doc=existing_doc),
        "strengths": build_strengths(evidence),
        "weaknesses": build_weaknesses(evidence),
        "why_wins": [_reason_dict(r) for r in why_wins],
        "why_loses": [_reason_dict(r) for r in why_loses],
        "evolution": {
            "status": evolution.status,
            "narrative": evolution.narrative,
            "steps": [
                {
                    "season": s.season,
                    "avg_total": s.avg_total,
                    "delta_from_prev": s.delta_from_prev,
                    "strongest_component": s.strongest_component,
                    "weakest_component": s.weakest_component,
                }
                for s in evolution.steps
            ],
            "citations": [_citation_dict(c) for c in evolution.citations],
        },
        "neo_verdict": build_neo_verdict(evidence.player_name, player_type, why_wins, why_loses, evolution),
        "sources": list(evidence.sources),
        "_meta": {
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
            "tournament_game_code": (tournament_context or {}).get("game_code"),
        },
    }
    return doc


def validate_player_intelligence_document(doc: dict) -> list:
    problems = []
    for section in REQUIRED_SECTIONS:
        if section not in doc:
            problems.append(f"missing required section: {section}")

    for section_key in ("why_wins", "why_loses"):
        for i, item in enumerate(doc.get(section_key, [])):
            if not item.get("citations"):
                problems.append(f"{section_key}[{i}] has no citations")

    player_type = doc.get("player_type") or {}
    if player_type.get("key") != "balanced" and not player_type.get("citations"):
        problems.append("player_type has no citations")

    return problems


# ---------------------------------------------------------------------------
# Player universe / tournament roster
# ---------------------------------------------------------------------------


def discover_player_universe() -> list:
    path = CONTENT_DIR / POPULATION_FILE
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return [r["player_id"] for r in doc.get("records", []) if r.get("player_id")]


def players_for_tournament(context: TournamentContext) -> list:
    path = context.artifact_path("entry_snapshot")
    if not path.exists():
        raise FileNotFoundError(f"no entry_snapshot artifact for game_code={context.game_code!r}: {path}")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return [e["player_id"] for e in doc.get("entries", []) if e.get("player_id")]


# ---------------------------------------------------------------------------
# Incremental generation
# ---------------------------------------------------------------------------


def compute_input_signature(
    player_id: str,
    warehouse_doc: dict,
    sg_doc: dict,
    profile_doc: dict,
    existing_doc: Optional[dict],
    tournament_context: Optional[dict],
) -> str:
    """Hash of exactly the real input slices that can change this
    player's document: the player's own warehouse rows, SG-field row,
    profile-field row, and the tournament context. `existing_doc` is
    accepted (matching the generator's own signature) but deliberately
    NOT hashed -- it is the previous OUTPUT, not an input, and every
    section here is assembled purely from evidence; hashing it in would
    fold the previous run's own signature into the next one and the
    skip check would never converge."""
    del existing_doc
    warehouse_rows = ke._player_tournament_rows(player_id, warehouse_doc)
    sg_row = next((r for r in sg_doc.get("records", []) if r.get("playerCode") == player_id), None)
    profile_row = next((r for r in profile_doc.get("records", []) if r.get("playerCode") == player_id), None)
    payload = {
        "warehouse_rows": warehouse_rows,
        "sg_row": sg_row,
        "profile_row": profile_row,
        "tournament_name": (tournament_context or {}).get("tournament_name"),
        "game_code": (tournament_context or {}).get("game_code"),
    }
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GenerationResult:
    player_id: str
    status: str  # "written" | "skipped" | "error"
    path: Optional[Path] = None
    error: Optional[str] = None
    elapsed_seconds: float = 0.0


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def generate_one(
    player_id: str,
    *,
    tournament_context: Optional[dict] = None,
    force: bool = False,
    warehouse_doc: Optional[dict] = None,
    sg_doc: Optional[dict] = None,
    profile_doc: Optional[dict] = None,
) -> GenerationResult:
    start = time.monotonic()
    try:
        warehouse_doc = warehouse_doc if warehouse_doc is not None else ke.load_warehouse()
        sg_doc = sg_doc if sg_doc is not None else ke.load_sg_field()
        profile_doc = profile_doc if profile_doc is not None else ke.load_profile_field()

        player_dir = OUTPUT_ROOT / str(player_id)
        latest_path = player_dir / "latest.json"
        existing_doc = None
        if latest_path.exists():
            existing_doc = json.loads(latest_path.read_text(encoding="utf-8"))

        signature = compute_input_signature(player_id, warehouse_doc, sg_doc, profile_doc, existing_doc, tournament_context)

        if not force and existing_doc is not None and existing_doc.get("_meta", {}).get("input_signature") == signature:
            return GenerationResult(player_id=player_id, status="skipped", path=latest_path, elapsed_seconds=time.monotonic() - start)

        evidence = ke.build_evidence(player_id, tournament_context=tournament_context)
        generated_at = datetime.now(timezone.utc).isoformat()
        doc = assemble_document(player_id, evidence, existing_doc=existing_doc, tournament_context=tournament_context, generated_at=generated_at)
        doc["_meta"]["input_signature"] = signature

        problems = validate_player_intelligence_document(doc)
        if problems:
            return GenerationResult(player_id=player_id, status="error", error="; ".join(problems), elapsed_seconds=time.monotonic() - start)

        _write_json(latest_path, doc)

        game_code = (tournament_context or {}).get("game_code")
        if game_code:
            history_path = player_dir / "history" / f"{game_code}.json"
            _write_json(history_path, doc)

        return GenerationResult(player_id=player_id, status="written", path=latest_path, elapsed_seconds=time.monotonic() - start)
    except Exception as exc:  # never raise -- one player's failure must not abort a batch
        return GenerationResult(player_id=player_id, status="error", error=str(exc), elapsed_seconds=time.monotonic() - start)


@dataclass(frozen=True)
class BatchResult:
    results: tuple
    total_elapsed_seconds: float

    @property
    def written(self) -> tuple:
        return tuple(r for r in self.results if r.status == "written")

    @property
    def skipped(self) -> tuple:
        return tuple(r for r in self.results if r.status == "skipped")

    @property
    def errors(self) -> tuple:
        return tuple(r for r in self.results if r.status == "error")


def generate_many(
    player_ids: list,
    *,
    tournament_context: Optional[dict] = None,
    force: bool = False,
    max_workers: int = 8,
) -> BatchResult:
    start = time.monotonic()
    warehouse_doc = ke.load_warehouse()
    sg_doc = ke.load_sg_field()
    profile_doc = ke.load_profile_field()

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                generate_one,
                player_id,
                tournament_context=tournament_context,
                force=force,
                warehouse_doc=warehouse_doc,
                sg_doc=sg_doc,
                profile_doc=profile_doc,
            ): player_id
            for player_id in player_ids
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    return BatchResult(results=tuple(results), total_elapsed_seconds=time.monotonic() - start)


def regenerate_for_tournament(game_code: str, *, force: bool = False, max_workers: int = 8) -> BatchResult:
    context = load_tournament_context(game_code)
    player_ids = players_for_tournament(context)
    tournament_context = {"game_code": context.game_code, "tournament_name": context.tournament_name}
    return generate_many(player_ids, tournament_context=tournament_context, force=force, max_workers=max_workers)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate player intelligence JSON documents.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--player-id", help="Generate a single player.")
    target.add_argument("--all", action="store_true", help="Generate every player in the roster.")
    target.add_argument("--tournament", help="Regenerate every participating player for this game_code.")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.player_id:
        result = generate_one(args.player_id, force=args.force)
        print(f"{result.player_id}: {result.status}" + (f" ({result.error})" if result.error else ""))
        return 0 if result.status != "error" else 1

    if args.all:
        batch = generate_many(discover_player_universe(), force=args.force, max_workers=args.workers)
        print(f"written={len(batch.written)} skipped={len(batch.skipped)} errors={len(batch.errors)} elapsed={batch.total_elapsed_seconds:.1f}s")
        return 0 if not batch.errors else 1

    batch = regenerate_for_tournament(args.tournament, force=args.force, max_workers=args.workers)
    print(f"written={len(batch.written)} skipped={len(batch.skipped)} errors={len(batch.errors)} elapsed={batch.total_elapsed_seconds:.1f}s")
    return 0 if not batch.errors else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
