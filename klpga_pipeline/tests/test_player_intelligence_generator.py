"""Tests for src/klpga/knowledge_engine/player_intelligence_generator.py"""

from __future__ import annotations

import json

import pytest

from klpga.knowledge_engine import knowledge_engine as ke
from klpga.knowledge_engine import player_intelligence_generator as pig


@pytest.fixture(autouse=True)
def _isolate_output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(pig, "OUTPUT_ROOT", tmp_path)
    yield


def _real_evidence(player_id="10097", tournament_name="OK저축은행 읏맨 오픈"):
    return ke.build_evidence(player_id, tournament_context={"tournament_name": tournament_name})


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def test_build_shot_profile_uses_current_season_components():
    evidence = _real_evidence()
    profile = pig.build_shot_profile(evidence, existing_doc=None)
    assert profile["season"] == evidence.current_season
    assert profile["avg_total"] == evidence.current_season_components.get("avg_total")


def test_build_course_fit_uses_course_history():
    evidence = _real_evidence()
    fit = pig.build_course_fit(evidence, existing_doc=None)
    assert fit["history"] == evidence.course_history


def test_build_neo_verdict_combines_type_wins_losses_evolution():
    evidence = _real_evidence()
    player_type = ke.classify_player_type(evidence)
    why_wins = ke.generate_why_wins(evidence)
    why_loses = ke.generate_why_loses(evidence)
    evolution = ke.generate_evolution(evidence)
    verdict = pig.build_neo_verdict(evidence.player_name, player_type, why_wins, why_loses, evolution)
    assert evidence.player_name in verdict["summary"]
    assert player_type.label_ko in verdict["summary"]


# ---------------------------------------------------------------------------
# assemble_document / validate_player_intelligence_document
# ---------------------------------------------------------------------------


def test_assemble_document_has_all_required_sections_and_validates_clean():
    evidence = _real_evidence()
    doc = pig.assemble_document("10097", evidence, tournament_context={"tournament_name": "OK저축은행 읏맨 오픈"})
    for section in pig.REQUIRED_SECTIONS:
        assert section in doc
    assert pig.validate_player_intelligence_document(doc) == []


def test_strengths_and_weaknesses_use_wider_cap_than_why_wins_loses():
    evidence = _real_evidence()
    strengths = pig.build_strengths(evidence)
    weaknesses = pig.build_weaknesses(evidence)
    assert len(strengths) <= pig.MAX_STRENGTHS
    assert len(weaknesses) <= pig.MAX_WEAKNESSES
    assert pig.MAX_STRENGTHS >= ke.MAX_REASONS
    assert pig.MAX_WEAKNESSES >= ke.MAX_REASONS


def test_validate_rejects_missing_section():
    evidence = _real_evidence()
    doc = pig.assemble_document("10097", evidence, tournament_context={"tournament_name": "OK저축은행 읏맨 오픈"})
    del doc["neo_verdict"]
    problems = pig.validate_player_intelligence_document(doc)
    assert any("neo_verdict" in p for p in problems)


def test_validate_rejects_insight_without_citations():
    evidence = _real_evidence()
    doc = pig.assemble_document("10097", evidence, tournament_context={"tournament_name": "OK저축은행 읏맨 오픈"})
    doc["why_wins"] = [{"text": "근거 없는 문장", "citations": []}]
    problems = pig.validate_player_intelligence_document(doc)
    assert any("why_wins[0]" in p for p in problems)


# ---------------------------------------------------------------------------
# compute_input_signature
# ---------------------------------------------------------------------------


def test_compute_input_signature_stable_for_same_inputs():
    warehouse_doc = ke.load_warehouse()
    sg_doc = ke.load_sg_field()
    profile_doc = ke.load_profile_field()
    ctx = {"tournament_name": "OK저축은행 읏맨 오픈", "game_code": "G1"}
    sig1 = pig.compute_input_signature("10097", warehouse_doc, sg_doc, profile_doc, None, ctx)
    sig2 = pig.compute_input_signature("10097", warehouse_doc, sg_doc, profile_doc, None, ctx)
    assert sig1 == sig2


def test_compute_input_signature_sensitive_to_tournament_context():
    warehouse_doc = ke.load_warehouse()
    sg_doc = ke.load_sg_field()
    profile_doc = ke.load_profile_field()
    sig1 = pig.compute_input_signature("10097", warehouse_doc, sg_doc, profile_doc, None, {"tournament_name": "A", "game_code": "G1"})
    sig2 = pig.compute_input_signature("10097", warehouse_doc, sg_doc, profile_doc, None, {"tournament_name": "B", "game_code": "G1"})
    assert sig1 != sig2


