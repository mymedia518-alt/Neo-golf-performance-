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


def _contribution_html(cb: Optional[dict]) -> str:
    """V5/V6: real SG decomposition. cb is None only when the event this
    question is about has no official per-component data on record (e.g.
    the most recent win, which has no tournament_cumulative warehouse row
    yet) -- reported as unavailable, never a fabricated split. A question
    whose contribution insight already lives in WIN/LOSS/TREND DNA above
    (V6: never duplicate a conclusion) carries no "contribution_breakdown"
    key at all, and _question_card skips this block for it entirely."""
    if not cb:
        return f'<p class="pi-empty">{terms.CONTRIBUTION_LABEL}: {terms.CONTRIBUTION_UNAVAILABLE}</p>'
    chips = "".join(f'<span class="label-chip">{escape(row["component"])} {row["share_pct"]:+.1f}%</span>' for row in cb["breakdown"])
    return (
        '<div class="piq-audit">'
        f'<span class="label-chip label-chip--positive">{terms.TOP_CONTRIBUTOR_LABEL}: {escape(cb["top_contributor"])}</span>'
        f"{chips}"
        "</div>"
    )


def _contribution_section_html(q: dict) -> str:
    """V6: never duplicate a conclusion. When `contribution_breakdown` is
    absent, this question's contribution insight already has its one home
    (WIN/LOSS/TREND DNA above) -- render nothing here rather than repeat
    it. Present-but-None still means "checked, no official data" and
    stays visible so that gap is disclosed, not silently skipped."""
    if "contribution_breakdown" not in q:
        return ""
    return f'<p class="piq-step-label piq-label-standalone">{terms.CONTRIBUTION_LABEL}</p>{_contribution_html(q["contribution_breakdown"])}'


def _decision_only(action: str) -> str:
    """V10: `action` (built by _action_from_protocol) always closes on a
    literal "결정: <one imperative sentence>" suffix -- this pulls out
    just that sentence for the visible PLAYER ACTION box. The full text
    (protocol + decision restated) still renders in full in DATA EVIDENCE
    below; nothing is dropped, only re-ordered."""
    marker = "결정: "
    idx = action.rfind(marker)
    return action[idx + len(marker):].strip() if idx != -1 else action


