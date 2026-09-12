"""R3 HOUSE: klpga.neo_win.r3_real_page -- the real-data R3 renderer.
Every fixture ISOLATED and SYNTHETIC, mirroring test_r2_real_page.py's
own established discipline one round later."""
from __future__ import annotations

import re

import pytest

from klpga.neo_win.r3_real_page import is_real_page, render_r3_real_page
from klpga.neo_win.r3_wait_page import is_wait_page, render_r3_wait_page

GAME_CODE = "TEST0003"
TOURNAMENT_NAME = "SYNTHETIC R3 TEST OPEN"


def _fixture_html(*, records, forecast_records=None, sponsor_by_id=None):
    return render_r3_real_page(
        tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE, date_range="2026.01.01 — 01.04",
        r3_freeze={"records": records}, forecast={"records": forecast_records or []},
        sponsor_by_id=sponsor_by_id or {},
    )


def _rows(html: str) -> list[str]:
    return re.findall(r"<tr[^>]*>(?:(?!</tr>).)*</tr>", html.split("<tbody>", 1)[1].split("</tbody>", 1)[0])


def test_header_carries_the_exact_8_column_contract_win_last_no_sg():
    html = _fixture_html(records=[])
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == ["순위", "선수", "합계", "3R", "Top20", "Top10", "Top5", "우승"]
    assert "SG" not in html


def test_header_groups_r3_outcome_and_r2_prediction_separately():
    """R3 FINAL WEB DRY-RUN task: any R2 probability shown on R3's page
    must be visually grouped/labeled as historical prediction, never
    mixed with R3's own real outcome columns."""
    html = _fixture_html(records=[])
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    assert '<th colspan="4">R3 결과 (공식)</th>' in header
    assert '<th colspan="4">R2 종료 후 예측</th>' in header


def test_uses_the_established_house_leaderboard_class():
    html = _fixture_html(records=[])
    assert "leaderboard-table leaderboard-table--r2-full" in html


def test_row_count_is_the_advancing_subset_not_the_full_freeze():
    records = [
        {"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -1, "r2_score_to_par": -1, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "선수이", "status": "WD", "r1_score_to_par": 1, "r2_score_to_par": 0, "r3_score_to_par": None},
    ]
    html = _fixture_html(records=records)
    rows = _rows(html)
    assert len(rows) == 1
    assert "선수일" in html
    assert "선수이" not in html


@pytest.mark.parametrize("status", ["WD", "DQ", "DNS"])
def test_non_active_status_excluded_from_main_table(status):
    records = [{"player_id": "p1", "player_name": "선수일", "status": status, "r1_score_to_par": 1, "r2_score_to_par": 1, "r3_score_to_par": None}]
    html = _fixture_html(records=records)
    assert len(_rows(html)) == 0
    assert "선수일" not in html


def test_active_status_shows_no_badge():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _fixture_html(records=records)
    assert "status-badge" not in html


def test_total_is_the_real_sum_of_r1_r2_r3_never_a_precomputed_field():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2, "r3_score_to_par": 1}]
    html = _fixture_html(records=records)
    row = _rows(html)[0]
    assert "data-label='합계'>-6<" in row  # -5-2+1 = -6
    assert "data-label='3R'>+1<" in row


def test_missing_r3_score_renders_empty_mark_never_zero():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2, "r3_score_to_par": None}]
    html = _fixture_html(records=records)
    row = _rows(html)[0]
    assert "data-label='3R'>—<" in row
    assert "data-label='합계'>—<" in row  # total needs all three, never half-computed
    assert "data-label='순위'>—<" in row  # no rank without a real, complete total


def test_ranking_ascending_ties_share_rank():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": 0, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": 0, "r3_score_to_par": 0},
        {"player_id": "p3", "player_name": "C", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0},
    ]
    html = _fixture_html(records=records)
    rows = _rows(html)
    assert "data-label='순위'>T1<" in rows[0]
    assert "data-label='순위'>T1<" in rows[1]
    assert "data-label='순위'>3<" in rows[2]


def test_forecast_probabilities_render_win_last():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    forecast_records = [{"player_id": "p1", "win_pct": 12.5, "top5_pct": 40.0, "top10_pct": 60.0, "top20_pct": 80.0}]
    html = _fixture_html(records=records, forecast_records=forecast_records)
    row = _rows(html)[0]
    assert "class='win' data-label='우승'>12.5%<" in row
    last_cell_label = re.findall(r"<td[^>]*data-label='([^']+)'", row)[-1]
    assert last_cell_label == "우승"


def test_player_missing_from_forecast_gets_empty_mark():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _fixture_html(records=records, forecast_records=[])
    row = _rows(html)[0]
    for label in ("우승", "Top5", "Top10", "Top20"):
        assert f"data-label='{label}'>—<" in row


def test_sponsor_slot_present_for_every_row_even_when_unknown():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _fixture_html(records=records, sponsor_by_id={})
    assert html.count("class='player-name'") == 1
    assert html.count("class='player-sponsor'") == 1
    assert re.search(r"class='player-sponsor'></span>", html)


def test_sponsor_shown_when_known():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _fixture_html(records=records, sponsor_by_id={"p1": "SYNTH SPONSOR CO"})
    assert "SYNTH SPONSOR CO" in html


def test_footer_reports_the_real_advancing_count():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "WD", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": None},
    ]
    html = _fixture_html(records=records)
    assert "총 1명" in html


def test_stage_nav_pre_r1_r2_clickable_r3_current_final_disabled():
    html = _fixture_html(records=[])
    assert f'href="/tournaments/2026/{GAME_CODE}/pre/"' in html
    assert f'href="/tournaments/2026/{GAME_CODE}/r1/"' in html
    assert f'href="/tournaments/2026/{GAME_CODE}/r2/"' in html
    assert f'href="/tournaments/2026/{GAME_CODE}/r3/" aria-current="page"' in html
    assert html.count('class="stage-nav__disabled"') == 1  # FINAL only


def test_breadcrumb_present_with_r3_as_current_stage():
    html = _fixture_html(records=[])
    assert '<nav class="breadcrumb"' in html
    assert '<span aria-current="page">R3</span>' in html


def test_real_page_never_mistaken_for_wait_page():
    real_html = _fixture_html(records=[{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}])
    wait_html = render_r3_wait_page(tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE)
    assert is_real_page(real_html) is True
    assert is_wait_page(real_html) is False
    assert is_real_page(wait_html) is False
    assert is_wait_page(wait_html) is True
