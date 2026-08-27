"""Tests for klpga.neo_win.comparison — BETA #001-C Phase 10's pure
BETA #001 vs BETA #001-C comparison, against hand-built snapshot
objects (no DB, no file I/O — this module never touches either)."""
from __future__ import annotations

from klpga.neo_win.archive import NeoWinEntrantSnapshot, NeoWinPredictionSnapshot, RECORD_KIND as NEO_WIN_RECORD_KIND
from klpga.neo_win.beta001c_archive import (
    NeoWinCEntrantSnapshot,
    NeoWinCPredictionSnapshot,
    RECORD_KIND as NEO_WIN_C_RECORD_KIND,
)
from klpga.neo_win.comparison import compare_beta001_to_beta001c


def _pre_entrant(rank, code, name, prob) -> NeoWinEntrantSnapshot:
    return NeoWinEntrantSnapshot(
        rank=rank, player_code=code, player_name=name, win_probability=prob, prior_events_n=10,
        prior_avg_round_score_to_par=-1.0, prior_recent_form_10=-1.0, prior_recent_form_10_n=10,
        neo_consistency_stddev=2.0, neo_consistency_stddev_n=10,
    )


def _pre_snapshot(entrants) -> NeoWinPredictionSnapshot:
    return NeoWinPredictionSnapshot(
        prediction_id="001", created_at_utc="2026-08-27T00:00:00Z", record_kind=NEO_WIN_RECORD_KIND,
        game_code="G1", tournament_name="T", cutoff_date="2026-08-27", cutoff_source="explicit_arg",
        model_id="NEO_WIN_V0_1", model_version="v0.1", model_features=("f",), training_tournament_count=10,
        field_size=len(entrants), entrants_predicted=len(entrants), dropped_entrants=0,
        probability_sum=1.0, minimum_probability=0.01, maximum_probability=0.5,
        zero_history_count=0, unmatched_count=0, official_metric_context={}, leakage_validation={"clean": True},
        missing_data_report={}, known_limitations=(), predictions=tuple(entrants),
    )


def _c_entrant(rank, code, name, prob) -> NeoWinCEntrantSnapshot:
    return NeoWinCEntrantSnapshot(rank=rank, player_code=code, player_name=name, win_probability=prob, prior_events_n=10)


def _c_snapshot(entrants) -> NeoWinCPredictionSnapshot:
    return NeoWinCPredictionSnapshot(
        prediction_id="001-C", created_at_utc="2026-08-27T00:00:00Z", record_kind=NEO_WIN_C_RECORD_KIND,
        game_code="G1", tournament_name="T", cutoff_date="2026-08-27", cutoff_source="explicit_arg",
        selected_model_id="MODEL_B", model_features=("f",), selection_decision={},
        training_tournament_count=10, field_size=len(entrants), entrants_predicted=len(entrants),
        probability_sum=1.0, minimum_probability=0.01, maximum_probability=0.5,
        duplicate_count=0, null_count=0, non_field_count=0, known_limitations=(), predictions=tuple(entrants),
    )


def test_matched_player_gets_full_delta_and_rank_change():
    pre = _pre_snapshot([_pre_entrant(1, "p1", "A", 0.10), _pre_entrant(2, "p2", "B", 0.05)])
    c = _c_snapshot([_c_entrant(2, "p1", "A", 0.03), _c_entrant(1, "p2", "B", 0.12)])
    result = compare_beta001_to_beta001c(pre, c)
    by_code = {r.player_code: r for r in result["rows"]}
    assert abs(by_code["p1"].delta_pct - (3.0 - 10.0)) < 1e-9
    assert by_code["p1"].rank_change == 1 - 2
    assert by_code["p2"].rank_change == 2 - 1


def test_player_only_in_pre_001_flagged():
    pre = _pre_snapshot([_pre_entrant(1, "p1", "A", 0.10)])
    c = _c_snapshot([])
    result = compare_beta001_to_beta001c(pre, c)
    row = result["rows"][0]
    assert row.in_pre_001_only is True
    assert row.corrected_001c_win_pct is None
    assert row.delta_pct is None


def test_player_only_in_001c_flagged():
    pre = _pre_snapshot([])
    c = _c_snapshot([_c_entrant(1, "p1", "A", 0.10)])
    result = compare_beta001_to_beta001c(pre, c)
    row = result["rows"][0]
    assert row.in_001c_only is True
    assert row.pre_001_win_pct is None


def test_biggest_risers_and_fallers_ordered():
    pre = _pre_snapshot([_pre_entrant(i + 1, f"p{i}", f"N{i}", 0.1) for i in range(5)])
    c = _c_snapshot([
        _c_entrant(1, "p0", "N0", 0.50),  # big riser
        _c_entrant(2, "p1", "N1", 0.10),
        _c_entrant(3, "p2", "N2", 0.10),
        _c_entrant(4, "p3", "N3", 0.10),
        _c_entrant(5, "p4", "N4", 0.01),  # big faller
    ])
    result = compare_beta001_to_beta001c(pre, c)
    assert result["biggest_risers"][0].player_code == "p0"
    assert result["biggest_fallers"][0].player_code == "p4"


def test_highlighted_names_never_hardcoded_caller_supplied():
    pre = _pre_snapshot([_pre_entrant(1, "p1", "서교림", 0.10)])
    c = _c_snapshot([_c_entrant(1, "p1", "서교림", 0.08)])
    result = compare_beta001_to_beta001c(pre, c, highlighted_names=("서교림", "누구"))
    assert result["highlighted"]["서교림"].player_code == "p1"
    assert result["highlighted"]["누구"] is None


def test_no_highlighted_names_by_default():
    pre = _pre_snapshot([_pre_entrant(1, "p1", "A", 0.10)])
    c = _c_snapshot([_c_entrant(1, "p1", "A", 0.10)])
    result = compare_beta001_to_beta001c(pre, c)
    assert result["highlighted"] == {}
