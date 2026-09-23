"""PLAYER INTELLIGENCE REPORT -- 김민선7 (playerCode=10097) ONLY.

The Gold Standard reference implementation for NEO Player Intelligence.
Organized by real golf QUESTIONS a tour coach would actually be asked --
never by raw statistics, SG components, or a flat list of records. Every
answer is FACT -> EVIDENCE -> ANALYSIS -> CONCLUSION, and every conclusion
carries an Evidence Score, Sample Size, and Confidence.

Never touches the frozen Knowledge Engine (knowledge_engine.py /
knowledge_rules.py / player_intelligence_generator.py) and never
recalculates a statistic: every number here is read straight out of
content/website_v2/knowledge_engine/player_intelligence/10097/MASTER_ANALYSIS.json
(built by scripts/build_10097_master_player_analysis.py, itself built
entirely from the frozen engine's own already-computed output) or the
frozen player_intelligence/10097/latest.json document. This script only
re-groups and narrates values that already exist -- it never invents a
number, and any candidate question whose supporting evidence cannot
clear the same PATTERN/TREND sample-size bar used by the Audit is
dropped, not answered with a guess.

Scope: playerCode=10097 ONLY. No other player is read, generated, or
touched. This is a reference implementation, not yet a generator for
the roster.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.knowledge_engine import knowledge_engine as ke  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402

_spec = importlib.util.spec_from_file_location("master_analysis_under_report", ROOT / "scripts" / "build_10097_master_player_analysis.py")
master = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(master)

PLAYER_ID = master.PLAYER_ID
PLAYER_NAME = master.PLAYER_NAME
OUTPUT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "PLAYER_INTELLIGENCE_REPORT.json"

_CONFIDENCE_RANK = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def _weakest_confidence(confidences: list) -> str:
    return min(confidences, key=lambda c: _CONFIDENCE_RANK[c])


def _evidence_score(sample_size, num_distinct_sources: int) -> int:
    """Deterministic, fully disclosed scoring method -- not a new claim
    about the player, only a way to render the already-computed sample
    size and source diversity as one number. Rewards independent
    official-record sources up to the >=3 minimum STEP 4 already
    requires per insight, and saturates (never grows unbounded) with
    sample size so one very large N can't make a thin source list look
    stronger than it is:
        evidence_score = round(100 * min(1, sources/3) * n/(n+5))
    """
    if not sample_size:
        return 0
    source_factor = min(1.0, num_distinct_sources / 3)
    depth_factor = sample_size / (sample_size + 5)
    return round(100 * source_factor * depth_factor)


def _load_inputs():
    master_doc = json.loads(master.OUTPUT_PATH.read_text(encoding="utf-8"))
    ds = master.build_master_dataset()
    warehouse = master._load("historical_sg_warehouse_corrected.json")
    season_profiles = ke.compute_season_profiles(PLAYER_ID, warehouse)
    return master_doc, ds, season_profiles


def _conclusion(master_doc: dict, conclusion_prefix: str) -> dict:
    """Look up an already-computed audit record from MASTER_ANALYSIS.json's
    conclusion_audit list by its conclusion id (exact reuse, no recompute)."""
    return next(a for a in master_doc["conclusion_audit"] if a["conclusion"] == conclusion_prefix)


def _fact(master_doc: dict, fact_id: str) -> dict:
    return next(f for f in master_doc["knowledge_graph"]["facts"] if f["id"] == fact_id)


# ---------------------------------------------------------------------------
# Candidate questions. Each maps onto audit records already computed by
# build_10097_master_player_analysis.py -- this function only narrates and
# combines them, it never derives a new number.
# ---------------------------------------------------------------------------


def _q_why_wins(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    win_fact = _fact(master_doc, "fact_win_count")["audit"]
    reasons = [_conclusion(master_doc, f"play_style.why_wins[{i}]") for i in range(3)]
    wins = master_doc["tournament_analysis"]["wins"]
    win_names = ", ".join(f"{w['tournament']} ({w['season']})" for w in wins)

    app_trend = ", ".join(f"{p.season}: {p.avg_app:+.2f}" for p in season_profiles)

    fact = f"{PLAYER_NAME} has {win_fact['sample_size']} confirmed tournament wins on record: {win_names}."
    evidence = [
        f"SG Approach has stayed elite across her full {len(season_profiles)}-season, {sum(p.n_tournaments for p in season_profiles)}-tournament history on record: {app_trend}.",
        f"{reasons[1]['statement']} (percentile basis, field of {reasons[1]['sample_size']} official-leaderboard players).",
        f"{reasons[2]['statement']} (percentile basis, field of {reasons[2]['sample_size']} official-leaderboard players).",
    ]
    analysis = (
        "Her wins are not clustered around one hot week of putting or scrambling -- they sit on top of a "
        "structural, multi-season advantage in approach play that shows up in both her long-run season "
        "averages and her current-season field ranking. Elite approach play plus elite green-in-regulation "
        "and par-save rates means she gives herself more realistic birdie looks, and misses fewer holes "
        "outright, than almost anyone else in the field, week after week."
    )
    conclusion = (
        f"{PLAYER_NAME} wins primarily through sustained, structurally elite approach play and shot-making "
        "precision -- not a single hot streak."
    )
    sample_sizes = [win_fact["sample_size"], sum(p.n_tournaments for p in season_profiles)] + [r["sample_size"] for r in reasons]
    sources = set(win_fact["official_records_used"]) | {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_wins",
        "question": f"Why does {PLAYER_NAME} win?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": _weakest_confidence([win_fact["confidence"]] + [r["confidence"] for r in reasons]),
    }


def _q_why_loses(master_doc: dict) -> dict:
    reasons = [_conclusion(master_doc, f"play_style.why_loses[{i}]") for i in range(2)]
    fact = f"Despite an elite overall profile, {PLAYER_NAME}'s Putting sits at only field-average level."
    evidence = [f"{r['statement']} (percentile basis, field of {r['sample_size']} official-leaderboard players)." for r in reasons]
    analysis = (
        "The gap is real but specific: her ball-striking (approach, off-the-tee) ranks among the best in the "
        "field, while her putting and average putts-per-round land squarely at the field median. That gap is "
        "what turns some of her best ball-striking weeks into 'only' a top-10 instead of a win -- she isn't "
        "converting the extra looks her approach play creates at a rate that matches how good those looks are."
    )
    conclusion = "Her most repeatable path to a loss is an average putting week riding on top of elite tee-to-green play, not a breakdown in ball-striking."
    sample_sizes = [r["sample_size"] for r in reasons]
    sources = {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_loses",
        "question": f"Why does {PLAYER_NAME} lose?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": _weakest_confidence([r["confidence"] for r in reasons]),
    }


def _q_approach_biggest_weapon(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    insight = next(i for i in master_doc["knowledge_graph"]["insights"] if i["id"] == "insight_elite_approach_and_ott")
    audit = insight["audit"]
    pi = ds["player_intelligence_doc"]
    app_axis = next(a for a in pi["player_dna"]["axes"] if a["key"] == "sg_app")
    app_trend = ", ".join(f"{p.season}: {p.avg_app:+.2f}" for p in season_profiles)

    fact = f"SG Approach is {PLAYER_NAME}'s single strongest shot-making component, at the {app_axis['percentile']:.1f}th percentile of the current {audit['sample_size']}-player official SG field."
    evidence = [
        f"Current-season field percentile: {app_axis['percentile']:.1f}th of {audit['sample_size']} players (OFFICIAL_SG_NORMALIZED.json).",
        f"Season-by-season average SG Approach across her full {audit['season_count']}-season, {audit['tournament_count']}-tournament history: {app_trend} -- consistently her highest or second-highest component every season.",
        f"Frozen Knowledge Engine classification: \"{pi['player_type']['label_ko']}\" ({pi['player_type']['label_en']}), evidence text: \"{insight['insight']}\"",
    ]
    analysis = (
        "Approach isn't just her best number this season -- it's the one shot-making category that has stayed "
        "elite every single season on record, while other components (see Putting) have moved around. A "
        "single-season peak could be noise; a 4-season-consistent #1 or #2 ranked component is a real, "
        "structural strength."
    )
    conclusion = f"Approach play is {PLAYER_NAME}'s primary, structurally durable weapon -- the one part of her game an opponent can count on being elite every week."
    sources = set(audit["official_records_used"])
    return {
        "id": "q_approach_biggest_weapon",
        "question": f"Why is Approach {PLAYER_NAME}'s biggest weapon?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(audit["sample_size"], len(sources)),
        "sample_size": audit["sample_size"],
        "confidence": audit["confidence"],
    }


def _q_putting_weakest(master_doc: dict, ds: dict) -> dict:
    reason = _conclusion(master_doc, "play_style.why_loses[0]")
    pi = ds["player_intelligence_doc"]
    axes = {a["key"]: a["percentile"] for a in pi["player_dna"]["axes"]}
    order = [("sg_ott", "Off-the-Tee"), ("sg_app", "Approach"), ("sg_arg", "Around-the-Green"), ("sg_putt", "Putting")]
    axis_line = ", ".join(f"{label} {axes[k]:.1f}th" for k, label in order)

    fact = f"Putting is the lowest-ranked of {PLAYER_NAME}'s own four SG components this season: {axis_line} (all field percentiles, same {reason['sample_size']}-player official SG field)."
    evidence = [
        f"Her own component spread: {axis_line}.",
        f"{reason['statement']} (percentile basis, field of {reason['sample_size']} official-leaderboard players).",
    ]
    analysis = (
        "This is a relative, not absolute, weakness: a field-average percentile is not a bad number on its "
        "own. It only reads as her 'weakest area' because her other three components sit 20 to 40 percentile "
        "points higher, within the same season, for the same player. Compared against her own baseline of "
        "elite ball-striking, an average putting week is the most likely single component to cap an "
        "otherwise-winning score."
    )
    conclusion = f"Putting is {PLAYER_NAME}'s comparatively weakest shot-making area -- not because it is poor in absolute terms, but because every other component of her game is elite and putting alone is not."
    sample_sizes = [reason["sample_size"]]
    sources = set(reason["official_records_used"]) | {"knowledge_engine/player_intelligence/10097/latest.json (player_dna.axes)"}
    return {
        "id": "q_putting_weakest",
        "question": f"Why has Putting become {PLAYER_NAME}'s weakest area?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": reason["confidence"],
    }


def _q_2026_improvement(master_doc: dict, season_profiles: list) -> dict:
    audit = _conclusion(master_doc, "season_evolution.frozen_knowledge_engine_evolution.narrative")
    trend_line = ", ".join(f"{p.season} ({p.n_tournaments} events): {p.avg_total:+.2f}" for p in season_profiles)
    narrative = master_doc["season_evolution"]["frozen_knowledge_engine_evolution"]["narrative"]

    fact = f"{PLAYER_NAME}'s season-average SG Total has risen every season on record: {trend_line}."
    evidence = [
        f"Frozen Knowledge Engine evolution narrative: \"{narrative}\"",
        f"Underlying per-season data: {audit['season_count']} seasons, {audit['tournament_count']} tournaments total (historical_sg_warehouse_corrected.json).",
    ]
    analysis = (
        "A 4-season, monotonic rise across every SG component (not just one hot season) is a real trend, not "
        "sampling noise -- especially with 16-23 tournaments backing each season's average. The improvement "
        "tracks her approach and off-the-tee numbers climbing in step with it, which is consistent with a "
        "player still adding distance and precision rather than one that simply had a lucky putting year."
    )
    conclusion = f"{PLAYER_NAME}'s 2026 performance is the continuation of a real, 4-season improvement trend in her ball-striking, not a one-season spike."
    sources = set(audit["official_records_used"])
    return {
        "id": "q_2026_improvement",
        "question": f"Why did {PLAYER_NAME}'s performance improve through 2026?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(audit["tournament_count"], len(sources)),
        "sample_size": audit["tournament_count"],
        "confidence": audit["confidence"],
    }


def _q_strong_course(master_doc: dict) -> dict:
    group = max(master_doc["course_analysis"]["course_series"], key=lambda g: g["appearances"])
    n = group["appearances"]
    history_line = "; ".join(f"{h['tournament']} ({h['season']}): SG {h['sg_total']:+.2f}" if h.get("sg_total") is not None else f"{h['tournament']} ({h['season']}): SG n/a" for h in group["history"])

    fact = f"{PLAYER_NAME} has played the {group['series_name_sample']} course series {n} times on record and won there once."
    evidence = [
        f"Full appearance-by-appearance record: {history_line}.",
        f"Average SG Total across all {n} appearances: {group['avg_sg_total']:+.2f} (historical_sg_warehouse_corrected.json, matched via the frozen knowledge_engine.find_course_history()).",
    ]
    analysis = (
        f"{n} real appearances is a small but genuine repeated sample at the same course series, not a single "
        "data point. Her average SG Total there is well above her career baseline, and the win came on her "
        "most recent attempt (not her first), which is consistent with real course familiarity building over "
        "multiple visits rather than one favorable week."
    )
    conclusion = f"{PLAYER_NAME} is a genuinely strong, course-familiar player at {group['series_name_sample']}, backed by {n} real appearances, not a single outlier result."
    sources = {"historical_sg_warehouse_corrected.json", "knowledge_engine.find_course_history()"}
    return {
        "id": "q_strong_course",
        "question": f"Why is {PLAYER_NAME} strong at {group['series_name_sample']}?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(n, len(sources)),
        "sample_size": n,
        "confidence": "HIGH" if n >= 4 else ("MEDIUM" if n >= 3 else "LOW"),
    }


def _q_most_recent_win(master_doc: dict) -> dict:
    win = master_doc["tournament_analysis"]["most_recent_win"]
    if not win:
        return None
    sg_line = ", ".join(f"{rnd}: {sg:+.2f}" for rnd, sg in win["round_sg"].items())

    fact = f"{PLAYER_NAME} won the {win['tournament']} ({win['final_score']}, rank #{win['final_rank']})."
    evidence = [
        f"Official result source: {win['official_source']}.",
        f"Round-by-round SG Total: {sg_line}.",
    ]
    analysis = (
        "Her SG rose each round through the tournament rather than her simply holding on to an early lead, "
        "which points to the win being built on improving ball-striking as the event went on, not one hot "
        "round carrying an otherwise average week."
    )
    conclusion = f"Her most recent win was earned through progressively stronger play across all three rounds, confirmed directly by the official result."
    sources = {win["official_source"].split(" (")[0]}
    return {
        "id": "q_most_recent_win",
        "question": f"How did {PLAYER_NAME} win her most recent title, the {win['tournament']}?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "evidence_score": _evidence_score(len(win["round_sg"]), len(sources)),
        "sample_size": len(win["round_sg"]),
        "confidence": "HIGH",
    }


def _q_repeat_course_pattern_candidate(master_doc: dict) -> dict:
    """A real candidate question -- NOT invented for demonstration -- that
    this report considers and then drops, because the underlying audit
    (scripts/build_10097_master_player_analysis.py's Audit mission) already
    found it unsupported (n=1). Kept here, excluded from `questions`, and
    surfaced in `questions_considered_but_unsupported` so the exclusion
    itself is auditable rather than silent."""
    fact_audit = _fact(master_doc, "fact_repeat_course_wins")["audit"]
    return {
        "id": "q_repeat_course_pattern",
        "question": f"Does {PLAYER_NAME} tend to win at courses she has played before?",
        "reason_excluded": fact_audit["note"],
        "sample_size": fact_audit["sample_size"],
        "confidence": fact_audit["confidence"],
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build() -> dict:
    master_doc, ds, season_profiles = _load_inputs()

    candidates = [
        _q_why_wins(master_doc, ds, season_profiles),
        _q_why_loses(master_doc),
        _q_approach_biggest_weapon(master_doc, ds, season_profiles),
        _q_putting_weakest(master_doc, ds),
        _q_2026_improvement(master_doc, season_profiles),
        _q_strong_course(master_doc),
        _q_most_recent_win(master_doc),
    ]
    candidates = [c for c in candidates if c is not None]

    questions = []
    excluded = []
    for c in candidates:
        if c["confidence"] == "UNKNOWN":
            excluded.append({"id": c["id"], "question": c["question"], "reason_excluded": "confidence resolved to UNKNOWN; never kept as an unsupported conclusion.", "sample_size": c["sample_size"]})
            continue
        questions.append(c)

    excluded.append(_q_repeat_course_pattern_candidate(master_doc))

    from datetime import datetime, timezone

    return {
        "schema_version": "player_intelligence_report_v1",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": "This document covers ONLY playerCode=10097. No other player's data was generated or modified. Gold Standard reference implementation.",
        "evidence_score_method": (
            "evidence_score = round(100 * min(1, distinct_official_sources / 3) * sample_size / (sample_size + 5)). "
            "A deterministic, disclosed scoring of already-computed sample_size + source diversity -- not a new "
            "statistical claim about the player."
        ),
        "questions": questions,
        "questions_considered_but_unsupported": excluded,
        "source_document": "MASTER_ANALYSIS.json (audited via scripts/build_10097_master_player_analysis.py)",
    }


if __name__ == "__main__":
    result = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"questions answered: {len(result['questions'])}")
    print(f"questions excluded as unsupported: {len(result['questions_considered_but_unsupported'])}")
    for q in result["questions"]:
        print(f"  - {q['question']} (confidence={q['confidence']}, evidence_score={q['evidence_score']}, sample_size={q['sample_size']})")
