"""Tests for scripts/build_9431_master_player_analysis.py,
scripts/build_9431_player_intelligence_report.py, and
src/klpga/website_v2/player_intelligence_9431_report.py -- the second
Gold Standard report, playerCode=9431 (박보겸) ONLY.

Mirrors the guarantees tests/test_10097_player_intelligence_report.py
already locks in for 10097 (never invent, audited conclusions, story-
first DNA, no duplication, Korean localization) but every number
asserted here is her own real data -- nothing is copied from 10097's
test expectations."""

from __future__ import annotations

import importlib.util
import re
import sys
from html import escape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2 import player_intelligence_9431_terms as terms  # noqa: E402

_master_spec = importlib.util.spec_from_file_location("master_script_9431_under_test", ROOT / "scripts" / "build_9431_master_player_analysis.py")
master_script = importlib.util.module_from_spec(_master_spec)
_master_spec.loader.exec_module(master_script)

_report_spec = importlib.util.spec_from_file_location("report_script_9431_under_test", ROOT / "scripts" / "build_9431_player_intelligence_report.py")
report_script = importlib.util.module_from_spec(_report_spec)
_report_spec.loader.exec_module(report_script)

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
VALID_DURABILITY = {report_script.LONG_TERM, report_script.RECENT_TREND, report_script.CONFIRMED_EVENT}
_PREDICTIVE_WORDS = ("predict", "forecast", "예상됩니다", "전망됩니다", "will win", "will improve")
_ALLOWED_GOLF_WORDS = {"SG", "GIR", "APP", "PUTT", "ARG", "OTT", "Birdie", "Bogey", "Driver", "Iron", "Wedge", "Fairway", "Green", "Total"}
_PROPER_NOUN_FRAGMENTS = {"EPC", "KLPGA", "Masters"}
_TECHNICAL_CITATION_PATTERN = re.compile(
    r"[\w.]+\.json(?:\s*\([^)]*\))?"
    r"|knowledge_engine\.\w+\(\)"
)


def _strip_technical_citations(text: str) -> str:
    return _TECHNICAL_CITATION_PATTERN.sub(" ", text)


def _english_words(text: str) -> list:
    return re.findall(r"[A-Za-z]+", text)


def _sentence_count(text: str) -> int:
    """Counts real sentence-ending punctuation, not a decimal point
    inside a number like '-0.09' (digit on both sides is never a
    sentence boundary)."""
    return len(re.findall(r"(?<!\d)[.!?](?!\d)", text))


# ---------------------------------------------------------------------------
# Master analysis: real data, playerCode=9431 only
# ---------------------------------------------------------------------------


def test_master_analysis_covers_only_9431():
    doc = master_script.build()
    assert doc["player_id"] == "9431"
    assert doc["player_name"] == "박보겸"
    assert "playerCode=9431" in doc["scope_note"]


def test_master_analysis_finds_her_real_two_wins_not_invented():
    doc = master_script.build()
    wins = doc["tournament_analysis"]["wins"]
    assert len(wins) == 2
    names = {w["tournament"] for w in wins}
    assert "제9회 교촌 1991 레이디스 오픈" in names
    assert "상상인 · 한경 와우넷 오픈 2024" in names


def test_repeat_course_pattern_is_confirmed_not_forced():
    """Unlike 10097 (n=1, UNKNOWN), her real pattern is n=2, CONFIRMED --
    this locks in that the master script computes this from real data,
    not a copied assumption."""
    doc = master_script.build()
    pattern = doc["pattern_trend_analysis"]
    assert pattern["pattern_observation_sample_size"] == 2
    assert pattern["pattern_observation_status"] == "CONFIRMED"
    assert pattern["pattern_observation_confidence"] == "MEDIUM"


