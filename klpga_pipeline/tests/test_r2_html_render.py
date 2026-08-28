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
    render_r1_model_scorecard_section,
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
