"""Tests for klpga.neo_win.accuracy_evaluation — roadmap #3's evidence-
only accuracy evaluation. Pure, hand-built HistoryStageSnapshot/
HistoryEntrant objects (no DB, no frozen files) — this module never
touches either."""
from __future__ import annotations

import math

from klpga.neo_win.accuracy_evaluation import (
    PREDICTION_STAGES,
    build_tournament_prediction,
    evaluate_all_stages,
    evaluate_stage,
    load_tournament_histories,
)
from klpga.neo_win.tournament_history import (
    RECORD_KIND,
    STAGE_FINAL,
    STAGE_PRE,
    STAGE_R1,
    STATUS_HISTORICAL_SNAPSHOT_MISSING,
    STATUS_RECORDED,
    HistoryEntrant,
    HistoryStageSnapshot,
    build_missing_stage_marker,
    write_history_stage_atomic,
    write_superseding_stage_event_atomic,
)


def _pre_stage(game_code, entrants, generated="2026-08-27T00:00:00Z") -> HistoryStageSnapshot:
    return HistoryStageSnapshot(
        game_code=game_code, stage=STAGE_PRE, record_kind=RECORD_KIND, recorded_at_utc="rt",
        source_prediction_id="001", source_model_version="v0.1", source_generated_at_utc=generated,
        tournament_name="T", field_size=len(entrants), entrants=tuple(entrants),
    )


def _final_stage(game_code, entrants, generated="2026-08-31T00:00:00Z") -> HistoryStageSnapshot:
    return HistoryStageSnapshot(
        game_code=game_code, stage=STAGE_FINAL, record_kind=RECORD_KIND, recorded_at_utc="rt",
        source_prediction_id="001", source_model_version="actual_result", source_generated_at_utc=generated,
        tournament_name="T", field_size=len(entrants), entrants=tuple(entrants),
    )


def _e(code, name, win_pct=None, confirmed_winner=None):
    return HistoryEntrant(player_code=code, player_name=name, win_pct=win_pct, actual_confirmed_winner=confirmed_winner)


# ---------------------------------------------------------------
# build_tournament_prediction — single (tournament, stage) evaluability
# ---------------------------------------------------------------


def test_full_evidence_produces_a_prediction():
    pre = _pre_stage("G1", [_e("p1", "A", win_pct=10.0), _e("p2", "B", win_pct=5.0)])
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True), _e("p2", "B", confirmed_winner=False)])
    pred, excl = build_tournament_prediction(pre, final)
    assert excl is None
    assert pred is not None
    assert pred.winner == "p1"
    assert abs(sum(pred.probabilities.values()) - 1.0) < 1e-9


def test_no_stage_snapshot_is_absence_not_exclusion():
    pred, excl = build_tournament_prediction(None, None)
    assert pred is None
    assert excl is None


def test_missing_status_stage_is_excluded_never_scored_as_zero():
    missing = build_missing_stage_marker("G1", STAGE_R1, reason="not found", recorded_at_utc="t")
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True)])
    pred, excl = build_tournament_prediction(missing, final)
    assert pred is None
    assert excl is not None
    assert "HISTORICAL_SNAPSHOT_MISSING" in excl.reason


def test_no_final_recorded_is_excluded():
    pre = _pre_stage("G1", [_e("p1", "A", win_pct=10.0)])
    pred, excl = build_tournament_prediction(pre, None)
    assert pred is None
    assert "no FINAL" in excl.reason


def test_final_with_zero_confirmed_winners_is_excluded():
    pre = _pre_stage("G1", [_e("p1", "A", win_pct=10.0)])
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=False)])
    pred, excl = build_tournament_prediction(pre, final)
    assert pred is None
    assert "confirmed winner" in excl.reason


def test_final_with_two_confirmed_winners_is_excluded():
    pre = _pre_stage("G1", [_e("p1", "A", win_pct=10.0), _e("p2", "B", win_pct=5.0)])
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True), _e("p2", "B", confirmed_winner=True)])
    pred, excl = build_tournament_prediction(pre, final)
    assert pred is None
    assert "2 confirmed winner" in excl.reason


def test_winner_absent_from_predicted_field_is_excluded():
    pre = _pre_stage("G1", [_e("p2", "B", win_pct=5.0)])
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True)])
    pred, excl = build_tournament_prediction(pre, final)
    assert pred is None
    assert "not present in this stage's predicted field" in excl.reason


def test_no_entrant_has_real_win_pct_is_excluded():
    pre = _pre_stage("G1", [_e("p1", "A", win_pct=None)])
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True)])
    pred, excl = build_tournament_prediction(pre, final)
    assert pred is None
    assert "no entrant" in excl.reason


def test_leakage_guard_excludes_prediction_recorded_after_final():
    pre = _pre_stage("G1", [_e("p1", "A", win_pct=10.0)], generated="2026-09-05T00:00:00Z")
    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True)], generated="2026-08-31T00:00:00Z")
    pred, excl = build_tournament_prediction(pre, final)
    assert pred is None
    assert "leakage guard" in excl.reason


