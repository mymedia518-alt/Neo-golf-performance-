"""Tests for scripts/build_10097_player_intelligence_report.py and
src/klpga/website_v2/player_intelligence_10097_report.py -- the
question-organized, Korean-localized Gold Standard report, playerCode=10097
ONLY."""

from __future__ import annotations

import importlib.util
import re
import sys
from html import escape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2 import player_intelligence_10097_terms as terms  # noqa: E402

_spec = importlib.util.spec_from_file_location("report_script_under_test", ROOT / "scripts" / "build_10097_player_intelligence_report.py")
report_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report_script)

REQUIRED_QUESTION_KEYS = {
    "id", "question", "fact", "evidence", "analysis", "conclusion",
    "why_it_matters", "player_takeaway", "coach_focus", "durability", "durability_reasoning", "why_this_matters", "action",
    "monitoring_protocol", "evidence_score", "sample_size", "confidence",
}

REQUIRED_PROTOCOL_KEYS = {
    "metric", "source", "sample_size", "normal_range", "warning_threshold", "next_review",
    "explanatory_metric", "current_reading", "current_status", "current_detail",
}

VALID_CURRENT_STATUS = {"NORMAL", "WATCH", "WARNING", "AT_FLOOR"}

# "Never predict. Never speculate." -- these would signal a forecast of a
# future value rather than a status check of an already-recorded one.
_PREDICTIVE_WORDS = ("predict", "forecast", "likely to score", "expected to", "should improve", "projected", "예상됩니다", "전망됩니다")

VALID_DURABILITY = {report_script.LONG_TERM, report_script.RECENT_TREND, report_script.CONFIRMED_EVENT}

# "NEO does not give opinions" -- an action/protocol may never lean on
# subjective, unmeasurable coaching language. These would signal an opinion
# smuggled back in instead of an operational, data-derived instruction.
_OPINION_WORDS_KO = ("믿으십시오", "믿어야", "확신", "느낌이 듭니다")

# Standard golf terms allowed to stay in English anywhere in the report
# (mission: "keep only standard golf terms in English"). Compound forms
# built from these (e.g. "SG APP", "SG Total") are also allowed.
_ALLOWED_GOLF_WORDS = {"SG", "GIR", "APP", "PUTT", "ARG", "OTT", "Birdie", "Bogey", "Driver", "Iron", "Wedge", "Fairway", "Green", "Total"}


def _english_words(text: str) -> list:
    """Every maximal run of ASCII letters in `text` -- used to check that
    nothing outside the allowed golf-term list leaks into this report's
    own generated prose. Numbers, punctuation and Korean are ignored."""
    return re.findall(r"[A-Za-z]+", text)


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
    doc = report_script.build()
    for q in doc["questions"]:
        assert q["why_it_matters"].strip()
        assert q["player_takeaway"].strip()
        assert q["coach_focus"].strip()
        assert q["why_this_matters"].strip()
        assert q["why_this_matters"].rstrip().endswith(".")


def test_every_question_ends_with_a_concrete_action_not_just_an_explanation():
    doc = report_script.build()
    for q in doc["questions"]:
        action = q["action"].strip()
        assert action
        assert len(action) >= 40, f"{q['id']}.action reads like a one-liner, not a real instruction: {action!r}"
        assert action != q["conclusion"]
        assert action != q["why_this_matters"]


def test_every_action_is_backed_by_a_measurable_monitoring_protocol():
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        assert REQUIRED_PROTOCOL_KEYS.issubset(protocol.keys())
        assert protocol["metric"].strip()
        assert protocol["source"].strip()
        assert protocol["sample_size"] > 0
        assert protocol["normal_range"].strip()
        assert protocol["warning_threshold"].strip()
        assert protocol["next_review"].strip()
        assert any(ch.isdigit() for ch in protocol["normal_range"])
        assert any(ch.isdigit() for ch in protocol["warning_threshold"])
        assert "historical_sg_warehouse_corrected.json" in protocol["source"] or "compute_season_profiles" in protocol["source"]


