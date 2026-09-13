"""4R FINAL PRE-BUILD (research/final-r4-pre-build-20260913): regression
tests for the PRE-FINAL freeze, FINAL truth schema, forecast-vs-actual
validator, course Deep Dive connector, report generator, content
export, and FINAL wait page.

Covers all 15 Phase-11 required regression items; each is called out by
its own test docstring below with the exact item it satisfies.
"""
from __future__ import annotations

import json

import pytest

import klpga.tournament_context as tournament_context
from klpga.tournament_context import resolve_context

from klpga.neo_win import final_pre_freeze, final_truth, final_validator, final_report, final_content_export, final_course_deep_dive
from klpga.neo_win.final_pre_freeze import FutureLeakageDetected
from klpga.neo_win.final_truth import FinalTruthError
from klpga.neo_win.final_validator import FinalValidationBlocked

IDENTITY = {
    "game_code": "FIXTUREFINAL02",
    "tournament_name": "Fixture Final Pre-Build Open",
    "season": 2027,
    "start_date": "2027-09-01",
    "end_date": "2027-09-04",
    "final_round_number": 4,
    "current_round_number": 3,
}
REGISTRY = {
    "FIXTUREFINAL02": {
        "url_base": "/tournaments/2027/fixture-final-pre-build-open/",
        "stage_state_filename": "FIXTURE_FINAL_PREBUILD_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "fr", "final"],
    }
}
PLAYERS = ["P1", "P2", "P3", "P4", "P5"]


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _snapshot(**overrides) -> dict:
    records = [
        {
            "player_id": "P1", "player_name": "Alice", "r1_score_to_par": -2.0, "r2_score_to_par": -1.0,
            "r3_score_to_par": -3.0, "r3_total_to_par": -6.0, "win_pct": 40.0, "top5_pct": 90.0,
            "top10_pct": 99.0, "top20_pct": 100.0, "neo_final_rank": 1,
        },
        {
            "player_id": "P2", "player_name": "Bob", "r1_score_to_par": 0.0, "r2_score_to_par": 0.0,
            "r3_score_to_par": -1.0, "r3_total_to_par": -1.0, "win_pct": 20.0, "top5_pct": 60.0,
            "top10_pct": 85.0, "top20_pct": 99.0, "neo_final_rank": 2,
        },
        {
            "player_id": "P3", "player_name": "Cara", "r1_score_to_par": 1.0, "r2_score_to_par": 1.0,
            "r3_score_to_par": 0.0, "r3_total_to_par": 2.0, "win_pct": 15.0, "top5_pct": 40.0,
            "top10_pct": 70.0, "top20_pct": 95.0, "neo_final_rank": 3,
        },
        {
            "player_id": "P4", "player_name": "Dana", "r1_score_to_par": 2.0, "r2_score_to_par": 2.0,
            "r3_score_to_par": 1.0, "r3_total_to_par": 5.0, "win_pct": 5.0, "top5_pct": 10.0,
            "top10_pct": 30.0, "top20_pct": 80.0, "neo_final_rank": 15,
        },
        {
            "player_id": "P5", "player_name": "Erin", "r1_score_to_par": 3.0, "r2_score_to_par": 3.0,
            "r3_score_to_par": 2.0, "r3_total_to_par": 8.0, "win_pct": 1.0, "top5_pct": 3.0,
            "top10_pct": 8.0, "top20_pct": 60.0, "neo_final_rank": 20,
        },
    ]
    payload = {
        "schema_version": 1,
        "artifact": "post_r3_final_forecast",
        "game_code": "FIXTUREFINAL02",
        "tournament_name": "Fixture Final Pre-Build Open",
        "stage": "POST_R3",
        "source_round": 3,
        "final_round_number": 4,
        "remaining_rounds": 1,
        "r3_freeze_artifact": "fixturefinal02_r3_frozen_evidence_v1",
        "r3_freeze_sha256": "deadbeef" * 8,
        "future_data_excluded": True,
        "feature_cutoff": "END_OF_R3",
        "seed": 20270901,
        "code_commit": "abc123",
        "build_id": "20270901T000000Z_POST_R3",
        "records": records,
    }
    payload.update(overrides)
    return payload