def test_compute_input_signature_ignores_existing_doc():
    """existing_doc must never be hashed -- otherwise the skip check
    would fold the previous run's own signature into the next one and
    never converge."""
    warehouse_doc = ke.load_warehouse()
    sg_doc = ke.load_sg_field()
    profile_doc = ke.load_profile_field()
    ctx = {"tournament_name": "OK저축은행 읏맨 오픈", "game_code": "G1"}
    sig_no_existing = pig.compute_input_signature("10097", warehouse_doc, sg_doc, profile_doc, None, ctx)
    sig_with_existing = pig.compute_input_signature("10097", warehouse_doc, sg_doc, profile_doc, {"some": "doc"}, ctx)
    assert sig_no_existing == sig_with_existing


# ---------------------------------------------------------------------------
# generate_one
# ---------------------------------------------------------------------------


def test_generate_one_real_write_then_skip(tmp_path):
    ctx = {"tournament_name": "OK저축은행 읏맨 오픈", "game_code": "G1"}
    r1 = pig.generate_one("10097", tournament_context=ctx)
    assert r1.status == "written"
    assert (tmp_path / "10097" / "latest.json").exists()

    r2 = pig.generate_one("10097", tournament_context=ctx)
    assert r2.status == "skipped"


def test_generate_one_force_always_rewrites():
    ctx = {"tournament_name": "OK저축은행 읏맨 오픈", "game_code": "G1"}
    pig.generate_one("10097", tournament_context=ctx)
    r2 = pig.generate_one("10097", tournament_context=ctx, force=True)
    assert r2.status == "written"


def test_generate_one_writes_history_only_with_context(tmp_path):
    r_no_ctx = pig.generate_one("10097")
    assert r_no_ctx.status == "written"
    assert not (tmp_path / "10097" / "history").exists()

    r_ctx = pig.generate_one("10097", tournament_context={"tournament_name": "OK저축은행 읏맨 오픈", "game_code": "G1"}, force=True)
    assert r_ctx.status == "written"
    assert (tmp_path / "10097" / "history" / "G1.json").exists()


def test_generate_one_never_raises_on_bad_id():
    result = pig.generate_one("NO_SUCH_PLAYER_ID_XYZ")
    assert result.status in ("written", "error")  # never an uncaught exception
    assert result.error is None or isinstance(result.error, str)


# ---------------------------------------------------------------------------
# generate_many
# ---------------------------------------------------------------------------


def test_generate_many_survives_one_players_exception(monkeypatch):
    real_build_evidence = ke.build_evidence

    def _boom_for_one(player_id, tournament_context=None):
        if player_id == "BOOM":
            raise RuntimeError("synthetic failure")
        return real_build_evidence(player_id, tournament_context=tournament_context)

    monkeypatch.setattr(ke, "build_evidence", _boom_for_one)
    batch = pig.generate_many(["10097", "BOOM", "10002"], max_workers=2)
    assert len(batch.results) == 3
    assert any(r.player_id == "BOOM" and r.status == "error" for r in batch.results)
    assert any(r.player_id == "10097" and r.status == "written" for r in batch.results)


def test_generate_many_reports_skip_counts_on_rerun():
    ids = ["10097", "10002"]
    batch1 = pig.generate_many(ids, max_workers=2)
    assert len(batch1.written) == 2
    assert len(batch1.skipped) == 0

    batch2 = pig.generate_many(ids, max_workers=2)
    assert len(batch2.skipped) == 2
    assert len(batch2.written) == 0


# ---------------------------------------------------------------------------
# players_for_tournament / discover_player_universe
# ---------------------------------------------------------------------------


def test_players_for_tournament_fails_closed():
    class FakeContext:
        game_code = "NO_SUCH_GAME_CODE"

        def artifact_path(self, artifact_type, ext="json"):
            from klpga.tournament_context import CONTENT_DIR

            return CONTENT_DIR / f"{self.game_code}_{artifact_type.upper()}.{ext}"

    with pytest.raises(FileNotFoundError):
        pig.players_for_tournament(FakeContext())


def test_players_for_tournament_reads_real_entry_snapshot():
    class FakeContext:
        game_code = "2026090002"

        def artifact_path(self, artifact_type, ext="json"):
            from klpga.tournament_context import CONTENT_DIR

            return CONTENT_DIR / f"{self.game_code}_{artifact_type.upper()}.{ext}"

    players = pig.players_for_tournament(FakeContext())
    assert len(players) == 108
    assert "9174" in players


def test_discover_player_universe_returns_real_roster():
    universe = pig.discover_player_universe()
    assert len(universe) > 100
    assert "10097" in universe


# ---------------------------------------------------------------------------
# Frozen Sprint-1 API contract check
# ---------------------------------------------------------------------------


def test_sprint1_public_api_is_frozen():
    for name in (
        "build_evidence",
        "classify_player_type",
        "generate_why_wins",
        "generate_why_loses",
        "generate_evolution",
        "generate_if_today",
        "generate_player_intelligence",
        "to_json_dict",
        "field_percentile",
        "compute_field_percentiles",
        "compute_season_profiles",
        "find_course_history",
    ):
        assert hasattr(ke, name), f"knowledge_engine.{name} is missing -- Sprint 1 API must stay frozen"
