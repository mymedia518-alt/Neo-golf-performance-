"""Tests for klpga.neo_win.r3_pipeline_orchestrator — the importable
BETA #001 R2 -> R3 pipeline core. Fully synthetic: a frozen R2 history
fixture + synthetic entry/official/db round-3 data + synthetic
r3_model_entrants, all written under tmp_path — this IS the dry-run
pipeline, proven here as a pytest test rather than only via the CLI
script, so it runs on every test invocation."""
from __future__ import annotations

from klpga.neo_win.r3_pipeline_orchestrator import (
    run_r3_evaluation_pipeline,
    write_r3_model_csv,
)
from klpga.neo_win.round_reconciliation import NormalizedPlayer
from klpga.neo_win.tournament_history import (
    STAGE_R2,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    read_effective_history_stage,
    write_history_stage_atomic,
)

GAME_CODE = "2026080099"


def _seed_frozen_r2_history(history_dir, win_by_code):
    entrants = tuple(
        HistoryEntrant(player_code=code, player_name=f"Player{code}", win_pct=win)
        for code, win in win_by_code.items()
    )
    entry = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R2, record_kind=RECORD_KIND, recorded_at_utc="2026-08-28T00:00:00Z",
        source_prediction_id="001-C-R2", source_model_version="round_update_r2", source_generated_at_utc="2026-08-28T00:00:00Z",
        tournament_name="Test Open", field_size=len(entrants), entrants=entrants,
    )
    write_history_stage_atomic(entry, history_dir)


def _normalized(codes, *, present=True):
    out = {}
    for i, code in enumerate(codes, start=1):
        if present:
            out[code] = NormalizedPlayer(
                player_code=code, player_name=f"Player{code}", position_display=str(i), position=i,
                round_score=70, score_to_par=-2, status=None,
            )
        else:
            out[code] = NormalizedPlayer(
                player_code=code, player_name=f"Player{code}", position_display=None, position=None,
                round_score=None, score_to_par=None, status=None,
            )
    return out


def _r3_model_entrants(codes):
    win_pool = 100.0 / len(codes) if codes else 0.0
    return [
        {
            "player_code": code, "player_name": f"Player{code}", "position": i, "score_to_par": -4.0,
            "win_pct": win_pool, "top5_pct": 50.0, "top10_pct": 70.0, "top20_pct": 90.0,
        }
        for i, code in enumerate(codes, start=1)
    ]


def test_reconciliation_pass_writes_csv_and_freezes(tmp_path):
    history_dir = tmp_path / "history"
    _seed_frozen_r2_history(history_dir, {"p1": 40.0, "p2": 25.0, "p3": 15.0, "p4": 10.0})

    codes = ["p1", "p2", "p3", "p4"]
    entry_r3 = _normalized(codes)
    official_r3 = _normalized(codes)
    db_r3 = _normalized(codes)  # matches official exactly -> PASS
    entrants = _r3_model_entrants(codes)

    output_root = tmp_path / "output"
    result = run_r3_evaluation_pipeline(
        game_code=GAME_CODE, tournament_name="Test Open", history_dir=history_dir,
        entry_r3=entry_r3, official_r3=official_r3, db_r3=db_r3,
        r3_model_entrants=entrants, output_root=output_root, freeze=True,
        source_prediction_id="001", source_model_version="v0.1", source_generated_at_utc="2026-08-25T00:00:00Z",
    )

    assert result["status"] == "OK"
    assert result["steps"]["STEP3_RECONCILIATION"]["verdict"] == "PASS"
    assert result["steps"]["STEP6_R2_TO_R3_DELTA_BASELINE"] == {"found": True, "n_r2_players_with_win_pct": 4}
    assert result["win_sum_pct"] == 100.0
    assert (output_root / "BETA_R3_FULL.csv").exists()
    assert result["steps"]["STEP8_R3_FREEZE"]["result"].startswith("RECORDED")

    frozen = read_effective_history_stage(history_dir, GAME_CODE, "R3")
    assert frozen is not None
    assert {e.player_code for e in frozen.entrants} == set(codes)


