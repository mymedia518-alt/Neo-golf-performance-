"""Tests for klpga.neo_win.r2_pipeline_orchestrator — Sections G & J's
importable pipeline core. Fully synthetic: a frozen R1 history
fixture + a synthetic official R2 leaderboard + synthetic R2 model
entrants, all written under tmp_path — this IS the Section L "dry
run", proven here as a pytest test rather than a separate script, so
it runs (and is checked) on every CI/local test invocation."""
from __future__ import annotations

from klpga.neo_win.r2_pipeline_orchestrator import (
    build_win_interim_rows,
    run_r2_evaluation_pipeline,
    write_r2_model_csv,
)
from klpga.neo_win.round_reconciliation import NormalizedPlayer
from klpga.neo_win.tournament_history import (
    STAGE_R1,
    HistoryEntrant,
    HistoryStageSnapshot,
    RECORD_KIND,
    write_history_stage_atomic,
)

GAME_CODE = "2026080099"


def _seed_frozen_r1_history(history_dir):
    entrants = tuple(
        HistoryEntrant(
            player_code=f"p{i}", player_name=f"Player{i}", win_pct=max(20.0 - i, 0.5),
            make_cut_pct=max(95.0 - i * 5, 5.0), position=i, score_to_par=float(-10 + i),
        )
        for i in range(1, 9)
    )
    entry = HistoryStageSnapshot(
        game_code=GAME_CODE, stage=STAGE_R1, record_kind=RECORD_KIND, recorded_at_utc="2026-08-27T00:00:00Z",
        source_prediction_id="001-C-R1", source_model_version="round_update", source_generated_at_utc="2026-08-27T00:00:00Z",
        tournament_name="Test Open", field_size=8, entrants=entrants,
    )
    write_history_stage_atomic(entry, history_dir)


def _official_r2(made_cut_codes, missed_cut_codes, wd_codes=(), missing_codes=()):
    official = {}
    for i, code in enumerate(made_cut_codes, start=1):
        official[code] = NormalizedPlayer(
            player_code=code, player_name=f"Player{code[1:]}", position_display=str(i), position=i,
            round_score=70, score_to_par=-2, status=None,
        )
    for code in missed_cut_codes:
        official[code] = NormalizedPlayer(
            player_code=code, player_name=f"Player{code[1:]}", position_display="CUT", position=None,
            round_score=None, score_to_par=None, status="CUT",
        )
    for code in wd_codes:
        official[code] = NormalizedPlayer(
            player_code=code, player_name=f"Player{code[1:]}", position_display="WD", position=None,
            round_score=None, score_to_par=None, status="WD",
        )
    # missing_codes deliberately absent entirely
    return official


def _r2_model_entrants(made_cut_codes, missed_cut_codes):
    entrants = []
    win_pool = 100.0 / len(made_cut_codes) if made_cut_codes else 0.0
    for i, code in enumerate(made_cut_codes, start=1):
        entrants.append({
            "player_code": code, "player_name": f"Player{code[1:]}", "position": i,
            "score_to_par": -4.0, "win_pct": win_pool, "make_cut_pct": 100.0,
        })
    for code in missed_cut_codes:
        entrants.append({
            "player_code": code, "player_name": f"Player{code[1:]}", "position": None,
            "score_to_par": None, "win_pct": 0.0, "make_cut_pct": 0.0,
        })
    return entrants


def test_dry_run_pipeline_end_to_end_synthetic_fixture(tmp_path):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir)

    made_cut = [f"p{i}" for i in range(1, 5)]
    missed_cut = [f"p{i}" for i in range(5, 7)]
    wd = ["p7"]
    # p8 has no R2 row at all -> UNRESOLVED

    official_r2 = _official_r2(made_cut, missed_cut, wd)
    r2_model_entrants = _r2_model_entrants(made_cut, missed_cut + wd)

    output_root = tmp_path / "dry_run_output"
    result = run_r2_evaluation_pipeline(
        game_code=GAME_CODE, tournament_name="Test Open",
        history_dir=history_dir, predictions_dir=tmp_path / "neo_win_predictions",
        outputs_csv_path=tmp_path / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv",
        official_r2=official_r2, r2_model_entrants=r2_model_entrants, output_root=output_root,
    )

    assert result["status"] == "OK", result["steps"].get("STEP10_VALIDATION")
    steps = result["steps"]
    assert steps["STEP_A_FROZEN_R1_SOURCE"]["n_players"] == 8
    assert steps["STEP2_RECONCILIATION"]["made_cut"] == 4
    assert steps["STEP2_RECONCILIATION"]["cut"] == 2
    assert steps["STEP2_RECONCILIATION"]["new_wd"] == 1
    assert steps["STEP2_RECONCILIATION"]["missing"] == 1  # p8
    assert steps["STEP3_CUT_EVALUATION"]["n_evaluated"] == 6  # 4 made + 2 missed, WD/unresolved excluded
    assert steps["STEP10_VALIDATION"]["all_passed"] is True

    # Real files were actually written, isolated under output_root.
    assert (output_root / "r1" / "predictions.csv").exists()
    assert (output_root / "r2" / "player_evaluation.csv").exists()
    assert (output_root / "r2" / "round_condition.json").exists()
    assert (output_root / "r2" / "BETA_R2_FULL.csv").exists()
    assert (output_root / "r2" / "index.html").exists()
    html = (output_root / "r2" / "index.html").read_text(encoding="utf-8")
    assert "NEO GOLF DATA — BETA #001 — R1 MODEL CHECK" in html
    assert "R1 predictions were frozen before Round 2 results were known." in html