def test_every_protocol_answers_what_metric_most_likely_explains_a_change():
    """V3, item 5: never a golf-domain guess. Either a real correlation
    that clears the disclosed threshold (named, with the coefficient
    shown), or an honest '없음'/'알 수 없음' with the real numbers behind
    that answer -- never silence, never invention."""
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        explanatory = protocol["explanatory_metric"]
        assert explanatory.strip()
        assert explanatory.startswith(("없음.", "알 수 없음", "SG "))
        if explanatory.startswith("없음.") or explanatory.startswith("알 수 없음"):
            assert "r=" in explanatory or "n=" in explanatory or "회" in explanatory


def test_every_protocol_has_a_current_status_checked_against_a_real_reading_not_a_forecast():
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        assert protocol["current_status"] in VALID_CURRENT_STATUS
        assert isinstance(protocol["current_reading"], (int, float))
        assert protocol["current_detail"].strip()
        assert "실측값" in protocol["current_detail"]


def test_report_never_predicts_or_speculates():
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        combined = " ".join([q["action"], protocol["explanatory_metric"], protocol["current_detail"]]).lower()
        for word in _PREDICTIVE_WORDS:
            assert word not in combined, f"{q['id']} reads as a prediction ({word!r})"


def test_pre_tournament_checklist_covers_every_answered_question():
    doc = report_script.build()
    checklist = doc["pre_tournament_checklist"]
    assert len(checklist) == len(doc["questions"])
    linked_ids = {item["id"] for item in checklist}
    assert linked_ids == {q["id"] for q in doc["questions"]}
    for item in checklist:
        assert item["current_status"] in VALID_CURRENT_STATUS
        assert item["metric"].strip()


def test_action_and_protocol_never_read_as_an_opinion():
    """Mission: NEO does not give opinions. NEO defines monitoring
    protocols. The action must be operational Korean (what to measure
    and when), opening on the monitored metric itself, never phrased as
    trust/confidence/belief."""
    doc = report_script.build()
    for q in doc["questions"]:
        action = q["action"]
        for word in _OPINION_WORDS_KO:
            assert word not in action, f"{q['id']}.action reads like an opinion ({word!r}): {action!r}"
        assert action.startswith(q["monitoring_protocol"]["metric"]), f"{q['id']}.action must open on the metric being monitored, not a subjective recommendation"
        assert "모니터링합니다" in action


def test_monitoring_protocol_method_uses_repeated_samples_not_single_snapshots():
    """The GIR/par-save/birdie-rate fields are current-season snapshots
    with no repeated historical series in this repository -- a protocol
    must never claim to monitor one of those on an operational cadence."""
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        assert protocol["sample_size"] >= 4
        for banned in ("gir_rate", "par_save_rate", "birdie_rate", "GIR", "그린 적중률", "파세이브율"):
            assert banned not in protocol["metric"]


def test_every_question_classifies_durability_and_shows_its_reasoning():
    doc = report_script.build()
    for q in doc["questions"]:
        assert q["durability"] in VALID_DURABILITY
        assert len(q["durability_reasoning"]) >= 40


def test_narrative_fields_are_real_sentences_not_bare_labels():
    doc = report_script.build()
    narrative_fields = ["fact", "analysis", "conclusion", "why_it_matters", "player_takeaway", "coach_focus", "why_this_matters", "action"]
    for q in doc["questions"]:
        for field in narrative_fields:
            text = q[field]
            assert len(text) >= 20, f"{q['id']}.{field} reads like a label, not an explanation: {text!r}"
            assert not text.strip().lower().startswith(("percentile", "rank #"))


def test_every_answered_question_has_evidence_score_sample_size_and_a_real_confidence():
    doc = report_script.build()
    for q in doc["questions"]:
        assert 0 <= q["evidence_score"] <= 100
        assert q["sample_size"] > 0
        assert q["confidence"] in {"HIGH", "MEDIUM", "LOW"}