def test_score_mismatch_hard_stops_before_prediction(tmp_path):
    """A real SCORE_MISMATCH anomaly must FAIL the reconciliation gate
    and produce NO csv/freeze — never a best-effort snapshot built on
    disagreeing data."""
    history_dir = tmp_path / "history"
    _seed_frozen_r2_history(history_dir, {"p1": 40.0})

    codes = ["p1"]
    entry_r3 = _normalized(codes)
    official_r3 = _normalized(codes)
    db_r3 = {
        "p1": NormalizedPlayer(
            player_code="p1", player_name="Playerp1", position_display="1", position=1,
            round_score=99, score_to_par=25, status=None,  # deliberately disagrees with official
        )
    }
    output_root = tmp_path / "output"

    result = run_r3_evaluation_pipeline(
        game_code=GAME_CODE, tournament_name="Test Open", history_dir=history_dir,
        entry_r3=entry_r3, official_r3=official_r3, db_r3=db_r3,
        r3_model_entrants=_r3_model_entrants(codes), output_root=output_root, freeze=True,
    )

    assert result["status"] == "HARD_STOP"
    assert result["steps"]["STEP3_RECONCILIATION"]["verdict"] == "FAIL"
    assert "p1" in result["steps"]["STEP3_RECONCILIATION"]["score_mismatch"]
    assert "STEP6_R2_TO_R3_DELTA_BASELINE" not in result["steps"]
    assert not (output_root / "BETA_R3_FULL.csv").exists()


def test_no_frozen_r2_stage_reports_unavailable_delta_but_still_ok(tmp_path):
    history_dir = tmp_path / "history"  # never seeded -> no STAGE_R2 at all
    codes = ["p1"]
    entry_r3 = _normalized(codes)
    official_r3 = _normalized(codes)
    db_r3 = _normalized(codes)
    output_root = tmp_path / "output"

    result = run_r3_evaluation_pipeline(
        game_code=GAME_CODE, tournament_name="Test Open", history_dir=history_dir,
        entry_r3=entry_r3, official_r3=official_r3, db_r3=db_r3,
        r3_model_entrants=_r3_model_entrants(codes), output_root=output_root,
    )

    assert result["status"] == "OK"
    assert result["steps"]["STEP6_R2_TO_R3_DELTA_BASELINE"] == {"found": False, "n_r2_players_with_win_pct": 0}
    csv_text = (output_root / "BETA_R3_FULL.csv").read_text(encoding="utf-8-sig")
    assert "unavailable" in csv_text  # r2_win_pct / r2_to_r3_win_change_pct columns


def test_freeze_false_never_writes_history(tmp_path):
    history_dir = tmp_path / "history"
    codes = ["p1"]
    result = run_r3_evaluation_pipeline(
        game_code=GAME_CODE, tournament_name="Test Open", history_dir=history_dir,
        entry_r3=_normalized(codes), official_r3=_normalized(codes), db_r3=_normalized(codes),
        r3_model_entrants=_r3_model_entrants(codes), output_root=tmp_path / "output", freeze=False,
    )
    assert result["status"] == "OK"
    assert read_effective_history_stage(history_dir, GAME_CODE, "R3") is None
    assert result["steps"]["STEP8_R3_FREEZE"]["result"].startswith("NOT FROZEN")


def test_double_freeze_is_skip_log_not_overwrite(tmp_path):
    history_dir = tmp_path / "history"
    codes = ["p1"]
    kwargs = dict(
        game_code=GAME_CODE, tournament_name="Test Open", history_dir=history_dir,
        entry_r3=_normalized(codes), official_r3=_normalized(codes), db_r3=_normalized(codes),
        r3_model_entrants=_r3_model_entrants(codes), freeze=True,
    )
    first = run_r3_evaluation_pipeline(output_root=tmp_path / "run1", **kwargs)
    second = run_r3_evaluation_pipeline(output_root=tmp_path / "run2", **kwargs)

    assert first["steps"]["STEP8_R3_FREEZE"]["result"].startswith("RECORDED")
    assert second["steps"]["STEP8_R3_FREEZE"]["result"].startswith("ALREADY_RECORDED")


def test_write_r3_model_csv_schema_matches_script46():
    entrants = [{"player_code": "p1", "player_name": "P1", "position": 1, "score_to_par": -4.0, "win_pct": 50.0,
                 "top5_pct": 80.0, "top10_pct": 90.0, "top20_pct": 95.0}]
    import csv as csv_module
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = write_r3_model_csv(entrants, {"p1": 40.0}, {"p1": "ACTIVE"}, Path(d) / "out.csv")
        with open(path, encoding="utf-8-sig") as f:
            reader = csv_module.DictReader(f)
            assert reader.fieldnames == [
                "player_code", "player_name", "player_status", "position", "score_to_par",
                "neo_win_pct", "neo_top5_pct", "neo_top10_pct", "neo_top20_pct",
                "r2_win_pct", "r2_to_r3_win_change_pct",
            ]
            row = next(reader)
            assert row["r2_win_pct"] == "40.0"
            assert row["r2_to_r3_win_change_pct"] == "10.0"