def test_repeat_course_pattern_text_is_order_accurate():
    """Both real wins occurred on attempt_number 1, not on a return visit
    -- the narrative must say so accurately, never assume the more
    intuitive "won after repeat visits" direction."""
    doc = master_script.build()
    pattern = doc["pattern_trend_analysis"]
    assert all(w["attempt_number"] == 1 for w in pattern["wins_on_repeat_courses"])
    assert "첫 real 출전" not in pattern["pattern_observation"]  # sanity: no garbled mixed-language text
    assert "첫" in pattern["pattern_observation"] or "first" in pattern["pattern_observation"].lower()


def test_master_analysis_never_defines_its_own_statistics_function():
    import inspect

    source = inspect.getsource(master_script)
    assert "def compute_" not in source


# ---------------------------------------------------------------------------
# Report: FACT -> EVIDENCE -> ANALYSIS -> CONCLUSION, audited
# ---------------------------------------------------------------------------


def test_build_returns_only_player_9431():
    doc = report_script.build()
    assert doc["player_id"] == "9431"
    assert doc["player_name"] == "박보겸"
    assert "playerCode=9431" in doc["scope_note"]


def test_every_question_has_the_required_structure_and_audit_fields():
    doc = report_script.build()
    assert len(doc["questions"]) >= 6
    for q in doc["questions"]:
        assert REQUIRED_QUESTION_KEYS.issubset(q.keys())
        assert q["fact"] and q["evidence"] and q["analysis"] and q["conclusion"]
        assert q["question"].strip().endswith("?")
        assert 0 <= q["evidence_score"] <= 100
        assert q["sample_size"] > 0
        assert q["confidence"] in {"HIGH", "MEDIUM", "LOW"}
        assert q["durability"] in VALID_DURABILITY


def test_every_action_is_measurable_never_an_opinion():
    doc = report_script.build()
    for q in doc["questions"]:
        action = q["action"]
        assert len(action) >= 40
        assert "모니터링합니다" in action
        assert action.startswith(q["monitoring_protocol"]["metric"])


def test_every_protocol_defines_all_required_fields():
    doc = report_script.build()
    for q in doc["questions"]:
        protocol = q["monitoring_protocol"]
        assert REQUIRED_PROTOCOL_KEYS.issubset(protocol.keys())
        assert protocol["current_status"] in VALID_CURRENT_STATUS
        assert isinstance(protocol["current_reading"], (int, float))
        assert protocol["normal_range"].strip()
        assert protocol["warning_threshold"].strip()
        assert protocol["next_review"].strip()


def test_repeat_course_pattern_protocol_reading_is_a_real_sg_value_not_a_count():
    """Regression: current_reading must be a real SG Total, never the
    sample count formatted as if it were one."""
    doc = report_script.build()
    q = next(q for q in doc["questions"] if q["id"] == "q_repeat_course_pattern")
    protocol = q["monitoring_protocol"]
    assert protocol["current_reading"] != protocol["sample_size"]
    assert protocol["current_reading"] == pytest.approx(1.5, abs=0.01)


def test_never_predicts_or_speculates():
    doc = report_script.build()
    for q in doc["questions"]:
        combined = " ".join([q["action"], q["monitoring_protocol"]["explanatory_metric"], q["monitoring_protocol"]["current_detail"]]).lower()
        for word in _PREDICTIVE_WORDS:
            assert word not in combined, f"{q['id']} reads as a prediction ({word!r})"


def test_why_wins_evidence_cites_her_real_per_win_component_values():
    """Regression: evidence must not reference an arbitrary unrelated
    tournament row -- both real wins' actual SG APP values must appear."""
    doc = report_script.build()
    q = next(q for q in doc["questions"] if q["id"] == "q_why_wins")
    evidence_text = " ".join(q["evidence"])
    assert "+4.13" in evidence_text or "4.13" in evidence_text
    assert "+1.96" in evidence_text or "1.96" in evidence_text


def test_so_what_fits_in_three_sentences_or_fewer():
    doc = report_script.build()
    for q in doc["questions"]:
        so_what = q["conclusion"] + " " + q["why_this_matters"]
        assert _sentence_count(so_what) <= 3, f"{q['id']}: {_sentence_count(so_what)} sentences: {so_what!r}"


