"""Tests for the "대회 기록" archive navigation feature (docs/tournaments/
index.html real build, docs/tournaments/2026/2026100004/ HJ중공업·동부건설
scaffold, and the root HOME rebuild pointing at HJ as the current
tournament).

Two invariants:

1. LEGACY PROTECTION (the important one): rebuilding/changing the current
   tournament must never remove or alter the existing OK저축은행/KB금융/
   하나금융/하이트진로/KG 레이디스 오픈 archive routes, or the shared
   docs/assets|about files. Every file recorded in
   ARCHIVE_NAV_LEGACY_PROTECTED_MANIFEST.json must still match its
   recorded sha256 exactly -- a live tripwire against any future edit to
   this feature accidentally touching legacy tournament content.

2. ARCHIVE CORRECTNESS: the archive index links each real tournament's
   NAME directly to a real, existing record page (no javascript:void(0),
   no "#", no 404 -- checked by resolving every href to an actual file on
   disk), shows only stages that actually exist on disk, and does NOT
   render a fake/dead link for the two tournaments that turned out to be
   content-less "공사중" placeholders (OK저축은행, KG 레이디스 오픈) -- while
   still listing them honestly with a non-link status note, never silently
   dropping them from the archive.

The HJ scaffold must carry no probability output (prediction is locked
until the Stableford model is validated), checked via the same
model_publication_gate used elsewhere in this pipeline for exactly this
purpose.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
MANIFEST_PATH = REPO_ROOT / "klpga_pipeline" / "content" / "website_v2" / "ARCHIVE_NAV_LEGACY_PROTECTED_MANIFEST.json"

sys.path.insert(0, str(REPO_ROOT / "klpga_pipeline" / "src"))
from klpga.website_v2.model_publication_gate import assert_no_blocked_probability_output  # noqa: E402

try:
    from bs4 import BeautifulSoup
    HAVE_BS4 = True
except ImportError:
    HAVE_BS4 = False


def _manifest() -> dict[str, str]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["files"]


@pytest.mark.parametrize("rel_path,expected_sha256", list(_manifest().items()))
def test_legacy_file_unchanged(rel_path, expected_sha256):
    f = REPO_ROOT / rel_path
    assert f.exists(), f"legacy-protected file missing entirely: {rel_path}"
    actual = hashlib.sha256(f.read_bytes()).hexdigest()
    assert actual == expected_sha256, (
        f"LEGACY PROTECTION VIOLATION: {rel_path} changed (expected sha256 "
        f"{expected_sha256}, got {actual}). The archive-navigation feature "
        f"must only link to existing tournament content, never edit it."
    )


def test_manifest_covers_all_five_archive_tournaments_plus_shared_assets():
    rels = set(_manifest().keys())
    required_prefixes = [
        "docs/tournaments/2026/2026090002/",
        "docs/tournaments/2026/2026090003/",
        "docs/tournaments/2026/2026100005/",
        "docs/tournaments/2026/ok-savings-bank-open/",
        "docs/tournaments/2026/kg-ladies-open/",
        "docs/assets/",
        "docs/about/",
    ]
    for prefix in required_prefixes:
        assert any(r.startswith(prefix) for r in rels), f"manifest missing coverage for {prefix}"


@pytest.mark.skipif(not HAVE_BS4, reason="beautifulsoup4 not installed")
def test_archive_index_real_tournaments_link_to_existing_files_no_dead_links():
    html = (DOCS / "tournaments" / "index.html").read_text(encoding="utf-8")
    assert "NEO GOLF DATA - 공사중" not in html, "archive index itself must no longer be the placeholder stub"
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".archive-card")
    assert len(cards) == 5, f"expected exactly 5 archive cards (3 real + 2 placeholder-only), got {len(cards)}"

    all_hrefs = [a["href"] for a in soup.select("a[href]")]
    for href in all_hrefs:
        assert href not in ("", "#"), f"placeholder/dead href found: {href!r}"
        assert not href.startswith("javascript:"), f"javascript: href found: {href!r}"
        if href.startswith("/"):
            target = DOCS / href.lstrip("/") / "index.html"
            assert target.exists(), f"archive link points to a nonexistent page: {href} (expected {target})"

    real_names = {
        "제26회 하이트진로 챔피언십", "하나금융그룹 챔피언십", "KB금융 골든라이프 챔피언십",
        "OK저축은행 읏맨 오픈", "제15회 KG 레이디스 오픈",
    }
    placeholder_names = set()
    for card in cards:
        h2 = card.select_one("h2")
        name = h2.get_text(strip=True)
        link = h2.find("a")
        if name in real_names:
            assert link is not None, f"{name}: real tournament must have a clickable name link"
            target = DOCS / link["href"].lstrip("/") / "index.html"
            assert target.exists(), f"{name}: name link target missing: {link['href']}"
            page_html = target.read_text(encoding="utf-8")
            assert "NEO GOLF DATA - 공사중" not in page_html, f"{name}: name link points to a placeholder stub, not a real record"
            assert card.select(".stage-links a"), f"{name}: expected at least one real stage link"
        elif name in placeholder_names:
            assert link is None, f"{name}: has no real record -- its name must not be a dead/fake link"
            assert "실제 기록 준비 중" in card.get_text(), f"{name}: must show an honest placeholder status, not pretend to have a record"
            assert not card.select(".stage-links a"), f"{name}: must not expose fabricated stage links"


@pytest.mark.skipif(not HAVE_BS4, reason="beautifulsoup4 not installed")
def test_archive_card_stage_links_match_real_directories_on_disk():
    html = (DOCS / "tournaments" / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    not_ready_markers = (
        "NEO GOLF DATA - 공사중", "아직 시작 전", "공식 FINAL 데이터가 아직 없습니다",
        'neo-stage-publication-ready" content="false"', 'neo-mock-data" content="true"',
    )
    for card in soup.select(".archive-card"):
        for a in card.select(".stage-links a"):
            href = a["href"]
            target = DOCS / href.lstrip("/") / "index.html"
            assert target.exists(), f"stage link {href} has no corresponding file on disk"
            target_html = target.read_text(encoding="utf-8")
            for marker in not_ready_markers:
                assert marker not in target_html, (
                    f"stage link {href} points to a not-yet-real or self-flagged "
                    f"not-publication-ready page (found {marker!r}) -- 존재하지 않거나 "
                    "준비되지 않은 기록을 실제 기록처럼 노출하면 안 된다"
                )


def test_hitejinro_deep_dive_mock_page_excluded_from_archive_despite_existing_on_disk():
    """2026100005/deep-dive/index.html self-flags neo-stage-publication-ready=false
    and neo-mock-data=true -- it must never appear as a stage link anywhere,
    even though the file itself is untouched (legacy content, left exactly as
    found; this test only asserts it isn't newly exposed via the archive)."""
    html = (DOCS / "tournaments" / "index.html").read_text(encoding="utf-8")
    assert "/tournaments/2026/2026100005/deep-dive/" not in html
    mock_path = DOCS / "tournaments" / "2026" / "2026100005" / "deep-dive" / "index.html"
    mock_html = mock_path.read_text(encoding="utf-8")
    assert 'neo-mock-data" content="true"' in mock_html, "sanity: the file should still self-flag as mock (untouched)"


def test_hitejinro_public_stages_are_exactly_pre_r1_r2_r3_fr():
    """하이트진로 archive navigation correction: 최종 검증(verification) and
    코스 분석(course-analysis) are real, publication-ready pages (unlike
    deep-dive) but are a deliberate editorial exclusion from public
    navigation -- not an auto-discovery judgment call. This locks the
    public stage set exactly, so a future archive rebuild can't silently
    re-surface either page even if some other heuristic would call them
    "real". Files must still exist on disk -- 파일 삭제 금지."""
    html = (DOCS / "tournaments" / "index.html").read_text(encoding="utf-8")
    if HAVE_BS4:
        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one('.archive-card:has(h2:-soup-contains("하이트진로"))')
        assert card is not None, "하이트진로 archive card not found"
        labels = [a.get_text(strip=True) for a in card.select(".stage-links a")]
        assert labels == ["사전 분석", "R1", "R2", "R3", "FR"], labels
        name_link = card.select_one("h2 a")
        assert name_link is not None
        assert "2026100005/fr/" in name_link["href"], "하이트진로 name must still enter at FR"
    assert "/tournaments/2026/2026100005/verification/" not in html
    assert "/tournaments/2026/2026100005/course-analysis/" not in html
    assert "최종 검증" not in html
    assert "코스 분석" not in html

    for other_dirname, expected_count in [
        ("2026090002", 5),   # pre, r1, r2, r3, final
        ("2026090003", 6),   # pre, r1, r2, r3, fr, final
        ("ok-savings-bank-open", 4),   # pre, r1, r2, r3 (no final -- never produced)
        ("kg-ladies-open", 5),   # pre, r1, r2, r3, final
    ]:
        count = html.count(f"/tournaments/2026/{other_dirname}/")
        assert count >= expected_count, (
            f"{other_dirname}: expected at least {expected_count} stage links unchanged, "
            f"found {count} occurrences in archive HTML"
        )

    # files must still exist on disk -- excluding from navigation is not deletion
    verification_path = DOCS / "tournaments" / "2026" / "2026100005" / "verification" / "index.html"
    course_analysis_path = DOCS / "tournaments" / "2026" / "2026100005" / "course-analysis" / "index.html"
    assert verification_path.exists(), "verification/index.html must NOT be deleted"
    assert course_analysis_path.exists(), "course-analysis/index.html must NOT be deleted"
    # and their content must be untouched (this turn only removes navigation links)
    v_html = verification_path.read_text(encoding="utf-8")
    c_html = course_analysis_path.read_text(encoding="utf-8")
    assert "최종 검증" in v_html or "검증" in v_html  # sanity: still the real page, not emptied
    assert len(c_html) > 1000  # sanity: still the real page, not emptied


def test_no_public_page_links_to_hitejinro_verification_or_course_analysis():
    """Section: HOME이나 다른 공개 페이지에 verification/course-analysis로
    들어가는 링크가 있다면 함께 제거한다. Scans every public page this
    feature controls (HOME, archive index, HJ scaffold)."""
    pages = [DOCS / "index.html", DOCS / "tournaments" / "index.html",
             DOCS / "tournaments" / "2026" / "2026100004" / "index.html"]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert "/tournaments/2026/2026100005/verification/" not in html, f"{page} links to verification"
        assert "/tournaments/2026/2026100005/course-analysis/" not in html, f"{page} links to course-analysis"


def test_hj_scaffold_has_no_blocked_probability_output():
    """2026-10-07 nav-simplification turn also rewrote this page's own
    copy (operator instruction): PRE is real and published now, so the
    old "경기 방식에 맞춘 NEO 분석은 준비되는 대로 공개합니다"/"아직 공개된
    분석은 없습니다" claims are false and were removed -- see
    build_hj_scaffold()'s own docstring. The "no blocked probability
    output" and "no leaked internal term" checks (the actual point of
    this test) still apply to the new copy unchanged."""
    path = DOCS / "tournaments" / "2026" / "2026100004" / "index.html"
    assert path.exists(), "2026100004 HJ scaffold must exist"
    html = path.read_text(encoding="utf-8")
    assert_no_blocked_probability_output(html, model_validated=False, label="2026100004 HJ scaffold")
    assert "변형 스테이블포드 방식으로 진행됩니다" in html
    assert "/tournaments/2026/2026100004/pre/" in html, "scaffold must link to the real, published PRE page"
    for leaked_internal_term in ("예측 잠금", "모델 검증", "Stableford Adapter", "publication gate", "검증될 때까지"):
        assert leaked_internal_term not in html, f"internal term leaked into HJ public copy: {leaked_internal_term!r}"


def test_home_locked_copy_uses_reader_language_not_internal_terms():
    """HOME's copy changed 2026-10-07 (operator instruction: ship the real
    HJ homepage now instead of holding it on a "준비되는 대로 공개" /
    예측 잠금 placeholder -- see scripts/225+226 and build_tournament_
    archive_and_hj_scaffold.py's build_home()). The old placeholder-era
    assertion ("준비되는 대로 공개합니다") is intentionally gone from HOME
    -- it is still asserted on the untouched HJ scaffold page in
    test_hj_scaffold_has_no_blocked_probability_output above. This test
    now locks the NEW real copy instead, keeping the internal-term leak
    check (still valid, still the point of this test)."""
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "변형 스테이블포드 방식으로 진행됩니다" in html
    assert "같은 경기력도 Stableford에서는 가치가 달라진다" in html
    for leaked_internal_term in ("예측 잠금", "모델 검증", "Stableford Adapter", "publication gate", "검증될 때까지"):
        assert leaked_internal_term not in html, f"internal term leaked into HOME public copy: {leaked_internal_term!r}"


# ---- Section J: automated visible-text public-term audit -----------------
PUBLIC_TERM_DENYLIST = [
    "M4", "inference", "pipeline", "reader", "artifact", "manifest", "snapshot",
    "hash", "JSON", "CSV", "SQLite", "gameCode", "SOURCE_GAP", "registration",
    "transform", "homography", "affine", "viewBox", "map_x", "map_y", "pp_x", "pp_y",
    "Monte Carlo", "random seed", "feature engineering", "scaffold", "stub",
    "guard", "gate", "PASS", "FAIL", "HOLD", "LOCK", "PUBLIC", "DEV",
    "model version", "walk-forward", "backtest", "calibration", "reconciliation",
    "parser", "renderer", "generator", "deploy", "branch", "commit", "repository",
    "GitHub", "Playwright", "QA", "endpoint", "scraper", "crawler",
    "publication gate", "Stableford Adapter", "예측 잠금", "neo-mock-data",
    "neo-stage-publication-ready", "검증될 때까지",
]


# 2026100005/deep-dive/ visibly discloses "더미 성적 데이터 · 레이아웃 미리보기"
# (dummy performance data / layout preview) next to several of its course-fit
# stat callouts, and "더미 데이터" once in its page-head badge -- this is an
# HONEST disclosure (not jargon to hide) and must stay exactly where it is,
# confined to that one still-excluded-from-navigation page. If it ever shows
# up anywhere else, that's either leaked fake data on a real page or a
# mislabeled real page -- either way a real bug, not a term to silently allow.
HONEST_MOCK_DISCLOSURE_TERMS = ["더미"]
HONEST_MOCK_DISCLOSURE_ALLOWED_PAGE = DOCS / "tournaments" / "2026" / "2026100005" / "deep-dive" / "index.html"


@pytest.mark.skipif(not HAVE_BS4, reason="beautifulsoup4 not installed")
def test_dummy_data_disclosure_confined_to_the_known_mock_page_only():
    for page in _all_public_tournament_pages():
        html = page.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(" ")
        for term in HONEST_MOCK_DISCLOSURE_TERMS:
            found = term in text
            if page == HONEST_MOCK_DISCLOSURE_ALLOWED_PAGE:
                assert found, f"expected honest '{term}' disclosure missing from {page} -- do not silently remove it"
            else:
                assert not found, f"'{term}' (dummy-data disclosure) leaked onto {page} -- real page mislabeled, or fake data copied in"


def _all_public_tournament_pages():
    pages = [DOCS / "index.html", DOCS / "tournaments" / "index.html"]
    pages.append(DOCS / "tournaments" / "2026" / "2026100004" / "index.html")
    for gc in ("2026090002", "2026090003", "2026100005", "ok-savings-bank-open", "kg-ladies-open"):
        base = DOCS / "tournaments" / "2026" / gc
        if base.exists():
            pages.extend(sorted(base.rglob("index.html")))
    return pages


@pytest.mark.skipif(not HAVE_BS4, reason="beautifulsoup4 not installed")
def test_public_term_audit_zero_hits_in_visible_text():
    """Visible-text-only scan (script/style stripped) across EVERY public
    tournament page, for internal dev/model terms a reader never needs to
    see -- including 2026100005/deep-dive/, whose own 'DATA QUALITY'/PASSx3
    block was cleaned up to reader language ('자료 안내'/'확인 완료'). The page
    stays excluded from archive click-through reachability regardless (see
    test_hitejinro_deep_dive_mock_page_excluded_from_archive_despite_existing_on_disk)
    because it is still substantively mock content (neo-mock-data=true) --
    this test only proves the jargon-term denylist is clean everywhere,
    it does not claim the page is ready for navigation."""
    hits = []
    for page in _all_public_tournament_pages():
        html = page.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(" ")
        for term in PUBLIC_TERM_DENYLIST:
            for m in re.finditer(re.escape(term), text, re.IGNORECASE):
                snippet = text[max(0, m.start() - 40):m.start() + 60].replace("\n", " ")
                hits.append((str(page.relative_to(REPO_ROOT)), term, snippet))
    assert hits == [], "internal term(s) leaked into public visible text:\n" + "\n".join(
        f"  {p} | {t!r} | ...{s}..." for p, t, s in hits
    )


def test_root_home_points_at_hj_as_current_tournament_and_has_no_blocked_probability_output():
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    assert_no_blocked_probability_output(html, model_validated=False, label="root HOME")
    assert 'content="current-tournament-v1"' in html, "root HOME must keep the current-tournament-v1 owner marker"
    assert "HJ중공업" in html
    assert "/tournaments/2026/2026100004/" in html
    assert "/tournaments/" in html, "root HOME must link to the 대회 기록 archive"