def test_unsupported_repeat_course_pattern_is_excluded_not_answered():
    doc = report_script.build()
    answered_ids = {q["id"] for q in doc["questions"]}
    assert "q_repeat_course_pattern" not in answered_ids

    excluded_ids = {x["id"] for x in doc["questions_considered_but_unsupported"]}
    assert "q_repeat_course_pattern" in excluded_ids
    excluded = next(x for x in doc["questions_considered_but_unsupported"] if x["id"] == "q_repeat_course_pattern")
    assert excluded["confidence"] == "UNKNOWN"
    assert excluded["sample_size"] == 1
    assert "코스" in excluded["question"]


def test_questions_are_organized_by_real_golf_questions_in_natural_korean():
    doc = report_script.build()
    for q in doc["questions"]:
        question = q["question"]
        assert question.strip().endswith("?")
        assert not question.strip().startswith("SG ")
        assert "percentile" not in question.lower()
        # a real golf question, phrased in Korean ("왜"/"어떻게"), not a
        # literal English "why"/"how" -- localization, not translation
        assert any(marker in question for marker in ("왜", "어떻게", "이유"))


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
# Localization: single terminology dictionary, no stray English
# ---------------------------------------------------------------------------

# Fields this script writes itself (not verbatim citations quoted from the
# frozen Knowledge Engine's own output, which spells golf terms out
# differently and is explicitly exempt -- see the module docstring).
_OWN_PROSE_FIELDS = ["fact", "analysis", "conclusion", "why_it_matters", "player_takeaway", "coach_focus", "durability_reasoning", "why_this_matters", "action"]


# Two real, documented exemptions from the "only golf terms stay English"
# rule -- neither is prose language choice, so neither is something to
# localize:
#   1. Real official tournament/sponsor names in the data itself (e.g. the
#      real tournament "덕신EPC 챔피언십", the "KLPGA" tour name, or a real
#      tournament literally titled "...Masters 2026") -- proper nouns this
#      report quotes from official records, not authored prose.
#   2. Technical data-source citations embedded in the ACTION text (real
#      file names, field names, code references) -- these identify exactly
#      where a number came from and are never meant to read as Korean.
_PROPER_NOUN_FRAGMENTS = {"EPC", "KLPGA", "Masters"}
_TECHNICAL_CITATION_PATTERN = re.compile(
    r"[\w.]+\.json(?:\s*\([^)]*\))?"  # historical_sg_warehouse_corrected.json (scope=..., field='...')
    r"|knowledge_engine\.\w+\(\)"  # knowledge_engine.find_course_history()
)


def _strip_technical_citations(text: str) -> str:
    return _TECHNICAL_CITATION_PATTERN.sub(" ", text)


def test_only_allowed_golf_terms_appear_in_english_in_this_reports_own_prose():
    """Mission: keep only standard golf terms in English; everything else
    must read as natural Korean. `evidence` bullets are excluded here
    because they legitimately embed verbatim frozen-engine citations
    (which spell terms out, e.g. "SG Approach") -- that exemption is
    documented and covered separately below."""
    doc = report_script.build()
    for q in doc["questions"]:
        for field in _OWN_PROSE_FIELDS:
            text = _strip_technical_citations(q[field])
            for word in _english_words(text):
                assert word in _ALLOWED_GOLF_WORDS or word in _PROPER_NOUN_FRAGMENTS, f"{q['id']}.{field} leaks a non-golf English word: {word!r} in {q[field]!r}"


def test_sg_components_are_always_sg_prefixed_never_a_bare_abbreviation():
    """A bare 'APP'/'PUTT'/'OTT'/'ARG' reads ambiguously in Korean prose
    (e.g. 'APP' alone reads as a phone app) -- this report's own prose
    must always write the SG-prefixed form."""
    doc = report_script.build()
    for q in doc["questions"]:
        for field in _OWN_PROSE_FIELDS:
            text = q[field]
            for bare in ("APP", "PUTT", "OTT", "ARG"):
                for m in re.finditer(re.escape(bare), text):
                    assert text[max(0, m.start() - 3) : m.start()] == "SG ", f"{q['id']}.{field} uses a bare {bare!r} without the SG prefix: {text[max(0,m.start()-10):m.end()+10]!r}"


