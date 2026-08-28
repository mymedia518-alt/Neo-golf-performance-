"""Tests for klpga.neo_win.r2_html_render — Sections H & I of the
R1->R2 evaluation pipeline. Pure string-rendering, synthetic data only
— never touches docs/index.html or the real R1 historical snapshot."""
from __future__ import annotations

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    calibration_report,
    summarize_cut_evaluation,
)
from klpga.neo_win.cut_evaluation import PlayerCutEvaluationRow
from klpga.neo_win.r1_r2_evaluation_report import top5_best_and_biggest_misses
from klpga.neo_win.r2_html_render import (
    R1_FROZEN_DISCLOSURE_SENTENCE,
    derive_score_to_par,
    render_r1_cut_headline_section,
    render_r1_model_scorecard_section,
    render_r2_forecast_page,
    render_r2_forecast_table_rows,
    render_r2_page,
    render_r2_table_rows,
)
from klpga.neo_win.round_condition_metadata import (
    build_r2_round_condition_metadata,
    round_condition_metadata_to_dict,
)
from klpga.neo_win.win_interim_check import PlayerWinInterimRow, win_interim_summary


def _cut_row(code, pct, outcome):
    return PlayerCutEvaluationRow(
        player_code=code, player_name=f"Player {code}", r1_rank=1, r1_score_to_par=-2.0,
        r1_make_cut_pct=pct, r2_outcome=outcome,
    )


def test_render_table_rows_formats_score_and_pct():
    entrants = [{"position": 1, "player_name": "A", "score_to_par": -3, "win_pct": 5.5, "make_cut_pct": 80.0}]
    html = render_r2_table_rows(entrants)
    assert '<td class="c-pos">1</td>' in html
    assert '<td class="c-name">A</td>' in html
    assert '<td class="c-score">-3</td>' in html
    assert '<td class="c-pct">5.50%</td>' in html
    assert '<td class="c-pct">80.00%</td>' in html


def test_render_table_rows_even_par_and_missing_values():
    entrants = [{"position": 2, "player_name": "B", "score_to_par": 0, "win_pct": None, "make_cut_pct": None}]
    html = render_r2_table_rows(entrants)
    assert '<td class="c-score">E</td>' in html
    assert '<td class="c-pct">unavailable</td>' in html


def test_scorecard_section_contains_all_required_headers():
    rows = [_cut_row("p1", 90.0, CUT_OUTCOME_MADE), _cut_row("p2", 10.0, CUT_OUTCOME_MISSED)]
    cut_summary = summarize_cut_evaluation(rows)
    calibration = calibration_report(rows)
    top5 = top5_best_and_biggest_misses(rows)
    win_rows = [PlayerWinInterimRow(player_code="p1", player_name="A", r1_win_rank=1, r1_win_pct=10.0, r2_leaderboard_position=1)]
    win_interim = win_interim_summary(win_rows)
    round_condition = round_condition_metadata_to_dict(build_r2_round_condition_metadata("2026080001"))

    html = render_r1_model_scorecard_section(cut_summary, calibration, top5, win_interim, round_condition)
    assert "NEO GOLF DATA — BETA #001 — R1 MODEL CHECK" in html
    assert "CUT PREDICTION" in html
    assert "CALIBRATION" in html
    assert "BEST PREDICTIONS" in html
    assert "BIGGEST MISSES" in html
    assert "R1 WIN% INTERIM CHECK" in html
    assert "ROUND CONDITION" in html
    assert R1_FROZEN_DISCLOSURE_SENTENCE in html
    assert win_interim["label"] in html
    assert "standing water beginning to appear" in html


def test_scorecard_handles_none_spearman_without_crashing():
    rows = [_cut_row("p1", 90.0, CUT_OUTCOME_MADE)]
    cut_summary = summarize_cut_evaluation(rows)
    calibration = calibration_report(rows)
    top5 = top5_best_and_biggest_misses(rows)
    win_rows = [PlayerWinInterimRow(player_code="p1", player_name="A", r1_win_rank=1, r1_win_pct=10.0, r2_leaderboard_position=None)]
    win_interim = win_interim_summary(win_rows)
    round_condition = round_condition_metadata_to_dict(build_r2_round_condition_metadata("2026080001"))
    html = render_r1_model_scorecard_section(cut_summary, calibration, top5, win_interim, round_condition)
    assert "N/A (fewer than 2 resolved players)" in html


