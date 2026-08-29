"""Tests for klpga.neo_win.r3_r4_evaluation_archive — the append-only
R3->R4 evaluation record store, self-contained from tournament_history."""
from __future__ import annotations

from klpga.neo_win.r3_r4_evaluation import PlayerR3R4Evaluation
from klpga.neo_win.r3_r4_evaluation_archive import (
    RECORD_KIND,
    STAGE_TRANSITION_R3_TO_R4,
    R3R4EvaluationAlreadyRecordedError,
    R3R4EvaluationSnapshot,
    evaluation_path,
    read_all_evaluations,
    read_evaluation,
    write_evaluation_atomic,
)

GAME_CODE = "2026080099"


def _snapshot(prediction_id="001-C"):
    rows = (
        PlayerR3R4Evaluation(
            player_code="p1", player_name="A", r3_total_score_to_par=-6.0,
            expected_r4_score_to_par=-1.0, r4_spread=2.0, actual_r4_score_to_par=-2.0,
            prediction_error=-1.0, absolute_error=1.0, z_score=-0.5,
        ),
    )
    return R3R4EvaluationSnapshot(
        game_code=GAME_CODE, prediction_id=prediction_id, stage_transition=STAGE_TRANSITION_R3_TO_R4,
        record_kind=RECORD_KIND, recorded_at_utc="2026-08-29T00:00:00Z",
        source_pre_snapshot_path="/fake/pre.json", source_pre_snapshot_sha256="a" * 64,
        source_r1_r2_r3_made_cut_input_sha256="b" * 64,
        aggregate={"evaluated_players": 1, "mae": 1.0, "me": -1.0, "rmse": 1.0,
                   "within_1_stroke_pct": 100.0, "within_sigma_pct": 100.0},
        rows=rows, known_limitations=("note1", "note2"),
    )


def test_write_then_read_roundtrips_exactly(tmp_path):
    snap = _snapshot()
    path = write_evaluation_atomic(snap, tmp_path)
    assert path == evaluation_path(tmp_path, GAME_CODE, "001-C")
    loaded = read_evaluation(path)
    assert loaded.game_code == GAME_CODE
    assert loaded.prediction_id == "001-C"
    assert loaded.source_pre_snapshot_sha256 == "a" * 64
    assert loaded.source_r1_r2_r3_made_cut_input_sha256 == "b" * 64
    assert loaded.known_limitations == ("note1", "note2")
    assert loaded.rows[0].player_code == "p1"
    assert loaded.rows[0].z_score == -0.5
    assert loaded.aggregate["mae"] == 1.0


def test_double_write_is_append_only_never_overwrites(tmp_path):
    write_evaluation_atomic(_snapshot(), tmp_path)
    import pytest
    with pytest.raises(R3R4EvaluationAlreadyRecordedError):
        write_evaluation_atomic(_snapshot(), tmp_path)
    # The original content survives untouched.
    loaded = read_evaluation(evaluation_path(tmp_path, GAME_CODE, "001-C"))
    assert loaded.rows[0].actual_r4_score_to_par == -2.0


def test_different_prediction_id_is_a_sibling_record_never_a_collision(tmp_path):
    write_evaluation_atomic(_snapshot(prediction_id="001-C"), tmp_path)
    write_evaluation_atomic(_snapshot(prediction_id="002"), tmp_path)
    p1 = evaluation_path(tmp_path, GAME_CODE, "001-C")
    p2 = evaluation_path(tmp_path, GAME_CODE, "002")
    assert p1 != p2
    assert p1.exists() and p2.exists()


def test_read_all_evaluations_finds_every_sibling_record(tmp_path):
    write_evaluation_atomic(_snapshot(prediction_id="001-C"), tmp_path)
    write_evaluation_atomic(_snapshot(prediction_id="002"), tmp_path)
    all_records = read_all_evaluations(tmp_path, GAME_CODE)
    assert {r.prediction_id for r in all_records} == {"001-C", "002"}


def test_read_all_evaluations_empty_archive_returns_empty_list(tmp_path):
    assert read_all_evaluations(tmp_path / "does_not_exist", GAME_CODE) == []