# ---------------------------------------------------------------------------
# DNA: story first, real SG decomposition, never duplicated
# ---------------------------------------------------------------------------


def _assert_reproducible_breakdown(dna: dict):
    assert dna["breakdown"]
    total = dna["total_value"]
    recomputed_sum = 0.0
    for row in dna["breakdown"]:
        assert row["component"] in terms.SG_COMPONENT.values()
        expected_share = round(row["value"] / total * 100, 1) if total else 0.0
        assert abs(row["share_pct"] - expected_share) < 0.15
        recomputed_sum += row["share_pct"]
    assert abs(recomputed_sum - 100.0) < 0.5
    assert dna["top_contributor"] == max(dna["breakdown"], key=lambda b: abs(b["share_pct"]))["component"]


def test_win_loss_trend_dna_are_reproducible_and_reflect_her_real_data():
    doc = report_script.build()
    for key in ("win_dna", "loss_dna", "trend_dna"):
        dna = doc[key]
        assert dna is not None
        _assert_reproducible_breakdown(dna)
    # Real, not templated from 10097: her WIN DNA top contributor is APP
    # (career-wide she is balanced), her LOSS DNA top contributor is PUTT.
    assert doc["win_dna"]["top_contributor"] == "SG APP"
    assert doc["loss_dna"]["top_contributor"] == "SG PUTT"


def test_dna_story_is_a_reproducible_one_sentence_restatement():
    doc = report_script.build()
    for key in ("win_dna", "loss_dna", "trend_dna"):
        dna = doc[key]
        assert _sentence_count(dna["story"]) == 1
        assert dna["top_contributor"] in dna["story"]


def test_never_duplicates_an_insight_across_the_report():
    doc = report_script.build()
    dna_breakdowns = [doc["win_dna"]["breakdown"], doc["loss_dna"]["breakdown"], doc["trend_dna"]["breakdown"]]
    seen = []
    for q in doc["questions"]:
        cb = q.get("contribution_breakdown")
        if not cb:
            continue
        assert cb["breakdown"] not in dna_breakdowns, f"{q['id']} duplicates a top-level DNA breakdown"
        for other_id, other_breakdown in seen:
            assert cb["breakdown"] != other_breakdown, f"{q['id']} duplicates {other_id}'s breakdown"
        seen.append((q["id"], cb["breakdown"]))


def test_why_wins_why_loses_have_no_redundant_contribution_breakdown():
    """These two questions' insight already lives in win_dna/loss_dna."""
    doc = report_script.build()
    for qid in ("q_why_wins", "q_why_loses"):
        q = next(q for q in doc["questions"] if q["id"] == qid)
        assert "contribution_breakdown" not in q


# ---------------------------------------------------------------------------
# Special requirement: major championship, checked honestly
# ---------------------------------------------------------------------------


def test_major_championship_analysis_is_honest_not_forced():
    doc = report_script.build()
    analysis = doc["major_championship_analysis"]
    assert analysis["status"] == "NOT_FOUND_ON_RECORD"
    assert "일반대회" in analysis["finding"]
    assert len(analysis["checked_sources"]) >= 3
    # Never claims a major win exists for either of her 2 real wins.
    assert "메이저대회 우승자" not in analysis["finding"] or "아닌" in analysis["finding"]


def test_no_question_falsely_labels_either_real_win_as_a_major():
    doc = report_script.build()
    for q in doc["questions"]:
        combined = q["fact"] + q["conclusion"]
        assert "메이저" not in combined, f"{q['id']} claims a major win that is not on record"


# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------

_OWN_PROSE_FIELDS = ["fact", "analysis", "conclusion", "why_it_matters", "player_takeaway", "coach_focus", "durability_reasoning", "why_this_matters", "action"]