def _question_card(q: dict) -> str:
    """V10 (Player Intelligence V10): redesigns ONLY what renders inside
    '분석 근거'. That toggle used to open onto an audit trail (fact,
    evidence, analysis, ... in citation order) -- it now opens onto a
    Tour Performance Department briefing, fixed order, never reversed:
    (1) PERFORMANCE ANALYSIS -- what happened, numbers/chips before prose
    (2) KEY FINDINGS -- at most 3 bullets
    (3) COACH INTERPRETATION -- what a coach tells the player
    (4) PLAYER ACTION -- exactly one decision, large and unmissable
    (5) DATA EVIDENCE -- every technical citation, sources, sample size,
        confidence, the full monitoring protocol -- pushed into its own
        nested, closed-by-default toggle, so it takes a second click.

    The always-visible hero (conclusion + why_this_matters, outside this
    toggle entirely) and the compact monitoring summary are unchanged.
    No field from the report JSON is dropped -- every value still
    renders somewhere; only where and in what order changed.
    """
    protocol = q["monitoring_protocol"]
    status_chip_class = _STATUS_CHIP_CLASS.get(protocol["current_status"], "label-chip")
    status_label = terms.STATUS_LABEL.get(protocol["current_status"], protocol["current_status"])
    monitoring_summary = (
        '<div class="piq-current-status piq-monitoring-summary">'
        f'<span class="label-chip {status_chip_class}">{terms.CURRENT_STATUS_LABEL}: {escape(status_label)}</span>'
        f'<span class="label-chip">{terms.CURRENT_READING_LABEL}: {protocol["current_reading"]:+.2f} SG</span>'
        f'<span class="label-chip">{terms.NEXT_REVIEW_LABEL}: {escape(protocol["next_review"])}</span>'
        "</div>"
    )

    # (1) PERFORMANCE ANALYSIS -- numbers/chart-equivalent chips first
    # (the real SG contribution breakdown, when this question has one, is
    # this report's only chart-equivalent visual), then fact -> analysis
    # -> why it matters, in that order, never reversed.
    current_numbers = (
        '<div class="piq-audit">'
        f'<span class="label-chip {status_chip_class}">{terms.CURRENT_STATUS_LABEL}: {escape(status_label)}</span>'
        f'<span class="label-chip">{terms.CURRENT_READING_LABEL}: {protocol["current_reading"]:+.2f} SG</span>'
        "</div>"
    )
    # (1) PERFORMANCE ANALYSIS -- what happened, numbers first, plus the
    # at-most-3 key findings (still "what happened", just itemized).
    key_findings_items = "".join(f"<li>{escape(e)}</li>" for e in q["evidence"][:3])
    performance_analysis = (
        f'<p class="piq-step-label piq-label-standalone">{terms.PERFORMANCE_ANALYSIS_TITLE}</p>'
        f"{_contribution_html(q['contribution_breakdown']) if 'contribution_breakdown' in q else ''}"
        f"{current_numbers}"
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["fact"]}</span>{escape(q["fact"])}</p>'
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["analysis"]}</span>{escape(q["analysis"])}</p>'
        f'<p class="piq-step-label piq-label-standalone">{terms.KEY_FINDINGS_TITLE}</p>'
        f'<ul class="piq-evidence-list">{key_findings_items}</ul>'
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["why_it_matters"]}</span>{escape(q["why_it_matters"])}</p>'
    )

    # (2) MECHANISM -- why/how, its own visible step (V13: Performance Lab
    # order is Performance Analysis -> Mechanism -> Root Cause -> Coach
    # Interpretation -> Player Action -> Evidence, never reversed).
    mechanism_step = (
        f'<p class="piq-step-label piq-label-standalone">{terms.MECHANISM_LABEL}</p>'
        f'<p class="piq-step">{escape(q["mechanism"])}</p>'
        if q.get("mechanism") else ""
    )

    # (3) ROOT CAUSE -- continues past "what changed" to the first real,
    # measurable cause this repository's data can support; never invented
    # past that point (the field itself says so when it stops).
    root_cause_step = (
        f'<p class="piq-step-label piq-label-standalone">{terms.ROOT_CAUSE_LABEL}</p>'
        f'<p class="piq-step">{escape(q["root_cause"])}</p>'
        if q.get("root_cause") else ""
    )

    # (3b) DECISION CONTEXT -- NEO evaluates decisions, not just results.
    # Only present on questions where a real, already-verified decision-to-
    # outcome link exists in the data (never invented for questions where
    # no decision-level record exists).
    decision_context_step = (
        f'<p class="piq-step-label piq-label-standalone">{terms.DECISION_CONTEXT_LABEL}</p>'
        f'<p class="piq-step">{escape(q["decision_context"])}</p>'
        if q.get("decision_context") else ""
    )

    # (4) COACH INTERPRETATION -- what a coach tells the player, short.
    coach_interpretation = (
        f'<p class="piq-step-label piq-label-standalone">{terms.COACH_INTERPRETATION_TITLE}</p>'
        '<div class="piq-brief">'
        f'<p><strong>{terms.SECTION_LABEL["coach_focus"]}.</strong> {escape(q["coach_focus"])}</p>'
        f'<p><strong>{terms.SECTION_LABEL["player_takeaway"]}.</strong> {escape(q["player_takeaway"])}</p>'
        "</div>"
    )

    # (5) PLAYER ACTION -- one decision, not advice, with the real
    # condition (reproducibility) it depends on shown right next to it.
    reproducibility_html = (
        f'<p class="piq-current-detail">{terms.REPRODUCIBILITY_LABEL}: {escape(q["reproducibility"])}</p>'
        if q.get("reproducibility") else ""
    )
    player_action = (
        f'<p class="piq-step-label piq-label-standalone">{terms.PLAYER_ACTION_TITLE}</p>'
        f'<p class="piq-action"><span class="piq-label">{terms.DECISION_LABEL}</span>{escape(_decision_only(q["action"]))}</p>'
        f"{reproducibility_html}"
    )

    # (6) EVIDENCE -- every technical citation, nested and closed by
    # default: durability reasoning, the audit chips, the raw
    # contribution numbers, the full action/protocol text (real file and
    # field citations live here), and the 5-item monitoring protocol.
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
    data_evidence_body = (
        f'<p class="piq-step"><span class="piq-label">{terms.SECTION_LABEL["durability"]}</span>{escape(q["durability_reasoning"])}</p>'
        f"{audit}"
        f"{_contribution_section_html(q)}"
        f'<p class="piq-step"><span class="piq-label">{terms.FULL_PROTOCOL_LABEL}</span>{escape(q["action"])}</p>'
        f'<p class="piq-step-label piq-label-standalone">{terms.SECTION_LABEL["monitoring_protocol"]}</p>'
        f"{_protocol_html(protocol)}"
    )
    data_evidence_toggle = (
        '<details class="piq-evidence-toggle">'
        f"<summary>{terms.DATA_EVIDENCE_TOGGLE_LABEL}</summary>"
        f'<div class="piq-evidence-toggle__body">{data_evidence_body}</div>'
        "</details>"
    )

    performance_lab_kicker = f'<p class="section-label">{terms.PERFORMANCE_LAB_LABEL}</p>'
    evidence_body = performance_lab_kicker + performance_analysis + mechanism_step + root_cause_step + decision_context_step + coach_interpretation + player_action + data_evidence_toggle
    evidence_toggle = (
        '<details class="piq-evidence-toggle">'
        f"<summary>{terms.EVIDENCE_TOGGLE_LABEL}</summary>"
        f'<div class="piq-evidence-toggle__body">{evidence_body}</div>'
        "</details>"
    )

    layer_chip = (
        f'<div class="piq-audit"><span class="label-chip label-chip--positive">{escape(terms.LAYER_LABEL.get(q["layer"], q["layer"]))} 레이어</span></div>'
        if q.get("layer") else ""
    )
    body = (
        f"{layer_chip}"
        f'<p class="piq-hero-conclusion">{escape(q["conclusion"])}</p>'
        f'<p class="piq-why-brief"><span class="piq-label">{terms.SECTION_LABEL["why_this_matters"]}</span>{escape(q["why_this_matters"])}</p>'
        f"{evidence_toggle}"
        f"{monitoring_summary}"
    )
    return (
        f'<details class="evidence-detail pi-section" id="{escape(q["id"])}" open>'
        f'<summary class="section-heading"><h2>{escape(q["question"])}</h2></summary>'
        f'<div class="pi-section__body">{body}</div>'
        f"</details>"
    )


