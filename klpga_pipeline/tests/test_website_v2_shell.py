from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from klpga.evidence import load_and_verify_manifest
from klpga.website_v2 import STAGES, TournamentMetadata, build_preview_site, render_page


REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "klpga_pipeline"
FIXTURE = PIPELINE_ROOT / "tests" / "fixtures" / "website_v2" / "beta002_shell.json"
MANIFEST = PIPELINE_ROOT / "evidence" / "beta001" / "manifest.json"


@pytest.fixture()
def preview(tmp_path: Path) -> Path:
    build_preview_site(FIXTURE, tmp_path)
    return tmp_path


def _pages(root: Path) -> list[Path]:
    return sorted(root.rglob("index.html"))


def _meta(**overrides) -> TournamentMetadata:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(overrides)
    return TournamentMetadata.from_dict(data)


def test_global_navigation_and_logo_home_link(preview: Path):
    for page in _pages(preview):
        html = page.read_text(encoding="utf-8")
        assert '<a class="wordmark" href="/"' in html
        for label, url in (("HOME", "/"), ("TOURNAMENTS", "/tournaments/"),
                           ("DEEP DIVE", "/deep-dive/"), ("ABOUT NEO", "/about/")):
            assert f'href="{url}"' in html and label in html


def test_all_stages_and_final_render_on_every_tournament_page(preview: Path):
    tournament = preview / "tournaments" / "2027" / "fixture-open"
    for page in _pages(tournament):
        html = page.read_text(encoding="utf-8")
        labels = re.findall(r'class="stage-nav__(?:link|disabled)"[^>]*>([^<]+)<', html)
        assert labels == ["OVERVIEW", "PRE", "R1", "R2", "R3", "FINAL"]


def test_final_is_reachable_when_published(preview: Path):
    overview = (preview / "tournaments" / "2027" / "fixture-open" / "index.html").read_text(encoding="utf-8")
    assert 'href="/tournaments/2027/fixture-open/final/">FINAL</a>' in overview
    assert (preview / "tournaments" / "2027" / "fixture-open" / "final" / "index.html").is_file()


def test_unpublished_stages_are_visible_non_clickable_and_accessible():
    meta = _meta(latest_published_stage="pre", published_stages=["overview", "pre"])
    html = render_page(title="Fixture", active_section="tournaments", body_html="<p>Fixture</p>",
                       tournament=meta, current_stage="pre")
    assert '<span class="stage-nav__disabled" aria-disabled="true">R1</span>' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>' in html
    assert f'href="{meta.stage_url("final")}"' not in html


@pytest.mark.parametrize("stage", STAGES)
def test_active_stage_has_aria_current_and_title_returns_to_overview(stage: str):
    meta = _meta()
    html = render_page(title="Fixture", active_section="tournaments", body_html="<p>Fixture</p>",
                       tournament=meta, current_stage=stage)
    assert f'href="{meta.stage_url(stage)}" aria-current="page">' in html
    assert f'<h1 id="tournament-name"><a href="{meta.base_url}">' in html


def test_no_fr_user_facing_navigation(preview: Path):
    for page in _pages(preview):
        html = page.read_text(encoding="utf-8")
        nav = re.search(r'<nav class="stage-nav".*?</nav>', html, re.DOTALL)
        if nav:
            assert re.search(r'>FR<', nav.group(0)) is None


def test_shared_css_and_no_inline_style_architecture(preview: Path):
    for page in _pages(preview):
        html = page.read_text(encoding="utf-8")
        assert html.count('<link rel="stylesheet" href="/assets/neo-site.css">') == 1
        assert "<style" not in html and ' style="' not in html
    assert (preview / "assets" / "neo-site.css").is_file()


def test_mobile_stage_navigation_contract(preview: Path):
    css = (preview / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert "overflow-x: auto" in css
    assert "white-space: nowrap" in css
    assert "min-height: 44px" in css
    assert "nth-child" not in css
    assert re.search(r"FINAL\s*\{[^}]*display\s*:\s*none", css, re.IGNORECASE) is None


def test_home_overview_and_every_global_destination_reachable(preview: Path):
    required = [
        preview / "index.html", preview / "tournaments" / "index.html",
        preview / "tournaments" / "2027" / "fixture-open" / "index.html",
        preview / "deep-dive" / "index.html", preview / "about" / "index.html",
    ]
    assert all(path.is_file() for path in required)


def test_internal_absolute_links_resolve_inside_preview(preview: Path):
    for page in _pages(preview):
        html = page.read_text(encoding="utf-8")
        for url in re.findall(r'href="(/[^"]*)"', html):
            path = url.split("#", 1)[0].split("?", 1)[0]
            target = preview / path.lstrip("/")
            if path.endswith("/"):
                target /= "index.html"
            assert target.exists(), f"{page}: broken link {url}"


def test_beta002_metadata_renders_without_template_changes():
    meta = _meta()
    html = render_page(title="Fixture", active_section="tournaments", body_html="<p>Fixture</p>",
                       tournament=meta, current_stage="overview")
    assert "NEO FIXTURE OPEN" in html and "BETA #002" in html and "2027" in html
    assert "KG LADIES OPEN" not in html and "BETA #001" not in html


def test_fixture_pages_cannot_be_mistaken_for_historical_evidence(preview: Path):
    for page in _pages(preview):
        html = page.read_text(encoding="utf-8")
        assert "PHASE 1 FIXTURE" in html
        assert "not historical prediction evidence" in html


def test_deep_dive_contract_is_preserved_without_page_load_fire(preview: Path):
    javascript = (preview / "assets" / "neo-site.js").read_text(encoding="utf-8")
    assert 'event: "deep_dive_interest"' in javascript
    assert 'addEventListener("click"' in javascript
    assert "trackDeepDiveInterest();" not in javascript
    assert "gtag(" not in javascript


def test_phase0_evidence_remains_valid():
    verified = load_and_verify_manifest(MANIFEST, REPO_ROOT)
    assert tuple(verified) == ("PRE", "R1", "R2", "R3")
