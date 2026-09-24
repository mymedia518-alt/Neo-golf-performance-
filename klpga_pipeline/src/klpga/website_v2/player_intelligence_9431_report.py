"""Renders the question-organized Player Intelligence Report for
playerCode=9431 (박보겸) ONLY -- the second Gold Standard reference
implementation, after 김민선7 (10097).

UI: do not redesign, reuse the existing Player Intelligence page. Every
rendering primitive here (question cards, WIN/LOSS/TREND DNA,
pre-tournament checklist, excluded-questions disclosure) is imported
directly from player_intelligence_10097_report.py, unmodified -- same
cards, same CSS classes, same layout, same Conclusion -> Why? ->
Evidence(collapsed) -> Monitoring structure and story-first DNA. This
module never redefines that HTML; only the player-specific input
(REPORT_PATH, `terms`) and one section 10097's schema doesn't have --
the major-championship disclosure -- are new here.

Never calculates anything itself: reads the already-generated
content/website_v2/knowledge_engine/player_intelligence/9431/
PLAYER_INTELLIGENCE_REPORT.json (built by
scripts/build_9431_player_intelligence_report.py) and renders it.

This module is called ONLY for player_id == "9431" (see
player_intelligence_v2.build_or_placeholder's special case). Every
other player is unaffected.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR
from klpga.website_v2 import player_intelligence_9431_terms as terms
from klpga.website_v2.player_intelligence_10097_report import (
    _checklist_html,
    _dna_html,
    _excluded_html,
    _hero_html,
    _question_card,
)

REPORT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / "9431" / "PLAYER_INTELLIGENCE_REPORT.json"


def load_report_cached() -> Optional[dict]:
    if not REPORT_PATH.exists():
        return None
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


_MAJOR_STATUS_LABEL_KO = {
    "NOT_FOUND_ON_RECORD": "공식 기록에서 확인되지 않음",
    "CONFIRMED": "공식 기록으로 확인됨",
}
_MAJOR_TITLE = "메이저 챔피언십 분석"


def _major_championship_html(analysis: Optional[dict]) -> str:
    """Special requirement disclosure: analyzed separately, as its own
    section, exactly like every other disclosure in this report -- never
    silently omitted, never forced into one of her real (non-major) wins."""
    if not analysis:
        return ""
    status_label = _MAJOR_STATUS_LABEL_KO.get(analysis["status"], analysis["status"])
    sources = "".join(f"<li>{escape(s)}</li>" for s in analysis.get("checked_sources", []))
    body = (
        f'<div class="piq-current-status"><span class="label-chip label-chip--negative">{status_label}</span></div>'
        f'<p class="piq-current-detail">{escape(analysis["finding"])}</p>'
        '<p class="piq-step-label piq-label-standalone">확인한 출처</p>'
        f'<ul class="piq-excluded-list">{sources}</ul>'
        f'<p class="pi-empty">{escape(analysis["note"])}</p>'
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-major-championship">'
        f'<summary class="section-heading"><h2>{_MAJOR_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{body}</div>'
        "</details>"
    )


def render_question_report_html(doc: dict, *, prev_link: Optional[dict] = None, next_link: Optional[dict] = None) -> str:
    """Pure function: report JSON in, page body HTML out."""
    from klpga.website_v2.player_intelligence_v2 import prev_next_html

    cards = "".join(_question_card(q) for q in doc["questions"])
    checklist = _checklist_html(doc.get("pre_tournament_checklist", []))
    dna = _dna_html(doc)
    major = _major_championship_html(doc.get("major_championship_analysis"))
    return (
        prev_next_html(prev_link, next_link)
        + _hero_html(doc)
        + checklist
        + dna
        + major
        + cards
        + _excluded_html(doc.get("questions_considered_but_unsupported", []))
    )
