"""Tests for klpga.neo_win.hitejinro_round_pipeline -- the round-
agnostic (R1/R2/R3/FR) evidence pipeline extracted 2026-10-01 from
scripts/200-203_*_r1_*.py, which each hardcoded round=1. Exercises the
REAL R1 evidence already committed under content/website_v2/ (the
same operator-saved klpga.co.kr captures used to build the real,
published R1 page) rather than synthetic fixtures -- this project's
established convention of testing against real data wherever it
already exists in the repo.

Also covers the one new fail-closed gate this module added:
require_raw_evidence() must refuse, before any write, the moment a
round's raw captures aren't on disk yet (e.g. R2, which this repo has
never received) -- 공식 데이터 없음, never fabricated."""
from __future__ import annotations

import json

import pytest

from klpga.neo_win import hitejinro_round_pipeline as _rp
from klpga.neo_win.hitejinro_round_pipeline import (
    GAME_CODE,
    LEADERBOARD_PATH,
    cross_validate,
    parse_leaderboard,
    parse_sg,
    raw_evidence_path,
    require_raw_evidence,
    sg_output_path,
)

pytestmark = pytest.mark.round_pipeline

_R1_EVIDENCE_PRESENT = all(raw_evidence_path(1, kind).is_file() for kind in ("LEADERBOARD", "SG", "SCORECARD"))

requires_r1_evidence = pytest.mark.skipif(
    not _R1_EVIDENCE_PRESENT,
    reason="real R1 raw evidence not present in this checkout -- see content/website_v2/incoming_evidence/2026100005/",
)


def test_require_raw_evidence_fails_closed_for_a_round_with_no_capture():
    """R2 (and R3/FR) have never received a real operator capture in
    this repo -- this must raise, naming every missing file, before
    parsing/merging/building anything. Never fabricates R2 data."""
    for round_number in (2, 3, 4):
        if all(raw_evidence_path(round_number, kind).is_file() for kind in ("LEADERBOARD", "SG", "SCORECARD")):
            pytest.skip(f"round {round_number} unexpectedly has real evidence now -- this test's premise changed")
        with pytest.raises(FileNotFoundError, match="공식 데이터 없음"):
            require_raw_evidence(round_number)


@requires_r1_evidence
def test_require_raw_evidence_passes_for_round_1():
    paths = require_raw_evidence(1)
    assert set(paths) == {"LEADERBOARD", "SG", "SCORECARD"}
    assert all(p.is_file() for p in paths.values())


@requires_r1_evidence
def test_parse_leaderboard_reproduces_the_real_r1_facts(tmp_path, monkeypatch):
    # 2026-10-02 fix: parse_leaderboard writes to the module-level
    # LEADERBOARD_PATH constant, which is THE single shared production
    # file every real round's data lives in (R1, then R2, then R3...).
    # Calling parse_leaderboard(1) against the real path here would
    # silently overwrite whatever real, more-advanced round data is
    # currently live -- confirmed this actually happened: running this
    # suite after the real R2 pipeline had already run reverted the
    # live, committed LEADERBOARD.json back to R1-only. Redirecting the
    # constant to a tmp_path keeps this test's real R1-evidence
    # assertions intact without ever touching the real production file.
    tmp_leaderboard = tmp_path / "LEADERBOARD.json"
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_leaderboard)
    out_path = parse_leaderboard(1)
    assert out_path == tmp_leaderboard
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    assert doc["game_code"] == GAME_CODE
    assert doc["final_round"] == 1
    assert doc["coverage"]["player_count"] == 108
    assert doc["coverage"]["completed_round1_count"] == 107
    not_yet_complete = doc["coverage"]["not_yet_complete_at_capture_time"]
    assert [p["player_id"] for p in not_yet_complete] == ["9401"]  # 마다솜, real disclosed gap
    completed = [r for r in doc["records"] if r["r1_score"] is not None]
    assert len(completed) == 107
    incomplete = [r for r in doc["records"] if r["player_id"] == "9401"][0]
    assert incomplete["r1_score"] is None
    assert incomplete["finish_position"] is None


@requires_r1_evidence
def test_parse_sg_is_a_verified_bijection_against_completed_r1_players(tmp_path, monkeypatch):
    tmp_leaderboard = tmp_path / "LEADERBOARD.json"
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_leaderboard)
    parse_leaderboard(1)  # SG join depends on LEADERBOARD.json already existing
    out_path = parse_sg(1)
    assert out_path == sg_output_path(1)
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    assert doc["game_code"] == GAME_CODE
    assert doc["round_number"] == 1
    assert doc["identity_join"]["bijection_verified"] is True
    assert doc["coverage"]["player_count"] == 107
    assert all(r["rounds"] <= 1 for r in doc["records"])
    assert {r["player_id"] for r in doc["records"]} == {
        r["player_id"] for r in json.loads(tmp_leaderboard.read_text(encoding="utf-8"))["records"]
        if r["r1_score"] is not None
    }


@requires_r1_evidence
def test_cross_validate_reports_a_100_percent_match_for_real_r1(tmp_path, monkeypatch):
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    parse_leaderboard(1)
    result = cross_validate(1)
    assert result["verdict"] == "100% MATCH"
    assert result["mismatches"] == []
    assert result["round_label"] == "R1"
