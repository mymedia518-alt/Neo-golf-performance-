"""Regression tests for docs/share/2026090002/index.html -- a second,
tournament-named share route (operator instruction, distinct from the
generic docs/share/index.html cache-bust page) carrying Hana-specific
OG copy and a real screenshot of the actual R1 first screen as its
representative image. Requirements: shows the real R1 108-player
screen, never references KB FINAL, carries the exact specified OG
tags, uses a genuinely new (real-screenshot, not KB FINAL) image, and
never modifies root HOME / the generic share page / PRE / R1."""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"
SCRIPTS_DIR = KLPGA_ROOT / "scripts"

HOME_PAGE = REPO_ROOT / "docs" / "index.html"
SHARE_PAGE = REPO_ROOT / "docs" / "share" / "index.html"
SHARE_TOURNAMENT_PAGE = REPO_ROOT / "docs" / "share" / "2026090002" / "index.html"
PRE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"
R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
R1_OG_IMAGE = REPO_ROOT / "docs" / "assets" / "hana-2026090002-r1-og.png"
GENERIC_OG_IMAGE = REPO_ROOT / "docs" / "assets" / "og-neo-golf-data.png"
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_tournament_share_page_exists():
    _rebuild()
    assert SHARE_TOURNAMENT_PAGE.is_file(), f"expected {SHARE_TOURNAMENT_PAGE} to exist"


def test_tournament_share_page_shows_the_real_r1_108_player_screen():
    """Requirement 3: same R1 108-player screen as docs/index.html."""
    _rebuild()
    home_html = HOME_PAGE.read_text(encoding="utf-8")
    page_html = SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8")
    home_body = home_html[home_html.index("<body>"):]
    page_body = page_html[page_html.index("<body>"):]
    assert home_body == page_body, "tournament share page body must be byte-identical to root HOME's body"
    assert page_html.count("<tr>") >= 108


def test_tournament_share_page_og_tags_are_exactly_as_specified():
    """Requirement 4: exact OG tag values."""
    _rebuild()
    html = SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8")
    assert '<meta property="og:title" content="NEO GOLF DATA · 하나금융그룹 챔피언십 R1">' in html
    assert '<meta property="og:description" content="하나금융그룹 챔피언십 R1 공식 결과와 NEO 분석">' in html
    assert '<meta property="og:url" content="https://www.neogolfdata.com/share/2026090002/">' in html
    assert '<meta property="og:image" content="https://www.neogolfdata.com/assets/hana-2026090002-r1-og.png">' in html


def test_tournament_share_page_image_is_a_real_r1_screenshot_never_kb_final():
    """Requirements 5-6: the image must be the new R1-screenshot file,
    never KB FINAL's image, and KB FINAL text must never appear."""
    _rebuild()
    html = SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8")
    assert "우승 (3).png" not in html
    assert "kb-2026090003" not in html
    assert "골든라이프" not in html
    assert "KB금융그룹 챔피언십" not in html

    assert R1_OG_IMAGE.is_file(), f"expected real R1 screenshot at {R1_OG_IMAGE}"
    r1_hash = _sha256(R1_OG_IMAGE)
    for kb_image in KB_FINAL_IMAGES:
        if kb_image.is_file():
            assert r1_hash != _sha256(kb_image), f"R1 OG image must not be byte-identical to {kb_image.name}"
    if GENERIC_OG_IMAGE.is_file():
        assert r1_hash != _sha256(GENERIC_OG_IMAGE), "R1 OG image must be its own distinct file, not the generic brand card"


def test_root_generic_share_pre_and_r1_pages_are_unaffected():
    """Requirement 9 (implicit scope): adding the tournament share
    route must never modify root HOME, the generic /share/ page, PRE,
    or R1 -- 156_build_home_page.py must only ever write DOCS_INDEX,
    SHARE_PAGE, and SHARE_TOURNAMENT_PAGE."""
    before_home = HOME_PAGE.read_text(encoding="utf-8")
    before_share = SHARE_PAGE.read_text(encoding="utf-8")
    before_pre = PRE_PAGE.read_text(encoding="utf-8")
    before_r1 = R1_PAGE.read_text(encoding="utf-8")

    _rebuild()

    assert HOME_PAGE.read_text(encoding="utf-8") == before_home
    assert SHARE_PAGE.read_text(encoding="utf-8") == before_share
    assert PRE_PAGE.read_text(encoding="utf-8") == before_pre
    assert R1_PAGE.read_text(encoding="utf-8") == before_r1

    source = (SCRIPTS_DIR / "156_build_home_page.py").read_text(encoding="utf-8")
    write_targets = sorted(set(re.findall(r"(\w+)\.write_text\(", source)))
    assert write_targets == ["DOCS_INDEX", "SHARE_PAGE", "SHARE_TOURNAMENT_PAGE", "SHORT_SHARE_PAGE"], (
        f"156_build_home_page.py must only ever write these four targets, found: {write_targets}"
    )
