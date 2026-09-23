"""Renders the question-organized Player Intelligence Report for
playerCode=10097 ONLY -- the Gold Standard reference implementation.

Integration only, never redesign: reads the already-generated
content/website_v2/knowledge_engine/player_intelligence/10097/
PLAYER_INTELLIGENCE_REPORT.json (built by
scripts/build_10097_player_intelligence_report.py, itself built entirely
from the frozen Knowledge Engine's own already-computed output) and
renders it as HTML. Never calculates anything itself.

This module is called ONLY for player_id == "10097" (see
player_intelligence_v2.build_or_placeholder's special case). Every other
player continues to render through the ordinary 13-section, stat-organized
render_player_intelligence_v2_html() path, completely untouched.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR

REPORT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / "10097" / "PLAYER_INTELLIGENCE_REPORT.json"

_CONFIDENCE_CHIP_CLASS = {
    "HIGH": "label-chip--positive",
    "MEDIUM": "label-chip",
    "LOW": "label-chip--negative",
    "UNKNOWN": "label-chip--negative",
}

_DURABILITY_LABEL = {
    "LONG_TERM_CHARACTERISTIC": "Long-term characteristic",
    "RECENT_TREND": "Recent trend — could change with another season",
    "CONFIRMED_HISTORICAL_EVENT": "Confirmed event — already happened",
}


def load_report_cached() -> Optional[dict]:
    if not REPORT_PATH.exists():
        return None
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _protocol_html(protocol: dict) -> str:
    rows = [
        ("Metric", protocol["metric"]),
        ("Source", protocol["source"]),
        ("Normal range", protocol["normal_range"]),
        ("Warning threshold", protocol["warning_threshold"]),
        ("Next review", protocol["next_review"]),
    ]
    items = "".join(f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in rows)
    return f'<dl class="piq-protocol">{items}</dl>'


def _question_card(q: dict) -> str:
    evidence_items = "".join(f"<li>{escape(e)}</li>" for e in q["evidence"])
    chip_class = _CONFIDENCE_CHIP_CLASS.get(q["confidence"], "label-chip")
    durability_label = _DURABILITY_LABEL.get(q["durability"], q["durability"])
    audit = (
        '<div class="piq-audit">'
        f'<span class="label-chip">Evidence Score {q["evidence_score"]}/100</span>'
        f'<span class="label-chip">Sample Size {q["sample_size"]}</span>'
        f'<span class="label-chip {chip_class}">Confidence: {escape(q["confidence"])}</span>'
        f'<span class="label-chip">{escape(durability_label)}</span>'
        "</div>"
    )
    body = (
        f'<p class="piq-step"><span class="piq-label">FACT</span>{escape(q["fact"])}</p>'
        f'<p class="piq-step-label piq-label-standalone">EVIDENCE</p>'
        f'<ul class="piq-evidence-list">{evidence_items}</ul>'
        f'<p class="piq-step"><span class="piq-label">ANALYSIS</span>{escape(q["analysis"])}</p>'
        f'<p class="piq-step piq-conclusion"><span class="piq-label">CONCLUSION</span>{escape(q["conclusion"])}</p>'
        f'<p class="piq-step"><span class="piq-label">WHY IT MATTERS</span>{escape(q["why_it_matters"])}</p>'
        f'<div class="piq-brief">'
        f'<p><strong>Player takeaway.</strong> {escape(q["player_takeaway"])}</p>'
        f'<p><strong>Coach focus.</strong> {escape(q["coach_focus"])}</p>'
        f'<p><strong>Durability.</strong> {escape(q["durability_reasoning"])}</p>'
        "</div>"
        f"{audit}"
        f'<p class="piq-why-this-matters"><span class="piq-label">WHY THIS MATTERS</span>{escape(q["why_this_matters"])}</p>'
        f'<p class="piq-action"><span class="piq-label">ACTION</span>{escape(q["action"])}</p>'
        f'<p class="piq-step-label piq-label-standalone">MONITORING PROTOCOL</p>'
        f'{_protocol_html(q["monitoring_protocol"])}'
    )
    return (
        f'<details class="evidence-detail pi-section" open>'
        f'<summary class="section-heading"><h2>{escape(q["question"])}</h2></summary>'
        f'<div class="pi-section__body">{body}</div>'
        f"</details>"
    )


def _excluded_html(excluded: list) -> str:
    if not excluded:
        return ""
    items = "".join(
        f'<li><strong>{escape(x["question"])}</strong> — {escape(x["reason_excluded"])} (sample size: {x["sample_size"]})</li>' for x in excluded
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-excluded">'
        '<summary class="section-heading"><h2>Questions Considered but Not Answered</h2></summary>'
        '<div class="pi-section__body"><p class="pi-empty">'
        "These are real questions this report considered. Each was dropped instead of guessed at, "
        "because the evidence behind it could not clear the bar this report holds every conclusion to."
        f'</p><ul class="piq-excluded-list">{items}</ul></div>'
        "</details>"
    )


def _hero_html(doc: dict) -> str:
    return (
        '<header class="pi-hero hero-data">'
        '<p class="section-label">PLAYER INTELLIGENCE — GOLD STANDARD REPORT</p>'
        f'<h1>{escape(doc["player_name"])}</h1>'
        f'<p class="pi-hero__meta">{len(doc["questions"])} questions answered, each traced FACT → EVIDENCE → ANALYSIS → CONCLUSION.</p>'
        "</header>"
    )


def render_question_report_html(doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None) -> str:
    """Pure function: report JSON in, page body HTML out."""
    from klpga.website_v2.player_intelligence_v2 import prev_next_html

    cards = "".join(_question_card(q) for q in doc["questions"])
    return prev_next_html(prev_link, next_link) + _hero_html(doc) + cards + _excluded_html(doc.get("questions_considered_but_unsupported", []))
