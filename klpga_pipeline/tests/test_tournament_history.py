"""Tests for klpga.neo_win.tournament_history — roadmap priority #2's
append-only PRE->R1->R2->R3->FINAL prediction history. Proves: (1)
stages cannot overwrite each other, (2) the same player links across
stages by player_code, (3) recording history never touches the source
frozen artifact, (4) missing values are explicit None, (5) FINAL's
actual result can be joined back to a prior stage's predictions."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from klpga.neo_win.archive import NeoWinEntrantSnapshot, NeoWinPredictionSnapshot, RECORD_KIND as NEO_WIN_RECORD_KIND
from klpga.neo_win.beta001c_archive import (
    NeoWinCEntrantSnapshot,
    NeoWinCPredictionSnapshot,
    RECORD_KIND as NEO_WIN_C_RECORD_KIND,
)
from klpga.neo_win.tournament_history import (
    STAGE_FINAL,
    STAGE_PRE,
    STAGE_R1,
    STATUS_HISTORICAL_SNAPSHOT_MISSING,
    STATUS_RECORDED,
    HistoryStageAlreadyRecordedError,
    build_final_stage_entry,
    build_missing_stage_marker,
    history_entry_from_beta001c_snapshot,
    history_entry_from_neo_win_pre_snapshot,
    history_entry_from_round_update_dict,
    join_final_to_stage,
    read_full_tournament_history,
    read_history_stage,
    write_history_stage_atomic,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _pre_snapshot(game_code="G1") -> NeoWinPredictionSnapshot:
    entrants = (
        NeoWinEntrantSnapshot(
            rank=1, player_code="p1", player_name="A", win_probability=0.10, prior_events_n=10,
            prior_avg_round_score_to_par=-1.0, prior_recent_form_10=-1.0, prior_recent_form_10_n=10,
            neo_consistency_stddev=2.0, neo_consistency_stddev_n=10,
        ),
        NeoWinEntrantSnapshot(
            rank=2, player_code="p2", player_name="B", win_probability=0.05, prior_events_n=8,
            prior_avg_round_score_to_par=-0.5, prior_recent_form_10=-0.5, prior_recent_form_10_n=8,
            neo_consistency_stddev=1.5, neo_consistency_stddev_n=8,
        ),
    )
    return NeoWinPredictionSnapshot(
        prediction_id="001", created_at_utc="2026-08-27T00:00:00Z", record_kind=NEO_WIN_RECORD_KIND,
        game_code=game_code, tournament_name="Test Open", cutoff_date="2026-08-27", cutoff_source="explicit_arg",
        model_id="NEO_WIN_V0_1", model_version="v0.1", model_features=("f",), training_tournament_count=10,
        field_size=2, entrants_predicted=2, dropped_entrants=0, probability_sum=1.0,
        minimum_probability=0.05, maximum_probability=0.5, zero_history_count=0, unmatched_count=0,
        official_metric_context={}, leakage_validation={"clean": True}, missing_data_report={},
        known_limitations=(), predictions=entrants,
    )


def _beta001c_snapshot(game_code="G1") -> NeoWinCPredictionSnapshot:
    entrants = (
        NeoWinCEntrantSnapshot(rank=1, player_code="p1", player_name="A", win_probability=0.12, prior_events_n=10),
        NeoWinCEntrantSnapshot(rank=2, player_code="p2", player_name="B", win_probability=0.04, prior_events_n=8),
    )
    return NeoWinCPredictionSnapshot(
        prediction_id="001-C", created_at_utc="2026-08-27T00:00:00Z", record_kind=NEO_WIN_C_RECORD_KIND,
        game_code=game_code, tournament_name="Test Open", cutoff_date="2026-08-27", cutoff_source="explicit_arg",
        selected_model_id="MODEL_B", model_features=("f",), selection_decision={},
        training_tournament_count=10, field_size=2, entrants_predicted=2, probability_sum=1.0,
        minimum_probability=0.04, maximum_probability=0.12, duplicate_count=0, null_count=0, non_field_count=0,
        known_limitations=(), predictions=entrants,
    )


def _round_update_dict(game_code="G1") -> dict:
    return {
        "prediction_id": "001-R1", "created_at_utc": "2026-08-28T00:00:00Z",
        "record_kind": "neo_win_beta_round_update_v1", "game_code": game_code, "tournament_name": "Test Open",
        "pre_prediction_id": "001", "pre_cutoff_date": "2026-08-27", "round_number": 1, "cut_fraction_used": 0.5,
        "cut_format": "single_36_hole_cut", "n_simulations": 5000, "field_size": 2, "entrants_scored": 2,
        "missing_r1_players": [], "win_probability_sum_pct": 100.0, "leakage_check": {"clean": True},
        "known_limitations": [],
        "predictions": [
            {"player_code": "p1", "player_name": "A", "pre_win_probability": 0.10, "r1_score_to_par": -3,
             "r1_position": 2, "strokes_behind_leader": 1.0, "post_r1_win_pct": 15.0, "post_r1_top5_pct": 40.0,
             "post_r1_top10_pct": 60.0, "post_r1_top20_pct": 80.0, "post_r1_make_cut_pct": 95.0,
             "probability_change_from_pre": 5.0, "missing_r1_data": False},
            {"player_code": "p2", "player_name": "B", "pre_win_probability": 0.05, "r1_score_to_par": None,
             "r1_position": None, "strokes_behind_leader": None, "post_r1_win_pct": None, "post_r1_top5_pct": None,
             "post_r1_top10_pct": None, "post_r1_top20_pct": None, "post_r1_make_cut_pct": None,
             "probability_change_from_pre": None, "missing_r1_data": True},
        ],
    }


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date, winner) "
        "VALUES ('E1', 'G1', 'Test Open', 2026, '2026-08-27', '2026-08-30', 'A')"
    )
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p1', 'A')")
    connection.execute("INSERT INTO player_master (player_id, player_name) VALUES ('p2', 'B')")
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('E1', 'G1', 2026, 'p1', 'A', '1', 1, 1, 4, -12)"
    )
    connection.execute(
        "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
        "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
        "('E1', 'G1', 2026, 'p2', 'B', 'CUT', NULL, 0, 2, 4)"
    )
    connection.commit()
    return connection


# ---------------------------------------------------------------
# 1. stages cannot overwrite each other
# ---------------------------------------------------------------


def test_writing_the_same_stage_twice_raises(tmp_path):
    entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="2026-08-27T01:00:00Z")
    write_history_stage_atomic(entry, tmp_path)
    with pytest.raises(HistoryStageAlreadyRecordedError):
        write_history_stage_atomic(entry, tmp_path)


def test_different_stages_for_the_same_tournament_coexist(tmp_path):
    pre_entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="2026-08-27T01:00:00Z")
    r1_entry = history_entry_from_round_update_dict(_round_update_dict(), recorded_at_utc="2026-08-28T01:00:00Z")
    p1 = write_history_stage_atomic(pre_entry, tmp_path)
    p2 = write_history_stage_atomic(r1_entry, tmp_path)
    assert p1 != p2
    assert p1.exists() and p2.exists()


def test_two_different_tournaments_never_collide(tmp_path):
    entry_a = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(game_code="G1"), recorded_at_utc="t")
    entry_b = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(game_code="G2"), recorded_at_utc="t")
    write_history_stage_atomic(entry_a, tmp_path)
    write_history_stage_atomic(entry_b, tmp_path)  # must not raise


# ---------------------------------------------------------------
# 2. same player links across stages (player_code, never name)
# ---------------------------------------------------------------


def test_same_player_code_present_across_pre_and_r1(tmp_path):
    pre_entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t1")
    r1_entry = history_entry_from_round_update_dict(_round_update_dict(), recorded_at_utc="t2")
    write_history_stage_atomic(pre_entry, tmp_path)
    write_history_stage_atomic(r1_entry, tmp_path)

    history = read_full_tournament_history(tmp_path, "G1")
    assert set(history.keys()) == {STAGE_PRE, STAGE_R1}
    pre_codes = {e.player_code for e in history[STAGE_PRE].entrants}
    r1_codes = {e.player_code for e in history[STAGE_R1].entrants}
    assert pre_codes == r1_codes == {"p1", "p2"}


# ---------------------------------------------------------------
# 3. frozen artifacts remain untouched
# ---------------------------------------------------------------


def test_recording_history_never_writes_to_the_source_snapshot_file(tmp_path):
    frozen_dir = tmp_path / "neo_win_predictions" / "2026"
    frozen_dir.mkdir(parents=True)
    frozen_path = frozen_dir / "neo_win_001_G1.json"
    snapshot = _pre_snapshot()
    from klpga.neo_win.archive import snapshot_to_dict as pre_snapshot_to_dict

    original_text = json.dumps(pre_snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n"
    frozen_path.write_text(original_text, encoding="utf-8")
    before_mtime = frozen_path.stat().st_mtime_ns
    before_bytes = frozen_path.read_bytes()

    history_root = tmp_path / "neo_tournament_history"
    entry = history_entry_from_neo_win_pre_snapshot(snapshot, recorded_at_utc="2026-08-27T02:00:00Z")
    write_history_stage_atomic(entry, history_root)

    assert frozen_path.stat().st_mtime_ns == before_mtime
    assert frozen_path.read_bytes() == before_bytes


def test_history_directory_is_separate_from_frozen_prediction_roots(tmp_path):
    entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t")
    history_root = tmp_path / "neo_tournament_history"
    path = write_history_stage_atomic(entry, history_root)
    assert "neo_win_predictions" not in str(path)
    assert "neo_win_c_predictions" not in str(path)


# ---------------------------------------------------------------
# 4. missing values are explicit None, never fabricated
# ---------------------------------------------------------------


def test_pre_stage_has_no_position_score_cut_top10_ever(tmp_path):
    entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t")
    for e in entry.entrants:
        assert e.position is None
        assert e.score_to_par is None
        assert e.make_cut_pct is None
        assert e.top10_pct is None
        assert e.win_pct is not None  # PRE DOES have win_pct


def test_r1_missing_player_data_preserved_as_none_not_zero(tmp_path):
    entry = history_entry_from_round_update_dict(_round_update_dict(), recorded_at_utc="t")
    p2 = next(e for e in entry.entrants if e.player_code == "p2")
    assert p2.win_pct is None
    assert p2.position is None
    assert p2.make_cut_pct is None
    p1 = next(e for e in entry.entrants if e.player_code == "p1")
    assert p1.win_pct == 15.0


def test_final_stage_missing_confirmed_win_is_false_not_none_when_finish_present(conn):
    entry = build_final_stage_entry(conn, "G1", source_prediction_id="001", recorded_at_utc="t")
    p2 = next(e for e in entry.entrants if e.player_code == "p2")
    assert p2.actual_confirmed_winner is False
    assert p2.actual_finish_position_numeric is None  # real CUT row has NULL finish_position_numeric


# ---------------------------------------------------------------
# 5. FINAL result can be joined to prior predictions
# ---------------------------------------------------------------


def test_final_joins_to_pre_by_player_code_with_actual_and_predicted_together(tmp_path, conn):
    pre_entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t1")
    final_entry = build_final_stage_entry(conn, "G1", source_prediction_id="001", recorded_at_utc="t2")

    joined = join_final_to_stage(final_entry, pre_entry)
    by_code = {r["player_code"]: r for r in joined}

    assert by_code["p1"]["predicted_win_pct"] == 10.0
    assert by_code["p1"]["actual_finish_position_numeric"] == 1
    assert by_code["p1"]["actual_confirmed_winner"] is True

    assert by_code["p2"]["predicted_win_pct"] == 5.0
    assert by_code["p2"]["actual_confirmed_winner"] is False


def test_join_final_to_stage_rejects_a_non_final_entry(tmp_path):
    pre_entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t")
    with pytest.raises(ValueError):
        join_final_to_stage(pre_entry, pre_entry)


def test_round_trip_write_then_read_preserves_all_fields(tmp_path):
    entry = history_entry_from_beta001c_snapshot(_beta001c_snapshot(), recorded_at_utc="t")
    path = write_history_stage_atomic(entry, tmp_path)
    loaded = read_history_stage(path)
    assert loaded.source_prediction_id == "001-C"
    assert loaded.source_model_version == "MODEL_B"
    assert {e.player_code for e in loaded.entrants} == {"p1", "p2"}


# ---------------------------------------------------------------
# build_missing_stage_marker — confirmed-absent stage, never a
# fabricated 0%, never a silently-skipped stage.
# ---------------------------------------------------------------


def test_missing_marker_has_no_entrants_and_zero_field_size():
    marker = build_missing_stage_marker("G1", STAGE_R1, reason="not found", recorded_at_utc="t")
    assert marker.status == STATUS_HISTORICAL_SNAPSHOT_MISSING
    assert marker.entrants == ()
    assert marker.field_size == 0
    assert marker.missing_reason == "not found"


def test_recorded_snapshot_defaults_to_recorded_status():
    entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t")
    assert entry.status == STATUS_RECORDED
    assert entry.missing_reason is None


def test_missing_marker_round_trips_through_write_and_read(tmp_path):
    marker = build_missing_stage_marker("G1", STAGE_R1, reason="no frozen R1 file found", recorded_at_utc="t")
    path = write_history_stage_atomic(marker, tmp_path)
    loaded = read_history_stage(path)
    assert loaded.status == STATUS_HISTORICAL_SNAPSHOT_MISSING
    assert loaded.missing_reason == "no frozen R1 file found"
    assert loaded.entrants == ()


def test_missing_marker_occupies_the_stage_path_append_only(tmp_path):
    marker = build_missing_stage_marker("G1", STAGE_R1, reason="not found", recorded_at_utc="t")
    write_history_stage_atomic(marker, tmp_path)
    with pytest.raises(HistoryStageAlreadyRecordedError):
        # A later real R1 recording must not silently overwrite a
        # standing MISSING marker for the same (game_code, stage).
        real_entry = history_entry_from_round_update_dict(_round_update_dict(), recorded_at_utc="t2")
        write_history_stage_atomic(real_entry, tmp_path)


def test_read_full_tournament_history_surfaces_missing_status(tmp_path):
    pre_entry = history_entry_from_neo_win_pre_snapshot(_pre_snapshot(), recorded_at_utc="t1")
    r1_marker = build_missing_stage_marker("G1", STAGE_R1, reason="not found", recorded_at_utc="t2")
    write_history_stage_atomic(pre_entry, tmp_path)
    write_history_stage_atomic(r1_marker, tmp_path)

    history = read_full_tournament_history(tmp_path, "G1")
    assert history[STAGE_PRE].status == STATUS_RECORDED
    assert history[STAGE_R1].status == STATUS_HISTORICAL_SNAPSHOT_MISSING
    assert history[STAGE_R1].entrants == ()
