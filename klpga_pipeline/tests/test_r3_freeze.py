"""R3 HOUSE: klpga.neo_win.r3_freeze -- the immutable R3 freeze
artifact. Synthetic-only (isolated tournament_context fixtures), never
touches real KB artifacts."""
from __future__ import annotations

import json

import pytest

from klpga.neo_win.r3_freeze import (
    R3FrozenEvidence, build_r3_frozen_evidence, load_r3_freeze, r3_freeze_exists,
    verify_r3_freeze_hash, write_r3_freeze_immutable,
)
from klpga.tournament_context import TournamentContext


@pytest.fixture
def context(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    monkeypatch.setattr(tc, "CONTENT_DIR", tmp_path / "content")
    (tmp_path / "content").mkdir()
    return TournamentContext(
        game_code="TEST0003", tournament_name="SYNTHETIC R3 TEST OPEN", season=2026,
        start_date="2026-01-01", end_date="2026-01-04", final_round_number=4,
        current_round_number=3, url_base="/tournaments/2026/TEST0003/",
        stage_state_filename="TEST0003_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )


@pytest.fixture
def r2_freeze_path(tmp_path, context):
    p = tmp_path / "content" / "TEST0003_R2_FROZEN_EVIDENCE.json"
    p.write_text(json.dumps({"records": [{"player_id": "p1"}]}), encoding="utf-8")
    return p


def _records():
    return [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": -2, "r2_score_to_par": -1, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "WD", "r1_score_to_par": 1, "r2_score_to_par": 2, "r3_score_to_par": None},
    ]


def test_round_must_be_3():
    with pytest.raises(ValueError, match="round must be 3"):
        R3FrozenEvidence(
            schema_version="x", game_code="X", round=2, official_source_identity="x",
            official_source_url=None, collection_timestamp="t", raw_official_response_sha256="h",
            parsed_canonical_sha256="h", expected_field_count=1, observed_player_count=1,
            status_counts={}, wd_dq_dns_evidence=[], feature_cutoff="END_OF_R3",
            r2_freeze_artifact="x", r2_freeze_sha256="h", code_commit="x", build_id="x", records=[],
        )


def test_cut_status_never_valid_at_r3():
    """The cut is settled by R2 -- CUT is never a real R3-stage status."""
    with pytest.raises(ValueError, match="CUT is settled by R2"):
        R3FrozenEvidence(
            schema_version="neo_r3_frozen_evidence_v1", game_code="X", round=3, official_source_identity="x",
            official_source_url=None, collection_timestamp="t", raw_official_response_sha256="h",
            parsed_canonical_sha256="h", expected_field_count=1, observed_player_count=1,
            status_counts={}, wd_dq_dns_evidence=[], feature_cutoff="END_OF_R3",
            r2_freeze_artifact="x", r2_freeze_sha256="h", code_commit="x", build_id="x",
            records=[{"player_id": "p1", "status": "CUT"}],
        )


def test_build_and_write_and_load_roundtrip(context, r2_freeze_path, tmp_path):
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="klpga.co.kr roundLeaderboard", official_source_url=None,
        collection_timestamp="2026-01-04T10:00:00Z", raw_official_response=b"[]", records=_records(),
        expected_field_count=2, status_counts={"ACTIVE": 1, "WD": 1, "DQ": 0, "DNS": 0},
        wd_dq_dns_evidence=[{"player_id": "p2", "status": "WD", "evidence": "official R3 leaderboard row"}],
        r2_freeze_path=r2_freeze_path, repo_root=tmp_path, build_id="B1",
    )
    assert not r3_freeze_exists(context)
    write_r3_freeze_immutable(context, evidence)
    assert r3_freeze_exists(context)
    loaded = load_r3_freeze(context)
    assert loaded["observed_player_count"] == 2
    assert loaded["r2_freeze_artifact"] == r2_freeze_path.name
    assert verify_r3_freeze_hash(context) is True


def test_write_is_immutable_refuses_overwrite(context, r2_freeze_path, tmp_path):
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="x", official_source_url=None,
        collection_timestamp="t", raw_official_response=b"[]", records=_records(),
        expected_field_count=2, status_counts={"ACTIVE": 1, "WD": 1, "DQ": 0, "DNS": 0},
        wd_dq_dns_evidence=[], r2_freeze_path=r2_freeze_path, repo_root=tmp_path, build_id="B1",
    )
    write_r3_freeze_immutable(context, evidence)
    with pytest.raises(FileExistsError):
        write_r3_freeze_immutable(context, evidence)


def test_missing_r2_freeze_refuses_to_build(context, tmp_path):
    with pytest.raises(FileNotFoundError):
        build_r3_frozen_evidence(
            context=context, official_source_identity="x", official_source_url=None,
            collection_timestamp="t", raw_official_response=b"[]", records=_records(),
            expected_field_count=2, status_counts={}, wd_dq_dns_evidence=[],
            r2_freeze_path=tmp_path / "does_not_exist.json", repo_root=tmp_path, build_id="B1",
        )


def test_load_missing_freeze_returns_none(context):
    assert load_r3_freeze(context) is None
    assert verify_r3_freeze_hash(context) is False