def test_only_allowed_golf_terms_appear_in_english_in_own_prose():
    doc = report_script.build()
    for q in doc["questions"]:
        for field in _OWN_PROSE_FIELDS:
            text = _strip_technical_citations(q[field])
            for word in _english_words(text):
                assert word in _ALLOWED_GOLF_WORDS or word in _PROPER_NOUN_FRAGMENTS, f"{q['id']}.{field} leaks {word!r}: {q[field]!r}"


def test_sg_components_are_always_sg_prefixed():
    doc = report_script.build()
    for q in doc["questions"]:
        for field in _OWN_PROSE_FIELDS:
            text = q[field]
            for bare in ("APP", "PUTT", "OTT", "ARG"):
                for m in re.finditer(re.escape(bare), text):
                    assert text[max(0, m.start() - 3) : m.start()] == "SG ", f"{q['id']}.{field} has a bare {bare!r}"


def test_terms_module_reuses_10097s_dictionary_verbatim():
    """The single terminology dictionary is shared, not redefined --
    zero risk to 10097, identical wording across both reports."""
    from klpga.website_v2 import player_intelligence_10097_terms as terms_10097

    assert terms.SG_COMPONENT is terms_10097.SG_COMPONENT
    assert terms.STATUS_LABEL is terms_10097.STATUS_LABEL
    assert terms.WIN_DNA == terms_10097.WIN_DNA == "WIN DNA"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_shows_korean_labels_and_her_real_content():
    from klpga.website_v2.player_intelligence_9431_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert terms.HERO_TITLE in html
    assert doc["player_name"] in html
    assert terms.WIN_DNA in html and terms.LOSS_DNA in html and terms.TREND_DNA in html
    for q in doc["questions"]:
        assert q["id"] in html


def test_render_shows_major_championship_disclosure():
    from klpga.website_v2.player_intelligence_9431_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "piq-major-championship" in html
    assert "일반대회" in html


def test_render_reuses_10097s_generic_rendering_functions_not_new_ones():
    """UI: do not redesign, reuse the existing Player Intelligence page.
    The renderer module imports its card/DNA/checklist primitives from
    10097's renderer rather than redefining them."""
    renderer_path = ROOT / "src" / "klpga" / "website_v2" / "player_intelligence_9431_report.py"
    source = renderer_path.read_text(encoding="utf-8")
    assert "from klpga.website_v2.player_intelligence_10097_report import" in source
    assert "def _question_card" not in source
    assert "def _dna_html" not in source


def test_render_never_organizes_by_raw_stat_table():
    from klpga.website_v2.player_intelligence_9431_report import render_question_report_html

    doc = report_script.build()
    html = render_question_report_html(doc)
    assert "<table" not in html


# ---------------------------------------------------------------------------
# Integration: build_or_placeholder routes ONLY 9431 (and 10097) to their
# Gold Standard renderers; every other player is untouched.
# ---------------------------------------------------------------------------


def test_build_or_placeholder_renders_question_report_for_9431_only():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    html_9431 = piv2.build_or_placeholder("9431", player_name="박보겸")
    assert terms.HERO_TITLE in html_9431
    assert "piq-major-championship" in html_9431


def test_build_or_placeholder_does_not_cross_wire_9431_and_10097():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    html_9431 = piv2.build_or_placeholder("9431", player_name="박보겸")
    html_10097 = piv2.build_or_placeholder("10097", player_name="김민선7")
    assert "박보겸" in html_9431 and "김민선7" not in html_9431
    assert "김민선7" in html_10097 and "박보겸" not in html_10097
    assert "piq-major-championship" not in html_10097


def test_build_or_placeholder_leaves_every_other_player_on_the_ordinary_stat_layout():
    from klpga.website_v2 import player_intelligence_v2 as piv2

    doc = piv2.load_document_cached("10002")
    if doc is None:
        pytest.skip("no latest.json for 10002 in this environment")
    html_other = piv2.build_or_placeholder("10002", player_name="test")
    assert terms.HERO_TITLE not in html_other
    assert "piq-major-championship" not in html_other
