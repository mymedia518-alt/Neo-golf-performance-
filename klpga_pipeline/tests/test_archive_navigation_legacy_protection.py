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

    real_names = {"제26회 하이트진로 챔피언십", "하나금융그룹 챔피언십", "KB금융 골든라이프 챔피언십"}
    placeholder_names = {"OK저축은행 읏맨 오픈", "제15회 KG 레이디스 오픈"}
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
    for card in soup.select(".archive-card"):
        for a in card.select(".stage-links a"):
            href = a["href"]
            target = DOCS / href.lstrip("/") / "index.html"
            assert target.exists(), f"stage link {href} has no corresponding file on disk"
            assert "NEO GOLF DATA - 공사중" not in target.read_text(encoding="utf-8"), (
                f"stage link {href} points to a placeholder stub -- 존재하지 않는 라운드를 "
                "실제 기록처럼 노출하면 안 된다"
            )


def test_hj_scaffold_has_no_blocked_probability_output():
    path = DOCS / "tournaments" / "2026" / "2026100004" / "index.html"
    assert path.exists(), "2026100004 HJ scaffold must exist"
    html = path.read_text(encoding="utf-8")
    assert_no_blocked_probability_output(html, model_validated=False, label="2026100004 HJ scaffold")
    assert "예측 잠금" in html, "HJ scaffold must explicitly disclose the locked-prediction state"


def test_root_home_points_at_hj_as_current_tournament_and_has_no_blocked_probability_output():
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    assert_no_blocked_probability_output(html, model_validated=False, label="root HOME")
    assert 'content="current-tournament-v1"' in html, "root HOME must keep the current-tournament-v1 owner marker"
    assert "HJ중공업" in html
    assert "/tournaments/2026/2026100004/" in html
    assert "/tournaments/" in html, "root HOME must link to the 대회 기록 archive"