def test_render_table_rows_clickable_false_by_default_unchanged():
    entrants = [{"position": 1, "player_name": "A", "score_to_par": -1, "win_pct": 1.0, "make_cut_pct": 50.0}]
    html = render_r2_table_rows(entrants)
    assert html == '<tr><td class="c-pos">1</td><td class="c-name">A</td><td class="c-score">-1</td><td class="c-pct">1.00%</td><td class="c-pct">50.00%</td></tr>'


def test_render_table_rows_clickable_true_wraps_name_in_button():
    entrants = [{"position": 1, "player_name": "A", "player_code": "p1", "score_to_par": -1, "win_pct": 1.0, "make_cut_pct": 50.0}]
    html = render_r2_table_rows(entrants, clickable=True)
    assert '<button type="button" class="player-name-btn"' in html
    assert 'data-player-code="p1"' in html
    assert ">A</button>" in html
    assert '<td class="c-pos">1</td>' in html  # other columns unaffected


def test_render_r2_page_player_card_assets_off_by_default():
    page = render_r2_page(tournament_name="T", status_pill_text="S", table_rows_html="", scorecard_html="")
    assert "player-card-trigger" not in page
    assert ".pc-backdrop" not in page


def test_render_r2_page_includes_player_card_assets_when_enabled():
    page = render_r2_page(
        tournament_name="T", status_pill_text="S", table_rows_html="", scorecard_html="",
        player_cards_html='<div class="player-card" id="player-card-p1">STUB CARD</div>',
        include_player_card_assets=True,
    )
    assert ".pc-backdrop" in page  # CSS injected
    assert "player-card-trigger" in page  # JS injected
    assert "STUB CARD" in page


def test_render_r2_page_includes_ga4_exactly_once_and_scorecard():
    table_html = render_r2_table_rows([{"position": 1, "player_name": "A", "score_to_par": -1, "win_pct": 1.0, "make_cut_pct": 50.0}])
    page = render_r2_page(
        tournament_name="Test Open", status_pill_text="Round 2 Complete",
        table_rows_html=table_html, scorecard_html="<section class=\"scorecard\">STUB</section>",
    )
    assert page.count("G-WVX07966WS") == 2  # script src + gtag config call, same convention as the real R1 page
    assert "<title>NEO R2 Tournament Prediction</title>" in page
    assert "STUB" in page
    assert "Test Open" in page
    assert "Round 2 Complete" in page


# ---------------------------------------------------------------
# render_r1_cut_headline_section — R2 FROZEN FORECAST's public headline
# ---------------------------------------------------------------


def _cut_summary(**overrides):
    base = {
        "n_evaluated": 110, "n_r1_players": 115, "actual_made_cut_count": 62, "actual_missed_cut_count": 48,
        "wd_count": 0, "wd_after_r1_start_count": 5, "dq_count": 0, "unresolved_count": 0,
        "threshold_accuracy_pct": 68.1818, "brier_score": 0.207404, "log_loss": 0.892103,
        "mean_predicted_cut_pct": 30.3664, "actual_cut_rate_pct": 56.3636,
    }
    base.update(overrides)
    return base


def test_headline_renders_all_survivors_phrasing_when_100pct():
    threshold_survival = {"threshold_pct": 40.0, "n_at_or_above": 35, "n_made_cut": 35}
    html = render_r1_cut_headline_section(_cut_summary(), threshold_survival, [])
    assert "NEO 첫 실전 검증" in html
    assert "1R 종료 후 공개한 컷 통과 확률, 실제 결과는?" in html
    assert "40% 이상으로 예측한 35명 → 35명 전원 컷 통과" in html
    assert "68.2%" in html
    assert "0.2074" in html
    assert "평균 예측 컷 통과 확률 30.4% / 실제 컷 통과율 56.4%" in html


