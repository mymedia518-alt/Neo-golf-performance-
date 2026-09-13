"""KB 2026090003 FINAL BUILD (operator screenshot, positions 1-33
gapless): regression tests for run_extended_comparison /
topk_set_comparison."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import klpga.tournament_context as tournament_context
from klpga.tournament_context import resolve_context
from klpga.neo_win import final_partial_evidence_validator as pev
from klpga.neo_win.final_partial_evidence_validator import PartialEvidenceBlocked

REPO_ROOT = Path(__file__).resolve().parents[1]

IDENTITY = {
    "game_code": "FIXTUREFINAL04", "tournament_name": "Fixture Final Extended Open", "season": 2027,
    "start_date": "2027-09-01", "end_date": "2027-09-04", "final_round_number": 4, "current_round_number": 3,
}
REGISTRY = {"FIXTUREFINAL04": {
    "url_base": "/tournaments/2027/fixture-final-extended-open/",
    "stage_state_filename": "FIXTURE_FINAL_EXTENDED_STAGE_STATE.json",
    "stage_order": ["pre", "r1", "r2", "r3", "fr", "final"],
}}


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _snapshot():
    # 10-player field; neo_final_rank intentionally scrambled vs.
    # simple win_pct order is not required (module trusts neo_final_rank).
    records = [
        {"player_id": f"P{i}", "player_name": f"Player{i}", "win_pct": max(1.0, 30.0 - i * 3),
         "top5_pct": 50.0, "top10_pct": 80.0, "top20_pct": 95.0, "neo_final_rank": i}
        for i in range(1, 11)
    ]
    return {
        "schema_version": 1, "artifact": "post_r3_final_forecast", "game_code": "FIXTUREFINAL04",
        "tournament_name": "Fixture Final Extended Open", "stage": "POST_R3", "source_round": 3,
        "final_round_number": 4, "r3_freeze_artifact": "x", "r3_freeze_sha256": "a" * 64,
        "future_data_excluded": True, "feature_cutoff": "END_OF_R3", "seed": 1,
        "code_commit": "abc", "build_id": "b1", "records": records,
    }


def _write_snapshot(tmp_path):
    (tmp_path / "FIXTUREFINAL04_POST_R3_FINAL_FORECAST.json").write_text(json.dumps(_snapshot()), encoding="utf-8")


def _rec(pid, name, pos_from, pos_to, rank_label):
    return {"player_id": pid, "player_name": name, "final_rank": rank_label, "position_from": pos_from, "position_to": pos_to}


def test_top5_supported_top10_not_when_gap_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    # actual top5 = P1..P5 (matches predicted exactly), but a gap exists
    # between position 5 and position 8 (positions 6-7 unknown).
    confirmed = [
        _rec("P1", "Player1", 1, 1, "1"),
        _rec("P2", "Player2", 2, 2, "2"),
        _rec("P3", "Player3", 3, 3, "3"),
        _rec("P4", "Player4", 4, 4, "4"),
        _rec("P5", "Player5", 5, 5, "5"),
        _rec("P8", "Player8", 8, 8, "8"),
    ]
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": ["x"]}
    result = pev.run_extended_comparison(context, evidence)
    assert result.positions_confirmed_gapless_through == 5
    assert result.topk[5].supported is True
    assert result.topk[5].precision == pytest.approx(1.0)
    assert result.topk[5].recall == pytest.approx(1.0)
    assert result.topk[10].supported is False
    assert "gapless" in result.topk[10].reason


def test_top10_supported_with_unmatched_name_in_range(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    confirmed = [_rec(f"P{i}", f"Player{i}", i, i, str(i)) for i in range(1, 10)]
    confirmed.append({"player_id": None, "player_name": "Mystery Player", "final_rank": "10", "position_from": 10, "position_to": 10})
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": []}
    result = pev.run_extended_comparison(context, evidence)
    assert result.topk[10].supported is True
    assert "Mystery Player" in result.topk[10].unmatched_actual_names
    # 9 real hits out of 10 predicted (P10 predicted but actual-unknown at position 10)
    assert result.topk[10].precision == pytest.approx(0.9)


def test_winner_metrics_reuse_klpga_models_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    confirmed = [_rec("P3", "Player3", 1, 1, "1"), _rec("P1", "Player1", 2, 2, "2")]
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": []}
    result = pev.run_extended_comparison(context, evidence)
    assert result.winner_player_id == "P3"
    assert result.winner_neo_probability_rank == 3
    assert result.winner_hit is False
    assert result.field_size == 10


def test_raises_when_winner_unmatched(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    confirmed = [{"player_id": None, "player_name": "Ghost", "final_rank": "1", "position_from": 1, "position_to": 1}]
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": []}
    with pytest.raises(PartialEvidenceBlocked, match="no player_id match"):
        pev.run_extended_comparison(context, evidence)


def test_real_kb_2026090003_extended_evidence_v1_end_to_end():
    evidence_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V1.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    from klpga.tournament_context import load_tournament_context
    context = load_tournament_context("2026090003")
    result = pev.run_extended_comparison(context, evidence)
    assert result.winner_name == "박보겸"
    assert result.positions_confirmed_gapless_through == 33
    assert result.topk[5].supported is True
    assert result.topk[10].supported is True
    assert result.topk[20].supported is True
    assert result.topk[5].precision == pytest.approx(0.8)
    # every unmatched name from the evidence file must surface somewhere
    # in the top-k unmatched lists, never silently dropped
    all_unmatched_seen = set()
    for k in (5, 10, 20):
        all_unmatched_seen.update(result.topk[k].unmatched_actual_names)
    assert "이예린" in all_unmatched_seen
    assert "홍정혜2" in all_unmatched_seen


def test_real_kb_2026090003_extended_evidence_v2_resolves_most_identities():
    """V2 (zoomed re-capture) must resolve nearly all of V1's
    review_required identities -- only the two genuinely-unreadable
    names (이예린, 홍정혜2, both outside the re-captured T11-T36 region)
    should remain unmatched."""
    evidence_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V2.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    from klpga.tournament_context import load_tournament_context
    context = load_tournament_context("2026090003")
    result = pev.run_extended_comparison(context, evidence)
    assert result.positions_confirmed_gapless_through == 39
    names = {u["player_name"] for u in result.unmatched_confirmed_names}
    assert names == {"이예린", "홍정혜2"}
    # previously-unresolved names must now have real player_ids
    by_name = {c.player_name: c for c in result.confirmed_players}
    assert by_name["짜라위 분짠(I)"].player_id == "11770"
    assert by_name["빳차라쭈타 콩끄라판(I)"].player_id == "1485"
    assert by_name["이주미"].player_id == "8234"
    assert by_name["문정민"].player_id == "10296"


def test_v1_evidence_file_preserved_unchanged_as_provenance():
    """Phase 11-style rule: V2 must never silently overwrite V1 --
    both files coexist, V2 explicitly names what it supersedes."""
    v1_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V1.json"
    v2_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V2.json"
    assert v1_path.is_file()
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    assert v1["schema_version"] == "operator_supplied_official_screenshot_final_v1"
    assert "supersedes" in v2
    assert "V1" in v2["supersedes"]


def test_biggest_movers_real_evidence():
    evidence_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V2.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    from klpga.tournament_context import load_tournament_context
    context = load_tournament_context("2026090003")
    result = pev.run_extended_comparison(context, evidence)
    over, under = pev.biggest_movers(result, n=3)
    assert all(c.rank_delta < 0 for c in over)
    assert all(c.rank_delta > 0 for c in under)
    # 이채은2: NEO predicted 14, actually finished at position 36 -- the
    # single largest overestimate in the confirmed field.
    assert over[0].player_name == "이채은2"
    assert over[0].rank_delta == 14 - 36


def test_real_kb_2026090003_extended_evidence_v3_fully_resolved():
    """V3 (final zoomed crop of positions 8 and T9) must leave zero
    unmatched / zero review_required across all 39 confirmed positions."""
    evidence_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert all(not r["review_required"] for r in evidence["confirmed_records"])
    assert all(r["player_id"] is not None for r in evidence["confirmed_records"])
    from klpga.tournament_context import load_tournament_context
    context = load_tournament_context("2026090003")
    result = pev.run_extended_comparison(context, evidence)
    assert result.positions_confirmed_gapless_through == 39
    assert result.unmatched_confirmed_names == []
    assert len(result.confirmed_players) == 39
    for k in (5, 10, 20):
        assert result.topk[k].supported is True
        assert result.topk[k].unmatched_actual_names == []
    by_name = {c.player_name: c for c in result.confirmed_players}
    assert by_name["이예원"].player_id == "9784"
    assert by_name["홍진영2"].player_id == "10586"


def test_v1_v2_evidence_files_preserved_unchanged_through_v3():
    v1_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V1.json"
    v2_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V2.json"
    v3_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    assert v1_path.is_file() and v2_path.is_file()
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    v3 = json.loads(v3_path.read_text(encoding="utf-8"))
    assert v1["schema_version"] == "operator_supplied_official_screenshot_final_v1"
    assert v2["schema_version"] == "operator_supplied_official_screenshot_final_v2"
    assert "V2" in v3["supersedes"]


def test_r3_frozen_snapshot_unchanged_after_v3():
    from klpga.neo_win import final_pre_freeze
    from klpga.tournament_context import load_tournament_context
    context = load_tournament_context("2026090003")
    assert final_pre_freeze.detect_snapshot_drift(context) is False
    manifest = final_pre_freeze.load_freeze_manifest(context)
    assert manifest["snapshot_sha256"] == "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"


def test_biggest_movers_excludes_unmatched(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    confirmed = [
        _rec("P1", "Player1", 1, 1, "1"),
        {"player_id": None, "player_name": "Mystery", "final_rank": "2", "position_from": 2, "position_to": 2},
    ]
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": []}
    result = pev.run_extended_comparison(context, evidence)
    over, under = pev.biggest_movers(result)
    all_names = {c.player_name for c in (over + under)}
    assert "Mystery" not in all_names


def test_never_writes_the_immutable_official_final_truth(tmp_path, monkeypatch):
    from klpga.neo_win import final_truth
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    confirmed = [_rec("P1", "Player1", 1, 1, "1")]
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": []}
    pev.run_extended_comparison(context, evidence)
    assert final_truth.final_truth_exists(context) is False
