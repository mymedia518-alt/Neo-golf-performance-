"""Tests for src/klpga/website_v2/player_intelligence_v2.py (Sprint 3)."""

from __future__ import annotations

import json
import os

import pytest

from klpga.website_v2 import player_intelligence_v2 as piv2


@pytest.fixture(autouse=True)
def _isolate_content_dir(tmp_path, monkeypatch):
    pi_dir = tmp_path / "player_intelligence"
    queue_path = tmp_path / "generation_queue.json"
    monkeypatch.setattr(piv2, "KNOWLEDGE_ENGINE_PI_DIR", pi_dir)
    monkeypatch.setattr(piv2, "GENERATION_QUEUE_PATH", queue_path)
    piv2._DOC_CACHE.clear()
    yield
    piv2._DOC_CACHE.clear()


def _write_doc(pi_dir, player_id, **overrides):
    doc = {
        "schema_version": "player_intelligence_generator_v2",
        "hero": {"player_id": player_id, "player_name": "테스트 선수", "current_season": 2025, "sample_count": 10},
        "player_type": {"key": "balanced", "label_ko": "균형형", "label_en": "Balanced", "evidence_text": "균형형입니다.", "citations": []},
        "player_dna": {"axes": [{"key": "sg_app", "label": "SG Approach", "percentile": 80.0}]},
        "current_form": {"recent_5_sg": 1.0, "recent_10_sg": 0.8, "long_term_sg": 0.5, "volatility": 0.3, "rate_stats": {"birdie_rate": 20.0}},
        "shot_profile": {"season": 2025, "avg_total": 1.0, "avg_ott": 0.1, "avg_app": 0.5, "avg_arg": 0.1, "avg_putt": 0.3},
        "course_fit": {"history": []},
        "strengths": [{"metric": "sg_app", "label": "SG Approach", "percentile": 80.0}],
        "weaknesses": [],
        "why_wins": [{"text": "테스트 승리 요인", "citations": [{"source": "x.json", "field_path": "y", "value": 1}]}],
        "why_loses": [],
        "evolution": {"status": "OK", "narrative": "상승 추세입니다.", "steps": [{"season": 2025, "avg_total": 1.0, "delta_from_prev": None, "strongest_component": "avg_app", "weakest_component": "avg_ott"}], "citations": []},
        "neo_verdict": {"summary": "테스트 선수는 균형형입니다."},
        "sources": [],
        "_meta": {"generated_at": "2025-01-01T00:00:00+00:00", "tournament_game_code": None},
    }
    doc.update(overrides)
    player_dir = pi_dir / str(player_id)
    player_dir.mkdir(parents=True, exist_ok=True)
    (player_dir / "latest.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


# ---------------------------------------------------------------------------
# load_document_cached
# ---------------------------------------------------------------------------


def test_load_document_cached_missing_returns_none():
    assert piv2.load_document_cached("NOPE") is None


def test_load_document_cached_returns_real_doc(tmp_path):
    doc = _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    loaded = piv2.load_document_cached("P1")
    assert loaded["hero"]["player_id"] == "P1"
    assert loaded == doc


def test_load_document_cached_hits_cache_same_object():
    _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    first = piv2.load_document_cached("P1")
    second = piv2.load_document_cached("P1")
    assert first is second


def test_load_document_cached_invalidates_on_mtime_change():
    _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    first = piv2.load_document_cached("P1")

    path = piv2.latest_json_path("P1")
    doc2 = json.loads(path.read_text(encoding="utf-8"))
    doc2["hero"]["player_name"] = "변경된 이름"
    path.write_text(json.dumps(doc2, ensure_ascii=False), encoding="utf-8")
    later = first["_meta"]["generated_at"]  # unused, just to keep first referenced
    os.utime(path, (path.stat().st_atime + 5, path.stat().st_mtime + 5))

    second = piv2.load_document_cached("P1")
    assert second["hero"]["player_name"] == "변경된 이름"
    assert second is not first


# ---------------------------------------------------------------------------
# enqueue_generation
# ---------------------------------------------------------------------------


def test_enqueue_generation_creates_real_file():
    assert not piv2.GENERATION_QUEUE_PATH.exists()
    piv2.enqueue_generation("P1", player_name="테스트")
    assert piv2.GENERATION_QUEUE_PATH.exists()
    queue = json.loads(piv2.GENERATION_QUEUE_PATH.read_text(encoding="utf-8"))
    assert queue["pending"] == [{"player_id": "P1", "player_name": "테스트"}]


def test_enqueue_generation_is_idempotent():
    piv2.enqueue_generation("P1", player_name="테스트")
    piv2.enqueue_generation("P1", player_name="테스트")
    queue = json.loads(piv2.GENERATION_QUEUE_PATH.read_text(encoding="utf-8"))
    assert len(queue["pending"]) == 1


# ---------------------------------------------------------------------------
# render_player_intelligence_v2_html
# ---------------------------------------------------------------------------


def test_render_player_intelligence_v2_html_all_sections_present():
    doc = _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    html = piv2.render_player_intelligence_v2_html(doc)
    for section_id in (
        "player-type",
        "player-dna",
        "key-kpis",
        "current-form",
        "shot-profile",
        "course-fit",
        "strengths",
        "risks",
        "evolution",
        "why-wins",
        "why-loses",
        "neo-verdict",
    ):
        assert f'id="{section_id}"' in html, f"missing section {section_id}"
    assert "테스트 선수" in html
    assert "테스트 승리 요인" in html


def test_render_player_intelligence_v2_html_never_fabricates_empty_states():
    doc = _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1", why_loses=[], weaknesses=[], course_fit={"history": []})
    html = piv2.render_player_intelligence_v2_html(doc)
    assert "해당 없음" in html  # explicit empty-state text, never a fabricated reason
    assert "과거 출전 기록이 없습니다" in html


def test_render_player_intelligence_v2_html_sections_are_collapsible_details():
    doc = _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    html = piv2.render_player_intelligence_v2_html(doc)
    assert html.count("<details") >= 12  # 12 collapsible sections + nested evidence details
    assert "<header class=\"pi-hero" in html  # hero is NOT inside a <details>


def test_render_player_intelligence_v2_html_prev_next_links():
    doc = _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    html = piv2.render_player_intelligence_v2_html(
        doc,
        prev_link={"href": "/player/10001/", "name": "이전 선수"},
        next_link={"href": "/player/10003/", "name": "다음 선수"},
    )
    assert 'href="/player/10001/"' in html
    assert 'href="/player/10003/"' in html


# ---------------------------------------------------------------------------
# render_generating_placeholder_html
# ---------------------------------------------------------------------------


def test_render_generating_placeholder_html_never_empty():
    html = piv2.render_generating_placeholder_html("P1", player_name="테스트")
    assert "Generating Player Intelligence" in html
    assert "테스트" in html
    assert html.strip()


# ---------------------------------------------------------------------------
# build_or_placeholder
# ---------------------------------------------------------------------------


def test_build_or_placeholder_real_doc():
    _write_doc(piv2.KNOWLEDGE_ENGINE_PI_DIR, "P1")
    html = piv2.build_or_placeholder("P1", player_name="테스트 선수")
    assert "Generating Player Intelligence" not in html
    assert "테스트 선수" in html


def test_build_or_placeholder_missing_queues_and_placeholders():
    html = piv2.build_or_placeholder("MISSING_ID", player_name="미생성 선수")
    assert "Generating Player Intelligence" in html
    queue = json.loads(piv2.GENERATION_QUEUE_PATH.read_text(encoding="utf-8"))
    assert queue["pending"][0]["player_id"] == "MISSING_ID"


# ---------------------------------------------------------------------------
# Real integration test against player 10097
# ---------------------------------------------------------------------------


def test_integration_real_player_10097(monkeypatch):
    from klpga.tournament_context import CONTENT_DIR

    real_dir = CONTENT_DIR / "knowledge_engine" / "player_intelligence"
    monkeypatch.setattr(piv2, "KNOWLEDGE_ENGINE_PI_DIR", real_dir)
    piv2._DOC_CACHE.clear()

    html = piv2.build_or_placeholder("10097", player_name="김민선7")
    assert "Generating Player Intelligence" not in html
    assert "정교한 아이언 플레이어" in html
