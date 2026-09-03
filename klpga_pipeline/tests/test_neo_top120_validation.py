from __future__ import annotations

import importlib.util
import functools
import http.server
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from klpga.website_v2.top120_validation import evaluate, validate_cohort

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"


def load(name): return json.loads((CONTENT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built():
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder", path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.build()


def test_official_cohort_is_exact_contiguous_top120_with_unique_identity():
    document = load("HOME_PLAYER_MASTER_TOP120.json"); rows = validate_cohort(document)
    assert len(rows) == 120
    assert [r["official_k_rank"] for r in rows] == list(range(1, 121))
    assert len({r["official_k_rank"] for r in rows}) == 120
    assert len({r["player_id"] for r in rows}) == 120
    assert len({r["player_name"] for r in rows}) == 120
    assert all(r["player_name"] and r["official_source"] and r["ranking_week"] and r["retrieved_at"] and r["identity_validation_state"] for r in rows)


def test_population_source_is_not_a_tournament_entry_artifact():
    document = load("HOME_PLAYER_MASTER_TOP120.json")
    assert document["population_kind"] == "official_klpga_kranking_top120"
    assert "entry" not in document["population_selection"].lower()
    assert "OK_OPEN" not in document["official_source"]


def test_player_id_only_join_missing_sg_is_never_zero_imputed():
    cohort = {"population_kind":"official_klpga_kranking_top120","records":[{"official_k_rank":i,"player_id":str(i),"player_name":f"선수{i}","official_source":"https://official","retrieved_at":"2026-09-02T00:00:00Z","identity_validation_state":"PASS_OFFICIAL_PLAYER_ID"} for i in range(1,121)]}
    rows, summary = evaluate(cohort, {"records":[]}, load("NEO_RANKING_VALIDATION_MODEL_V1.json"))
    assert summary["sg_connected"] == summary["neo_ranked"] == 0
    assert all(r["features"] is None and r["validation_score"] is None and r["neo_validation_rank"] is None for r in rows)
    assert all(r["sg_join_state"] == "DATA_INSUFFICIENT" for r in rows)


def test_model_config_forbids_win_probability_and_is_explicitly_validation_only():
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    source = (ROOT / "src" / "klpga" / "website_v2" / "top120_validation.py").read_text(encoding="utf-8")
    assert config["publication_class"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    assert "win_probability" in config["forbidden_features"]
    assert "win_probability" not in source
    assert sum(v["weight"] for v in config["features"].values()) == pytest.approx(1.0)


def test_candidate_contract_and_pending_handling(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert html.count("data-player-row") == 120
    assert "검증 대기" in html and "NEO 랭킹 검증" in html
    assert "검증 선수" not in html and "win_probability" not in html
    assert built == {**built, "cohort_count":120}
    dataset = json.loads((OUTPUT / "data" / "neo-top120-evaluation.json").read_text(encoding="utf-8"))
    assert all(r["official_source"] and r["model_id"] for r in dataset["records"])
    assert all(r["rank_delta"] is None for r in dataset["records"] if r["neo_validation_rank"] is None)
    for route in ("tournaments/index.html", "tournaments/2026/kg-ladies-open/r1/index.html", "tournaments/2026/kg-ladies-open/r2/index.html",
                  "tournaments/2026/ok-savings-bank-open/pre/index.html", "tournaments/2026/ok-savings-bank-open/final/index.html",
                  "about/index.html", "deep-dive/index.html"):
        assert (OUTPUT / route).is_file()


def test_ok_stage_assets_and_deep_dive_are_complete(built):
    assert (OUTPUT / "assets" / "neo.css").is_file()
    assert (OUTPUT / "assets" / "neo-site.js").is_file()
    # navigation.css was retired -- the canonical .neo-global-header/nav
    # component is styled entirely from neo-site.css now (a second,
    # separately-linked stylesheet just for the header was a drift risk,
    # not a real requirement -- see global_navigation.py).
    assert not (OUTPUT / "assets" / "navigation.css").exists()
    ok = OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open"
    for stage in ("pre", "r1", "r2", "final"):
        html = (ok / stage / "index.html").read_text(encoding="utf-8")
        assert 'href="/assets/neo.css"' in html
    deep = (OUTPUT / "deep-dive" / "index.html").read_text(encoding="utf-8")
    assert len(deep) > 1000 and "data-chart-series" in deep


def test_every_public_route_has_global_home_navigation(built):
    routes = (
        "index.html",
        "tournaments/index.html",
        "deep-dive/index.html",
        "about/index.html",
        "tournaments/2026/kg-ladies-open/r1/index.html",
        "tournaments/2026/kg-ladies-open/r2/index.html",
        "tournaments/2026/ok-savings-bank-open/pre/index.html",
        "tournaments/2026/ok-savings-bank-open/r1/index.html",
        "tournaments/2026/ok-savings-bank-open/r2/index.html",
        "tournaments/2026/ok-savings-bank-open/final/index.html",
    )
    required = (
        'href="/">홈</a>',
        'href="/tournaments/">대회</a>',
        'href="/deep-dive/">딥다이브</a>',
        'href="/about/">소개</a>',
    )
    for route in routes:
        html = (OUTPUT / route).read_text(encoding="utf-8")
        assert 'href="/">NEO GOLF DATA</a>' in html, route
        assert all(link in html for link in required), route
        assert html.count('class="neo-global-header"') == 1, route
    css = (OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert ".neo-global-header__inner{display:flex" in css
    assert ".neo-global-nav{display:flex" in css and "overflow-x:auto" in css


def test_home_is_korean_first_and_table_alignment_is_explicit(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert html.count("data-player-row") == 120
    assert "KLPGA 공식 K-Ranking 1~120위" in html
    assert "NEO 랭킹 검증" in html
    assert "검증 대기" in html
    assert all(term in html for term in ("K-Ranking", "NEO Ranking", "최근 경기력"))
    assert "DATA INSUFFICIENT" not in html
    assert all(term not in html for term in (">HOME<", ">TOURNAMENTS<", ">DEEP DIVE<", ">ABOUT<", "production 아님"))
    css = (OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert ".home-table{width:100%;min-width:960px;table-layout:fixed}" in css
    assert ".home-table th:nth-child(3),.home-table td:nth-child(3){width:12rem;text-align:left" in css
    assert "font-variant-numeric:tabular-nums" in css


def test_http_routes_are_real_index_pages_not_directory_listings(built):
    routes = {
        "/": "<title>",
        "/tournaments/": "대회 분석 허브",
        "/deep-dive/": "<title>",
        "/about/": "<title>",
        "/tournaments/2026/kg-ladies-open/r1/": "<title>",
        "/tournaments/2026/kg-ladies-open/r2/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/pre/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/r1/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/r2/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/final/": "<title>",
    }
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUTPUT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for route, marker in routes.items():
            index = OUTPUT / route.strip("/") / "index.html" if route != "/" else OUTPUT / "index.html"
            assert index.is_file(), route
            response = urllib.request.urlopen(base + route, timeout=10)
            body = response.read().decode("utf-8")
            assert response.status == 200
            assert "Directory listing for" not in body
            assert marker in body
    finally:
        server.shutdown()
        thread.join(timeout=10)
