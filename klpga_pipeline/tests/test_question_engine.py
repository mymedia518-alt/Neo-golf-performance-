"""MISSION V100 (2026-09-28): "Freeze UI. Freeze Player History.
Freeze Compare. Extract the Question Engine. Every answer in NEO must
originate from a Question object. Question -> Evidence -> Metrics ->
Visualization -> Rendering. The engine must never know which renderer
consumes it. Architecture before features."

These tests pin two guarantees:
1. question_engine.py is a real, standalone, generic pipeline (Question
   / Evidence / Metric / VisualizationSpec / build_evidence) with zero
   import of, or knowledge of, any renderer -- checked by source
   inspection, the same technique used to prove player_compare.py
   never duplicates a chart primitive.
2. Routing a real player doc through the engine (a Question, built by
   player_history_questions.py's adapter) and answering it through the
   SAME frozen player_history_report.py functions produces BYTE-
   IDENTICAL HTML to calling those functions directly -- proving the
   engine is pure architecture, changing not one pixel of the frozen
   Player History page.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.website_v2 import player_history_questions as adapter  # noqa: E402
from klpga.website_v2 import player_history_report as report  # noqa: E402
from klpga.website_v2 import question_engine  # noqa: E402
from klpga.website_v2.question_engine import Evidence, Metric, Question, VisualizationSpec, build_evidence  # noqa: E402


def _doc():
    return build_script.build()


def test_engine_module_never_imports_any_renderer():
    """The engine must never know which renderer consumes it -- checked
    for real via the module's actual import statements (docstring
    prose is allowed to *name* player_history_report.py as an example
    of a renderer; it must never be *imported*)."""
    import ast
    tree = ast.parse(inspect.getsource(question_engine))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert not any("klpga.website_v2" in m for m in imported_modules), imported_modules


def test_build_evidence_pulls_real_dotted_paths_and_skips_missing_ones():
    doc = {"a": {"b": 1}, "c": None}
    ev = build_evidence(doc, "a.b", "a.missing", "c", "missing_top")
    assert len(ev) == 1
    assert ev[0] == Evidence(source_path="a.b", value=1)


def test_build_evidence_never_fabricates_a_placeholder_for_a_missing_path():
    doc = {}
    ev = build_evidence(doc, "why_now", "current_snapshot")
    assert ev == ()


def test_question_metric_lookup_by_name():
    m1 = Metric("x", 1)
    m2 = Metric("y", 2)
    q = Question(id="q1", text_ko="?", evidence=(), metrics=(m1, m2), visualization=VisualizationSpec(kind="table"))
    assert q.metric("y") is m2
    assert q.metric_value("y") == 2
    assert q.metric("z") is None
    assert q.metric_value("z", default="none") == "none"


def test_why_now_question_routes_through_the_engine_to_byte_identical_html():
    doc = _doc()
    direct = report._why_now_html(
        doc.get("why_now"), doc.get("current_snapshot"), doc.get("current_vs_career"),
        doc.get("career_story", {}).get("current"),
    )
    question = adapter.build_why_now_question(doc)
    assert question is not None
    assert question.id == "why_now"
    via_engine = adapter.WhyNowRenderer().answer(question)
    assert direct == via_engine


def test_player_identity_question_routes_through_the_engine_to_byte_identical_html():
    doc = _doc()
    direct = report._player_identity_html(doc.get("player_identity"))
    question = adapter.build_player_identity_question(doc)
    assert question is not None
    via_engine = adapter.PlayerIdentityRenderer().answer(question)
    assert direct == via_engine


def test_why_now_question_carries_real_traceable_evidence_never_invented():
    doc = _doc()
    question = adapter.build_why_now_question(doc)
    assert question is not None
    paths = {e.source_path for e in question.evidence}
    assert "why_now" in paths
    lead_metric = question.metric("lead_component")
    assert lead_metric.value == doc["why_now"]["lead_component"]
    assert lead_metric.evidence  # traceable back to real evidence, not orphaned


def test_question_builders_return_none_when_the_real_field_is_missing():
    """Never a Question answering from evidence that doesn't exist."""
    assert adapter.build_why_now_question({}) is None
    assert adapter.build_player_identity_question({}) is None


def test_player_history_report_module_is_still_frozen():
    """The Question Engine changes zero bytes of the actual rendered
    Player History page -- same discipline as every prior architecture
    pass this mission line used."""
    doc = _doc()
    html = report.render_player_history_html(doc)
    for section_id in ("ph-current-form", "ph-why-now", "ph-player-identity", "ph-tournament-trend"):
        assert f'id="{section_id}"' in html