def test_headline_renders_partial_survival_phrasing_when_not_100pct():
    threshold_survival = {"threshold_pct": 40.0, "n_at_or_above": 10, "n_made_cut": 7}
    html = render_r1_cut_headline_section(_cut_summary(), threshold_survival, [])
    assert "10명 → 7명 컷 통과" in html
    assert "전원" not in html


def test_headline_never_hides_the_worst_calibration_gap():
    calibration = [
        {"bucket": "0-20%", "n": 48, "avg_predicted_pct": 10.0, "actual_made_cut_rate_pct": 18.75, "calibration_gap_pct": 8.75},
        {"bucket": "40-60%", "n": 16, "avg_predicted_pct": 50.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 50.0},
    ]
    html = render_r1_cut_headline_section(_cut_summary(), {"threshold_pct": 40.0, "n_at_or_above": 0, "n_made_cut": 0}, calibration)
    assert "40-60%" in html  # the worse gap, not the smaller 0-20% one
    assert "50.0%p" in html or "+50.0%p" in html


# ---------------------------------------------------------------
# render_r2_forecast_table_rows / render_r2_forecast_page
# ---------------------------------------------------------------


def _forecast_row(code="p1", name="A", rank="1", score=140, top20=80.0, top10=50.0, top5=30.0, win=10.0):
    return {
        "player_code": code, "player_name": name, "r2_rank": rank, "r2_total_score": score,
        "top20_pct": top20, "top10_pct": top10, "top5_pct": top5, "win_pct": win,
    }


def test_forecast_table_rows_render_all_seven_columns_worth_of_data():
    html = render_r2_forecast_table_rows([_forecast_row()], clickable=False)
    assert "<td class=\"c-pos\">1</td>" in html
    assert "140" in html
    assert "80.00%" in html and "50.00%" in html and "30.00%" in html and "10.00%" in html


def test_forecast_table_rows_clickable_uses_player_name_cell():
    html = render_r2_forecast_table_rows([_forecast_row()], clickable=True)
    assert "player-card-trigger" in html or "button" in html.lower()


def test_forecast_table_rows_without_par_total_has_no_topar_column():
    html = render_r2_forecast_table_rows([_forecast_row(score=138)], clickable=False)
    assert "c-topar" not in html


def test_forecast_table_rows_with_par_total_adds_topar_column():
    html = render_r2_forecast_table_rows([_forecast_row(score=138)], clickable=False, par_total=144)
    assert '<td class="c-topar">-6</td>' in html


def test_forecast_table_rows_topar_even_par_renders_as_e():
    html = render_r2_forecast_table_rows([_forecast_row(score=144)], clickable=False, par_total=144)
    assert '<td class="c-topar">E</td>' in html


def test_forecast_table_rows_topar_over_par_renders_with_plus():
    html = render_r2_forecast_table_rows([_forecast_row(score=147)], clickable=False, par_total=144)
    assert '<td class="c-topar">+3</td>' in html


def test_forecast_table_rows_topar_missing_total_score_renders_unavailable():
    html = render_r2_forecast_table_rows([_forecast_row(score=None)], clickable=False, par_total=144)
    assert '<td class="c-topar">unavailable</td>' in html


def test_derive_score_to_par_pure_arithmetic():
    assert derive_score_to_par(138, 144) == -6
    assert derive_score_to_par(144, 144) == 0
    assert derive_score_to_par(147, 144) == 3
    assert derive_score_to_par(None, 144) is None
    assert derive_score_to_par(138, None) is None


def test_forecast_page_includes_headline_and_table_and_player_cards():
    headline = "<section class=\"headline\">STUB HEADLINE</section>"
    table = render_r2_forecast_table_rows([_forecast_row()], clickable=False)
    page = render_r2_forecast_page(
        tournament_name="Test Open", status_pill_text="2라운드 종료", headline_html=headline,
        table_rows_html=table, player_cards_html="<div>STUB CARD</div>", include_player_card_assets=True,
    )
    assert "STUB HEADLINE" in page
    assert "TOP20" in page and "TOP10" in page and "TOP5" in page and "WIN" in page
    assert "현재순위" in page
    assert "STUB CARD" in page
    assert "player-card-trigger" in page or "PLAYER_CARD" in page.upper()
    assert "Test Open" in page
    assert "2라운드 종료" in page
