"""Tests for klpga.neo_win.r2_production_page — the R2 PRODUCTION
DEPLOYMENT page renderer. Pure string rendering, synthetic data only.
Never touches docs/index.html or the real R1 historical snapshot."""
from __future__ import annotations

from klpga.neo_win.r2_production_page import (
    PRODUCTION_CSS,
    render_calibration_section,
    render_production_hero_section,
    render_production_page,
    render_r2_forecast_section,
    render_r2_forecast_table_rows,
)


def _cut_summary(**overrides):
    base = {
        "n_evaluated": 110, "n_r1_players": 115, "actual_made_cut_count": 62, "actual_missed_cut_count": 48,
        "threshold_accuracy_pct": 68.1818, "brier_score": 0.207404, "log_loss": 0.892103,
        "mean_predicted_cut_pct": 30.3664, "actual_cut_rate_pct": 56.3636,
    }
    base.update(overrides)
    return base


def _calibration():
    return [
        {"bucket": "0-20%", "n": 48, "made_cut_count": 9, "avg_predicted_pct": 10.0, "actual_made_cut_rate_pct": 18.75, "calibration_gap_pct": 8.75},
        {"bucket": "20-40%", "n": 27, "made_cut_count": 18, "avg_predicted_pct": 30.0, "actual_made_cut_rate_pct": 66.67, "calibration_gap_pct": 36.67},
        {"bucket": "40-60%", "n": 16, "made_cut_count": 16, "avg_predicted_pct": 50.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 50.0},
        {"bucket": "60-80%", "n": 12, "made_cut_count": 12, "avg_predicted_pct": 70.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 30.0},
        {"bucket": "80-100%", "n": 7, "made_cut_count": 7, "avg_predicted_pct": 90.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 10.0},
    ]


def _forecast_row(code="p1", name="A", rank="1", score=140, top20=80.0, top10=50.0, top5=30.0, win=10.0):
    return {"player_code": code, "player_name": name, "r2_rank": rank, "r2_total_score": score,
            "top20_pct": top20, "top10_pct": top10, "top5_pct": top5, "win_pct": win}


# ---------------------------------------------------------------
# render_production_hero_section — exact required Korean text
# ---------------------------------------------------------------


def test_hero_renders_exact_required_text():
    threshold_survival = {"threshold_pct": 40.0, "n_at_or_above": 35, "n_made_cut": 35}
    html = render_production_hero_section(_cut_summary(), threshold_survival, _calibration())
    assert "NEO 첫 실전 검증" in html
    assert "1R 종료 후 공개한 컷 통과 확률, 실제 결과는?" in html
    assert "40% 이상으로 예측한 35명" in html
    assert "35명 전원 컷 통과" in html
    assert "평가 대상 110명" in html
    assert "50% 기준 분류 정확도 68.2%" in html
    assert "Brier Score 0.2074" in html
    assert "평균 예측 30.4% | 실제 컷 통과율 56.4%" in html
    assert "높은 확률을 부여한 선수들의 생존은 잘 포착했지만, 전체적으로 컷 통과 가능성을 낮게 평가했다." in html
    assert "BETA #001에서 확인된 첫 번째 개선 과제다." in html


def test_hero_partial_survival_phrasing():
    threshold_survival = {"threshold_pct": 40.0, "n_at_or_above": 10, "n_made_cut": 6}
    html = render_production_hero_section(_cut_summary(), threshold_survival, [])
    assert "10명" in html and "6명 컷 통과" in html
    assert "전원" not in html


# ---------------------------------------------------------------
# render_calibration_section
# ---------------------------------------------------------------


def test_calibration_section_renders_all_buckets_and_title():
    html = render_calibration_section(_calibration())
    assert "예측 확률별 실제 컷 통과율" in html
    for bucket in ("0-20%", "20-40%", "40-60%", "60-80%", "80-100%"):
        assert bucket in html
    assert "66.7%" in html  # real 20-40% actual rate


def test_calibration_section_highlights_buckets_at_or_above_threshold():
    html = render_calibration_section(_calibration(), highlight_threshold_pct=40.0)
    assert 'class="cal-bucket-highlight"' in html
    # the 40-60/60-80/80-100 rows should be highlighted, 0-20/20-40 should not
    assert html.count('class="cal-bucket-highlight"') == 3


# ---------------------------------------------------------------
# render_r2_forecast_section
# ---------------------------------------------------------------


def test_forecast_section_has_required_title_subtitle_and_columns():
    table_html = render_r2_forecast_table_rows([_forecast_row()], clickable=False)
    html = render_r2_forecast_section(table_html)
    assert "2R 종료 후 우승 경쟁 예측" in html
    assert "3R 시작 전 동결된 예측입니다. 이후 결과에 따라 수정하지 않습니다." in html
    assert "현재 순위" in html
    assert all(col in html for col in ("TOP20", "TOP10", "TOP5", "WIN"))


# ---------------------------------------------------------------
# render_production_page — full page
# ---------------------------------------------------------------


def test_production_page_includes_all_sections_ga4_once_and_player_cards():
    threshold_survival = {"threshold_pct": 40.0, "n_at_or_above": 35, "n_made_cut": 35}
    hero = render_production_hero_section(_cut_summary(), threshold_survival, _calibration())
    calibration = render_calibration_section(_calibration())
    table_html = render_r2_forecast_table_rows([_forecast_row()], clickable=False)
    forecast_section = render_r2_forecast_section(table_html)

    page = render_production_page(
        tournament_name="제15회 KG 레이디스 오픈", status_pill_text="Round 2 Complete",
        hero_html=hero, calibration_html=calibration, forecast_section_html=forecast_section,
        player_cards_html="<div>STUB CARD</div>", include_player_card_assets=True,
    )
    assert page.count("G-WVX07966WS") == 2
    assert "NEO 첫 실전 검증" in page
    assert "예측 확률별 실제 컷 통과율" in page
    assert "2R 종료 후 우승 경쟁 예측" in page
    assert "STUB CARD" in page
    assert "player-card-trigger" in page or "PLAYER_CARD" in page.upper()
    assert "제15회 KG 레이디스 오픈" in page


def test_production_css_uses_a_brighter_navy_not_pure_black():
    """The visual-direction requirement: deep navy/charcoal, not the
    R1 page's near-black #0b0d10."""
    assert "#0b0d10" not in PRODUCTION_CSS
    assert "--bg:" in PRODUCTION_CSS