def test_dry_run_hard_stops_when_no_frozen_r1_source(tmp_path):
    result = run_r2_evaluation_pipeline(
        game_code="9999999999", tournament_name="Nonexistent",
        history_dir=tmp_path / "neo_tournament_history", predictions_dir=tmp_path / "neo_win_predictions",
        outputs_csv_path=tmp_path / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv",
        official_r2={}, r2_model_entrants=[], output_root=tmp_path / "out",
    )
    assert result["status"] == "HARD_STOP"
    assert not (tmp_path / "out").exists()  # nothing written on a hard stop


def test_dry_run_never_touches_a_real_r1_html_path(tmp_path):
    history_dir = tmp_path / "neo_tournament_history"
    _seed_frozen_r1_history(history_dir)
    r1_html_path = tmp_path / "docs" / "tournaments" / "2026" / "test" / "r1" / "index.html"
    r1_html_path.parent.mkdir(parents=True)
    r1_html_path.write_text("FROZEN R1 SNAPSHOT — NEVER MODIFIED", encoding="utf-8")
    before_bytes = r1_html_path.read_bytes()

    import hashlib

    expected_sha = hashlib.sha256(before_bytes).hexdigest()

    result = run_r2_evaluation_pipeline(
        game_code=GAME_CODE, tournament_name="Test Open",
        history_dir=history_dir, predictions_dir=tmp_path / "neo_win_predictions",
        outputs_csv_path=tmp_path / "outputs" / "beta001_r1" / "BETA001_R1_FULL.csv",
        official_r2=_official_r2(["p1", "p2"], ["p3"]), r2_model_entrants=_r2_model_entrants(["p1", "p2"], ["p3"]),
        output_root=tmp_path / "dry_run_output", r1_html_path=r1_html_path, r1_html_expected_sha256=expected_sha,
    )

    assert r1_html_path.read_bytes() == before_bytes  # byte-identical after the run
    checks = {c["check"]: c for c in result["steps"]["STEP10_VALIDATION"]["checks"]}
    assert checks["R1_HISTORICAL_HTML_UNCHANGED"]["passed"] is True
    assert checks["R2_PATH_NEVER_OVERWRITES_R1"]["passed"] is True


def test_build_win_interim_rows_ranks_by_win_pct_descending():
    from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
    from klpga.neo_win.r1_to_r2_reconciliation import PlayerR2Reconciled
    from klpga.neo_win.cut_evaluation import CUT_OUTCOME_MADE

    frozen = [
        PlayerR1Frozen(tournament_id="t", player_code="p1", player_name="A", r1_actual_rank=2, r1_actual_score_to_par=-1.0, r1_win_probability_pct=5.0, r1_make_cut_probability_pct=80.0, model_version="v", prediction_generated_at="t"),
        PlayerR1Frozen(tournament_id="t", player_code="p2", player_name="B", r1_actual_rank=1, r1_actual_score_to_par=-3.0, r1_win_probability_pct=15.0, r1_make_cut_probability_pct=90.0, model_version="v", prediction_generated_at="t"),
    ]
    reconciled = [
        PlayerR2Reconciled(player_code="p2", player_name="B", r2_position=1, r2_score_to_par=-4, r2_outcome=CUT_OUTCOME_MADE, in_frozen_r1=True, in_official_r2=True),
    ]
    rows = build_win_interim_rows(frozen, reconciled)
    assert rows[0].player_code == "p2"  # higher win_pct (15.0) ranked first
    assert rows[0].r1_win_rank == 1
    assert rows[0].r2_leaderboard_position == 1
    assert rows[1].player_code == "p1"
    assert rows[1].r2_leaderboard_position is None


def test_write_r2_model_csv(tmp_path):
    entrants = [{"player_code": "p1", "player_name": "A", "position": 1, "score_to_par": -4.0, "win_pct": 50.0, "make_cut_pct": 100.0}]
    path = write_r2_model_csv(entrants, tmp_path / "r2" / "BETA_R2_FULL.csv")
    assert path.exists()
    assert "p1" in path.read_text(encoding="utf-8")
