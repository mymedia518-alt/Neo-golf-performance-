"""Renderer-side adapter: bridges question_engine.Question objects to
player_history_report.py's existing, frozen renderer functions.

MISSION V100 (2026-09-28): "the engine must never know which renderer
consumes it." This module is that boundary on the Player History side.
It imports BOTH question_engine (the generic engine) and
player_history_report (one real renderer) -- and is the ONLY module
that imports both. question_engine.py itself imports neither this
module nor player_history_report; a future coach_mode_questions.py or
tournament_preview_questions.py would be its own equally-thin bridge,
never requiring a change here.

player_history_report.py is untouched by this module. Its section
functions still take plain dicts exactly as they always have -- this
module only proves that the SAME real doc, once wrapped as a
Question's Evidence/Metrics, produces byte-identical HTML through the
exact same frozen functions render_player_history_html already calls.
No new visual, no new metric, no new fact -- architecture, not a
feature. UI is frozen; this changes none of it."""
from __future__ import annotations

from typing import Optional

from klpga.website_v2 import player_history_report as report
from klpga.website_v2.question_engine import Evidence, Metric, Question, VisualizationSpec, build_evidence


def _evidence_map(question: Question) -> dict:
    return {e.source_path: e.value for e in question.evidence}


def build_why_now_question(doc: dict) -> Optional[Question]:
    """"왜 지금 잘 치고 있는가?" -- the exact real evidence
    _why_now_html already renders from (doc["why_now"] plus the three
    optional context dicts), now named and traceable as a Question."""
    why_now = doc.get("why_now")
    if not why_now:
        return None
    evidence = build_evidence(doc, "why_now", "current_snapshot", "current_vs_career", "career_story.current")
    metrics = (
        Metric("lead_component", why_now.get("lead_component"), evidence=evidence),
        Metric("lead_delta", why_now.get("lead_delta"), unit="SG", evidence=evidence),
        Metric("sentence", why_now.get("sentence"), evidence=evidence),
    )
    return Question(
        id="why_now",
        text_ko="왜 지금 잘 치고 있는가?",
        evidence=evidence,
        metrics=metrics,
        visualization=VisualizationSpec(kind="arrow_grid+skill_chain", metrics=metrics),
    )


def build_player_identity_question(doc: dict) -> Optional[Question]:
    """"어떤 유형의 선수인가?" -- the exact real evidence
    _player_identity_html already renders from (doc["player_identity"])."""
    identity = doc.get("player_identity")
    if not identity:
        return None
    evidence = build_evidence(doc, "player_identity")
    metrics = (
        Metric("primary_type", identity.get("primary_type"), evidence=evidence),
        Metric("primary_component", identity.get("primary_component"), evidence=evidence),
        Metric("primary_share_pct", identity.get("primary_share_pct"), unit="%", evidence=evidence),
    )
    return Question(
        id="player_identity",
        text_ko="어떤 유형의 선수인가?",
        evidence=evidence,
        metrics=metrics,
        visualization=VisualizationSpec(kind="identity_badge", metrics=metrics),
    )


class WhyNowRenderer:
    """Implements question_engine.Renderer for the 'why_now' Question.
    Pulls the exact real sub-dicts back out of the Question's own
    Evidence (never reconstructed from scalar Metrics -- so there is no
    way a subtly-wrong dict reaches the frozen function) and calls
    _why_now_html exactly as render_player_history_html always has."""

    def answer(self, question: Question) -> str:
        ev = _evidence_map(question)
        return report._why_now_html(
            ev.get("why_now"),
            ev.get("current_snapshot"),
            ev.get("current_vs_career"),
            ev.get("career_story.current"),
        )


class PlayerIdentityRenderer:
    """Implements question_engine.Renderer for the 'player_identity'
    Question -- same guarantee as WhyNowRenderer above."""

    def answer(self, question: Question) -> str:
        ev = _evidence_map(question)
        return report._player_identity_html(ev.get("player_identity"))