def test_terminology_dictionary_is_the_single_source_used_by_generator_and_renderer():
    """Mission: create a single terminology dictionary and apply it
    everywhere; wording must be identical across the entire report."""
    from klpga.website_v2 import player_intelligence_10097_report as renderer

    assert renderer.terms is terms  # same module object, not a re-declared copy
    doc = report_script.build()
    html = renderer.render_question_report_html(doc)
    for label in terms.SECTION_LABEL.values():
        assert label in html
    for label in terms.PROTOCOL_ROW_LABEL.values():
        assert label in html


def test_headings_never_mix_a_bare_english_ui_label_with_korean():
    """Mission: never mix English and Korean in headings. Question
    headings (h2) may contain the allowed golf terms embedded in Korean
    sentences, but never a standalone English UI label."""
    doc = report_script.build()
    banned_ui_labels = ("FACT", "EVIDENCE", "ANALYSIS", "CONCLUSION", "ACTION", "MONITORING PROTOCOL", "GOLD STANDARD")
    for q in doc["questions"]:
        for label in banned_ui_labels:
            assert label not in q["question"]


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def test_render_question_report_html_contains_korean_section_labels():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.SECTION_LABEL["fact"] in html
    assert terms.SECTION_LABEL["evidence"] in html
    assert terms.SECTION_LABEL["analysis"] in html
    assert terms.SECTION_LABEL["conclusion"] in html
    assert terms.SECTION_LABEL["why_it_matters"] in html
    assert terms.SECTION_LABEL["why_this_matters"] in html
    assert terms.SECTION_LABEL["player_takeaway"] in html
    assert terms.SECTION_LABEL["coach_focus"] in html
    assert terms.CHIP_LABEL["evidence_score"] in html
    assert terms.CHIP_LABEL["sample_size"] in html
    assert terms.CHIP_LABEL["confidence"] in html
    # no leftover English UI labels from the pre-localization version
    for stale in ("FACT", "EVIDENCE", "ANALYSIS", "CONCLUSION", "WHY IT MATTERS", "WHY THIS MATTERS", "Player takeaway", "Coach focus", "Evidence Score", "Sample Size", "Confidence:", "GOLD STANDARD"):
        assert stale not in html
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
    assert any(label in html for label in terms.DURABILITY_LABEL.values())


def test_render_shows_the_monitoring_protocol_fields_in_korean():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.SECTION_LABEL["monitoring_protocol"] in html
    for label in terms.PROTOCOL_ROW_LABEL.values():
        assert label in html
    assert "MONITORING PROTOCOL" not in html
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        assert escape_or_raw(protocol["metric"], html)
        assert escape_or_raw(protocol["normal_range"], html)
        assert escape_or_raw(protocol["warning_threshold"], html)
        assert escape_or_raw(protocol["next_review"], html)


def test_render_shows_explanatory_metric_and_current_status():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.PROTOCOL_ROW_LABEL["explanatory_metric"] in html
    assert terms.CURRENT_STATUS_LABEL in html
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        assert escape_or_raw(protocol["explanatory_metric"], html)
        assert escape_or_raw(protocol["current_detail"], html)


def test_render_shows_pre_tournament_checklist_linking_to_each_section():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.CHECKLIST_TITLE in html
    for item in doc["pre_tournament_checklist"]:
        assert escape_or_raw(item["metric"], html)
    hrefs = re.findall(r'href="#([^"]+)"', html)
    ids = set(re.findall(r'<details[^>]*\bid="([^"]+)"', html))
    for href in hrefs:
        assert href in ids, f"checklist link #{href} has no matching section id"
    for q in doc["questions"]:
        assert f'id="{q["id"]}"' in html


def test_render_puts_action_as_the_true_last_element_of_every_section():
    """Every section must END with an actionable takeaway. ACTION must
    render after every other labeled block within its own question card,
    not just appear somewhere on the page. Scoped per-card (not a global
    html.index()) because two questions can legitimately share the
    identical monitoring protocol and action text."""
    from html import escape
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.SECTION_LABEL["action"] in html

    card_starts = [html.index(f'id="{escape(q["id"])}"') for q in doc["questions"]]
    card_starts.append(len(html))
    for i, q in enumerate(doc["questions"]):
        card = html[card_starts[i] : card_starts[i + 1]]
        why_this_matters_text = q["why_this_matters"] if q["why_this_matters"] in card else escape(q["why_this_matters"])
        action_text = q["action"] if q["action"] in card else escape(q["action"])
        assert card.index(action_text) > card.index(why_this_matters_text), f"{q['id']}: action does not come after why_this_matters"


