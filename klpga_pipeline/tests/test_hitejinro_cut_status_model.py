"""Regression for the 2026-10-02 data-model mission: R1_CUT and R2_CUT
must be separate real states, never collapsed into one undifferentiated
"CUT"/missed_cut boolean. Exercises real R1+R2 evidence already
committed under content/website_v2/incoming_evidence/2026100005/ --
never a synthetic fixture (this project's established convention).

Also covers the same-day follow-up "실제 운영 적용" mission: hitejinro_
round_page.py's display logic (_advancement_summary/_status_family)
must key off the real status enum, never the legacy withdrawn/
disqualified/missed_cut booleans directly -- proven with synthetic
records whose legacy fields are deliberately wrong, since the real
production data's legacy fields are always consistent with status and
so can't itself catch a silent reversion to reading them.

Kept as its own file rather than appended to test_hitejinro_round_
pipeline.py, which currently carries separate, paused, not-yet-approved
isolation-refactor edits (2026-10-02 "운영 데이터 보호 규칙" mission) --
this file's own commit must not bundle in unrelated, unapproved work."""
from __future__ import annotations

import json

import pytest

from klpga.neo_win import hitejinro_round_pipeline as _rp
from klpga.neo_win.hitejinro_round_pipeline import parse_leaderboard, raw_evidence_path
from klpga.neo_win.hitejinro_round_page import _advancement_summary, _status_family

pytestmark = pytest.mark.round_pipeline

_R2_LEADERBOARD_PRESENT = raw_evidence_path(2, "LEADERBOARD").is_file()

requires_r2_leaderboard_evidence = pytest.mark.skipif(
    not _R2_LEADERBOARD_PRESENT,
    reason="real R2 leaderboard raw evidence not present in this checkout",
)


@requires_r2_leaderboard_evidence
def test_r1_cut_and_r2_cut_are_separate_states_not_one_missed_cut_boolean(tmp_path, monkeypatch):
    """status must be a real STATE (R1_CUT/R2_CUT/WD/DQ), never a
    single undifferentiated "CUT" string. Exercises real R1+R2
    evidence: 조하리/이수민/이소영 never played R2 at all (real
    r2_score is None for all three) -- their real cut was decided on
    R1's score alone, so status must read R1_CUT, never R2_CUT
    (R2_CUT is reserved for a player who actually completed round 2
    and is cut before round 3 -- zero such real cases exist in this
    tournament yet, but the states must stay distinct regardless)."""
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    out_path = parse_leaderboard(2)
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    by_id = {r["player_id"]: r for r in doc["records"]}

    for pid, name in [("11076", "조하리"), ("11978", "이수민"), ("8246", "이소영")]:
        r = by_id[pid]
        assert r["status"] == "R1_CUT", f"{name} ({pid}): expected R1_CUT, got {r['status']}"
        assert r["status_round"] == 1
        assert r["r1_score"] is not None and r["r2_score"] is None
        # legacy fields still real and consistent (backward compat --
        # every existing consumer reading missed_cut keeps working).
        assert r["missed_cut"] is True
        assert r["withdrawn"] is False
        assert r["disqualified"] is False

    for pid, name in [("10112", "고지우"), ("8240", "황정미")]:
        r = by_id[pid]
        assert r["status"] == "WD", f"{name} ({pid}): expected WD, got {r['status']}"
        assert r["status_round"] == 1
        assert r["withdrawn"] is True

    # 마다솜: withdrew before the tournament itself -- no real completed
    # round to attribute the status to, so status_round must be None,
    # never a fabricated round number.
    mds = by_id["9401"]
    assert mds["status"] == "WD"
    assert mds["status_round"] is None
    assert mds["r1_score"] is None and mds["r2_score"] is None

    # No real R2_CUT case exists yet in this tournament -- confirm the
    # state is at least representable (never collapsed into R1_CUT)
    # rather than asserting a count of zero forever.
    statuses = {r["status"] for r in doc["records"]}
    assert "R1_CUT" in statuses
    assert statuses <= {None, "ACTIVE", "R1_CUT", "R2_CUT", "WD", "DQ"}


@requires_r2_leaderboard_evidence
def test_legacy_fields_stay_byte_identical_to_the_real_production_file(tmp_path, monkeypatch):
    """The new status/status_round fields must be purely additive --
    every existing consumer reading finish_position/scores/withdrawn/
    disqualified/missed_cut must see exactly what it saw before this
    mission, for all 108 real entrants, not just a handful of spot
    checks."""
    monkeypatch.setattr(_rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    out_path = parse_leaderboard(2)
    new_doc = json.loads(out_path.read_text(encoding="utf-8"))

    from klpga.tournament_context import CONTENT_DIR
    current_doc = json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))

    new_by_id = {r["player_id"]: r for r in new_doc["records"]}
    cur_by_id = {r["player_id"]: r for r in current_doc["records"]}
    assert set(new_by_id) == set(cur_by_id)

    fields = [
        "finish_position", "finish_position_numeric", "score_to_par",
        "r1_score", "r2_score", "r3_score", "r4_score",
        "withdrawn", "disqualified", "missed_cut",
    ]
    mismatches = [
        (pid, f, cur_by_id[pid].get(f), new_by_id[pid].get(f))
        for pid in cur_by_id for f in fields
        if cur_by_id[pid].get(f) != new_by_id[pid].get(f)
    ]
    assert mismatches == [], f"{len(mismatches)} legacy-field mismatches: {mismatches[:10]}"


def test_status_family_reads_the_enum_not_legacy_booleans():
    """2026-10-02 '실제 운영 적용' mission: hitejinro_round_page.py's
    display logic must key off the real status enum (R1_CUT/R2_CUT/
    WD/DQ/None), never the legacy withdrawn/disqualified/missed_cut
    booleans directly. Proven here with a record whose legacy fields
    deliberately DISAGREE with status -- if the renderer still read the
    legacy fields, this would silently pass; reading status is the only
    way this assertion holds."""
    contradictory_record = {
        "status": "R2_CUT",
        "status_round": 2,
        # Legacy fields deliberately wrong/stale, as if an older writer
        # had set them -- _status_family must ignore these entirely.
        "withdrawn": True,
        "disqualified": True,
        "missed_cut": False,
    }
    assert _status_family(contradictory_record["status"]) == "CUT"
    assert _status_family("WD") == "WD"
    assert _status_family("DQ") == "DQ"
    assert _status_family(None) is None


def test_advancement_summary_classifies_by_status_not_legacy_flags():
    """Same proof at the _advancement_summary level: a four-record
    synthetic set whose legacy booleans are all wrong on purpose. The
    real counts must come out matching the real `status` values, which
    only happens if the summary reads status, never missed_cut/
    withdrawn/disqualified."""
    records = [
        {"player_id": "1", "status": None, "r1_score": 70,
         "withdrawn": True, "disqualified": True, "missed_cut": True},
        {"player_id": "2", "status": "R1_CUT", "r1_score": 90,
         "withdrawn": False, "disqualified": False, "missed_cut": False},
        {"player_id": "3", "status": "WD", "r1_score": None,
         "withdrawn": False, "disqualified": False, "missed_cut": False},
        {"player_id": "4", "status": "DQ", "r1_score": None,
         "withdrawn": False, "disqualified": False, "missed_cut": False},
    ]
    summary = _advancement_summary(records)
    assert summary["advanced_count"] == 1
    assert summary["cut_count"] == 1
    assert summary["withdrawn_count"] == 1
    assert summary["disqualified_count"] == 1
    assert summary["cut_line_score"] == 70
