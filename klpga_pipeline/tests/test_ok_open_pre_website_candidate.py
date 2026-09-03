import json
import re
import hashlib
import subprocess
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_candidate_uses_public_master_and_renders_contract(tmp_path):
    out = builder.build()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert html.count("<tr>") - 1 == 120
    for label in ["선수", "KLPGA K-RANKING", "NEO 경기력", "SG Total 순위", "우승확률"]:
        assert label in html
    for forbidden in ["SCORE", "THRU", "현재 라운드", "TOP20", "TOP10", "TOP5", "player_id", "VERY_HIGH", "INSUFFICIENT_EVIDENCE"]:
        assert forbidden not in html
    assert "K-RANKING은 누적 성과, NEO는 최근 경기력을 봅니다." in html
    assert "★★★★★" not in html and "★★★★☆" not in html and "★★★☆☆" not in html and "★★☆☆☆" not in html and "★☆☆☆☆" not in html
    assert "데이터 부족" in html
    assert "aria-label='NEO 경기력" in html
    assert html.count("NEO 경기력") >= 1
    assert len(re.findall(r"<span class='band'[^>]*>최상위</span>", html)) == 15
    assert len(re.findall(r"<span class='band'[^>]*>데이터 부족</span>", html)) == 3
    assert "NEO 경기력 구간" not in html


def test_manifest_points_to_canonical_master():
    out = builder.build()
    manifest = json.loads((out / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_master"].endswith("OK_OPEN_2026_PRE_PUBLIC_MASTER.json")
    assert manifest["entry_count"] == 120


def test_mobile_table_containment_contract():
    out = builder.build()
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert ".grid > *,.panel{min-width:0}" in css
    assert ".table-wrap{width:100%;max-width:100%;overflow-x:auto" in css


def test_about_and_center_alignment_contract():
    out = builder.build()
    about = (out / "about" / "index.html").read_text(encoding="utf-8")
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert "결과만으로는 보이지 않는 경기력을 데이터에서 봅니다." in about
    assert ".player,.sponsor{text-align:center}" in css


def test_info_control_is_interactive_in_generated_html():
    out = builder.build()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "class='info-control'" in html
    assert "aria-expanded='false'" in html
    assert "aria-controls='neo-info'" in html
    assert "role='tooltip'" in html
    assert "최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다." in html
    assert "addEventListener('click'" in html
    assert "지금의 경기력" not in html
    assert "지금 경기력" not in html


def test_mobile_popover_is_viewport_safe():
    out = builder.build()
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert "@media(max-width:760px){.info-popover{position:fixed;left:16px;right:16px;top:112px" in css
    assert "max-width:none" in css


def test_canonical_pre_route_and_stage_navigation_are_generated():
    out = builder.build()
    route = out / "tournaments" / "2026" / "ok-savings-bank-open" / "pre" / "index.html"
    assert route.exists()
    html = route.read_text(encoding="utf-8")
    for stage in ["PRE", "R1", "R2", "FINAL"]:
        assert stage in html
    assert "tournaments/2026/ok-savings-bank-open/pre/" in html
    assert "tournaments/2026/ok-savings-bank-open/r3/" not in html


def test_public_ui_contract_generated_route():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/pre/index.html").read_text(encoding="utf-8")
    assert html.count("<tr>") - 1 == 120
    assert "<th>선수</th>" in html
    assert "KLPGA K-RANKING" in html and "SG Total" in html and "우승확률" in html
    assert all(x not in html for x in ["VERY_HIGH", "HIGH", "TYPICAL", "LOW", "VERY_LOW", "INSUFFICIENT_EVIDENCE", "TOP20", "TOP10", "TOP5", "player_id"])
    assert sum(html.count(c) for c in "★☆") == 0
    assert len(re.findall(r"<span class='band'[^>]*>데이터 부족</span>", html)) == 3
    assert "평가 보류" not in html
    assert "지금의 경기력" not in html and "지금 경기력" not in html
    assert "최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다." in html
    assert ".player,.sponsor{text-align:center}" not in html  # style contract is in linked CSS
    assert "aria-label='NEO 경기력" in html


def test_all_54_hole_stage_routes_are_truthful_and_hash_linked():
    out = builder.build()
    root = out / "tournaments/2026/ok-savings-bank-open"
    for stage in ["pre", "r1", "r2", "final"]:
        page = root / stage / "index.html"
        assert page.exists()
        html = page.read_text(encoding="utf-8")
        assert "neo-public-master-sha256" in html
        assert "아직" in html or stage == "pre"
    assert not (root / "r3").exists()
    manifest = json.loads((out / "data/manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["source_master_sha256"]) == 64
    source = subprocess.check_output(["git", "cat-file", "-p", "HEAD:klpga_pipeline/content/website_v2/OK_OPEN_2026_PRE_PUBLIC_MASTER.json"])
    expected = hashlib.sha256(source).hexdigest().upper()
    assert manifest["source_master_sha256"] == expected
    for stage in ["pre", "r1", "r2", "final"]:
        page = (root / stage / "index.html").read_text(encoding="utf-8")
        assert f'name="neo-public-master-sha256" content="{expected}"' in page


def test_stage_links_resolve_from_every_generated_stage_page():
    # v3 UI/UX rebuild (spec 9/10): a stage that has no real data yet must
    # never be a clickable link -- only PRE is real today, so it's the
    # only stage-nav item with an href; R1/R2/FINAL render as disabled
    # (present as text, no href) on every stage page, including on their
    # own pages.
    from urllib.parse import urljoin
    out = builder.build()
    root = out / "tournaments/2026/ok-savings-bank-open"
    for stage in ["pre", "r1", "r2", "final"]:
        page_url = f"http://localhost/tournaments/2026/ok-savings-bank-open/{stage}/"
        html = (root / stage / "index.html").read_text(encoding="utf-8")
        pre_href = "/tournaments/2026/ok-savings-bank-open/pre/"
        assert pre_href in html
        assert urljoin(page_url, pre_href).endswith("/pre/")
        for target in ["r1", "r2", "final"]:
            href = f"/tournaments/2026/ok-savings-bank-open/{target}/"
            assert href not in html, f"{target} has no real data yet and must not be a clickable link on the {stage} page"
            assert f'class="stage-nav__disabled"' in html and target.upper() in html
        assert "/r3/" not in html
