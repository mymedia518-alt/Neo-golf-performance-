"""Data Quality Report -- the receiving page for the source-
reconciliation / pipeline content MISSION V50 moved OUT of the public
Player History page.

MISSION V50 (2026-09-28): "Remove Developer Thinking from Player
History... Player History is no longer a database report." MISSION
V50.1 (2026-09-28), a correction: "Optimize for zero repetition, not
fewer sections... If a section teaches something unique, keep it."
V50's first pass moved real, unique player insight (the official
season snapshot, season-evolution charts, the rolling-trend chart, the
2025 technical stats table, the DNA growth-velocity table, career
heartbeat, the three other round extremes) here too, on the mistaken
theory that "reports bare numbers" and "developer-facing" were the
same problem. V50.1 restored all of that to Player History -- none of
it repeats another section, so none of it belonged here. What
genuinely belongs on THIS page is only content that is about NEO's own
pipeline, never about the player: source-reconciliation status,
PASS/PARTIAL/BLOCKED semantics, the season coverage matrix, the
not-yet-available list, the field-confidence legend, the collection
roadmap, and the quality timeline.

This module renders ZERO chart/section logic of its own -- every
function it calls is imported, unchanged, from player_history_report.py
(the same real, already-tested functions). No duplicate code, per this
project's standing rule."""
from __future__ import annotations

from html import escape

from klpga.website_v2.player_history_report import _data_confidence_html, _reconciliation_html

PAGE_TITLE = "데이터 품질 보고서"
PAGE_INTRO = (
    "이 페이지는 Player History의 대회 기록이 어떻게 대조(reconciliation)되었는지 보여주는 기술 문서입니다. "
    "선수를 이해하려면 Player History로 돌아가세요."
)


def render_data_quality_html(doc: dict, *, player_history_url: str = "") -> str:
    """Pure function: the SAME PLAYER_HISTORY.json doc in, a separate
    technical page out. Every real field rendered here already existed
    in the doc -- nothing was recomputed or invented to build this
    page; it is a relocation, not new content."""
    back_link = f'<p class="ph-dq-back"><a href="{escape(player_history_url)}">← Player History로 돌아가기</a></p>' if player_history_url else ""
    body = (
        '<div class="ph-dq-header">'
        f'<p class="section-label">DATA QUALITY REPORT</p>'
        f'<h1>{escape(doc.get("player_name", ""))}</h1>'
        f'<p class="pi-hero__meta">{escape(PAGE_INTRO)}</p>'
        f'{back_link}'
        '</div>'
        + _reconciliation_html(
            doc.get("reconciliation"), doc.get("status"), doc.get("coverage_matrix"), doc.get("not_available", []),
            data_confidence=_data_confidence_html(
                doc.get("page_confidence"), doc.get("field_confidence_legend"),
                doc.get("provenance_summary"), doc.get("data_confidence_roadmap"), doc.get("data_quality_timeline"),
            ),
        )
    )
    return f'<div class="ph-page ph-dq-page">{body}</div>'
