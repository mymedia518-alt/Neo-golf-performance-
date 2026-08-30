from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from klpga.website_v2 import STAGES, TournamentMetadata, build_preview_site, render_page

ROOT=Path(__file__).resolve().parents[2]/"klpga_pipeline"
FIXTURE=ROOT/"tests/fixtures/website_v2/beta002_shell.json"


def meta(**overrides):
    data=json.loads(FIXTURE.read_text(encoding="utf-8")); data.update(overrides); return TournamentMetadata.from_dict(data)


@pytest.fixture()
def preview(tmp_path):
    build_preview_site(FIXTURE,tmp_path); return tmp_path


def test_korean_global_nav_and_logo(preview):
    for page in preview.rglob("index.html"):
        html=page.read_text(encoding="utf-8")
        assert '<a class="wordmark" href="/"' in html
        for label,url in (("홈","/"),("대회","/tournaments/"),("예측 기록","/predictions/"),("DEEP DIVE","/deep-dive/"),("NEO 소개","/about/")):
            assert label in html and f'href="{url}"' in html


def test_stage_nav_semantics_and_final(preview):
    root=preview/"tournaments/2027/fixture-open"
    for page in root.rglob("index.html"):
        labels=re.findall(r'class="stage-nav__(?:link|disabled)"[^>]*>([^<]+)<',page.read_text(encoding="utf-8"))
        assert labels==["개요","PRE","R1","R2","R3","FINAL"]


def test_active_and_disabled_stage_accessibility():
    m=meta(latest_published_stage="pre",published_stages=["overview","pre"])
    html=render_page(title="검증",active_section="tournaments",body_html="<p>검증</p>",tournament=m,current_stage="pre")
    assert 'href="'+m.stage_url("pre")+'" aria-current="page">PRE' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>' in html


def test_future_tournament_uses_same_shell_without_public_beta_label():
    m=meta(); html=render_page(title="검증",active_section="tournaments",body_html="<p>검증</p>",tournament=m,current_stage="overview")
    assert "NEO FIXTURE OPEN" in html and "2027" in html
    assert "BETA #002" not in html and "KG LADIES" not in html


def test_fixture_is_clearly_non_authentic(preview):
    for page in preview.rglob("index.html"):
        html=page.read_text(encoding="utf-8")
        assert "구조 검증용 자료" in html and "실제 예측 기록이 아닙니다" in html


def test_shared_assets_and_mobile_contract(preview):
    css=(preview/"assets/neo-site.css").read_text(encoding="utf-8")
    assert "overflow-x: auto" in css and "white-space: nowrap" in css and "min-height: 44px" in css
    for page in preview.rglob("index.html"):
        html=page.read_text(encoding="utf-8")
        assert html.count('/assets/neo-site.css')==1 and "<style" not in html


def test_deep_dive_event_contract_is_click_only(preview):
    js=(preview/"assets/neo-site.js").read_text(encoding="utf-8")
    assert 'event: "deep_dive_interest"' in js and 'addEventListener("click"' in js
    assert "trackDeepDiveInterest();" not in js and "gtag(" not in js


@pytest.mark.parametrize("stage",STAGES)
def test_tournament_title_returns_to_overview(stage):
    m=meta(); html=render_page(title="검증",active_section="tournaments",body_html="",tournament=m,current_stage=stage)
    assert f'<h1 id="tournament-name"><a href="{m.base_url}">' in html
