"""Tests for klpga.neo_win.r2_production_validation — the R2
PRODUCTION DEPLOYMENT hard-validation gate. Every check operates on
already-frozen real-shaped data (never recomputes a probability)."""
from __future__ import annotations

from klpga.neo_win.r2_production_page import render_r2_forecast_table_rows
from klpga.neo_win.r2_production_validation import (
    check_forecast_population_matches_expected,
    check_ga4_present_exactly_once,
    check_monotonicity_from_source,
    check_no_excluded_status_players_in_forecast,
    check_no_fabricated_extra_rows,
    check_player_card_present_for_every_row,
    check_probabilities_render_exactly,
    check_win_sum_from_source,
)


def _fc_row(code, name="A", rank="1", score=140, top20=80.0, top10=50.0, top5=30.0, win=10.0):
    return {"player_code": code, "player_name": name, "r2_rank": rank, "r2_total_score": score,
            "top20_pct": top20, "top10_pct": top10, "top5_pct": top5, "win_pct": win}


def _eval_row(code, status="MADE_CUT"):
    return {"player_code": code, "player_name": "A", "actual_r2_status": status}


# ---------------------------------------------------------------
# check_forecast_population_matches_expected
# ---------------------------------------------------------------


def test_population_check_skips_when_no_expected_value():
    result = check_forecast_population_matches_expected([_fc_row("p1")], None)
    assert result["passed"] is True


def test_population_check_passes_when_matching():
    result = check_forecast_population_matches_expected([_fc_row("p1"), _fc_row("p2")], 2)
    assert result["passed"] is True


def test_population_check_fails_when_mismatched():
    result = check_forecast_population_matches_expected([_fc_row("p1")], 62)
    assert result["passed"] is False


# ---------------------------------------------------------------
# check_win_sum_from_source / check_monotonicity_from_source
# ---------------------------------------------------------------


def test_win_sum_passes_near_100():
    rows = [_fc_row("p1", win=60.0), _fc_row("p2", win=40.0)]
    assert check_win_sum_from_source(rows)["passed"] is True


def test_win_sum_fails_far_from_100():
    rows = [_fc_row("p1", win=1.0), _fc_row("p2", win=1.0)]
    assert check_win_sum_from_source(rows)["passed"] is False


def test_monotonicity_passes_for_valid_data():
    rows = [_fc_row("p1", win=10, top5=30, top10=50, top20=80)]
    assert check_monotonicity_from_source(rows)["passed"] is True


def test_monotonicity_fails_when_violated():
    rows = [_fc_row("p1", win=90, top5=30, top10=50, top20=80)]
    result = check_monotonicity_from_source(rows)
    assert result["passed"] is False
    assert "p1" in result["detail"]


# ---------------------------------------------------------------
# check_no_excluded_status_players_in_forecast
# ---------------------------------------------------------------


def test_no_excluded_players_passes_when_forecast_is_clean():
    forecast = [_fc_row("p1"), _fc_row("p2")]
    cut_eval = [_eval_row("p1", "MADE_CUT"), _eval_row("p2", "MADE_CUT"), _eval_row("p3", "WD_AFTER_R1_START")]
    assert check_no_excluded_status_players_in_forecast(forecast, cut_eval)["passed"] is True


def test_no_excluded_players_fails_if_wd_player_leaks_into_forecast():
    forecast = [_fc_row("p1"), _fc_row("p3")]  # p3 leaked
    cut_eval = [_eval_row("p1", "MADE_CUT"), _eval_row("p3", "WD_AFTER_R1_START")]
    result = check_no_excluded_status_players_in_forecast(forecast, cut_eval)
    assert result["passed"] is False
    assert "p3" in result["detail"]


def test_no_excluded_players_fails_if_missed_cut_player_leaks_into_forecast():
    forecast = [_fc_row("p1"), _fc_row("p4")]
    cut_eval = [_eval_row("p1", "MADE_CUT"), _eval_row("p4", "MISSED_CUT")]
    result = check_no_excluded_status_players_in_forecast(forecast, cut_eval)
    assert result["passed"] is False
    assert "p4" in result["detail"]


# ---------------------------------------------------------------
# check_probabilities_render_exactly / check_no_fabricated_extra_rows
# ---------------------------------------------------------------


def test_probabilities_render_exactly_passes_for_real_render():
    rows = [_fc_row("p1", top20=80.0, top10=50.0, top5=30.0, win=10.0)]
    html = render_r2_forecast_table_rows(rows, clickable=False)
    assert check_probabilities_render_exactly(rows, html)["passed"] is True


def test_probabilities_render_exactly_fails_if_a_value_is_altered():
    rows = [_fc_row("p1", top20=80.0, top10=50.0, top5=30.0, win=10.0)]
    html = render_r2_forecast_table_rows(rows, clickable=False)
    tampered_rows = [_fc_row("p1", top20=99.99, top10=50.0, top5=30.0, win=10.0)]
    result = check_probabilities_render_exactly(tampered_rows, html)
    assert result["passed"] is False


def test_no_fabricated_extra_rows_passes_for_real_render():
    rows = [_fc_row("p1"), _fc_row("p2")]
    html = render_r2_forecast_table_rows(rows, clickable=False)
    assert check_no_fabricated_extra_rows(rows, html)["passed"] is True


def test_no_fabricated_extra_rows_fails_if_html_has_extra_pct_cells():
    rows = [_fc_row("p1")]
    html = render_r2_forecast_table_rows(rows, clickable=False) + '<td class="c-pct">99.99%</td>'
    result = check_no_fabricated_extra_rows(rows, html)
    assert result["passed"] is False


# ---------------------------------------------------------------
# check_ga4_present_exactly_once / check_player_card_present_for_every_row
# ---------------------------------------------------------------


def test_ga4_check_passes_for_exactly_2_occurrences():
    html = "src=G-WVX07966WS ... gtag('config', 'G-WVX07966WS')"
    assert check_ga4_present_exactly_once(html)["passed"] is True


def test_ga4_check_fails_for_wrong_count():
    assert check_ga4_present_exactly_once("no ga4 here")["passed"] is False
    assert check_ga4_present_exactly_once("G-WVX07966WS " * 3)["passed"] is False


def test_player_card_present_check_passes_when_all_rows_have_a_card():
    rows = [_fc_row("p1"), _fc_row("p2")]
    html = 'data-player-code="p1" data-player-code="p2"'
    assert check_player_card_present_for_every_row(rows, html)["passed"] is True


def test_player_card_present_check_fails_when_a_row_is_missing_its_card():
    rows = [_fc_row("p1"), _fc_row("p2")]
    html = 'data-player-code="p1"'
    result = check_player_card_present_for_every_row(rows, html)
    assert result["passed"] is False
    assert "p2" in result["detail"]
