"""Regression test for the reported bug: from Hana's PRE page, R1 in
the stage-nav rendered as a disabled <span> (no href at all), so there
was no way to click through to the real, already-published R1 page.
139_build_hana_pre_kb_structure.py's stage_nav block is the only place
that markup is generated -- this locks its R1 entry down as a real,
correctly-targeted link going forward."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"
R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
R1_URL = "/tournaments/2026/2026090002/r1/"

_STAGE_NAV_RE = re.compile(r'<nav class="stage-nav"[^>]*>.*?</nav>', re.S)
_R1_ITEM_RE = re.compile(
    r'<li class="stage-nav__item">'
    r'(?:<a class="stage-nav__link" href="([^"]*)"[^>]*>R1</a>'
    r'|<span class="stage-nav__disabled"[^>]*>R1</span>)'
    r'</li>'
)


def _pre_stage_nav() -> str:
    html = PRE_PAGE.read_text(encoding="utf-8")
    match = _STAGE_NAV_RE.search(html)
    assert match, f"no stage-nav found in {PRE_PAGE}"
    return match.group(0)


def test_pre_stage_nav_r1_is_a_real_link_not_a_disabled_span():
    stage_nav = _pre_stage_nav()
    match = _R1_ITEM_RE.search(stage_nav)
    assert match, f"R1 stage-nav item not found in the expected <li> shape: {stage_nav}"
    href = match.group(1)
    assert href is not None, (
        "PRE's stage-nav still renders R1 as a disabled <span> -- clicking it does nothing. "
        "It must be a real <a href> once R1 is published."
    )
    assert href == R1_URL, f"PRE's R1 stage-nav link points at {href!r}, expected {R1_URL!r}"


def test_pre_r1_link_target_is_a_real_published_page():
    """The other half of "클릭 시 실제 R1 페이지로 이동": the href PRE
    points at must resolve to a real, already-built R1 page on disk,
    not a 404."""
    assert R1_PAGE.is_file(), f"PRE links to {R1_URL} but no page exists at {R1_PAGE}"
    r1_html = R1_PAGE.read_text(encoding="utf-8")
    assert "<title>" in r1_html and "108" in r1_html, (
        f"{R1_PAGE} exists but doesn't look like the real R1 results page"
    )


def test_pre_page_data_is_unaffected_by_the_nav_fix():
    """The fix must be markup-only: PRE's 108-player table, K-Ranking/
    NEO 경기력/확률 columns are untouched by the stage-nav change."""
    html = PRE_PAGE.read_text(encoding="utf-8")
    assert "PRE 참가 선수 <small>108명</small>" in html
    assert html.count("<tr>") >= 108 or html.count("data-label=") > 0
