from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from klpga.evidence import load_and_verify_manifest
from klpga.website_v2 import build_beta001_candidate

REPO_ROOT=Path(__file__).resolve().parents[2]
PIPELINE_ROOT=REPO_ROOT/"klpga_pipeline"
CONTENT=PIPELINE_ROOT/"content/website_v2/beta001.json"
AVAILABILITY=PIPELINE_ROOT/"content/website_v2/beta001_availability.json"
MANIFEST=PIPELINE_ROOT/"evidence/beta001/manifest.json"


@pytest.fixture()
def candidate(tmp_path: Path) -> Path:
    build_beta001_candidate(CONTENT,MANIFEST,REPO_ROOT,tmp_path)
    return tmp_path


def pages(root: Path):
    return [p for p in root.rglob("index.html") if "protected" not in p.parts]


def test_data_availability_matrix_is_machine_readable_and_omits_missing_modules(candidate):
    matrix=json.loads(AVAILABILITY.read_text(encoding="utf-8"))
    assert matrix["stage_forecast"]["r3_win_probability"] is True
    assert matrix["hole_by_hole"]["available"] is False
    assert set(matrix["omitted_modules"]) == {"hole difficulty chart","hole score distribution","tournament score composition","player score composition"}
    assert json.loads((candidate/"data/availability.json").read_text(encoding="utf-8")) == matrix


def test_required_routes_and_korean_global_navigation(candidate):
    required=["","tournaments","predictions","deep-dive","about"]+[f"tournaments/2026/kg-ladies-open/{s}" for s in ("","pre","r1","r2","r3","final")]
    assert all((candidate/r/"index.html").is_file() for r in required)
    for page in pages(candidate):
        html=page.read_text(encoding="utf-8")
        for label in ("홈","대회","예측 기록","DEEP DIVE","NEO 소개"): assert label in html
        assert '<a class="wordmark" href="/"' in html


def test_all_tournament_stages_and_final_are_always_discoverable(candidate):
    root=candidate/"tournaments/2026/kg-ladies-open"
    for page in root.rglob("index.html"):
        html=page.read_text(encoding="utf-8")
        labels=re.findall(r'class="stage-nav__(?:link|disabled)"[^>]*>([^<]+)<',html)
        assert labels == ["개요","PRE","R1","R2","R3","FINAL"]


def test_home_is_dense_data_hub_not_marketing_or_beta(candidate):
    html=(candidate/"index.html").read_text(encoding="utf-8")
    for value in ("결과가 나오기 전","최근 대회","최근 데이터","R3 주요 우승 확률","15.04%","11.56%","8.40%","7.47%","가장 큰 상승","가장 큰 하락"):
        assert value in html
    assert "BETA #001" not in html and "LATEST TOURNAMENT" not in html and "OFFICIAL WINNER" not in html
    assert "<table" not in html


def test_overview_is_forecast_to_result_command_center(candidate):
    html=(candidate/"tournaments/2026/kg-ladies-open/index.html").read_text(encoding="utf-8")
    for value in ("써닝포인트","PAR 72","예측 → 실제 결과","신다인","7.47%","271 (-17)","70 · 70 · 67 · 64","R3 예측 보기","FINAL 분석 보기"):
        assert value in html
    assert "우승자 지목이 아니라" in html


def test_shared_native_forecast_template_watch_and_evidence(candidate):
    root=candidate/"tournaments/2026/kg-ladies-open"
    for stage in ("r1","r2","r3"):
        html=(root/stage/"index.html").read_text(encoding="utf-8")
        assert "NEO WATCH" in html and 'data-forecast-table' in html and '<iframe' not in html
        assert "방법론 / 원본 기록" in html and "SHA-256" in html
        assert '<svg class="line-chart"' in html and 'data-chart-series' in html


def test_pre_reconstruction_is_honest(candidate):
    html=(candidate/"tournaments/2026/kg-ladies-open/pre/index.html").read_text(encoding="utf-8")
    assert "재구성 아카이브" in html and "원본 출판 캡처가 아닙니다" in html
    assert "published_original" not in html


def test_r3_exact_probability_and_no_posthoc_result(candidate):
    html=(candidate/"tournaments/2026/kg-ladies-open/r3/index.html").read_text(encoding="utf-8")
    assert "신다인" in html and "7.47%" in html and "7.40%" not in html
    assert "결과가 나온 뒤 수정하지 않았습니다" in html
    assert "271 (-17)" not in html and "<strong>64</strong>" not in html


def test_final_is_richest_page_with_three_real_charts(candidate):
    root=candidate/"tournaments/2026/kg-ladies-open"
    final=(root/"final/index.html").read_text(encoding="utf-8")
    assert final.count('<svg class="line-chart"') == 3
    for value in ("FINAL · 결과","70","67","64","271","(-17)","우승 확률 변화","순위 변화","라운드 스코어","7.47%"):
        assert value in final
    assert "71 / 67 / 68 / 73" not in final and "279" not in final and "-9" not in final
    assert len(final) > max(len((root/s/"index.html").read_text(encoding="utf-8")) for s in ("r1","r2","r3")) / 2


