"""Tests for scripts/build_10097_player_intelligence_report.py and
src/klpga/website_v2/player_intelligence_10097_report.py -- the
question-organized Gold Standard report, playerCode=10097 ONLY."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("report_script_under_test", ROOT / "scripts" / "build_10097_player_intelligence_report.py")
report_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report_script)

REQUIRED_QUESTION_KEYS = {
    "id", "question", "fact", "evidence", "analysis", "conclusion",
    "why_it_matters", "player_takeaway", "coach_focus", "durability", "durability_reasoning", "why_this_matters", "action",
    "evidence_score", "sample_size", "confidence",
}

VALID_DURABILITY = {report_script.LONG_TERM, report_script.RECENT_TREND, report_script.CONFIRMED_EVENT}


def test_build_returns_only_player_10097():
    doc = report_script.build()
    assert doc["player_id"] == "10097"
    assert doc["player_name"] == "김민선7"
    assert "playerCode=10097" in doc["scope_note"]


def test_every_question_has_the_required_fact_evidence_analysis_conclusion_structure():
    doc = report_script.build()
    assert len(doc["questions"]) > 0
    for q in doc["questions"]:
        assert REQUIRED_QUESTION_KEYS.issubset(q.keys())
        assert q["fact"]
        assert len(q["evidence"]) > 0
        assert q["analysis"]
        assert q["conclusion"]
        assert q["question"].strip().endswith("?")


def test_every_question_answers_the_coaching_brief():
    """Mission: every insight must add why it matters, what the player
    should learn, what the coach should watch, and a one-sentence WHY
    THIS MATTERS close -- never just a described number."""
    doc = report_script.build()
    for q in doc["questions"]:
        assert q["why_it_matters"].strip()
        assert q["player_takeaway"].strip()
        assert q["coach_focus"].strip()
        assert q["why_this_matters"].strip()
        # "one sentence": a single terminal sentence-ending punctuation mark
        assert q["why_this_matters"].count(". ") == 0
        assert q["why_this_matters"].rstrip().endswith(".")


def test_every_question_ends_with_a_concrete_action_not_just_an_explanation():
    """Mission: NEO exists to improve performance, not only explain it --
    never stop at an explanation. Every section must end with a concrete,
    actionable takeaway, distinct from the more general why_this_matters
    close and from a restatement of the conclusion."""
    doc = report_script.build()
    for q in doc["questions"]:
        action = q["action"].strip()
        assert action
        assert len(action.split()) >= 12, f"{q['id']}.action reads like a one-liner, not a real instruction: {action!r}"
        # not just a repeat of the conclusion or why_this_matters
        assert action != q["conclusion"]
        assert action != q["why_this_matters"]


def test_every_question_classifies_durability_and_shows_its_reasoning():
    """Mission: is this a long-term characteristic or only a recent
    trend, and could it disappear if another season is added?"""
    doc = report_script.build()
    for q in doc["questions"]:
        assert q["durability"] in VALID_DURABILITY
        assert len(q["durability_reasoning"].split()) >= 15  # a real explanation, not a one-word label


def test_narrative_fields_explain_meaning_not_just_describe_numbers():
    """Mission: 'never describe numbers, explain what they mean.' FACT,
    ANALYSIS, CONCLUSION and the coaching-brief fields must read as
    prose explaining significance, not a bare number or percentile
    label standing alone."""
    doc = report_script.build()
    narrative_fields = ["fact", "analysis", "conclusion", "why_it_matters", "player_takeaway", "coach_focus", "why_this_matters", "action"]
    for q in doc["questions"]:
        for field in narrative_fields:
            text = q[field]
            assert len(text.split()) >= 8, f"{q['id']}.{field} reads like a label, not an explanation: {text!r}"
            assert not text.strip().lower().startswith(("sg ", "percentile", "rank #"))


def test_every_answered_question_has_evidence_score_sample_size_and_a_real_confidence():
    doc = report_script.build()
    for q in doc["questions"]:
        assert 0 <= q["evidence_score"] <= 100
        assert q["sample_size"] > 0
        assert q["confidence"] in {"HIGH", "MEDIUM", "LOW"}  # never UNKNOWN -- unsupported conclusions are excluded, not kept


def test_unsupported_repeat_course_pattern_is_excluded_not_answered():
    """The n=1 'wins at previously-played courses' pattern claim was
    already downgraded to UNKNOWN by the Audit mission -- this report
    must never turn it back into an answered question."""
    doc = report_script.build()
    answered_ids = {q["id"] for q in doc["questions"]}
    assert "q_repeat_course_pattern" not in answered_ids

    excluded_ids = {x["id"] for x in doc["questions_considered_but_unsupported"]}
    assert "q_repeat_course_pattern" in excluded_ids
    excluded = next(x for x in doc["questions_considered_but_unsupported"] if x["id"] == "q_repeat_course_pattern")
    assert excluded["confidence"] == "UNKNOWN"
    assert excluded["sample_size"] == 1


def test_questions_are_organized_by_real_golf_questions_not_stat_labels():
    doc = report_script.build()
    for q in doc["questions"]:
        lowered = q["question"].lower()
        assert not lowered.startswith("sg ")
        assert "percentile" not in lowered
        assert lowered.count("why") + lowered.count("how") + lowered.count("does") > 0


def test_evidence_score_formula_is_deterministic_and_disclosed():
    assert report_script._evidence_score(0, 3) == 0
    assert report_script._evidence_score(100, 3) == 95  # round(100 * 1.0 * 100/105)
    assert report_script._evidence_score(100, 1) == 32  # round(100 * (1/3) * 100/105)


def test_report_script_never_defines_its_own_statistics_function():
    """This script only re-groups and narrates values already computed by
    the frozen Knowledge Engine / build_10097_master_player_analysis.py --
    it must never define a new "def compute_*" of its own."""
    import inspect

    source = inspect.getsource(report_script)
    assert "def compute_" not in source


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def test_render_question_report_html_contains_fact_evidence_analysis_conclusion_labels():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "FACT" in html
    assert "EVIDENCE" in html
    assert "ANALYSIS" in html
    assert "CONCLUSION" in html
    assert "WHY IT MATTERS" in html
    assert "WHY THIS MATTERS" in html
    assert "Player takeaway" in html
    assert "Coach focus" in html
    assert "Evidence Score" in html
    assert "Sample Size" in html
    assert "Confidence" in html
    for q in doc["questions"]:
        assert q["question"] in html or q["question"].replace("'", "&#x27;") in html


def test_render_shows_every_coaching_brief_field_and_durability_chip():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    for q in doc["questions"]:
        assert escape_or_raw(q["why_it_matters"], html)
        assert escape_or_raw(q["player_takeaway"], html)
        assert escape_or_raw(q["coach_focus"], html)
        assert escape_or_raw(q["why_this_matters"], html)
        assert escape_or_raw(q["action"], html)
    assert "Long-term characteristic" in html or "Confirmed event" in html


def test_render_puts_action_as_the_true_last_element_of_every_section():
    """Mission: every section must END with an actionable takeaway --
    never stop at an explanation. ACTION must render after every other
    labeled block within its own question card, not just appear somewhere
    on the page."""
    from html import escape
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "ACTION" in html
    for q in doc["questions"]:
        why_this_matters_text = q["why_this_matters"] if q["why_this_matters"] in html else escape(q["why_this_matters"])
        action_text = q["action"] if q["action"] in html else escape(q["action"])
        assert html.index(action_text) > html.index(why_this_matters_text), f"{q['id']}: action does not come after why_this_matters"


def escape_or_raw(text: str, html: str) -> bool:
    from html import escape

    return text in html or escape(text) in html


def test_render_never_organizes_by_raw_sg_table():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "<table" not in html  # no stat table -- narrative cards only


def test_render_shows_excluded_questions_transparently():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "Questions Considered but Not Answered" in html
    assert "courses she has played before" in html


# ---------------------------------------------------------------------------
# Integration: build_or_placeholder special-cases ONLY player_id 10097
# ---------------------------------------------------------------------------


def test_build_or_placeholder_renders_question_report_for_10097_only():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    html_10097 = piv2.build_or_placeholder("10097", player_name="김민선7")
    assert "GOLD STANDARD REPORT" in html_10097
    assert "FACT" in html_10097 and "CONCLUSION" in html_10097


def test_build_or_placeholder_leaves_every_other_player_on_the_ordinary_stat_layout():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    doc = piv2.load_document_cached("10002")
    if doc is None:
        pytest.skip("no latest.json for 10002 in this environment")
    html_other = piv2.build_or_placeholder("10002", player_name="test")
    assert "GOLD STANDARD REPORT" not in html_other
    assert "PLAYER INTELLIGENCE</p>" in html_other or "선수 유형" in html_other
