"""KB 2026090003 FINAL BUILD (operator-unblocked, partial field):
regression tests for final_partial_evidence_validator.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import klpga.tournament_context as tournament_context
from klpga.tournament_context import resolve_context
from klpga.neo_win import final_pre_freeze, final_partial_evidence_validator as pev
from klpga.neo_win.final_partial_evidence_validator import PartialEvidenceBlocked

REPO_ROOT = Path(__file__).resolve().parents[1]

IDENTITY = {
    "game_code": "FIXTUREFINAL03",
    "tournament_name": "Fixture Final Partial Open",
    "season": 2027,
    "start_date": "2027-09-01",
    "end_date": "2027-09-04",
    "final_round_number": 4,
    "current_round_number": 3,
}
REGISTRY = {
    "FIXTUREFINAL03": {
        "url_base": "/tournaments/2027/fixture-final-partial-open/",
        "stage_state_filename": "FIXTURE_FINAL_PARTIAL_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "fr", "final"],
    }
}


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _snapshot():
    records = [
        {"player_id": "P1", "player_name": "Alice", "win_pct": 40.0, "top5_pct": 90.0, "top10_pct": 99.0, "top20_pct": 100.0, "neo_final_rank": 1},
        {"player_id": "P2", "player_name": "Bob", "win_pct": 20.0, "top5_pct": 60.0, "top10_pct": 85.0, "top20_pct": 99.0, "neo_final_rank": 2},
        {"player_id": "P3", "player_name": "Cara", "win_pct": 15.0, "top5_pct": 40.0, "top10_pct": 70.0, "top20_pct": 95.0, "neo_final_rank": 3},
        {"player_id": "P4", "player_name": "Dana", "win_pct": 10.0, "top5_pct": 30.0, "top10_pct": 60.0, "top20_pct": 90.0, "neo_final_rank": 4},
        {"player_id": "P5", "player_name": "Erin", "win_pct": 5.0, "top5_pct": 10.0, "top10_pct": 30.0, "top20_pct": 80.0, "neo_final_rank": 9},
        {"player_id": "P6", "player_name": "Fay", "win_pct": 10.0, "top5_pct": 20.0, "top10_pct": 40.0, "top20_pct": 85.0, "neo_final_rank": 5},
    ]
    return {
        "schema_version": 1, "artifact": "post_r3_final_forecast", "game_code": "FIXTUREFINAL03",
        "tournament_name": "Fixture Final Partial Open", "stage": "POST_R3", "source_round": 3,
        "final_round_number": 4, "r3_freeze_artifact": "x", "r3_freeze_sha256": "a" * 64,
        "future_data_excluded": True, "feature_cutoff": "END_OF_R3", "seed": 1,
        "code_commit": "abc", "build_id": "b1", "records": records,
    }


def _write_snapshot(tmp_path):
    (tmp_path / "FIXTUREFINAL03_POST_R3_FINAL_FORECAST.json").write_text(json.dumps(_snapshot()), encoding="utf-8")


def _evidence(confirmed_records, full_field_recovered=False, unsupported=None):
    return {
        "full_field_recovered": full_field_recovered,
        "confirmed_records": confirmed_records,
        "unsupported_full_field_metrics": unsupported or ["complete FINAL leaderboard"],
    }


def test_winner_underdog_hit_and_metrics(tmp_path, monkeypatch):
    """P5 (predicted rank 9, 5% win prob) wins -- winner_hit is False,
    but top10_hit_for_winner is True since predicted rank 9 <= 10."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence([
        {"player_id": "P5", "player_name": "Erin", "final_rank": 1},
        {"player_id": "P1", "player_name": "Alice", "final_rank": "T2"},
        {"player_id": "P6", "player_name": "Fay", "final_rank": "T2"},
        {"player_id": "P2", "player_name": "Bob", "final_rank": 4},
        {"player_id": "P3", "player_name": "Cara", "final_rank": 5},
    ])
    result = pev.run_partial_comparison(context, evidence)
    assert result.winner_player_id == "P5"
    assert result.winner_neo_probability_rank == 9
    assert result.winner_hit is False
    assert result.top5_hit_for_winner is False
    assert result.top10_hit_for_winner is True
    assert result.field_size == 6


