"""Tests for src/klpga/knowledge_engine/tournament_dna_generator.py (Sprint 4)."""

from __future__ import annotations

import json

import pytest

from klpga.knowledge_engine import tournament_dna_generator as tdg


@pytest.fixture(autouse=True)
def _isolate_output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(tdg, "OUTPUT_ROOT", tmp_path)
    yield


def test_validate_rejects_missing_section():
    doc = {"identity": {"game_code": "g1", "tournament_name": "t"}}
    problems = tdg.validate_tournament_dna_document(doc)
    assert any("course_dna" in p for p in problems)


def test_validate_rejects_verdict_over_two_sentences():
    doc = {s: {} for s in tdg.REQUIRED_SECTIONS}
    doc["identity"] = {"game_code": "g1", "tournament_name": "t"}
    doc["verdict"] = {"summary": "하나. 둘. 셋."}
    doc["story"] = []
    problems = tdg.validate_tournament_dna_document(doc)
    assert any("2 sentences" in p for p in problems)


def test_validate_clean_document_has_no_problems():
    doc = {s: {} for s in tdg.REQUIRED_SECTIONS}
    doc["identity"] = {"game_code": "g1", "tournament_name": "t"}
    doc["verdict"] = {"summary": "하나. 둘."}
    doc["story"] = ["사실 하나"]
    problems = tdg.validate_tournament_dna_document(doc)
    assert problems == []


def test_generate_one_real_write_then_skip(tmp_path):
    r1 = tdg.generate_one("2026120001")
    assert r1.status == "written"
    path = tmp_path / "2026120001" / "TournamentDNA.json"
    assert path.exists()

    r2 = tdg.generate_one("2026120001")
    assert r2.status == "skipped"


def test_generate_one_force_always_rewrites():
    tdg.generate_one("2026120001")
    r2 = tdg.generate_one("2026120001", force=True)
    assert r2.status == "written"


def test_generate_one_never_raises_on_bad_game_code():
    result = tdg.generate_one("NO_SUCH_GAME_CODE_XYZ")
    assert result.status == "error"
    assert result.error


def test_generate_one_real_kg_ladies_open_includes_hole_sections():
    result = tdg.generate_one("2026080001")
    assert result.status == "written"
    doc = json.loads(result.path.read_text(encoding="utf-8"))
    assert len(doc["danger_holes"]) > 0
    assert len(doc["opportunity_holes"]) > 0


def test_generated_document_has_no_validation_problems():
    result = tdg.generate_one("2026120001")
    doc = json.loads(result.path.read_text(encoding="utf-8"))
    assert tdg.validate_tournament_dna_document(doc) == []
