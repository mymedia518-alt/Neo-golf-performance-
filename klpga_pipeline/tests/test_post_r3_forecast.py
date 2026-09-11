"""R3 HOUSE: klpga.neo_win.post_r3_forecast -- the canonical post-R3
forecast. Synthetic-only, isolated tournament_context fixtures."""
from __future__ import annotations

import json

import pytest

from klpga.neo_win.post_r3_forecast import (
    PostR3ForecastError, post_r3_forecast_path, post_r3_forecast_status, run_post_r3_forecast,
)
from klpga.neo_win.r3_freeze import build_r3_frozen_evidence, write_r3_freeze_immutable
from klpga.tournament_context import TournamentContext

GAME_CODE = "TEST0003"


@pytest.fixture
def context(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    monkeypatch.setattr(tc, "CONTENT_DIR", tmp_path / "content")
    (tmp_path / "content").mkdir()
    return TournamentContext(
        game_code=GAME_CODE, tournament_name="SYNTHETIC R3 FORECAST OPEN", season=2026,
        start_date="2026-01-01", end_date="2026-01-04", final_round_number=4,
        current_round_number=3, url_base=f"/tournaments/2026/{GAME_CODE}/",
        stage_state_filename=f"{GAME_CODE}_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )


@pytest.fixture
def r2_freeze_path(tmp_path, context):
    p = tmp_path / "content" / f"{GAME_CODE}_R2_FROZEN_EVIDENCE.json"
    p.write_text(json.dumps({"records": [{"player_id": "p1"}, {"player_id": "p2"}]}), encoding="utf-8")
    return p


def _write_r3_freeze(context, r2_freeze_path, tmp_path, records):
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="klpga.co.kr roundLeaderboard", official_source_url=None,
        collection_timestamp="2026-01-04T10:00:00Z", raw_official_response=b"[]", records=records,
        expected_field_count=len(records), status_counts={"ACTIVE": sum(1 for r in records if r.get("status", "ACTIVE") == "ACTIVE")},
        wd_dq_dns_evidence=[], r2_freeze_path=r2_freeze_path, repo_root=tmp_path, build_id="B1",
    )
    write_r3_freeze_immutable(context, evidence)


def _pre_performance(pids):
    return {"profiles": [
        {"player_id": pid, "windows": {"recent5": {"components": {"total": {"mean": -0.3}}}}}
        for pid in pids
    ]}


def test_no_freeze_refuses_to_write(context, tmp_path):
    with pytest.raises(PostR3ForecastError, match="no verified R3 freeze"):
        run_post_r3_forecast(context, pre_performance_snapshot={"profiles": []}, repo_root=tmp_path, build_id="B1", seed=1, n_simulations=10)


def test_zero_simulations_refuses(context, r2_freeze_path, tmp_path):
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    _write_r3_freeze(context, r2_freeze_path, tmp_path, records)
    with pytest.raises(PostR3ForecastError, match="n_simulations must be > 0"):
        run_post_r3_forecast(context, pre_performance_snapshot=_pre_performance(["p1"]), repo_root=tmp_path, build_id="B1", seed=1, n_simulations=0)


def test_writes_real_forecast_with_correct_contract(context, r2_freeze_path, tmp_path):
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": -3, "r2_score_to_par": -1, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 1},
    ]
    _write_r3_freeze(context, r2_freeze_path, tmp_path, records)
    assert post_r3_forecast_status(context) == "NOT_CREATED"

    forecast = run_post_r3_forecast(
        context, pre_performance_snapshot=_pre_performance(["p1", "p2"]), repo_root=tmp_path,
        build_id="B1", seed=42, n_simulations=200,
    )
    assert post_r3_forecast_status(context) == "CREATED"
    assert forecast["artifact"] == "post_r3_final_forecast"
    assert forecast["source_round"] == 3
    assert forecast["remaining_rounds"] == 1  # final_round_number(4) - 3
    assert forecast["n_simulations"] == 200
    assert {r["player_id"] for r in forecast["records"]} == {"p1", "p2"}
    assert forecast["win_probability_sum_pct"] == pytest.approx(100.0, abs=0.01)
    assert forecast["future_data_excluded"] is True
    assert post_r3_forecast_path(context).is_file()

    for row in forecast["records"]:
        assert row["win_pct"] <= row["top5_pct"] <= row["top10_pct"] <= row["top20_pct"] <= 100.0


def test_wd_player_excluded_and_reported_missing(context, r2_freeze_path, tmp_path):
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "WD", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": None},
    ]
    _write_r3_freeze(context, r2_freeze_path, tmp_path, records)
    forecast = run_post_r3_forecast(context, pre_performance_snapshot=_pre_performance(["p1", "p2"]), repo_root=tmp_path, build_id="B1", seed=1, n_simulations=100)
    assert {r["player_id"] for r in forecast["records"]} == {"p1"}


def test_missing_pre_profile_excluded_and_reported(context, r2_freeze_path, tmp_path):
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    _write_r3_freeze(context, r2_freeze_path, tmp_path, records)
    forecast = run_post_r3_forecast(context, pre_performance_snapshot={"profiles": []}, repo_root=tmp_path, build_id="B1", seed=1, n_simulations=100)
    assert forecast["records"] == []
    assert forecast["missing_players"][0]["player_id"] == "p1"
    assert forecast["missing_players"][0]["profile"] is False


def test_missing_r3_score_for_active_player_excluded_and_reported(context, r2_freeze_path, tmp_path):
    """A real, confirmed advancing player missing their own R3 score
    (e.g. in-progress/rain-delayed) is a real ingestion gap, never
    simulated on a fabricated score."""
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": None}]
    _write_r3_freeze(context, r2_freeze_path, tmp_path, records)
    forecast = run_post_r3_forecast(context, pre_performance_snapshot=_pre_performance(["p1"]), repo_root=tmp_path, build_id="B1", seed=1, n_simulations=100)
    assert forecast["records"] == []
    assert forecast["missing_players"][0]["r3_score"] is False


def test_final_round_number_leaves_nothing_to_forecast_refuses(context, r2_freeze_path, tmp_path):
    import dataclasses
    r3_context = dataclasses.replace(context, final_round_number=3)  # R3 IS the final round
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    _write_r3_freeze(r3_context, r2_freeze_path, tmp_path, records)
    with pytest.raises(PostR3ForecastError, match="nothing to forecast"):
        run_post_r3_forecast(r3_context, pre_performance_snapshot=_pre_performance(["p1"]), repo_root=tmp_path, build_id="B1", seed=1, n_simulations=100)