def escape_or_raw(text: str, html: str) -> bool:
    from html import escape

    return text in html or escape(text) in html


def test_render_never_organizes_by_raw_sg_table():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "<table" not in html  # no stat table -- narrative cards only


def test_most_recent_win_never_generalizes_beyond_the_one_confirmed_event():
    """A real check of her full round-to-round SG history (not just this
    one tournament) found no consistent rising pattern across her career
    -- so this question must describe the one win accurately without
    claiming it generalizes into a repeatable trait."""
    doc = report_script.build()
    q = next(q for q in doc["questions"] if q["id"] == "q_most_recent_win")
    assert q["durability"] == report_script.CONFIRMED_EVENT
    for field in ("conclusion", "analysis", "durability_reasoning"):
        text = q[field]
        # "매번 대회 후반에 강해진다"는 일반화가 등장한다면, 반드시 같은 문장
        # 안에서 명시적으로 부정되어야 합니다 (근거 없는 반복적 특성으로 주장하지 않음).
        if "대회 후반에 강해진다" in text or "항상" in text:
            assert any(neg in text for neg in ("안 됩니다", "않습니다", "일반화하지")), f"{q['id']}.{field} asserts an unsupported generalization: {text!r}"


# ---------------------------------------------------------------------------
# UI REFACTOR MISSION (Gold Standard): Conclusion -> Why? -> Evidence
# (collapsed) -> Monitoring. No analysis/conclusion/data changes -- only
# order, visibility, and how much is shown before any click.
# ---------------------------------------------------------------------------


def _card_slices(html: str, doc: dict) -> list:
    starts = [html.index(f'id="{escape(q["id"])}"') for q in doc["questions"]]
    starts.append(len(html))
    return [html[starts[i] : starts[i + 1]] for i in range(len(doc["questions"]))]


def test_ui_refactor_leads_with_a_large_conclusion_before_why_and_collapsed_evidence():
    """SECTION ORDER: Conclusion -> Why? -> Evidence (collapsed) ->
    Monitoring. Scoped per-card, like the action-ordering test above,
    since two questions can share protocol text."""
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    for q, card in zip(doc["questions"], _card_slices(html, doc)):
        conclusion_idx = card.index("piq-hero-conclusion")
        why_idx = card.index("piq-why-brief")
        evidence_idx = card.index("piq-evidence-toggle")
        fact_idx = card.index(f'piq-label">{terms.SECTION_LABEL["fact"]}</span>')
        monitoring_idx = card.index("piq-monitoring-summary")
        assert conclusion_idx < why_idx < evidence_idx < fact_idx < monitoring_idx, (
            f"{q['id']}: section order is not Conclusion -> Why -> Evidence(collapsed) -> Monitoring"
        )


def test_ui_refactor_evidence_stays_collapsed_by_default():
    """Rule 3: evidence must stay hidden inside expandable sections. The
    per-question <details> itself is still `open` (so the conclusion is
    visible without a click), but the nested '분석 근거' <details> must
    NOT carry `open` -- it is closed until the reader chooses to expand it."""
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert html.count('<details class="piq-evidence-toggle">') == len(doc["questions"])
    assert "piq-evidence-toggle\" open" not in html
    assert html.count(f"<summary>{terms.EVIDENCE_TOGGLE_LABEL}</summary>") == len(doc["questions"])


