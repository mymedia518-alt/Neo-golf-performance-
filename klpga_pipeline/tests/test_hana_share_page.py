"""Regression tests for docs/share/index.html -- a cache-bust-only
route added because Threads' cached link-preview for
www.neogolfdata.com kept showing the old KB FINAL page even after root
HOME itself was fixed. Requirements: shows the real NEO GOLF DATA
homepage screen, never references the KB FINAL image/text, carries its
own fresh OG tags (title/description/url/image), and never modifies
root HOME or the PRE/R1 pages."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"
SCRIPTS_DIR = KLPGA_ROOT / "scripts"

HOME_PAGE = REPO_ROOT / "docs" / "index.html"
SHARE_PAGE = REPO_ROOT / "docs" / "share" / "index.html"
PRE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"
R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
OG_IMAGE = REPO_ROOT / "docs" / "assets" / "og-neo-golf-data.png"
KB_FINAL_IMAGES = [
    REPO_ROOT / "docs" / "assets" / "우승 (3).png",
    REPO_ROOT / "docs" / "assets" / "kb-2026090003-r3-forecast-vs-final.png",
]


def _rebuild() -> None:
    subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "156_build_home_page.py")],
        check=True,
        cwd=str(KLPGA_ROOT),
    )


def test_share_page_exists_and_is_a_real_file():
    _rebuild()
    assert SHARE_PAGE.is_file(), f"expected {SHARE_PAGE} to exist"


def test_share_page_shows_the_real_homepage_screen():
    """Requirement 2: share/ must display the actual real homepage
    screen, not a stripped-down or fabricated substitute -- its body
    (everything from <body> onward) must be byte-identical to root
    HOME's own body."""
    _rebuild()
    home_html = HOME_PAGE.read_text(encoding="utf-8")
    share_html = SHARE_PAGE.read_text(encoding="utf-8")
    home_body = home_html[home_html.index("<body>"):]
    share_body = share_html[share_html.index("<body>"):]
    assert home_body == share_body, "share/ body must be byte-identical to root HOME's body"
    assert share_html.count("<tr>") >= 108


def test_share_page_never_references_kb_final():
    """Requirement 3: the KB FINAL *tournament* (its image, its full
    name, its own game code) must never appear. This does NOT forbid
    "KB금융그룹" standing alone -- that is a real, verified sponsor name
    for one of Hana's own R1 players (already present on root HOME
    too, see docs/index.html), unrelated to the KB FINAL tournament."""
    _rebuild()
    html = SHARE_PAGE.read_text(encoding="utf-8")
    assert "우승 (3).png" not in html
    assert "kb-2026090003" not in html
    assert "2026090003" not in html
    assert "골든라이프" not in html
    assert "KB금융그룹 챔피언십" not in html


def test_share_page_og_tags_are_exactly_as_specified():
    """Requirements 4-6: og:title/description/url exact values."""
    _rebuild()
    html = SHARE_PAGE.read_text(encoding="utf-8")
    assert '<meta property="og:title" content="NEO GOLF DATA">' in html
    assert '<meta property="og:description" content="KLPGA 공식 데이터 기반 골프 분석">' in html
    assert '<meta property="og:url" content="https://www.neogolfdata.com/share/">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html


def test_share_page_uses_a_new_image_never_the_kb_final_image():
    """Requirement 7: representative image must be new, not KB FINAL."""
    _rebuild()
    html = SHARE_PAGE.read_text(encoding="utf-8")
    match = re.search(r'<meta property="og:image" content="([^"]+)">', html)
    assert match, "share page must declare an og:image"
    og_image_url = match.group(1)
    assert "og-neo-golf-data.png" in og_image_url
    assert "우승" not in og_image_url and "kb-2026090003" not in og_image_url

    assert OG_IMAGE.is_file(), f"expected new share-page image at {OG_IMAGE}"
    import hashlib

    new_hash = hashlib.sha256(OG_IMAGE.read_bytes()).hexdigest()
    for kb_image in KB_FINAL_IMAGES:
        if kb_image.is_file():
            kb_hash = hashlib.sha256(kb_image.read_bytes()).hexdigest()
            assert new_hash != kb_hash, f"share-page image must not be byte-identical to {kb_image.name}"


def test_root_home_pre_and_r1_pages_are_unaffected_by_the_share_route():
    """Requirement 9: adding /share/ must never modify root HOME, PRE,
    or R1 -- 156_build_home_page.py must only ever write DOCS_INDEX and
    SHARE_PAGE."""
    before_home = HOME_PAGE.read_text(encoding="utf-8")
    before_pre = PRE_PAGE.read_text(encoding="utf-8")
    before_r1 = R1_PAGE.read_text(encoding="utf-8")

    _rebuild()

    assert HOME_PAGE.read_text(encoding="utf-8") == before_home, "root HOME must be unchanged by building /share/"
    assert PRE_PAGE.read_text(encoding="utf-8") == before_pre, "PRE must be unchanged by building /share/"
    assert R1_PAGE.read_text(encoding="utf-8") == before_r1, "R1 must be unchanged by building /share/"

    source = (SCRIPTS_DIR / "156_build_home_page.py").read_text(encoding="utf-8")
    write_targets = sorted(set(re.findall(r"(\w+)\.write_text\(", source)))
    assert write_targets == ["DOCS_INDEX", "SHARE_PAGE", "SHARE_TOURNAMENT_PAGE", "SHORT_SHARE_PAGE"], (
        f"156_build_home_page.py must only ever write these four targets, found: {write_targets}"
    )