# ---------------------------------------------------------------
# evaluate_stage / evaluate_all_stages — aggregation
# ---------------------------------------------------------------


def test_evaluate_stage_insufficient_evidence_when_nothing_qualifies():
    result = evaluate_stage({}, STAGE_PRE)
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.sample_size == 0
    assert result.summary is None
    assert result.calibration is None


def test_evaluate_stage_reports_sample_size_and_real_metrics():
    histories = {
        "G1": {
            STAGE_PRE: _pre_stage("G1", [_e("p1", "A", win_pct=50.0), _e("p2", "B", win_pct=50.0)]),
            STAGE_FINAL: _final_stage("G1", [_e("p1", "A", confirmed_winner=True), _e("p2", "B", confirmed_winner=False)]),
        },
        "G2": {
            STAGE_PRE: _pre_stage("G2", [_e("p3", "C", win_pct=25.0), _e("p4", "D", win_pct=75.0)]),
            STAGE_FINAL: _final_stage("G2", [_e("p3", "C", confirmed_winner=False), _e("p4", "D", confirmed_winner=True)]),
        },
    }
    result = evaluate_stage(histories, STAGE_PRE)
    assert result.status == "EVALUATED"
    assert result.sample_size == 2
    # G1's winner (p1) had exactly 50%, G2's winner (p4) had exactly 75%.
    expected_mean_log_loss = (-math.log(0.5) + -math.log(0.75)) / 2
    assert abs(result.summary.mean_log_loss - expected_mean_log_loss) < 1e-6
    assert result.exclusions == ()


def test_evaluate_stage_mixes_valid_and_excluded_tournaments():
    histories = {
        "G1": {
            STAGE_PRE: _pre_stage("G1", [_e("p1", "A", win_pct=50.0)]),
            STAGE_FINAL: _final_stage("G1", [_e("p1", "A", confirmed_winner=True)]),
        },
        "G2": {  # no FINAL recorded -> excluded
            STAGE_PRE: _pre_stage("G2", [_e("p3", "C", win_pct=25.0)]),
        },
        "G3": {  # R1 missing -> excluded from R1 evaluation specifically
            STAGE_R1: build_missing_stage_marker("G3", STAGE_R1, reason="not found", recorded_at_utc="t"),
            STAGE_FINAL: _final_stage("G3", [_e("p5", "E", confirmed_winner=True)]),
        },
    }
    pre_result = evaluate_stage(histories, STAGE_PRE)
    assert pre_result.sample_size == 1
    assert len(pre_result.exclusions) == 1

    r1_result = evaluate_stage(histories, STAGE_R1)
    assert r1_result.status == "INSUFFICIENT_EVIDENCE"
    assert len(r1_result.exclusions) == 1
    assert STATUS_HISTORICAL_SNAPSHOT_MISSING in r1_result.exclusions[0].reason


def test_evaluate_all_stages_covers_pre_r1_r2_r3_never_final():
    result = evaluate_all_stages({})
    assert set(result.keys()) == set(PREDICTION_STAGES)
    assert STAGE_FINAL not in result
    for stage_result in result.values():
        assert stage_result.status == "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------
# RED TEAM follow-up (test D): evaluation must use the real
# superseding snapshot, never a stale HISTORICAL_SNAPSHOT_MISSING
# marker that a later real recording has since corrected. This is an
# end-to-end test against real files (load_tournament_histories reads
# neo_tournament_history/ from disk) — evaluate_stage's own dict-based
# tests above never see write_or_supersede_history_stage's file-level
# resolution, so it needs coverage of its own.
# ---------------------------------------------------------------


def test_load_tournament_histories_evaluates_superseding_event_not_stale_marker(tmp_path):
    marker = build_missing_stage_marker("G1", STAGE_R1, reason="not found", recorded_at_utc="t1")
    write_history_stage_atomic(marker, tmp_path)

    real_r1 = HistoryStageSnapshot(
        game_code="G1", stage=STAGE_R1, record_kind=RECORD_KIND, recorded_at_utc="t2",
        source_prediction_id="001-C-R1", source_model_version="round_update",
        source_generated_at_utc="2026-08-28T00:00:00Z", tournament_name="T", field_size=1,
        entrants=(_e("p1", "A", win_pct=50.0),),
    )
    write_superseding_stage_event_atomic(real_r1, tmp_path)

    final = _final_stage("G1", [_e("p1", "A", confirmed_winner=True)], generated="2026-08-31T00:00:00Z")
    write_history_stage_atomic(final, tmp_path)

    histories = load_tournament_histories(tmp_path, ["G1"])
    assert histories["G1"][STAGE_R1].status == STATUS_RECORDED  # not HISTORICAL_SNAPSHOT_MISSING

    result = evaluate_stage(histories, STAGE_R1)
    assert result.status == "EVALUATED"
    assert result.sample_size == 1
    assert result.exclusions == ()
