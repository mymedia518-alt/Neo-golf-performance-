"""Tests for klpga.neo_win.r2_forecast — the R2 FROZEN FORECAST row
builder and its hard-gate validation checks. Never recomputes a
probability; only shapes klpga.neo_win.round_update_r2.
simulate_post_round2's own real output and checks its properties."""
from __future__ import annotations

import csv

from klpga.neo_win.ground_truth_diagnostic import GroundTruthRow
from klpga.neo_win.r2_forecast import (
    build_r2_forecast_rows,
    check_forecast_population_matches_confirmed_continuers,
    check_probability_monotonicity,
    check_win_sum_approximately_100,
    write_r2_forecast_csv,
)
from klpga.neo_win.round_reconciliation import NormalizedPlayer


def _gt_row(code, name="A", rank="5", total_score=140):
    return GroundTruthRow(
        player_code=code, official_name=name, r1_present=True, r2_present=True,
        r2_raw_rank=rank, r2_raw_status=None, r2_round_score=70, r2_total_score=total_score,
        r3_grouping_present=True, r3_group=None, r3_tee_time="09:10", r3_starting_tee="1",
        final_ground_truth_status="MADE_CUT_CONFIRMED", reason="test",
    )


def _official(code, position=5):
    return {code: NormalizedPlayer(player_code=code, player_name="A", position_display=str(position), position=position, round_score=70, score_to_par=-2, status=None)}


def _sim(win=10.0, top5=30.0, top10=50.0, top20=80.0):
    return {"win_pct": win, "top5_pct": top5, "top10_pct": top10, "top20_pct": top20, "make_cut_pct": 100.0}


# ---------------------------------------------------------------
# build_r2_forecast_rows
# ---------------------------------------------------------------


def test_build_rows_one_per_sim_result_player():
    gt = [_gt_row("p1", total_score=140), _gt_row("p2", total_score=145)]
    sim_result = {"p1": _sim(win=20.0), "p2": _sim(win=5.0)}
    official = {**_official("p1", 1), **_official("p2", 10)}
    rows = build_r2_forecast_rows(gt, sim_result, official)
    assert {r["player_code"] for r in rows} == {"p1", "p2"}
    assert len(rows) == 2


def test_percentages_rounded_to_2_decimal_places_display_only():
    gt = [_gt_row("p1")]
    sim_result = {"p1": {"win_pct": 12.34567, "top5_pct": 30.111, "top10_pct": 50.999, "top20_pct": 80.005, "make_cut_pct": 100.0}}
    rows = build_r2_forecast_rows(gt, sim_result, _official("p1"))
    row = rows[0]
    assert row["win_pct"] == 12.35
    assert row["top5_pct"] == 30.11
    assert row["top10_pct"] == 51.0
    assert row["top20_pct"] == 80.01 or row["top20_pct"] == 80.0  # rounding of .005 is banker's/float-dependent


def test_sorted_by_real_r2_rank_then_total_score():
    gt = [_gt_row("p1", rank="2", total_score=141), _gt_row("p2", rank="1", total_score=139)]
    sim_result = {"p1": _sim(), "p2": _sim()}
    official = {**_official("p1", 2), **_official("p2", 1)}
    rows = build_r2_forecast_rows(gt, sim_result, official)
    assert [r["player_code"] for r in rows] == ["p2", "p1"]


def test_real_rank_display_and_total_score_come_from_ground_truth_not_recomputed():
    gt = [_gt_row("p1", rank="T4", total_score=138)]
    rows = build_r2_forecast_rows(gt, {"p1": _sim()}, _official("p1", 4))
    assert rows[0]["r2_rank"] == "T4"
    assert rows[0]["r2_total_score"] == 138


def test_no_internal_sort_key_leaks_into_output_row():
    rows = build_r2_forecast_rows([_gt_row("p1")], {"p1": _sim()}, _official("p1"))
    assert "_r2_rank_sort" not in rows[0]


# ---------------------------------------------------------------
# write_r2_forecast_csv
# ---------------------------------------------------------------


def test_write_csv_has_required_columns(tmp_path):
    rows = build_r2_forecast_rows([_gt_row("p1")], {"p1": _sim()}, _official("p1"))
    out = tmp_path / "forecast.csv"
    write_r2_forecast_csv(rows, out)
    with open(out, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "player_code", "player_name", "r2_rank", "r2_total_score",
            "top20_pct", "top10_pct", "top5_pct", "win_pct",
        ]
        written = list(reader)
    assert len(written) == 1


# ---------------------------------------------------------------
# hard-gate checks
# ---------------------------------------------------------------


def test_population_check_passes_when_exact_match():
    sim_result = {"p1": _sim(), "p2": _sim()}
    result = check_forecast_population_matches_confirmed_continuers(sim_result, {"p1", "p2"})
    assert result["passed"] is True


def test_population_check_fails_on_extra_or_missing_player():
    sim_result = {"p1": _sim(), "p3": _sim()}
    result = check_forecast_population_matches_confirmed_continuers(sim_result, {"p1", "p2"})
    assert result["passed"] is False
    assert "p2" in result["detail"] and "p3" in result["detail"]


def test_monotonicity_check_passes_for_real_shaped_data():
    sim_result = {"p1": _sim(win=10, top5=30, top10=50, top20=80)}
    assert check_probability_monotonicity(sim_result)["passed"] is True


def test_monotonicity_check_fails_when_violated():
    sim_result = {"p1": _sim(win=90, top5=30, top10=50, top20=80)}  # win > top5, impossible for real data
    result = check_probability_monotonicity(sim_result)
    assert result["passed"] is False
    assert "p1" in result["detail"]


def test_win_sum_check_passes_near_100():
    sim_result = {"p1": _sim(win=60.0), "p2": _sim(win=40.0)}
    assert check_win_sum_approximately_100(sim_result)["passed"] is True


def test_win_sum_check_fails_when_far_from_100():
    sim_result = {"p1": _sim(win=10.0), "p2": _sim(win=10.0)}
    result = check_win_sum_approximately_100(sim_result)
    assert result["passed"] is False


def test_win_sum_check_passes_trivially_when_empty():
    assert check_win_sum_approximately_100({})["passed"] is True
