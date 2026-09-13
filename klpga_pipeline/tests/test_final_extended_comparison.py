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


def test_real_kb_2026090003_extended_evidence_end_to_end():
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


def test_never_writes_the_immutable_official_final_truth(tmp_path, monkeypatch):
    from klpga.neo_win import final_truth
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    confirmed = [_rec("P1", "Player1", 1, 1, "1")]
    evidence = {"confirmed_records": confirmed, "unsupported_full_field_metrics": []}
    pev.run_extended_comparison(context, evidence)
    assert final_truth.final_truth_exists(context) is False
