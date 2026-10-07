"""2026-10-07 global-nav simplification (operator instruction: "사이트
navigation을 단순화해"). Locks the top global menu to exactly six items,
identically, on every public page site-wide -- no more "현재 대회", no
more a page's own self-pointing "대회" tab.

Canonical order: 홈 / 대회 기록 / 랭킹 / 딥다이브 / NEO LAB / 소개, hrefs
/, /tournaments/, /ranking/, /deep-dive/, /neo-lab/, /about/ -- see
scripts/229_normalize_global_nav.py for the normalizer and its active-
state rule."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

CANONICAL_LABELS = ["홈", "대회 기록", "랭킹", "딥다이브", "NEO LAB", "소개"]
CANONICAL_HREFS = ["/", "/tournaments/", "/ranking/", "/deep-dive/", "/neo-lab/", "/about/"]

NAV_RE = re.compile(r'<nav class="neo-global-nav" aria-label="주요 메뉴">(.*?)</nav>', re.DOTALL)
LINK_RE = re.compile(r'<a href="([^"]*)"[^>]*>([^<]*)</a>')


def _all_nav_pages() -> list[Path]:
    pages = []
    for path in sorted(DOCS_ROOT.rglob("index.html")):
        html = path.read_text(encoding="utf-8")
        if NAV_RE.search(html):
            pages.append(path)
    return pages


def test_at_least_48_public_pages_carry_the_global_nav():
    # Sanity floor so this test suite can't silently stop checking
    # anything if a future refactor renames the nav class.
    assert len(_all_nav_pages()) >= 48


def test_every_public_page_global_nav_is_exactly_the_canonical_six_items():
    for path in _all_nav_pages():
        html = path.read_text(encoding="utf-8")
        inner = NAV_RE.search(html).group(1)
        links = LINK_RE.findall(inner)
        hrefs = [h for h, _ in links]
        labels = [l for _, l in links]
        rel = path.relative_to(REPO_ROOT)
        assert hrefs == CANONICAL_HREFS, f"{rel}: hrefs {hrefs}"
        assert labels == CANONICAL_LABELS, f"{rel}: labels {labels}"


def test_no_public_page_shows_현재_대회_in_global_nav():
    for path in _all_nav_pages():
        html = path.read_text(encoding="utf-8")
        inner = NAV_RE.search(html).group(1)
        assert "현재 대회" not in inner, f"{path.relative_to(REPO_ROOT)}: 현재 대회 still in global nav"


def test_no_public_page_global_nav_self_links_as_대회():
    """The old pattern (a page's own 대회 tab pointing back at itself,
    e.g. the R1 page's nav linking /tournaments/2026/.../r1/) must be
    fully gone -- every 대회 기록 link now points at the fixed archive
    index, never a per-tournament or per-stage URL."""
    for path in _all_nav_pages():
        html = path.read_text(encoding="utf-8")
        inner = NAV_RE.search(html).group(1)
        for href, label in LINK_RE.findall(inner):
            if label == "대회 기록":
                assert href == "/tournaments/", f"{path.relative_to(REPO_ROOT)}: 대회 기록 href={href!r}"


def test_home_still_has_its_own_현재_대회_card_label_outside_the_nav():
    """현재 대회 is removed from the GLOBAL nav only -- HOME's own hero
    still legitimately labels its current-tournament card/CTA with it
    (the operator's own stated reasoning: HOME is the entry point)."""
    html = (DOCS_ROOT / "index.html").read_text(encoding="utf-8")
    assert "현재 대회" in html
    nav_inner = NAV_RE.search(html).group(1)
    assert "현재 대회" not in nav_inner


def test_hj_tournament_root_never_claims_rounds_are_public_before_they_exist():
    html = (DOCS_ROOT / "tournaments" / "2026" / "2026100004" / "index.html").read_text(encoding="utf-8")
    assert "아직 공개된 분석은 없습니다" not in html
    assert "준비되는 대로 공개합니다" not in html
    for key in ("r1", "r2", "r3", "fr"):
        path = DOCS_ROOT / "tournaments" / "2026" / "2026100004" / key / "index.html"
        if not path.is_file():
            assert f"/tournaments/2026/2026100004/{key}/" not in html.split("stage-nav")[0], (
                f"{key} page does not exist yet but root links to it outside the (correctly disabled) stage-nav"
            )