_REPOSITORY_INTELLIGENCE_TITLE = "저장소 교차 검증 (V7)"


def _repository_intelligence_html(ri: Optional[dict]) -> str:
    """V7: discloses the separate Repository Intelligence V1 mission's
    cross-check -- what was found, and, honestly, that none of it met
    this report's evidence bar to change any conclusion above."""
    if not ri:
        return ""
    items = "".join(
        f'<li><strong>{escape(f["label"])}</strong> ({escape(f["branch"])}, <code>{escape(f["file"])}</code>) — '
        f'{"플레이어 고유 수치 있음" if f["player_specific_number_found"] else "플레이어 고유 수치 없음"}</li>'
        for f in ri["findings"]
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-repository-intelligence">'
        f'<summary class="section-heading"><h2>{_REPOSITORY_INTELLIGENCE_TITLE}</h2></summary>'
        '<div class="pi-section__body">'
        f'<p class="pi-empty">{escape(ri["search_scope"])}</p>'
        f'<ul class="piq-excluded-list">{items}</ul>'
        f'<p class="piq-current-detail">{escape(ri["summary"])}</p>'
        "</div></details>"
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


def _player_playbook_html(playbook: Optional[dict]) -> str:
    """V13: PLAYER PLAYBOOK (공략/방어/수용/지양/신뢰) -- a synthesis, not
    a new claim. Every line is the same decision already shown inside its
    own question card above; this only groups them by category so a
    player can scan the whole game plan in one place. Always visible
    (open), since it is the report's single highest-density summary."""
    if not playbook or not playbook.get("entries"):
        return ""
    items = "".join(
        f'<li><span class="label-chip label-chip--positive">{escape(terms.PLAYBOOK_CATEGORY_LABEL_V13.get(e["category"], e["category"]))}</span> '
        f'{escape(e["decision"])} — <a href="#{escape(e["question_id"])}">{escape(e["question"])}</a></li>'
        for e in playbook["entries"]
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-playbook" open>'
        f'<summary class="section-heading"><h2>{terms.PLAYER_PLAYBOOK_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{items}</ul></div>'
        "</details>"
    )


def _coach_console_html(console: Optional[dict]) -> str:
    """V13: COACH CONSOLE -- exactly five lines (KEEP/CHANGE/MONITOR/
    AVOID/DO NOT TOUCH), one per category, never more. Same reuse
    discipline as the Player Playbook: every line is a decision already
    computed by its own question card, only regrouped."""
    if not console or not console.get("entries"):
        return ""
    items = "".join(
        f'<li><span class="label-chip">{escape(terms.COACH_CONSOLE_CATEGORY_LABEL.get(e["category"], e["category"]))}</span> '
        f'{escape(e["decision"])} — <a href="#{escape(e["question_id"])}">{escape(e["question"])}</a></li>'
        for e in console["entries"]
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-coach-console" open>'
        f'<summary class="section-heading"><h2>{terms.COACH_CONSOLE_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{items}</ul></div>'
        "</details>"
    )


def _unsupported_modules_html(modules: Optional[list]) -> str:
    """V12: honest disclosure of the analysis modules this mission asked
    for that this repository's real data cannot support (hole-by-hole,
    distance-band, pin-position, shot-sequence, decision-process data --
    none of it exists here) -- named and reasoned, never silently
    skipped, never guessed to fill the gap."""
    if not modules:
        return ""
    items = "".join(f'<li><strong>{escape(m["module"])}</strong> — {escape(m["reason"])}</li>' for m in modules)
    return (
        '<details class="evidence-detail pi-section" id="piq-unsupported-modules">'
        f'<summary class="section-heading"><h2>{terms.UNSUPPORTED_MODULES_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><p class="pi-empty">{terms.UNSUPPORTED_MODULES_DESCRIPTION}</p>'
        f'<ul class="piq-excluded-list">{items}</ul></div>'
        "</details>"
    )


def _dna_story_html(label: str, dna: Optional[dict]) -> str:
    """V6: story first. One short, deterministic sentence (already
    written by the script from the real top_contributor/share_pct, never
    composed here) is all that's visible without expanding anything."""
    story = dna["story"] if dna else terms.CONTRIBUTION_UNAVAILABLE
    return f"<li><strong>{escape(label)}</strong> — {escape(story)}</li>"


def _dna_numbers_html(label: str, dna: Optional[dict]) -> str:
    """V6: numbers second -- rendered only inside the '분석 근거' toggle
    below, never before it."""
    if not dna:
        return f'<p class="pi-empty">{escape(label)}: {terms.CONTRIBUTION_UNAVAILABLE}</p>'
    chips = "".join(f'<span class="label-chip">{escape(row["component"])} {row["share_pct"]:+.1f}%</span>' for row in dna["breakdown"])
    if "sample_size" in dna:
        scope_chip = f'<span class="label-chip">{terms.CHIP_LABEL["sample_size"]} {dna["sample_size"]}/{dna["events_considered"]}</span>'
    else:
        scope_chip = f'<span class="label-chip">{dna["from_season"]} → {dna["to_season"]}</span>'
    return (
        f'<p class="piq-step-label piq-label-standalone">{escape(label)}</p>'
        '<div class="piq-audit">'
        f'<span class="label-chip label-chip--positive">{terms.TOP_CONTRIBUTOR_LABEL}: {escape(dna["top_contributor"])}</span>'
        f"{scope_chip}{chips}"
        "</div>"
    )


def _dna_html(doc: dict) -> str:
    stories = (
        _dna_story_html(terms.WIN_DNA, doc.get("win_dna"))
        + _dna_story_html(terms.LOSS_DNA, doc.get("loss_dna"))
        + _dna_story_html(terms.TREND_DNA, doc.get("trend_dna"))
    )
    numbers = (
        _dna_numbers_html(terms.WIN_DNA, doc.get("win_dna"))
        + _dna_numbers_html(terms.LOSS_DNA, doc.get("loss_dna"))
        + _dna_numbers_html(terms.TREND_DNA, doc.get("trend_dna"))
    )
    evidence_toggle = (
        '<details class="piq-evidence-toggle">'
        f"<summary>{terms.EVIDENCE_TOGGLE_LABEL}</summary>"
        f'<div class="piq-evidence-toggle__body">{numbers}</div>'
        "</details>"
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-dna" open>'
        f'<summary class="section-heading"><h2>{terms.WIN_DNA} · {terms.LOSS_DNA} · {terms.TREND_DNA}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{stories}</ul>{evidence_toggle}</div>'
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
        f'<p class="piq-why-brief"><span class="piq-label">{terms.NEO_PRINCIPLE_TITLE}</span>{escape(terms.NEO_PRINCIPLE_TEXT)}</p>'
        "</header>"
    )


def _performance_funnel_html(funnel: Optional[dict]) -> str:
    """V16: THE PERFORMANCE FUNNEL -- Technique -> Opportunity ->
    Conversion -> Competition -> Winning. Every stage is an independent,
    directly-explainable real number (SG percentile, a real season rate,
    or a literal event count) -- never a percentile averaged or divided
    against another percentile, never a synthetic efficiency %. Always
    visible (open), since this is now how every other section should be
    read."""
    if not funnel:
        return ""
    t, o, c, comp, w = funnel["technique"], funnel["opportunity"], funnel["conversion"], funnel["competition"], funnel["winning"]

    def _pct_chips(percentiles: dict) -> str:
        return "".join(f'<span class="label-chip">{escape(k)} {v}</span>' for k, v in percentiles.items() if v is not None)

    stages_html = (
        '<div class="piq-brief">'
        f'<p><strong>1 · {escape(t["label"])}</strong> {escape(t["question"])}</p>'
        f'<div class="piq-audit">{_pct_chips(t["percentiles"])}</div>'
        f'<p class="piq-current-detail">{escape(t["note"])}</p>'
        f'<p><strong>2 · {escape(o["label"])}</strong> {escape(o["question"])}</p>'
        f'<div class="piq-audit"><span class="label-chip">GIR율 {o["gir_rate"]["raw"]:.1f}% (백분위 {o["gir_rate"]["percentile"]})</span></div>'
        f'<p class="piq-current-detail">{escape(o["note"])}</p>'
        f'<p><strong>3 · {escape(c["label"])}</strong> {escape(c["question"])}</p>'
        '<div class="piq-audit">'
        f'<span class="label-chip">버디율 {c["birdie_rate"]["raw"]:.1f}% (백분위 {c["birdie_rate"]["percentile"]})</span>'
        f'<span class="label-chip">파세이브율 {c["par_save_rate"]["raw"]:.1f}% (백분위 {c["par_save_rate"]["percentile"]})</span>'
        f'<span class="label-chip">리커버리율 {c["recovery_rate"]["raw"]:.1f}% (백분위 {c["recovery_rate"]["percentile"]})</span>'
        "</div>"
        f'<p class="piq-current-detail">{escape(c["note"])}</p>'
        f'<p><strong>4 · {escape(comp["label"])}</strong> {escape(comp["question"])}</p>'
        f'<div class="piq-audit"><span class="label-chip">Top10 {comp["top10_events"]}회 / 전체 {comp["total_events"]}회</span></div>'
        f'<p class="piq-current-detail">{escape(comp["note"])}</p>'
        f'<p><strong>5 · {escape(w["label"])}</strong> {escape(w["question"])}</p>'
        f'<div class="piq-audit"><span class="label-chip">우승 {w["win_events"]}회 / Top10 {w["top10_events"]}회</span></div>'
        f'<p class="piq-current-detail">{escape(w["note"])}</p>'
        "</div>"
    )
    weakest = t["weakest"]
    signal_html = f'<p class="piq-why-brief">기술 단계에서 가장 낮은 실측 백분위는 {escape(weakest["component"])}({weakest["percentile"]})입니다 -- 리크 맵에서 이 항목의 실측 영향을 확인하십시오.</p>'

    return (
        '<details class="evidence-detail pi-section" id="piq-performance-funnel" open>'
        f'<summary class="section-heading"><h2>{terms.PERFORMANCE_FUNNEL_TITLE}</h2></summary>'
        f'<div class="pi-section__body">{stages_html}{signal_html}</div>'
        "</details>"
    )


def _leak_map_html(leak_map: Optional[dict]) -> str:
    """V16: LEAK MAP -- at most 3 leaks, each with Where/Why/Performance
    Loss (a real number, or 알 수 없음 when no verified historical figure
    supports one -- never estimated)/Coach Decision. Always visible."""
    if not leak_map or not leak_map.get("leaks"):
        return ""
    items = "".join(
        (
            '<li>'
            f'<span class="label-chip label-chip--positive">우선순위 {leak["priority"]}</span> '
            f'<strong>{escape(leak["where"])}</strong>'
            f'<p class="piq-current-detail">{terms.LEAK_FIELD_LABEL["why"]}: {escape(leak["why"])}</p>'
            f'<p class="piq-current-detail">{terms.LEAK_FIELD_LABEL["performance_loss"]}: {escape(leak["performance_loss"])}</p>'
            f'<p class="piq-current-detail">{terms.LEAK_FIELD_LABEL["coach_decision"]}: {escape(leak["coach_decision"])}</p>'
            f' <a href="#{escape(leak["question_id"])}">근거 질문 보기</a>'
            "</li>"
        )
        for leak in leak_map["leaks"]
    )
    return (
        '<details class="evidence-detail pi-section" id="piq-leak-map" open>'
        f'<summary class="section-heading"><h2>{terms.LEAK_MAP_TITLE}</h2></summary>'
        f'<div class="pi-section__body"><ul class="piq-checklist">{items}</ul></div>'
        "</details>"
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
    performance_funnel = _performance_funnel_html(doc.get("performance_funnel"))
    leak_map = _leak_map_html(doc.get("leak_map"))
    checklist = _checklist_html(doc.get("pre_tournament_checklist", []))
    dna = _dna_html(doc)
    coach_console = _coach_console_html(doc.get("coach_console"))
    playbook = _player_playbook_html(doc.get("player_playbook"))
    excluded = _excluded_html(doc.get("questions_considered_but_unsupported", []))
    unsupported_modules = _unsupported_modules_html(doc.get("unsupported_analysis_modules_v12"))
    repository_intelligence = _repository_intelligence_html(doc.get("repository_intelligence_v7"))
    return (
        prev_next_html(prev_link, next_link) + _hero_html(doc) + performance_funnel + leak_map + checklist + dna
        + coach_console + playbook + cards
        + excluded + unsupported_modules + repository_intelligence
    )
