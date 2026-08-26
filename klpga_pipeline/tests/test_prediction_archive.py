"""Tests for klpga.archive.prediction_archive — the immutable
prediction snapshot layer. Covers the 11 required properties from the
archive-layer task plus schema/verification unit tests. Uses small,
hand-built `InferenceResult`/`EntrantPrediction` fixtures for most
tests (no model math is exercised here — that's `test_model_inference.py`'s
job) and one small real synthetic DB for the DB-mutation-after-archive
test."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from klpga.archive.prediction_archive import (
    ExpectedFacts,
    PredictionAlreadyArchivedError,
    archive_paths,
    build_live_atomic_provenance,
    build_rerun_reconstruction_provenance,
    read_prediction_snapshot,
    snapshot_from_inference_result,
    snapshot_to_json_text,
    verify_against_observed_facts,
    write_prediction_snapshot_atomic,
)
from klpga.models.inference import EntrantPrediction, InferenceResult, run_inference

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"


def _entrant(rank, code, name, prob, n=10, avg=-2.5, form10=-3.0, form10_n=8, unmatched=False):
    return EntrantPrediction(
        rank=rank,
        player_code=code,
        player_name=name,
        win_probability=prob,
        prior_events_n=n,
        prior_avg_round_score_to_par=avg,
        prior_recent_form_10=form10,
        prior_recent_form_10_n=form10_n,
        history_slice="moderate_10_19" if n else "cold_0",
        is_unmatched=unmatched,
    )


def _result(predictions, **overrides):
    probs = [p.win_probability for p in predictions]
    defaults = dict(
        game_code="2026080001",
        tournament_name="제15회 KG 레이디스 오픈",
        tournament_name_source="explicit_arg",
        field_size=len(predictions),
        cutoff_date="2026-08-27",
        cutoff_date_source="explicit_arg",
        training_tournament_count=100,
        model_id="M4",
        model_features=("prior_avg_round_score_to_par", "prior_recent_form_10"),
        predictions=tuple(predictions),
        sum_probability=sum(probs),
        min_probability=min(probs),
        max_probability=max(probs),
        zero_history_count=sum(1 for p in predictions if p.prior_events_n == 0),
        unmatched_count=sum(1 for p in predictions if p.is_unmatched),
        predicted_count=len(predictions),
        entrants_parsed=len(predictions),
        dropped_entrants=0,
        duplicate_player_codes=0,
    )
    defaults.update(overrides)
    return InferenceResult(**defaults)


def _sample_result():
    return _result(
        [
            _entrant(1, "11134", "서교림", 0.100967),
            _entrant(2, "22222", "B선수", 0.25),
            _entrant(3, "ROOKIE1", "루키", 0.05, n=0, avg=None, form10=None, form10_n=0),
            _entrant(4, "13355", "배윤철 0908(A)", 0.03, n=0, avg=None, form10=None, form10_n=0, unmatched=True),
            _entrant(5, "55555", "E선수", 0.559033, n=15),
        ]
    )


def _snapshot(prediction_id="001", result=None):
    result = result or _sample_result()
    return snapshot_from_inference_result(
        result,
        prediction_id=prediction_id,
        created_at_utc="2026-08-26T00:00:00Z",
        provenance=build_live_atomic_provenance(),
    )


# ----------------------------------------------------------------
# 1. duplicate prediction_id cannot overwrite
# ----------------------------------------------------------------


def test_duplicate_prediction_id_cannot_overwrite(tmp_path):
    snap = _snapshot()
    json_path, csv_path = write_prediction_snapshot_atomic(snap, tmp_path)
    original_json_bytes = json_path.read_bytes()
    original_csv_bytes = csv_path.read_bytes()

    # A second write attempt for the SAME (prediction_id, game_code),
    # even with different content, must be rejected before anything
    # is touched.
    different_snap = _snapshot(result=_result([_entrant(1, "99999", "다른선수", 1.0)]))
    with pytest.raises(PredictionAlreadyArchivedError):
        write_prediction_snapshot_atomic(different_snap, tmp_path)

    assert json_path.read_bytes() == original_json_bytes
    assert csv_path.read_bytes() == original_csv_bytes


# ----------------------------------------------------------------
# 2. archive contains every entrant
# ----------------------------------------------------------------


def test_archive_contains_every_entrant(tmp_path):
    result = _sample_result()
    snap = _snapshot(result=result)
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    archived_codes = {row["player_code"] for row in data["predictions"]}
    assert archived_codes == {p.player_code for p in result.predictions}


# ----------------------------------------------------------------
# 3. archive field_size == prediction rows
# ----------------------------------------------------------------


def test_field_size_equals_prediction_row_count(tmp_path):
    snap = _snapshot()
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["field_size"] == len(data["predictions"])
    assert data["entrants_predicted"] == len(data["predictions"])


# ----------------------------------------------------------------
# 4. probability sum preserved
# ----------------------------------------------------------------


def test_probability_sum_preserved_exactly(tmp_path):
    result = _sample_result()
    snap = _snapshot(result=result)
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["probability_sum"] == result.sum_probability
    assert sum(row["win_probability"] for row in data["predictions"]) == pytest.approx(
        result.sum_probability, abs=1e-12
    )


# ----------------------------------------------------------------
# 5. player_code uniqueness
# ----------------------------------------------------------------


def test_player_code_uniqueness_in_archive(tmp_path):
    snap = _snapshot()
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    codes = [row["player_code"] for row in data["predictions"]]
    assert len(codes) == len(set(codes))


def test_snapshot_from_inference_result_rejects_duplicate_player_codes():
    result = _result([_entrant(1, "A", "x", 0.5), _entrant(2, "A", "y", 0.5)])
    with pytest.raises(ValueError, match="duplicate player_code"):
        snapshot_from_inference_result(
            result, prediction_id="001", created_at_utc="2026-08-26T00:00:00Z",
            provenance=build_live_atomic_provenance(),
        )


# ----------------------------------------------------------------
# 6. zero-history entrant preserved
# ----------------------------------------------------------------


def test_zero_history_entrant_preserved(tmp_path):
    result = _sample_result()
    snap = _snapshot(result=result)
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    rookie = next(row for row in data["predictions"] if row["player_code"] == "ROOKIE1")
    assert rookie["prior_events_n"] == 0
    assert rookie["win_probability"] == pytest.approx(0.05)
    assert rookie["history_slice"] == "cold_0"


# ----------------------------------------------------------------
# 7. unmatched entrant preserved
# ----------------------------------------------------------------


def test_unmatched_entrant_preserved(tmp_path):
    result = _sample_result()
    snap = _snapshot(result=result)
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    unmatched = next(row for row in data["predictions"] if row["player_code"] == "13355")
    assert unmatched["player_master_matched"] is False
    assert unmatched["player_name_display"] == "배윤철 0908(A)"
    assert unmatched["win_probability"] == pytest.approx(0.03)


# ----------------------------------------------------------------
# 8. future database mutation cannot modify an existing archive
# ----------------------------------------------------------------


def _new_conn(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_tournament(connection, event_id, game_code, start_date, ranked_players):
    connection.execute(
        "INSERT OR IGNORE INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, ?, 2026, ?, ?)",
        (event_id, game_code, event_id, start_date, start_date),
    )
    for rank, player_id in enumerate(ranked_players, start=1):
        connection.execute(
            "INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_id, player_id)
        )
        connection.execute(
            "INSERT INTO player_event (event_id, game_code, season, player_id, player_name, finish_position, "
            "finish_position_numeric, made_cut, rounds_played, score_to_par) VALUES "
            "(?, ?, 2026, ?, ?, ?, ?, 1, 4, ?)",
            (event_id, game_code, player_id, player_id, str(rank), rank, -20 + rank),
        )


def test_future_database_mutation_cannot_modify_an_existing_archive(tmp_path):
    db_path = tmp_path / "klpga.sqlite"
    conn = _new_conn(db_path)
    players = ["A", "B", "C"]
    for t in range(6):
        event_id = f"T{t:02d}"
        ranked = players[t % len(players):] + players[: t % len(players)]
        _insert_tournament(conn, event_id, event_id, f"2026-{(t % 12) + 1:02d}-01", ranked)
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('KG2026', 'A', 'A', 'test', '2026-08-25T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
        "VALUES ('KG2026', 'B', 'B', 'test', '2026-08-25T00:00:00Z')"
    )
    conn.commit()

    result = run_inference(conn, "KG2026", cutoff_date_arg="2027-01-01")
    snap = snapshot_from_inference_result(
        result, prediction_id="001", created_at_utc="2026-08-26T00:00:00Z",
        provenance=build_live_atomic_provenance(),
    )
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path / "predictions")
    archived_bytes_before = json_path.read_bytes()

    # A later data-collection run adds a brand-new historical tournament
    # to the SAME database file/connection.
    _insert_tournament(conn, "T99", "T99", "2026-12-01", ["A", "B", "C"])
    conn.commit()

    assert json_path.read_bytes() == archived_bytes_before
    reread = read_prediction_snapshot(json_path)
    assert reread.training_tournament_count == result.training_tournament_count
    conn.close()


# ----------------------------------------------------------------
# 9. post-tournament evaluation cannot mutate prediction snapshot
# ----------------------------------------------------------------


def test_reading_an_archived_snapshot_never_requires_write_access(tmp_path):
    snap = _snapshot()
    json_path, _ = write_prediction_snapshot_atomic(snap, tmp_path)
    original_bytes = json_path.read_bytes()

    # Lock the file read-only at the filesystem level (what any future
    # post-tournament evaluation reader would see) and confirm reading
    # still works — proving the reader path never needs, and therefore
    # can never exercise, write access to the original file.
    os.chmod(json_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        reread = read_prediction_snapshot(json_path)
        assert reread.prediction_id == snap.prediction_id
        assert json_path.read_bytes() == original_bytes
    finally:
        os.chmod(json_path, stat.S_IRUSR | stat.S_IWUSR)


# ----------------------------------------------------------------
# 10. deterministic serialization where practical
# ----------------------------------------------------------------


def test_serialization_is_deterministic(tmp_path):
    result = _sample_result()
    snap_a = snapshot_from_inference_result(
        result, prediction_id="001", created_at_utc="2026-08-26T00:00:00Z",
        provenance=build_live_atomic_provenance(),
    )
    snap_b = snapshot_from_inference_result(
        result, prediction_id="001", created_at_utc="2026-08-26T00:00:00Z",
        provenance=build_live_atomic_provenance(),
    )
    assert snapshot_to_json_text(snap_a) == snapshot_to_json_text(snap_b)


# ----------------------------------------------------------------
# 11. partial/failed write cannot leave a valid-looking archive
# ----------------------------------------------------------------


def test_partial_csv_failure_leaves_no_corrupt_file_at_final_name(tmp_path, monkeypatch):
    import klpga.archive.prediction_archive as archive_module

    snap = _snapshot()
    json_path, csv_path = archive_paths(tmp_path, snap.prediction_id, snap.game_code, snap.cutoff_date)

    real_claim = archive_module._atomic_claim
    call_count = {"n": 0}

    def _flaky_claim(content_bytes, final_path):
        call_count["n"] += 1
        if final_path.suffix == ".csv":
            raise OSError("simulated disk failure while writing CSV")
        return real_claim(content_bytes, final_path)

    monkeypatch.setattr(archive_module, "_atomic_claim", _flaky_claim)

    with pytest.raises(RuntimeError, match="CSV write failed"):
        write_prediction_snapshot_atomic(snap, tmp_path)

    # JSON (already fully written+validated before the CSV step) is
    # left in place and is fully valid — never a partial/corrupt file.
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["prediction_id"] == "001"
    # CSV never appears at its final name — no truncated/garbage file
    # masquerading as a real archive entry.
    assert not csv_path.exists()


def test_write_failure_before_link_leaves_no_file_at_final_name(tmp_path, monkeypatch):
    import klpga.archive.prediction_archive as archive_module

    snap = _snapshot()
    json_path, _ = archive_paths(tmp_path, snap.prediction_id, snap.game_code, snap.cutoff_date)

    def _boom(content_bytes, final_path):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(archive_module, "_atomic_claim", _boom)

    with pytest.raises(OSError):
        write_prediction_snapshot_atomic(snap, tmp_path)

    assert not json_path.exists()


# ----------------------------------------------------------------
# Reconstruction cross-check
# ----------------------------------------------------------------


def test_verify_against_observed_facts_reports_no_mismatch_when_everything_matches():
    result = _sample_result()
    expected = ExpectedFacts(
        game_code="2026080001",
        field_size=5,
        training_tournament_count=100,
        entrants_predicted=5,
        dropped_entrants=0,
        probability_sum=result.sum_probability,
        top_player_code="11134",
        top_player_name="서교림",
        top_player_display_probability_pct=10.097,
    )
    assert verify_against_observed_facts(result, expected) == []


def test_verify_against_observed_facts_flags_display_probability_mismatch():
    result = _sample_result()
    expected = ExpectedFacts(top_player_code="11134", top_player_display_probability_pct=55.0)
    mismatches = verify_against_observed_facts(result, expected)
    assert any("display probability" in m for m in mismatches)


def test_verify_against_observed_facts_flags_wrong_top_player():
    result = _sample_result()
    expected = ExpectedFacts(top_player_code="99999")
    mismatches = verify_against_observed_facts(result, expected)
    assert any("top_player_code" in m for m in mismatches)


def test_verify_against_observed_facts_skips_unset_fields():
    result = _sample_result()
    assert verify_against_observed_facts(result, ExpectedFacts()) == []


def test_rerun_reconstruction_provenance_never_labeled_original():
    provenance = build_rerun_reconstruction_provenance(
        original_run_status="successful_pre_tournament_run_observed",
        original_machine_readable_snapshot_available=False,
        reconstruction_reason="test",
        verification={"first_run_top_player_code": "11134"},
    )
    assert provenance["source"] == "rerun_reconstruction"
    assert "original" not in provenance["source"]
