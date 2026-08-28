"""Tests for klpga.neo_win.player_card — the Korean-first mobile
player card MVP. Covers the "never show a future cut probability once
decided" rule, "never fabricate a missing probability-history stage",
the why_text stage restriction, and the clickable name cell."""
from __future__ import annotations

import pytest

from klpga.neo_win.cut_evaluation import CUT_OUTCOME_DQ, CUT_OUTCOME_MADE, CUT_OUTCOME_MISSED, CUT_OUTCOME_WD
from klpga.neo_win.player_card import (
    CUT_STATUS_PENDING,
    PlayerCardData,
    ProbabilityHistoryPoint,
    RoundScoreRow,
    build_why_text,
    render_player_card_html,
    render_player_card_js,
    render_player_name_cell,
)


def _card(**overrides):
    defaults = dict(
        player_code="p1", player_name="홍길동", tournament_name="테스트 오픈", stage_display="2라운드",
    )
    defaults.update(overrides)
    return PlayerCardData(**defaults)


# ---------------------------------------------------------------
# build_why_text — only the two approved stages
# ---------------------------------------------------------------


def test_why_text_r1_matches_exact_spec_wording():
    text = build_why_text("R1")
    assert "대회 이전 경기력과 1라운드 실제 결과" in text
    assert "시뮬레이션한 우승 확률입니다" in text


def test_why_text_r2_matches_exact_spec_wording():
    text = build_why_text("R2")
    assert "1·2라운드 실제 결과" in text


def test_why_text_unsupported_stage_raises_never_invents():
    with pytest.raises(ValueError):
        build_why_text("PRE")
    with pytest.raises(ValueError):
        build_why_text("R3")
    with pytest.raises(ValueError):
        build_why_text("FINAL")


# ---------------------------------------------------------------
# Cut status — never a future probability once decided
# ---------------------------------------------------------------


def test_cut_pending_shows_probability():
    html = render_player_card_html(_card(win_pct=3.2, cut_status=CUT_STATUS_PENDING, cut_pct=62.42))
    assert "62.42%" in html
    assert "컷 통과 확률" in html


def test_cut_made_shows_checkmark_never_probability_even_if_cut_pct_supplied():
    html = render_player_card_html(_card(win_pct=4.8, cut_status=CUT_OUTCOME_MADE, cut_pct=99.9))
    assert "컷 통과 ✓" in html
    assert "99.9" not in html  # the stale probability must never leak through


def test_cut_missed_shows_missed_label():
    html = render_player_card_html(_card(cut_status=CUT_OUTCOME_MISSED, cut_pct=12.0))
    assert "컷 탈락" in html
    assert "12.0" not in html


def test_cut_wd_shows_withdrawn_label():
    html = render_player_card_html(_card(cut_status=CUT_OUTCOME_WD))
    assert "기권 (WD)" in html


def test_cut_dq_shows_disqualified_label():
    html = render_player_card_html(_card(cut_status=CUT_OUTCOME_DQ))
    assert "실격 (DQ)" in html


def test_cut_pending_with_no_cut_pct_renders_nothing_never_fabricates():
    html = render_player_card_html(_card(win_pct=3.2, cut_status=CUT_STATUS_PENDING, cut_pct=None))
    assert "컷 통과 확률" not in html


# ---------------------------------------------------------------
# Probability history — never fabricates a missing stage
# ---------------------------------------------------------------


def test_probability_history_renders_only_supplied_stages():
    data = _card(
        win_pct=4.8,
        probability_history=(
            ProbabilityHistoryPoint("PRE", 2.7),
            ProbabilityHistoryPoint("R1", 3.2),
            ProbabilityHistoryPoint("R2", 4.8),
        ),
    )
    html = render_player_card_html(data)
    assert "대회 전 → 1R → 2R" in html
    assert "2.70% → 3.20% → 4.80%" in html


def test_probability_history_two_stages_only_never_shows_r2_before_it_exists():
    data = _card(win_pct=3.2, probability_history=(ProbabilityHistoryPoint("PRE", 2.7), ProbabilityHistoryPoint("R1", 3.2)))
    html = render_player_card_html(data)
    assert "대회 전 → 1R" in html
    assert "R2" not in html


def test_win_probability_delta_is_percentage_points_not_percent_change():
    data = _card(
        win_pct=4.8,
        probability_history=(ProbabilityHistoryPoint("R1", 3.2), ProbabilityHistoryPoint("R2", 4.8)),
    )
    html = render_player_card_html(data)
    assert "▲ +1.60%p" in html
    assert "1R 종료 후 3.20%" in html


def test_win_probability_negative_delta_shows_down_arrow():
    data = _card(
        win_pct=2.0,
        probability_history=(ProbabilityHistoryPoint("R1", 3.2), ProbabilityHistoryPoint("R2", 2.0)),
    )
    html = render_player_card_html(data)
    assert "▼ -1.20%p" in html


