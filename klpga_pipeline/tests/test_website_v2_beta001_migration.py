from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from klpga.evidence import load_and_verify_manifest
from klpga.website_v2 import build_beta001_candidate


REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "klpga_pipeline"
CONTENT = PIPELINE_ROOT / "content" / "website_v2" / "beta001.json"
MANIFEST = PIPELINE_ROOT / "evidence" / "beta001" / "manifest.json"


@pytest.fixture()
def candidate(tmp_path: Path) -> Path:
    build_beta001_candidate(CONTENT, MANIFEST, REPO_ROOT, tmp_path)
    return tmp_path


def _html_pages(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.html") if "protected" not in path.parts)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_required_candidate_routes_exist(candidate: Path):
    routes = ["", "tournaments", "deep-dive", "about"]
    routes += [f"tournaments/2026/kg-ladies-open/{stage}" for stage in ("", "pre", "r1", "r2", "r3", "final")]
    assert all((candidate / route / "index.html").is_file() for route in routes)


def test_every_beta001_page_has_complete_navigation(candidate: Path):
    tournament_root = candidate / "tournaments" / "2026" / "kg-ladies-open"
    for page in sorted(tournament_root.rglob("index.html")):
        html = page.read_text(encoding="utf-8")
        assert all(label in html for label in ("HOME", "TOURNAMENTS", "DEEP DIVE", "ABOUT NEO"))
        labels = re.findall(r'class="stage-nav__(?:link|disabled)"[^>]*>([^<]+)<', html)
        assert labels == ["OVERVIEW", "PRE", "R1", "R2", "R3", "FINAL"]
        assert 'href="/"' in html
        assert 'href="/tournaments/2026/kg-ladies-open/"' in html


def test_internal_links_are_not_broken(candidate: Path):
    for page in _html_pages(candidate):
        for url in re.findall(r'(?:href|src)="(/[^"]*)"', page.read_text(encoding="utf-8")):
            path = url.split("#", 1)[0].split("?", 1)[0]
            if path.startswith("/assets/") or path.startswith("/protected/"):
                target = candidate / path.lstrip("/")
            else:
                target = candidate / path.lstrip("/")
                if path.endswith("/"):
                    target /= "index.html"
            assert target.exists(), f"{page}: broken {url}"


def test_r1_r2_stable_routes_and_protected_bytes(candidate: Path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = {record["stage"].lower(): record for record in manifest["stages"]}
    for stage in ("r1", "r2", "r3"):
        route = candidate / "tournaments" / "2026" / "kg-ladies-open" / stage / "index.html"
        assert route.is_file()
        assert _sha(candidate / "protected" / "beta001" / f"{stage}.html") == records[stage]["sha256"]


def test_pre_is_disclosed_as_reconstructed_not_original(candidate: Path):
    html = (candidate / "tournaments" / "2026" / "kg-ladies-open" / "pre" / "index.html").read_text(encoding="utf-8")
    assert "RECONSTRUCTED ARCHIVE EVIDENCE" in html
    assert "not an original publication capture" in html
    assert "ORIGINAL PUBLISHED FORECAST EVIDENCE" not in html


def test_r3_is_original_protected_snapshot_not_reconstructed(candidate: Path):
    html = (candidate / "tournaments" / "2026" / "kg-ladies-open" / "r3" / "index.html").read_text(encoding="utf-8")
    assert "Original publication evidence" in html
    assert "View original evidence" in html
    assert "RECONSTRUCTED ARCHIVE EVIDENCE" not in html
    assert "<iframe" not in html


def test_final_is_result_with_only_validated_scores(candidate: Path):
    html = (candidate / "tournaments" / "2026" / "kg-ladies-open" / "final" / "index.html").read_text(encoding="utf-8")
    assert "FINAL · RESULT" in html and "Official final result" in html
    assert "신다인" in html and "271 (-17)" in html
    for score in (70, 70, 67, 64):
        assert f"<strong>{score}</strong>" in html
    assert "71 / 67 / 68 / 73" not in html and "279" not in html and "-9" not in html
    assert "FINAL · FORECAST" not in html


def test_result_fields_do_not_leak_into_forecast_records_or_pages(candidate: Path):
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    forbidden = {"winner", "rounds", "total", "to_par", "official_result", "final_result"}
    assert all(not (forbidden & set(record)) for record in data["forecast_stages"].values())
    for stage in ("pre", "r1", "r2", "r3"):
        html = (candidate / "tournaments" / "2026" / "kg-ladies-open" / stage / "index.html").read_text(encoding="utf-8")
        assert "271 (-17)" not in html
        assert "R4</small><br><strong>64" not in html


def test_home_is_site_home_not_full_tournament_dashboard(candidate: Path):
    html = (candidate / "index.html").read_text(encoding="utf-8")
    assert "NEO GOLF DATA" in html and "Latest tournament" in html and "Latest result" in html
    assert "골프는 결과로 끝나지만" in html and "NEO는 결과가 나오기 전을 기록합니다" in html
    assert "KLPGA 대회 데이터" in html and "우승 확률" in html
    assert "<table" not in html


def test_overview_summarizes_and_routes_without_stage_tables(candidate: Path):
    html = (candidate / "tournaments" / "2026" / "kg-ladies-open" / "index.html").read_text(encoding="utf-8")
    assert "Stage timeline" in html and "Forecast → Result" in html
    assert "7.47%" in html and "271 (-17)" in html
    assert "우승자 지목이 아닙니다" in html
    assert "<table" not in html


def test_deep_dive_is_real_destination_and_event_is_click_only(candidate: Path):
    deep = (candidate / "deep-dive" / "index.html").read_text(encoding="utf-8")
    home = (candidate / "index.html").read_text(encoding="utf-8")
    javascript = (candidate / "assets" / "neo-site.js").read_text(encoding="utf-8")
    assert "공동 선두 네 명, 서로 다른 확률" in deep
    assert "data-deep-dive-interest" in home
    assert 'event: "deep_dive_interest"' in javascript
    assert "addEventListener(\"click\"" in javascript
    before_click_handler = javascript.split('addEventListener("click"', 1)[0]
    assert 'event: "deep_dive_interest"' in before_click_handler
    assert "gtag('config'" not in javascript and 'gtag("config"' not in javascript


def test_r1_r2_r3_use_one_native_forecast_template(candidate: Path):
    for stage in ("r1", "r2", "r3"):
        html = (candidate / "tournaments" / "2026" / "kg-ladies-open" / stage / "index.html").read_text(encoding="utf-8")
        assert 'class="section-v2 forecast-stage"' in html
        assert 'data-forecast-table' in html
        assert "<iframe" not in html
        assert "View original evidence" in html


def test_phase3_r3_and_final_semantics(candidate: Path):
    root = candidate / "tournaments" / "2026" / "kg-ladies-open"
    r3 = (root / "r3" / "index.html").read_text(encoding="utf-8")
    final = (root / "final" / "index.html").read_text(encoding="utf-8")
    assert "ROUND 3 FORECAST · FROZEN" in r3
    assert "FINAL 정보를 사용해 다시 쓰지 않았습니다" in r3
    assert "신다인" in r3 and "7.47%" in r3
    assert "7.40%" not in r3
    assert "어제 NEO는 어떻게 봤나" in final and "7.47%" in final
    assert "71 / 67 / 68 / 73" not in final and "279 (-9)" not in final
    prohibited = ("NEO predicted Shin Dain", "NEO picked the winner", "NEO correctly predicted", "우승자를 맞혔다", "우승을 예측했다")
    assert all(text not in r3 + final for text in prohibited)


def test_no_broken_encoding_in_normal_forecast_pages(candidate: Path):
    root = candidate / "tournaments" / "2026" / "kg-ladies-open"
    for stage in ("r1", "r2", "r3"):
        html = (root / stage / "index.html").read_text(encoding="utf-8")
        assert "�" not in html
        assert "쨌" not in html


def test_candidate_shell_has_no_ga4_initialization_and_protected_pages_have_at_most_one(candidate: Path):
    shell_pages = "\n".join(page.read_text(encoding="utf-8") for page in _html_pages(candidate))
    assert "googletagmanager.com/gtag/js" not in shell_pages
    assert "gtag('config'" not in shell_pages and 'gtag("config"' not in shell_pages
    for page in (candidate / "protected" / "beta001").glob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert html.count("googletagmanager.com/gtag/js") <= 1
        assert html.count("gtag('config'") + html.count('gtag("config"') <= 1


def test_no_fixture_content_or_beta001_hardcoding_in_shell(candidate: Path):
    authentic = "\n".join(page.read_text(encoding="utf-8") for page in _html_pages(candidate))
    assert "PHASE 1 FIXTURE" not in authentic and "NEO FIXTURE OPEN" not in authentic
    shell = (PIPELINE_ROOT / "src" / "klpga" / "website_v2" / "shell.py").read_text(encoding="utf-8")
    assert "KG LADIES" not in shell and "BETA #001" not in shell


def test_single_shared_css_and_js_no_inline_architecture(candidate: Path):
    for page in _html_pages(candidate):
        html = page.read_text(encoding="utf-8")
        assert html.count('/assets/neo-site.css') == 1
        assert html.count('/assets/neo-site.js') == 1
        assert "<style" not in html and ' style="' not in html


@pytest.mark.parametrize("width", [320, 360, 375, 390, 430, 768])
def test_mobile_css_contract_for_required_widths(candidate: Path, width: int):
    css = (candidate / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert width >= 320
    assert ".stage-nav" in css and "overflow-x: auto" in css
    assert "white-space: nowrap" in css and "min-height: 44px" in css
    assert "nth-child" not in css
    assert "body" in css and "overflow-x: hidden" not in css
    assert ".table-scroll" in css and "overflow-x: auto" in css


def test_legacy_url_compatibility_decision_is_recorded(candidate: Path):
    html = (candidate / "about" / "index.html").read_text(encoding="utf-8")
    for route in ("/predictions/", "/predictions/001/", "/predictions/history/", "/methodology/"):
        assert route in html
    assert "public-history evidence is not established" in html


def test_phase0_evidence_remains_valid_after_candidate_generation():
    verified = load_and_verify_manifest(MANIFEST, REPO_ROOT)
    assert verified == {
        "PRE": "0e1fbd013d1e5280887636fc7d504b537f71833dfca918bb876e7ce0fd5301ea",
        "R1": "be9b5fb56090667aea7924abdd7f481d079579687dc1eb1a561134f353b3400c",
        "R2": "531cac52a7c122e0a0a161f18704570f4972eb744b928128c1317fd06a49eeae",
        "R3": "30797700f3e2e6530c1de02575723d94dbb67da860ade493068d891294ffde15",
    }