def _write_snapshot(tmp_path, payload=None):
    payload = payload if payload is not None else _snapshot()
    (tmp_path / "FIXTUREFINAL02_POST_R3_FINAL_FORECAST.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _truth_records():
    records = [
        {"player_id": "P1", "player_name": "Alice", "final_rank": 1, "final_score": "-10", "r4_score": -4,
         "rounds_completed": 4, "status": "ACTIVE", "top5_actual": True, "top10_actual": True, "top20_actual": True},
        {"player_id": "P2", "player_name": "Bob", "final_rank": 2, "final_score": "-3", "r4_score": -2,
         "rounds_completed": 4, "status": "ACTIVE", "top5_actual": True, "top10_actual": True, "top20_actual": True},
        {"player_id": "P3", "player_name": "Cara", "final_rank": 3, "final_score": "0", "r4_score": -2,
         "rounds_completed": 4, "status": "ACTIVE", "top5_actual": True, "top10_actual": True, "top20_actual": True},
        {"player_id": "P4", "player_name": "Dana", "final_rank": 4, "final_score": "4", "r4_score": -1,
         "rounds_completed": 4, "status": "ACTIVE", "top5_actual": False, "top10_actual": True, "top20_actual": True},
        {"player_id": "P5", "player_name": "Erin", "final_rank": "WD", "final_score": "—", "r4_score": None,
         "rounds_completed": 3, "status": "WD", "top5_actual": False, "top10_actual": False, "top20_actual": False},
    ]
    return records


def _build_and_freeze(tmp_path, monkeypatch, snapshot_payload=None):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_snapshot(tmp_path, snapshot_payload)
    context = _context()
    path, written = final_pre_freeze.write_freeze_manifest_if_absent(context)
    assert written is True
    return context


def _write_truth(tmp_path, context, *, records=None, synthetic=False):
    from pathlib import Path
    truth = final_truth.build_final_truth(
        context=context,
        official_source="klpga.co.kr (fixture)",
        collected_at="2027-09-04T12:00:00Z",
        raw_official_response=b"<html>fixture</html>",
        records=records if records is not None else _truth_records(),
        repo_root=Path(__file__).resolve().parents[1],
        build_id="20270904T000000Z_FINAL",
        synthetic_test_only=synthetic,
    )
    if synthetic:
        path = final_truth.final_truth_path(context)
        path.parent.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict
        path.write_text(json.dumps(asdict(truth), ensure_ascii=False), encoding="utf-8")
    else:
        final_truth.write_final_truth_immutable(context, truth)
    return truth


# ---------------------------------------------------------------
# Phase 1-2: PRE-FINAL freeze + manifest
# ---------------------------------------------------------------


def test_verify_and_build_manifest_success(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    manifest = final_pre_freeze.load_freeze_manifest(context)
    assert manifest["status"] == "FROZEN"
    assert manifest["future_leakage_check"] == "PASS"
    assert manifest["player_count"] == 5
    assert manifest["surprise_classification_rule"]["neo_high_if"] == "neo_final_rank <= 10"


def test_future_leakage_detected_raises_on_r4_marker(tmp_path, monkeypatch):
    """Phase 11 item 1: PRE-FINAL snapshot에 R4 미래 데이터가 없음."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    bad = _snapshot()
    bad["records"][0]["r4_score"] = -3  # leaked future data
    _write_snapshot(tmp_path, bad)
    context = _context()
    with pytest.raises(FutureLeakageDetected):
        final_pre_freeze.write_freeze_manifest_if_absent(context)


def test_future_leakage_detected_when_source_round_equals_final_round(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    bad = _snapshot(source_round=4)
    _write_snapshot(tmp_path, bad)
    context = _context()
    with pytest.raises(FutureLeakageDetected):
        final_pre_freeze.write_freeze_manifest_if_absent(context)


def test_write_freeze_manifest_if_absent_is_write_once(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    path = final_pre_freeze._freeze_manifest_path(context)
    before = path.read_bytes()
    path2, written2 = final_pre_freeze.write_freeze_manifest_if_absent(context)
    assert written2 is False
    assert path2.read_bytes() == before


def test_detect_snapshot_drift_false_when_unchanged(tmp_path, monkeypatch):
    """Phase 11 item 2: snapshot hash 변경 감지 (negative case)."""
    context = _build_and_freeze(tmp_path, monkeypatch)
    assert final_pre_freeze.detect_snapshot_drift(context) is False


def test_detect_snapshot_drift_true_when_changed(tmp_path, monkeypatch):
    """Phase 11 item 2: snapshot hash 변경 감지 (positive case)."""
    context = _build_and_freeze(tmp_path, monkeypatch)
    snapshot_path = final_pre_freeze._pre_final_snapshot_path(context)
    tampered = json.loads(snapshot_path.read_text(encoding="utf-8"))
    tampered["records"][0]["win_pct"] = 999.0
    snapshot_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    assert final_pre_freeze.detect_snapshot_drift(context) is True


def test_real_2026090003_pre_final_snapshot_freezes_cleanly_read_only():
    """Verifies the ACTUAL already-frozen POST_R3 forecast for the real
    tournament passes the future-leakage check and produces a valid
    manifest -- read-only, never writes into the real content tree."""
    from klpga.tournament_context import load_tournament_context
    real_context = load_tournament_context("2026090003")
    manifest = final_pre_freeze.verify_and_build_manifest(real_context)
    assert manifest.status == "FROZEN"
    assert manifest.future_leakage_check == "PASS"
    assert manifest.game_code == "2026090003"
    assert manifest.player_count > 0


# ---------------------------------------------------------------
# Phase 3: FINAL Truth schema
# ---------------------------------------------------------------


def test_final_truth_roundtrip_write_and_verify(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    assert final_truth.final_truth_exists(context) is True
    assert final_truth.verify_final_truth_hash(context) is True


def test_final_truth_duplicate_player_id_rejected():
    """Phase 11 item 8: FINAL Truth duplicate 없음."""
    records = _truth_records()
    records.append(dict(records[0]))
    with pytest.raises(FinalTruthError, match="duplicate player_id"):
        final_truth.build_final_truth(
            context=_context(), official_source="x", collected_at="2027-09-04T12:00:00Z",
            raw_official_response=b"x", records=records, repo_root=__import__("pathlib").Path("."),
            build_id="b1",
        )


def test_final_truth_bad_status_rejected():
    records = _truth_records()
    records[0]["status"] = "CUT"  # never a valid FINAL status (cut is settled by R2)
    with pytest.raises(FinalTruthError, match="never-valid status"):
        final_truth.build_final_truth(
            context=_context(), official_source="x", collected_at="2027-09-04T12:00:00Z",
            raw_official_response=b"x", records=records, repo_root=__import__("pathlib").Path("."),
            build_id="b1",
        )


def test_final_truth_missing_required_field_rejected():
    records = _truth_records()
    del records[0]["top10_actual"]
    with pytest.raises(FinalTruthError, match="missing required field"):
        final_truth.build_final_truth(
            context=_context(), official_source="x", collected_at="2027-09-04T12:00:00Z",
            raw_official_response=b"x", records=records, repo_root=__import__("pathlib").Path("."),
            build_id="b1",
        )


def test_final_truth_write_immutable_raises_on_existing(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    truth2 = final_truth.build_final_truth(
        context=context, official_source="x", collected_at="2027-09-04T12:00:00Z",
        raw_official_response=b"x", records=_truth_records(), repo_root=__import__("pathlib").Path("."),
        build_id="b2",
    )
    with pytest.raises(FileExistsError):
        final_truth.write_final_truth_immutable(context, truth2)


def test_final_truth_synthetic_test_only_cannot_be_written_via_real_path(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    truth = final_truth.build_final_truth(
        context=context, official_source="x", collected_at="2027-09-04T12:00:00Z",
        raw_official_response=b"x", records=_truth_records(), repo_root=__import__("pathlib").Path("."),
        build_id="b1", synthetic_test_only=True,
    )
    with pytest.raises(FinalTruthError, match="synthetic_test_only"):
        final_truth.write_final_truth_immutable(context, truth)


def test_final_truth_tied_final_rank_allowed():
    """Phase 11 item 10: tied rank handling -- never rejected."""
    records = _truth_records()
    records[1]["final_rank"] = 2
    records[2]["final_rank"] = 2  # legitimate tie for 2nd
    truth = final_truth.build_final_truth(
        context=_context(), official_source="x", collected_at="2027-09-04T12:00:00Z",
        raw_official_response=b"x", records=records, repo_root=__import__("pathlib").Path("."),
        build_id="b1",
    )
    assert truth.observed_player_count == 5


def test_final_truth_wd_status_allowed_with_non_numeric_rank():
    """Phase 11 item 9: WD/DQ handling."""
    records = _truth_records()
    assert records[4]["status"] == "WD"
    assert records[4]["final_rank"] == "WD"
    truth = final_truth.build_final_truth(
        context=_context(), official_source="x", collected_at="2027-09-04T12:00:00Z",
        raw_official_response=b"x", records=records, repo_root=__import__("pathlib").Path("."),
        build_id="b1",
    )
    assert truth.status_counts["WD"] == 1


# ---------------------------------------------------------------
# Phase 4-5: forecast vs actual validator + surprise classification
# ---------------------------------------------------------------


def test_validation_blocked_when_no_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    with pytest.raises(FinalValidationBlocked, match="no PRE-FINAL freeze manifest"):
        final_validator.run_final_validation(context)


def test_validation_blocked_when_no_truth(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    with pytest.raises(FinalValidationBlocked, match="no FINAL truth"):
        final_validator.run_final_validation(context)


def test_validation_blocked_when_truth_synthetic(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context, synthetic=True)
    with pytest.raises(FinalValidationBlocked, match="synthetic_test_only"):
        final_validator.run_final_validation(context)


def test_validation_blocked_on_drift(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    snapshot_path = final_pre_freeze._pre_final_snapshot_path(context)
    tampered = json.loads(snapshot_path.read_text(encoding="utf-8"))
    tampered["records"][0]["win_pct"] = 999.0
    snapshot_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FinalValidationBlocked, match="drifted"):
        final_validator.run_final_validation(context)


def test_run_final_validation_end_to_end(tmp_path, monkeypatch):
    """Phase 11 item 3: 선수 ID join integrity, end to end."""
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    result = final_validator.run_final_validation(context)
    assert result.winner_player_id == "P1"
    assert result.winner_hit is True  # P1 predicted rank 1, actual rank 1
    assert result.top5_hit is True
    assert result.field_size == 5
    # P1: predicted 1, actual 1 -> A (NEO HIGH / ACTUAL HIGH)
    # P4: predicted 15, actual 4 -> C (NEO LOW / ACTUAL HIGH) -- positive surprise
    by_id = {s.player_id: s for s in result.surprises}
    assert by_id["P1"].quadrant == "A_NEO_HIGH_ACTUAL_HIGH"
    assert by_id["P4"].quadrant == "C_NEO_LOW_ACTUAL_HIGH"
    assert by_id["P4"].rank_delta == 15 - 4
    # P5 (WD) excluded from rank-based scoring entirely
    assert "P5" not in by_id


def test_join_by_player_id_not_name(tmp_path, monkeypatch):
    """Phase 11 item 4: 이름만으로 잘못 join하지 않음."""
    context = _build_and_freeze(tmp_path, monkeypatch)
    records = _truth_records()
    # Same player_id P2, but the name on record differs from the
    # forecast's "Bob" -- the join must still succeed via player_id.
    records[1]["player_name"] = "Robert (legal name correction)"
    _write_truth(tmp_path, context, records=records)
    result = final_validator.run_final_validation(context)
    by_id = {s.player_id: s for s in result.surprises}
    assert by_id["P2"].final_rank == 2  # joined correctly despite name mismatch


def test_biggest_surprises_ordering(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    result = final_validator.run_final_validation(context)
    positive, negative = final_validator.biggest_surprises(result, n=5)
    assert positive[0].player_id == "P4"  # biggest positive: predicted 9 -> actual 4
    assert all(s.rank_delta > 0 for s in positive)
    assert all(s.rank_delta < 0 for s in negative)


# ---------------------------------------------------------------
# Phase 11 item 5-6: probability range + monotonic invariant
# ---------------------------------------------------------------


def test_probability_range_and_monotonic_invariant_on_fixture():
    """Phase 11 items 5-6: probability range 0-100(%) and
    WIN <= TOP5 <= TOP10 <= TOP20 for every forecast record."""
    for r in _snapshot()["records"]:
        assert 0.0 <= r["win_pct"] <= 100.0
        assert 0.0 <= r["top5_pct"] <= 100.0
        assert 0.0 <= r["top10_pct"] <= 100.0
        assert 0.0 <= r["top20_pct"] <= 100.0
        assert r["win_pct"] <= r["top5_pct"] <= r["top10_pct"] <= r["top20_pct"]


def test_real_2026090003_forecast_satisfies_probability_invariants():
    from klpga.tournament_context import load_tournament_context
    real_context = load_tournament_context("2026090003")
    snapshot = final_pre_freeze.load_pre_final_snapshot(real_context)
    seen_ids = set()
    for r in snapshot["records"]:
        assert 0.0 <= r["win_pct"] <= 100.0
        assert r["win_pct"] <= r["top5_pct"] <= r["top10_pct"] <= r["top20_pct"] + 1e-9
        pid = r["player_id"]
        assert pid not in seen_ids, f"duplicate player_id {pid} in real PRE-FINAL forecast"
        seen_ids.add(pid)


# ---------------------------------------------------------------
# Phase 6: course Deep Dive connector
# ---------------------------------------------------------------


def test_course_deep_dive_blocked_when_no_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    connection = final_course_deep_dive.connect_course_deep_dive(context)
    assert connection.status == "BLOCKED"
    assert "no course Deep Dive artifact found" in connection.reason


def test_course_deep_dive_connected_when_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    path = context.artifact_path(final_course_deep_dive.COURSE_DEEP_DIVE_ARTIFACT_TYPE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({f: "x" for f in final_course_deep_dive.REQUIRED_FIELDS}), encoding="utf-8")
    connection = final_course_deep_dive.connect_course_deep_dive(context)
    assert connection.status == "CONNECTED"
    assert connection.data is not None


def test_course_deep_dive_blocked_when_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    path = context.artifact_path(final_course_deep_dive.COURSE_DEEP_DIVE_ARTIFACT_TYPE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"field_average_relative_score": 1.0}), encoding="utf-8")
    connection = final_course_deep_dive.connect_course_deep_dive(context)
    assert connection.status == "BLOCKED"
    assert "missing required field" in connection.reason


def test_real_2026090003_course_deep_dive_is_honestly_blocked():
    """Confirms the Phase 6 finding in code: no Blackstone/Icheon Deep
    Dive data exists for the real tournament today -- the connector
    must report BLOCKED, never fabricate a connection."""
    from klpga.tournament_context import load_tournament_context
    real_context = load_tournament_context("2026090003")
    connection = final_course_deep_dive.connect_course_deep_dive(real_context)
    assert connection.status == "BLOCKED"
    assert connection.data is None


def test_course_deep_dive_never_touches_existing_preview_paths(tmp_path, monkeypatch):
    """Phase 11 item 15: 기존 Deep Dive 깨지지 않음 -- the connector's
    artifact path always resolves under CONTENT_DIR, never the
    unrelated previews/website-v2-phase1/deep-dive fixture shell."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    path = context.artifact_path(final_course_deep_dive.COURSE_DEEP_DIVE_ARTIFACT_TYPE)
    assert "previews" not in str(path)
    assert str(path).startswith(str(tmp_path))


# ---------------------------------------------------------------
# Phase 7: report generator
# ---------------------------------------------------------------


def test_report_blocked_when_validator_blocked(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    report = final_report.build_final_report(context)
    assert report["status"] == "BLOCKED"
    assert "no FINAL truth" in report["blocked_reason"]


def test_report_partial_when_deep_dive_unavailable(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    report = final_report.build_final_report(context)
    assert report["status"] == "PARTIAL"
    assert report["course_connection"]["status"] == "BLOCKED"
    assert report["forecast_performance"]["winner_hit"] is True


def test_report_complete_when_deep_dive_available(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    dd_path = context.artifact_path(final_course_deep_dive.COURSE_DEEP_DIVE_ARTIFACT_TYPE)
    dd_path.write_text(json.dumps({f: "x" for f in final_course_deep_dive.REQUIRED_FIELDS}), encoding="utf-8")
    report = final_report.build_final_report(context)
    assert report["status"] == "VALIDATION_COMPLETE"


def test_report_never_marks_complete_without_real_truth(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context, synthetic=True)
    report = final_report.build_final_report(context)
    assert report["status"] == "BLOCKED"


# ---------------------------------------------------------------
# Phase 9: content export
# ---------------------------------------------------------------


def test_content_export_all_blocked_when_report_blocked(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    sources = final_content_export.export_content_sources(context)
    assert set(sources) == set(final_content_export.CHANNELS)
    assert all(v["status"] == "BLOCKED" for v in sources.values())


def test_content_export_channels_share_the_same_winner(tmp_path, monkeypatch):
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)
    sources = final_content_export.export_content_sources(context)
    winner_names = {
        sources["naver_blog"]["event_summary"]["winner_name"],
        sources["threads"]["winner"],
        sources["card_news"]["cards"][0]["value"],
        sources["homepage_deep_dive"]["report"]["event_summary"]["winner_name"],
    }
    assert winner_names == {"Alice"}


# ---------------------------------------------------------------
# Phase 10: postmortem-freeze / no auto-tuning guard
# ---------------------------------------------------------------


def test_build_final_report_never_writes_any_file(tmp_path, monkeypatch):
    """Phase 10/11: report generation is pure read+compute -- it must
    never write to ANY file (production model config included), so a
    FINAL result can never silently auto-tune production parameters as
    a side effect of being validated/reported."""
    context = _build_and_freeze(tmp_path, monkeypatch)
    _write_truth(tmp_path, context)

    from pathlib import Path
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes

    def _forbid_write_text(self, *a, **kw):
        raise AssertionError(f"unexpected file write during build_final_report: {self}")

    def _forbid_write_bytes(self, *a, **kw):
        raise AssertionError(f"unexpected file write during build_final_report: {self}")

    monkeypatch.setattr(Path, "write_text", _forbid_write_text)
    monkeypatch.setattr(Path, "write_bytes", _forbid_write_bytes)
    try:
        report = final_report.build_final_report(context)
    finally:
        monkeypatch.setattr(Path, "write_text", original_write_text)
        monkeypatch.setattr(Path, "write_bytes", original_write_bytes)
    assert report["status"] == "PARTIAL"


def test_no_model_auto_tuning_reference_in_final_modules():
    """Static guard: none of the new FINAL modules import or call
    anything that writes to a model config/weights artifact -- the
    postmortem->challenger->promotion pipeline (Phase 10) stays a
    separate, explicit, human-gated step, never automatic."""
    import inspect
    from klpga.neo_win import final_report as _fr, final_validator as _fv, final_pre_freeze as _fp
    forbidden = ("model_config", "MODEL_WEIGHTS", "update_production_model", "retrain")
    for module in (_fr, _fv, _fp):
        source = inspect.getsource(module)
        for token in forbidden:
            assert token not in source, f"{module.__name__} references {token!r} -- auto-tuning risk"


# ---------------------------------------------------------------
# Phase 8: FINAL wait page
# ---------------------------------------------------------------


def test_final_wait_page_is_wait_page():
    from klpga.neo_win.final_wait_page import render_final_wait_page, is_wait_page, FINAL_SLOT_IDS
    html = render_final_wait_page(tournament_name="Fixture Final Pre-Build Open", game_code="FIXTUREFINAL02")
    assert is_wait_page(html)
    for slot_id in FINAL_SLOT_IDS:
        assert f'id="{slot_id}"' in html
        assert 'data-neo-slot-empty="true"' in html


def test_final_wait_page_no_internal_state_exposed():
    """Phase 11 item 12: public page에 내부 상태 노출 없음."""
    from klpga.neo_win.final_wait_page import render_final_wait_page
    html = render_final_wait_page(tournament_name="Fixture Final Pre-Build Open", game_code="FIXTUREFINAL02")
    for forbidden in ("sha256", "code_commit", "build_id", "manifest", ".py", "content/website_v2", "FROZEN"):
        assert forbidden not in html


def test_final_wait_page_has_no_player_rows_or_fabricated_numbers():
    """Phase 11 item 11 (missing sponsor = blank) is a public-page rule
    for a REAL leaderboard row; at this pre-build stage there are no
    player rows at all -- the strongest available guarantee that
    nothing is fabricated."""
    from klpga.neo_win.final_wait_page import render_final_wait_page
    html = render_final_wait_page(tournament_name="Fixture Final Pre-Build Open", game_code="FIXTUREFINAL02")
    assert "player-sponsor" not in html
    assert "<tr" not in html