def test_top5_set_precision_recall(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    # actual top5 = P5,P1,P6,P2,P3 (winner P5) -- predicted top5 by
    # neo_final_rank = P1,P2,P3,P4,P6. Overlap: P1,P2,P3,P6 (4 hits).
    # predicted-only: P4. actual-only: P5.
    evidence = _evidence([
        {"player_id": "P5", "player_name": "Erin", "final_rank": 1},
        {"player_id": "P1", "player_name": "Alice", "final_rank": "T2"},
        {"player_id": "P6", "player_name": "Fay", "final_rank": "T2"},
        {"player_id": "P2", "player_name": "Bob", "final_rank": 4},
        {"player_id": "P3", "player_name": "Cara", "final_rank": 5},
    ])
    result = pev.run_partial_comparison(context, evidence)
    hit_ids = {d["player_id"] for d in result.top5_set_hits}
    assert hit_ids == {"P1", "P2", "P3", "P6"}
    assert {d["player_id"] for d in result.top5_set_predicted_only} == {"P4"}
    assert {d["player_id"] for d in result.top5_set_actual_only} == {"P5"}
    assert result.top5_precision == pytest.approx(4 / 5)
    assert result.top5_recall == pytest.approx(4 / 5)


def test_confirmed_players_include_neo_predicted_rank_and_actual(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence([
        {"player_id": "P5", "player_name": "Erin", "final_rank": 1},
        {"player_id": "P1", "player_name": "Alice", "final_rank": "T2"},
        {"player_id": "P6", "player_name": "Fay", "final_rank": "T2"},
        {"player_id": "P2", "player_name": "Bob", "final_rank": 4},
        {"player_id": "P3", "player_name": "Cara", "final_rank": 5},
    ])
    result = pev.run_partial_comparison(context, evidence)
    by_id = {c.player_id: c for c in result.confirmed_players}
    assert by_id["P5"].neo_predicted_rank == 9
    assert by_id["P5"].actual_final_rank == "1"
    assert by_id["P1"].neo_predicted_rank == 1
    assert by_id["P1"].actual_final_rank == "T2"


def test_blocked_metrics_passed_through_verbatim(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence(
        [{"player_id": "P5", "player_name": "Erin", "final_rank": 1}],
        unsupported=["thing A", "thing B"],
    )
    result = pev.run_partial_comparison(context, evidence)
    assert result.blocked_metrics == ["thing A", "thing B"]


def test_raises_when_full_field_recovered_flag_set(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence([{"player_id": "P5", "player_name": "Erin", "final_rank": 1}], full_field_recovered=True)
    with pytest.raises(PartialEvidenceBlocked, match="PARTIAL"):
        pev.run_partial_comparison(context, evidence)


def test_raises_when_no_confirmed_records(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    with pytest.raises(PartialEvidenceBlocked, match="zero confirmed"):
        pev.run_partial_comparison(context, _evidence([]))


def test_raises_when_no_single_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence([
        {"player_id": "P1", "player_name": "Alice", "final_rank": "T1"},
        {"player_id": "P2", "player_name": "Bob", "final_rank": "T1"},
    ])
    with pytest.raises(PartialEvidenceBlocked, match="exactly one confirmed winner"):
        pev.run_partial_comparison(context, evidence)


def test_raises_when_confirmed_player_not_in_frozen_forecast(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence([
        {"player_id": "P1", "player_name": "Alice", "final_rank": 1},
        {"player_id": "GHOST", "player_name": "Nobody", "final_rank": 2},
    ])
    with pytest.raises(PartialEvidenceBlocked, match="no entry in the frozen R3 forecast"):
        pev.run_partial_comparison(context, evidence)


def test_never_writes_the_immutable_official_final_truth(tmp_path, monkeypatch):
    """This partial-evidence path must NEVER write to final_truth.py's
    write-once official path -- doing so would permanently block a
    later real, complete official ingestion."""
    from klpga.neo_win import final_truth
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path)
    context = _context()
    evidence = _evidence([
        {"player_id": "P5", "player_name": "Erin", "final_rank": 1},
        {"player_id": "P1", "player_name": "Alice", "final_rank": "T2"},
    ])
    pev.run_partial_comparison(context, evidence)
    assert final_truth.final_truth_exists(context) is False


def test_real_kb_2026090003_operator_evidence_end_to_end():
    """End-to-end against the actual committed evidence file for the
    real tournament -- winner=박보겸, predicted rank 5, not NEO's #1
    pick, but within its own top10/top5 hit-for-winner definitions."""
    from klpga.tournament_context import load_tournament_context
    evidence_path = REPO_ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_REPORTED_FINAL_EVIDENCE_V1.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    context = load_tournament_context("2026090003")
    result = pev.run_partial_comparison(context, evidence)
    assert result.winner_name == "박보겸"
    assert result.winner_neo_probability_rank == 5
    assert result.winner_hit is False
    assert result.top5_hit_for_winner is True
    assert result.field_size == 70
    assert result.top5_precision == pytest.approx(0.8)
    assert result.top5_recall == pytest.approx(0.8)
