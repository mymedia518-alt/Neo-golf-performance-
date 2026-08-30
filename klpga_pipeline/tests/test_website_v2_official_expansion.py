from __future__ import annotations

import json
from pathlib import Path

from klpga.website_v2.analytics import classify_hole_score, multi_line_chart_svg
from klpga.website_v2.official_data import parse_leaderboard_html, parse_sg_html, validate_sg_record

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "content" / "website_v2" / "kg_2026080001_official.json"
CANDIDATE = ROOT / "candidate" / "website-v2"


def test_official_dataset_complete_leaderboard_and_winner():
    data=json.loads(OFFICIAL.read_text(encoding="utf-8")); assert len(data["leaderboard"]) == 119
    winner=data["leaderboard"][0]; assert (winner["player"],winner["rounds"],winner["total"],winner["to_par"]) == ("신다인",[70,70,67,64],271,"-17")
    assert sum(row["status"]=="WD" for row in data["leaderboard"]) == 3
    assert any(row["tie"] and row["rank"].startswith("T") for row in data["leaderboard"])


def test_leaderboard_parser_preserves_tie_and_withdrawal():
    html='<div id="btnDetail" _playercode="1"><table><tr>'+''.join(f'<td>{x}</td>' for x in ['', 'T3','', '', '선수','-1','F','','70','70','70','70','280','',''])+'</tr></table></div>'
    row=parse_leaderboard_html(html)[0]; assert row["tie"] and row["rank_numeric"]==3


def test_sg_parser_scope_and_math():
    cells=['1','신다인','3.71 (1)','2.24 (6)','0.86 (9)','1.11 (15)','0.27 (23)','1.47 (6)','4']
    html='<div id="record-one"><table><tbody><tr>'+''.join(f'<td>{x}</td>' for x in cells)+'</tr></tbody></table></div>'
    row=parse_sg_html(html,scope="tournament_cumulative",round_number=None)[0]
    assert row["scope"]=="tournament_cumulative" and validate_sg_record(row)["total_within_tolerance"]


def test_exact_score_classification_does_not_fabricate_group_split():
    assert [classify_hole_score(2,4),classify_hole_score(3,4),classify_hole_score(4,4),classify_hole_score(5,4),classify_hole_score(6,4),classify_hole_score(7,4)] == ["Eagle","Birdie","Par","Bogey","Double Bogey","Triple Bogey+"]


def test_multi_player_chart_preserves_missing_points():
    svg=multi_line_chart_svg(title="trend",series_by_player={"A":[{"stage":"PRE","value":1.0},{"stage":"R1","value":None},{"stage":"R2","value":2.0}],"B":[{"stage":"PRE","value":2.0},{"stage":"R1","value":3.0},{"stage":"R2","value":4.0}]})
    assert 'data-chart-series' in svg and '"value":null' in svg and "PRE" in svg


def test_final_and_deep_dive_contracts_are_data_first_and_responsive():
    final=(CANDIDATE/"tournaments/2026/kg-ladies-open/final/index.html").read_text(encoding="utf-8")
    deep=(CANDIDATE/"deep-dive/index.html").read_text(encoding="utf-8")
    css=(CANDIDATE/"assets/neo-site.css").read_text(encoding="utf-8")
    assert "PRE 1.90%" in final and "SG 전체" in final and "공식 최종 리더보드" in final
    assert "LAYER A · NEO MODEL" in deep and "LAYER B · PERFORMANCE ANALYSIS" in deep
    assert "SG는 이 모델 버전의 입력이 아닙니다" in deep
    assert ".chart-scroll,.chart-full{width:100%;max-width:100%;overflow:visible}" in css
    assert "min-width:31rem" not in css and "min-width:29rem" not in css


def test_post_tournament_product_story_and_plain_language():
    home=(CANDIDATE/"index.html").read_text(encoding="utf-8")
    final=(CANDIDATE/"tournaments/2026/kg-ladies-open/final/index.html").read_text(encoding="utf-8")
    about=(CANDIDATE/"about/index.html").read_text(encoding="utf-8")
    assert "신다인은 어떻게" in home and "271 (-17)" in home and "FINAL 분석 보기" in home
    for level in ("FINAL · 결과","JOURNEY","WHY · 대회 누적 경기력","PERFORMANCE · FINAL 라운드","NEXT · 앞으로 무엇을 볼까?"):
        assert level in final
    assert "SG</b>는 다른 선수들과 비교" in final and "+는 벌고, −는 잃었다는 뜻" in final
    assert "확률과 실제 결과는 같은 개념이 아닙니다" in final
    assert "한 대회로 영구적인 강점이나 약점을 정하지 않습니다" in final
    assert all(term not in (home+final).lower() for term in ("bet ","odds","lock","guaranteed winner","payout"))
    assert "맞히는 것보다" in about


def test_performance_direction_requires_multi_event_thresholds():
    final=(CANDIDATE/"tournaments/2026/kg-ladies-open/final/index.html").read_text(encoding="utf-8")
    for label in ("5개 대회","10개 대회","시즌","장기"):
        assert label in final
    assert "퍼팅이 약점이다" not in final and "티샷이 약점이다" not in final


def test_deep_dive_shows_model_performance_and_hole_composition_layers():
    deep=(CANDIDATE/"deep-dive/index.html").read_text(encoding="utf-8")
    assert "R3 공동선두 4명의 우승확률 변화" in deep and "R3까지 스코어 구성" in deep
    assert "SG는 이 모델 버전의 입력이 아닙니다" in deep
    assert "KLPGA 공식 R3 단일 라운드 SG" in deep