def test_ui_refactor_hides_raw_file_and_field_citations_unless_evidence_expanded():
    """Rule 4: never show raw JSON/file/field names or implementation
    details unless '분석 근거' is expanded. Every protocol['source'] in
    this report is a real file name, field reference, or function call
    (asserted elsewhere) -- so it, and the action text that embeds it,
    must only ever appear inside the collapsed toggle body."""
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    for q, card in zip(doc["questions"], _card_slices(html, doc)):
        toggle_open = card.index('<details class="piq-evidence-toggle">')
        toggle_close = card.index("</details>", toggle_open) + len("</details>")
        outside_toggle = card[:toggle_open] + card[toggle_close:]
        assert ".json" not in outside_toggle, f"{q['id']}: raw file citation leaked outside 분석 근거"
        assert "knowledge_engine." not in outside_toggle, f"{q['id']}: raw function citation leaked outside 분석 근거"
        assert q["monitoring_protocol"]["source"] not in outside_toggle, f"{q['id']}: data source citation leaked outside 분석 근거"


def test_ui_refactor_monitoring_summary_is_visible_and_technical_detail_free():
    """Visual priority: Medium: Monitoring, Hidden: Technical details.
    The always-visible monitoring readout shows status/reading/next
    check but never the file-backed source citation or the raw stats
    prose that the full protocol table carries."""
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    for q, card in zip(doc["questions"], _card_slices(html, doc)):
        protocol = q["monitoring_protocol"]
        summary_start = card.index("piq-monitoring-summary")
        summary = card[summary_start:]
        assert terms.CURRENT_STATUS_LABEL in summary
        assert terms.NEXT_REVIEW_LABEL in summary
        assert protocol["source"] not in summary


def test_ui_refactor_default_visible_text_is_reduced_by_at_least_half():
    """Rule 5: reduce visible text by at least 50%. Compares what renders
    without a click (conclusion + the one-line why) against everything
    that used to always be visible before this refactor (fact, evidence,
    the full analysis, why_it_matters, the three brief paragraphs, action,
    and the protocol's own prose) -- now behind '분석 근거'."""
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        visible = q["conclusion"] + q["why_this_matters"]
        collapsed = (
            q["fact"]
            + "".join(q["evidence"])
            + q["analysis"]
            + q["why_it_matters"]
            + q["player_takeaway"]
            + q["coach_focus"]
            + q["durability_reasoning"]
            + q["action"]
            + protocol["metric"]
            + protocol["normal_range"]
            + protocol["warning_threshold"]
            + protocol["explanatory_metric"]
        )
        assert len(visible) <= 0.5 * len(collapsed), f"{q['id']}: default-visible text is not reduced by at least 50%"


def test_ui_refactor_does_not_touch_colors_or_typography_tokens():
    """Rule: do not redesign the website, change colors, or change
    typography. The new piq-* rules must reuse the page's existing color
    variables and font stack, never introduce a new hex color or
    font-family."""
    css_text = (ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css").read_text(encoding="utf-8")
    start = css_text.index("/* Player Intelligence UI refactor")
    end_marker = ".piq-evidence-toggle__body{margin-top:.85rem}"
    end = css_text.index(end_marker, start) + len(end_marker)
    block = css_text[start:end]
    assert "font-family" not in block
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", block), "new UI-refactor CSS introduces a raw hex color instead of reusing --tokens"


def test_render_shows_excluded_questions_transparently():
    from klpga.website_v2.player_intelligence_10097_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.EXCLUDED_TITLE in html
    assert "출전했던 코스" in html


# ---------------------------------------------------------------------------
# Integration: build_or_placeholder special-cases ONLY player_id 10097
# ---------------------------------------------------------------------------


def test_build_or_placeholder_renders_question_report_for_10097_only():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    html_10097 = piv2.build_or_placeholder("10097", player_name="김민선7")
    assert terms.HERO_TITLE in html_10097
    assert terms.SECTION_LABEL["fact"] in html_10097 and terms.SECTION_LABEL["conclusion"] in html_10097


def test_build_or_placeholder_leaves_every_other_player_on_the_ordinary_stat_layout():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    doc = piv2.load_document_cached("10002")
    if doc is None:
        pytest.skip("no latest.json for 10002 in this environment")
    html_other = piv2.build_or_placeholder("10002", player_name="test")
    assert terms.HERO_TITLE not in html_other
    assert terms.CHECKLIST_TITLE not in html_other
    assert "PLAYER INTELLIGENCE</p>" in html_other or "선수 유형" in html_other