def test_missing_hole_data_is_disclosed_without_synthetic_counts(candidate):
    final=(candidate/"tournaments/2026/kg-ladies-open/final/index.html").read_text(encoding="utf-8")
    assert "홀별 분석은 이번 대회에서 제공하지 않습니다" in final
    assert "검증된 입력이 없어 생략" in final
    assert "Eagle        1" not in final and "Birdie      18" not in final


def test_deep_dive_real_data_and_click_only_ga4(candidate):
    deep=(candidate/"deep-dive/index.html").read_text(encoding="utf-8")
    js=(candidate/"assets/neo-site.js").read_text(encoding="utf-8")
    for value in ("15.04%","11.56%","7.47%","0.24%","평균 라운드 스코어","최근 경기력"):
        assert value in deep
    assert 'event: "deep_dive_interest"' in js and 'addEventListener("click", trackDeepDiveInterest)' in js
    assert "trackDeepDiveInterest();" not in js and "gtag(" not in js


def test_no_unnecessary_english_or_beta_in_product_flow(candidate):
    normal="\n".join(p.read_text(encoding="utf-8") for p in pages(candidate))
    normal=re.sub(r'<details class="evidence-detail".*?</details>',"",normal,flags=re.DOTALL)
    for phrase in ("LATEST TOURNAMENT","LATEST RESULT","OFFICIAL WINNER","TOURNAMENT OVERVIEW","FROZEN FORECAST","PROTECTED SOURCES","ABOUT NEO","BETA #001"):
        assert phrase not in normal
    assert "FORECASTS FROZEN" not in normal.upper()


def test_no_mojibake_iframe_duplicate_assets_or_broken_links(candidate):
    for page in pages(candidate):
        html=page.read_text(encoding="utf-8")
        assert "�" not in html and "쨌" not in html and "<iframe" not in html
        assert html.count('/assets/neo-site.css') == 1 and html.count('/assets/neo-site.js') == 1
        for url in re.findall(r'(?:href|src)="(/[^"#?]*)',html):
            target=candidate/url.lstrip("/")
            if url.endswith("/"): target/= "index.html"
            assert target.exists(),f"{page}: broken {url}"


@pytest.mark.parametrize("width",[320,360,375,390,430,768])
def test_mobile_table_chart_and_navigation_contract(candidate,width):
    css=(candidate/"assets/neo-site.css").read_text(encoding="utf-8")
    assert width >= 320 and "overflow-x: auto" in css and "white-space: nowrap" in css and "min-height: 44px" in css
    assert ".line-chart" in css and ".chart-scroll" in css
    assert re.search(r"stage-nav[^{}]*nth-child",css,re.IGNORECASE) is None
    assert "overflow-x: hidden" not in css


def test_protected_copies_and_phase0_evidence_are_immutable(candidate):
    expected={"PRE":"0e1fbd013d1e5280887636fc7d504b537f71833dfca918bb876e7ce0fd5301ea","R1":"be9b5fb56090667aea7924abdd7f481d079579687dc1eb1a561134f353b3400c","R2":"531cac52a7c122e0a0a161f18704570f4972eb744b928128c1317fd06a49eeae","R3":"30797700f3e2e6530c1de02575723d94dbb67da860ade493068d891294ffde15"}
    assert load_and_verify_manifest(MANIFEST,REPO_ROOT)==expected
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8")); records={x["stage"]:x for x in manifest["stages"]}
    for stage in ("R1","R2","R3"):
        assert hashlib.sha256((candidate/"protected/beta001"/f"{stage.lower()}.html").read_bytes()).hexdigest()==records[stage]["sha256"]


def test_forecast_result_isolation_and_no_synthetic_production_data(candidate):
    data=json.loads(CONTENT.read_text(encoding="utf-8")); forbidden={"winner","rounds","total","to_par","official_result","final_result"}
    assert all(not(forbidden & set(record)) for record in data["forecast_stages"].values())
    root=candidate/"tournaments/2026/kg-ladies-open"
    for stage in ("pre","r1","r2","r3"):
        html=(root/stage/"index.html").read_text(encoding="utf-8")
        assert "271 (-17)" not in html and "Dry Run Player" not in html


def test_typography_audit_and_korean_readable_scale_exist():
    audit=json.loads((PIPELINE_ROOT/"content/website_v2/klpga_typography_audit.json").read_text(encoding="utf-8"))
    assert audit["observed"]["root_size_px"]==14 and audit["observed"]["body_family"][0]=="SDGothic"
    assert audit["neo_decision"]["font_family"][0]=="Pretendard"
    css=(PIPELINE_ROOT/"src/klpga/website_v2/static/neo-site.css").read_text(encoding="utf-8")
    assert "Apple SD Gothic Neo" in css and "Malgun Gothic" in css and "6.5rem" not in css
