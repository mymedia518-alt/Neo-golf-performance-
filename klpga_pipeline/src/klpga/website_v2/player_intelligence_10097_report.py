"""Renders the question-organized Player Intelligence Report for
playerCode=10097 ONLY -- the Gold Standard reference implementation.

Integration only, never redesign: reads the already-generated
content/website_v2/knowledge_engine/player_intelligence/10097/
PLAYER_INTELLIGENCE_REPORT.json (built by
scripts/build_10097_player_intelligence_report.py, itself built entirely
from the frozen Knowledge Engine's own already-computed output) and
renders it as HTML. Never calculates anything itself.

Localization, not translation: every UI label here comes from ONE
shared dictionary, player_intelligence_10097_terms.py (imported as
`terms`), the same one the report-generating script uses -- so the
wording is identical everywhere it appears. Only the standard golf
terms that dictionary defines stay in English; every structural label
(FACT/EVIDENCE/..., chip labels, status/durability labels, section
titles) is natural Korean, never a bare English UI label.

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
from klpga.website_v2 import player_intelligence_10097_terms as terms

REPORT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / "10097" / "PLAYER_INTELLIGENCE_REPORT.json"

_CONFIDENCE_CHIP_CLASS = {
    "HIGH": "label-chip--positive",
    "MEDIUM": "label-chip",
    "LOW": "label-chip--negative",
    "UNKNOWN": "label-chip--negative",
}

_STATUS_CHIP_CLASS = {
    "NORMAL": "label-chip--positive",
    "WATCH": "label-chip",
    "WARNING": "label-chip--negative",
    "AT_FLOOR": "label-chip",
}


def load_report_cached() -> Optional[dict]:
    if not REPORT_PATH.exists():
        return None
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _protocol_html(protocol: dict) -> str:
    rows = [
        (terms.PROTOCOL_ROW_LABEL["metric"], protocol["metric"]),
        (terms.PROTOCOL_ROW_LABEL["source"], protocol["source"]),
        (terms.PROTOCOL_ROW_LABEL["normal_range"], protocol["normal_range"]),
        (terms.PROTOCOL_ROW_LABEL["warning_threshold"], protocol["warning_threshold"]),
        (terms.PROTOCOL_ROW_LABEL["next_review"], protocol["next_review"]),
        (terms.PROTOCOL_ROW_LABEL["explanatory_metric"], protocol["explanatory_metric"]),
    ]
    items = "".join(f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in rows)
    status_chip_class = _STATUS_CHIP_CLASS.get(protocol["current_status"], "label-chip")
    status_label = terms.STATUS_LABEL.get(protocol["current_status"], protocol["current_status"])
    current = (
        '<div class="piq-current-status">'
        f'<span class="label-chip {status_chip_class}">{terms.CURRENT_STATUS_LABEL}: {escape(status_label)}</span>'
        f'<span class="label-chip">{terms.CURRENT_READING_LABEL}: {protocol["current_reading"]:+.2f} SG</span>'
        f"</div>"
        f'<p class="piq-current-detail">{escape(protocol["current_detail"])}</p>'
    )
    return f'<dl class="piq-protocol">{items}</dl>{current}'


def _question_card(q: dict) -> str:
    evidence_items = "".join(f"<li>{escape(e)}</li>" for e in q["evidence"])
    chip_class = _CONFIDENCE_CHIP_CLASS.get(q["confidence"], "label-chip")
    confidence_label = terms.CONFIDENCE_LABEL.get(q["confidence"], q["confidence"])
    durability_label = terms.DURABILITY_LABEL.get(q["durability"], q["durability"])
    audit = (
        '<div class="piq-audit">'
        f'<span class="label-chip">{terms.CHIP_LABEL["evidence_score"]} {q["evidence_score"]}/100</span>'
        f'<span class="label-chip">{terms.CHIP_LABEL["sample_size"]} {q["sample_size"]}</span>'
        f'<span class="label-chip {chip_class}">{terms.CHIP_LABEL["confidence"]}: {escape(confidence_label)}</span>'
        f'<span class="label-chip">{escape(durability_label)}</span>'
        "</div>"
    )
    body = (
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["fact"]}</span>{escape(q["fact"])}</p>'
        f'<p class="piq-step-label piq-label-standalone">{terms.SECTION_LABEL["evidence"]}</p>'
        f'<ul class="piq-evidence-list">{evidence_items}</ul>'
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["analysis"]}</span>{escape(q["analysis"])}</p>'
        f'<p class="piq-step piq-conclusion"><span class="piq-label">{terms.SECTION_LABEL["conclusion"]}</span>{escape(q["conclusion"])}</p>'
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["why_it_matters"]}</span>{escape(q["why_it_matters"])}</p>'
        f'<div class="piq-brief">'
        f'<p><strong>{terms.SECTION_LABEL["player_takeaway"]}.</strong> {escape(q["player_takeaway"])}</p>'
        f'<p><strong>{terms.SECTION_LABEL["coach_focus"]}.</strong> {escape(q["coach_focus"])}</p>'
        f'<p><strong>{terms.SECTION_LABEL["durability"]}.</strong> {escape(q["durability_reasoning"])}</p>'
        "</div>"
        f"{audit}"
        f'<p class="piq-why-this-matters"><span class="piq-label">{terms.SECTION_LABEL["why_this_matters"]}</span>{escape(q["why_this_matters"])}</p>'
        f'<p class="piq-action"><span class="piq-label">{terms.SECTION_LABEL["action"]}</span>{escape(q["action"])}</p>'
        f'<p class="piq-step-label piq-label-standalone">{terms.SECTION_LABEL["monitoring_protocol"]}</p>'
        f'{_protocol_html(q["monitoring_protocol"])}'
    )
    return (
        f'<details class="evidence-detail pi-section" id="{escape(q["id"])}" open>'
        f'<summary class="section-heading"><h2>{escape(q["question"])}</h2></summary>'
        f'<div class="pi-section__body">{body}</div>'
        f"</details>"
    )


def _excluded_html(excluded: list) -> str:
    if not excluded:
        return ""
    items = "".join(
        f'<li><strong>{escape(x["question"])}</strong> — {escape(x["reason_excluded"])} ({terms.CHIP_LABEL["sample_size"]}: {x["sample_size"]})</li>' for x in excluded
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-excluded">'
        f'<summary class="section-heading"><h2>{terms.EXCLUDED_TITLE}</h2></summary>'
        '<div class="pi-section__body"><p class="pi-empty">'
        f"{terms.EXCLUDED_DESCRIPTION}"
        f'</p><ul class="piq-excluded-list">{items}</ul></div>'
        "</details>"
    )


def _hero_html(doc: dict) -> str:
    return (
        '<header class="pi-hero hero-data">'
        f'<p class="section-label">{terms.HERO_TITLE}</p>'
        f'<h1>{escape(doc["player_name"])}</h1>'
        f'<p class="pi-hero__meta">총 {len(doc["questions"])}개의 질문에 답했으며, 각 질문은 '
        f'{terms.SECTION_LABEL["fact"]} → {terms.SECTION_LABEL["evidence"]} → {terms.SECTION_LABEL["analysis"]} → '
        f'{terms.SECTION_LABEL["conclusion"]} 순서로 정리되어 있고, 모두 최근 실측값을 기준으로 점검하는 '
        f'{terms.SECTION_LABEL["monitoring_protocol"]}을 함께 제공합니다.</p>'
        "</header>"
    )


def _checklist_html(checklist: list) -> str:
    if not checklist:
        return ""
    rows = "".join(
        (
            f'<li><span class="label-chip {_STATUS_CHIP_CLASS.get(item["current_status"], "label-chip")}">'
            f'{escape(terms.STATUS_LABEL.get(item["current_status"], item["current_status"]))}</span> '
            f'<strong>{escape(item["metric"])}</strong> ({item["current_reading"]:+.2f} SG) — '
            f'<a href="#{escape(item["id"])}">{escape(item["linked_question"])}</a></li>'
        )
        for item in checklist
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-checklist" open>'
        f'<summary class="section-heading"><h2>{terms.CHECKLIST_TITLE}</h2></summary>'
        '<div class="pi-section__body"><p class="pi-empty">'
        f"{terms.CHECKLIST_DESCRIPTION}"
        f'</p><ul class="piq-checklist">{rows}</ul></div>'
        "</details>"
    )


def render_question_report_html(doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None) -> str:
    """Pure function: report JSON in, page body HTML out."""
    from klpga.website_v2.player_intelligence_v2 import prev_next_html

    cards = "".join(_question_card(q) for q in doc["questions"])
    checklist = _checklist_html(doc.get("pre_tournament_checklist", []))
    return prev_next_html(prev_link, next_link) + _hero_html(doc) + checklist + cards + _excluded_html(doc.get("questions_considered_but_unsupported", []))