def test_no_history_renders_no_history_section():
    html = render_player_card_html(_card(win_pct=5.0))
    assert "우승 확률 변화" not in html


# ---------------------------------------------------------------
# Missing metrics are omitted, never shown as fabricated defaults
# ---------------------------------------------------------------


def test_missing_sample_size_omits_data_sample_and_historical_rounds_row():
    html = render_player_card_html(_card(sample_size_rounds=None, expected_round_score=-0.95, consistency_stddev=2.6))
    assert "데이터 표본" not in html
    assert "과거 데이터" not in html
    assert "예상 라운드 성적" in html  # the fields that ARE present still render


def test_all_player_data_fields_present():
    html = render_player_card_html(_card(sample_size_rounds=296, expected_round_score=-0.95, consistency_stddev=2.6))
    assert "296라운드" in html
    assert "-0.95" in html
    assert "2.60" in html
    assert "데이터 표본" in html


def test_missing_round_scores_omits_tournament_result_section():
    html = render_player_card_html(_card())
    assert "이번 대회 성적" not in html


def test_total_strokes_none_leaves_current_position_block_unchanged():
    html_without = render_player_card_html(_card(current_position="1", current_score_to_par=-9))
    html_with_default = render_player_card_html(_card(current_position="1", current_score_to_par=-9, total_strokes=None))
    assert html_without == html_with_default
    assert "합계타수" not in html_without


def test_total_strokes_present_adds_score_summary_field():
    html = render_player_card_html(_card(current_position="1", current_score_to_par=-9, total_strokes=135))
    assert "합계타수" in html
    assert '<span class="pc-value">135</span>' in html
    assert '<span class="pc-value">-9</span>' in html


def test_total_strokes_alone_renders_current_position_block():
    html = render_player_card_html(_card(total_strokes=138))
    assert "합계타수" in html
    assert '<span class="pc-value">138</span>' in html


def test_round_scores_and_total_render():
    data = _card(
        round_scores=(RoundScoreRow(1, 69, -3), RoundScoreRow(2, 71, -1)),
        total_score_to_par=-4,
    )
    html = render_player_card_html(data)
    assert "<td>1R</td><td>69</td><td>-3</td>" in html
    assert "<td>2R</td><td>71</td><td>-1</td>" in html
    assert "합계" in html
    assert "<td>-4</td>" in html


# ---------------------------------------------------------------
# Brand + structure
# ---------------------------------------------------------------


def test_brand_name_never_translated():
    html = render_player_card_html(_card())
    assert "NEO GOLF DATA" in html


def test_card_id_and_data_attribute_keyed_by_player_code():
    html = render_player_card_html(_card(player_code="p42"))
    assert 'id="player-card-p42"' in html
    assert 'data-player-code="p42"' in html


def test_card_carries_tournament_id_and_stage_for_ga4_event():
    html = render_player_card_html(_card(tournament_id="2026080001", stage="R2"))
    assert 'data-tournament-id="2026080001"' in html
    assert 'data-stage="R2"' in html


def test_readable_without_javascript_player_name_is_plain_text_content():
    html = render_player_card_html(_card(player_name="박현경"))
    assert "박현경" in html
    assert "hidden" in html  # still present in the DOM, just hidden pre-JS-toggle — never conditionally rendered


# ---------------------------------------------------------------
# render_player_name_cell — clickable name, accessible fallback
# ---------------------------------------------------------------


def test_render_player_name_cell_is_a_real_button_with_player_code():
    html = render_player_name_cell("p7", "이서윤4")
    assert html == (
        '<td class="c-name"><button type="button" class="player-name-btn" '
        'data-player-card-trigger data-player-code="p7">이서윤4</button></td>'
    )


def test_render_player_name_cell_readable_text_survives_without_js():
    html = render_player_name_cell("p1", "김민주")
    assert "김민주" in html  # plain text content, not injected via JS


# ---------------------------------------------------------------
# GA4 event JS — exact parameter list, no probability, guarded by gtag
# ---------------------------------------------------------------


def test_ga4_js_includes_required_params_only_no_probability():
    js = render_player_card_js(ga4_enabled=True)
    assert "player_card_open" in js
    assert "player_code" in js
    assert "player_name" in js
    assert "tournament_id" in js
    assert "stage" in js
    assert "win_pct" not in js
    assert "probability" not in js.lower()


def test_ga4_js_guarded_by_gtag_existence_check():
    js = render_player_card_js(ga4_enabled=True)
    assert "typeof gtag === 'function'" in js


def test_ga4_disabled_omits_event_dispatch():
    js = render_player_card_js(ga4_enabled=False)
    assert "player_card_open" not in js
