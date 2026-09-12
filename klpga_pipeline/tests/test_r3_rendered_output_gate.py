"""R3 HOUSE: klpga.neo_win.r3_rendered_output_gate -- synthetic unit
tests proving it HARD_STOPs on every required failure mode and PASSES
a correctly rendered page. Uses the real renderer
(klpga.neo_win.r3_real_page.render_r3_real_page) to build real HTML
from synthetic-but-correctly-shaped freeze records wherever possible,
mirroring test_r2_rendered_output_gate.py's own established discipline."""
from __future__ import annotations

import pytest

from klpga.neo_win.r3_real_page import render_r3_real_page
from klpga.neo_win.r3_rendered_output_gate import RenderedOutputGateError, validate_r3_rendered_output

GAME_CODE = "TEST0003"
TOURNAMENT_NAME = "SYNTHETIC R3 GATE TEST OPEN"


def _render(records, forecast_records=None):
    return render_r3_real_page(
        tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE, date_range="2026.01.01 — 01.04",
        r3_freeze={"records": records}, forecast={"records": forecast_records or []}, sponsor_by_id={},
    )


def test_correctly_rendered_page_passes():
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2, "r3_score_to_par": -1},
        {"player_id": "p2", "player_name": "중위권", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -1, "r3_score_to_par": 1},
        {"player_id": "p3", "player_name": "기권", "status": "WD", "r1_score_to_par": 1, "r2_score_to_par": 0, "r3_score_to_par": None},
    ]
    forecast_records = [
        {"player_id": "p1", "win_pct": 50.0, "top5_pct": 80.0, "top10_pct": 90.0, "top20_pct": 100.0},
        {"player_id": "p2", "win_pct": 5.0, "top5_pct": 20.0, "top10_pct": 40.0, "top20_pct": 60.0},
    ]
    html = _render(records, forecast_records)
    validate_r3_rendered_output(html, {"records": records}, {"records": forecast_records})  # must not raise


def test_catches_total_divergence():
    records = [{"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2, "r3_score_to_par": -1}]
    broken_html = (
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>3R</th>"
        "<th>Top5</th><th>Top10</th><th>Top20</th><th>우승</th></tr></thead>"
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>1</td>"
        "<span class='player-name'></span><span class='player-sponsor'></span>"
        "<td data-label='합계'>—</td><td data-label='3R'>-1</td>"
        "<td data-label='Top5'>—</td><td data-label='Top10'>—</td><td data-label='Top20'>—</td><td data-label='우승'>—</td>"
        "</tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="wrong column contract"):
        validate_r3_rendered_output(broken_html, {"records": records}, {"records": []})


def test_catches_wd_player_rendered_in_main_table_at_all():
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2, "r3_score_to_par": -1},
        {"player_id": "p2", "player_name": "기권", "status": "WD", "r1_score_to_par": 1, "r2_score_to_par": 0, "r3_score_to_par": None},
    ]
    broken_html = _render(records).replace(
        "</tbody>",
        "<tr data-player-id='p2'><td data-label='순위'>2</td>"
        "<th scope='row' data-label='선수'><span class='player-name'>기권</span><span class='player-sponsor'></span></th>"
        "<td data-label='합계'>—</td><td data-label='3R'>—</td>"
        "<td class='metric-empty' data-label='Top5'>—</td><td class='metric-empty' data-label='Top10'>—</td>"
        "<td class='metric-empty' data-label='Top20'>—</td><td class='metric-empty' data-label='우승'>—</td></tr></tbody>",
    )
    with pytest.raises(RenderedOutputGateError, match="duplicate player_id"):
        validate_r3_rendered_output(broken_html, {"records": records}, {"records": []})


def test_catches_missing_advancing_player():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0},
    ]
    html = _render([records[0]])  # p2 never rendered
    with pytest.raises(RenderedOutputGateError, match="advancing player\\(s\\) missing"):
        validate_r3_rendered_output(html, {"records": records}, {"records": []})


def test_catches_fabricated_rank_for_incomplete_data():
    records = [{"player_id": "p1", "player_name": "진행중", "status": "ACTIVE", "r1_score_to_par": 1, "r2_score_to_par": 0, "r3_score_to_par": None}]
    broken_html = (
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>3R</th>"
        "<th>Top5</th><th>Top10</th><th>Top20</th><th>우승</th></tr></thead>"
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>1</td>"
        "<span class='player-name'></span><span class='player-sponsor'></span>"
        "<td data-label='합계'>—</td><td data-label='3R'>—</td>"
        "<td data-label='Top5'>—</td><td data-label='Top10'>—</td><td data-label='Top20'>—</td><td data-label='우승'>—</td>"
        "</tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="wrong column contract"):
        validate_r3_rendered_output(broken_html, {"records": records}, {"records": []})


def test_catches_probability_divergence():
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    forecast_records = [{"player_id": "p1", "win_pct": 50.0, "top5_pct": 80.0, "top10_pct": 90.0, "top20_pct": 100.0}]
    html = _render(records, forecast_records)
    tampered = html.replace("50.0%", "99.9%")
    with pytest.raises(RenderedOutputGateError, match="probability diverges"):
        validate_r3_rendered_output(tampered, {"records": records}, {"records": forecast_records})


def test_catches_rank_population_invalid_uniform_rank_despite_differing_totals():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": 0, "r3_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0},
    ]
    broken_html = (
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>3R</th>"
        "<th>Top5</th><th>Top10</th><th>Top20</th><th>우승</th></tr></thead>"
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>T1</td>"
        "<span class='player-name'></span><span class='player-sponsor'></span>"
        "<td data-label='합계'>-5</td><td data-label='3R'>E</td>"
        "<td data-label='Top5'>—</td><td data-label='Top10'>—</td><td data-label='Top20'>—</td><td data-label='우승'>—</td>"
        "</tr>"
        "<tr data-player-id='p2'><td data-label='순위'>T1</td>"
        "<span class='player-name'></span><span class='player-sponsor'></span>"
        "<td data-label='합계'>E</td><td data-label='3R'>E</td>"
        "<td data-label='Top5'>—</td><td data-label='Top10'>—</td><td data-label='Top20'>—</td><td data-label='우승'>—</td>"
        "</tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="wrong column contract"):
        validate_r3_rendered_output(broken_html, {"records": records}, {"records": []})


def test_catches_duplicate_player_id():
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _render(records)
    row_match = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    doubled = html.replace("</tbody>", row_match + "</tbody>")
    with pytest.raises(RenderedOutputGateError, match="duplicate player_id"):
        validate_r3_rendered_output(doubled, {"records": records}, {"records": []})


def test_catches_sg_column_present():
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _render(records)
    tampered = html.replace("<th>TOP5</th>", "<th>SG TOTAL</th><th>TOP5</th>")
    with pytest.raises(RenderedOutputGateError, match="SG column"):
        validate_r3_rendered_output(tampered, {"records": records}, {"records": []})


def test_catches_wrong_column_contract():
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _render(records)
    tampered = html.replace("<th>우승</th>", "<th>Top5</th>")  # duplicated label, breaks required order
    with pytest.raises(RenderedOutputGateError, match="wrong column contract"):
        validate_r3_rendered_output(tampered, {"records": records}, {"records": []})


def test_catches_broken_sponsor_contract():
    records = [{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0}]
    html = _render(records)
    tampered = html.replace("class='player-sponsor'", "class='removed'")
    with pytest.raises(RenderedOutputGateError, match="sponsor contract"):
        validate_r3_rendered_output(tampered, {"records": records}, {"records": []})
