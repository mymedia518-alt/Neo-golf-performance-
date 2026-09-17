"""Regression tests for docs/2026090002/index.html -- a short-URL
alias for docs/share/2026090002/index.html (operator instruction).
Requirements: exactly the same real R1 108-player screen, exactly the
same representative image, only og:url differs (the short path
itself); adding it must never modify the existing tournament share
page, its OG image, root HOME, the generic /share/ page, PRE, or R1."""
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
SHORT_SHARE_PAGE = REPO_ROOT / "docs" / "2026090002" / "index.html"
PRE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"
R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
R1_OG_IMAGE = REPO_ROOT / "docs" / "assets" / "hana-2026090002-r1-og.png"


def _rebuild() -> None:
    subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "156_build_home_page.py")],
        check=True,
        cwd=str(KLPGA_ROOT),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_short_share_page_exists():
    _rebuild()
    assert SHORT_SHARE_PAGE.is_file(), f"expected {SHORT_SHARE_PAGE} to exist"


def test_short_share_page_body_is_byte_identical_to_tournament_share_page():
    """Requirement 2: exactly the same R1 108-player screen as
    docs/share/2026090002/index.html."""
    _rebuild()
    tournament_html = SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8")
    short_html = SHORT_SHARE_PAGE.read_text(encoding="utf-8")
    tournament_body = tournament_html[tournament_html.index("<body>"):]
    short_body = short_html[short_html.index("<body>"):]
    assert tournament_body == short_body, "short share page body must be byte-identical to /share/2026090002/'s body"
    assert short_html.count("<tr>") >= 108


def test_short_share_page_og_url_and_image_are_exactly_as_specified():
    """Requirement 3: og:url is the short path; og:image is the same
    existing R1 screenshot (not a new or different image)."""
    _rebuild()
    html = SHORT_SHARE_PAGE.read_text(encoding="utf-8")
    assert '<meta property="og:url" content="https://www.neogolfdata.com/2026090002/">' in html
    assert '<meta property="og:image" content="https://www.neogolfdata.com/assets/hana-2026090002-r1-og.png">' in html


def test_short_share_page_links_to_the_correct_real_image_file():
    """Requirement 5: the short-URL page's declared og:image must
    resolve to the actual, existing R1 screenshot file on disk -- the
    same file the tournament share page already uses, not a
    dangling/incorrect reference."""
    _rebuild()
    html = SHORT_SHARE_PAGE.read_text(encoding="utf-8")
    match = re.search(r'<meta property="og:image" content="([^"]+)">', html)
    assert match, "short share page must declare an og:image"
    assert match.group(1).endswith("/assets/hana-2026090002-r1-og.png")
    assert R1_OG_IMAGE.is_file(), f"expected the real R1 screenshot to exist at {R1_OG_IMAGE}"

    tournament_html = SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8")
    tournament_match = re.search(r'<meta property="og:image" content="([^"]+)">', tournament_html)
    assert tournament_match and tournament_match.group(1) == match.group(1), (
        "short share page must point at the exact same image URL as /share/2026090002/, not a copy or a new file"
    )


def test_short_share_page_never_references_kb_final():
    _rebuild()
    html = SHORT_SHARE_PAGE.read_text(encoding="utf-8")
    assert "우승 (3).png" not in html
    assert "kb-2026090003" not in html
    assert "골든라이프" not in html
    assert "KB금융그룹 챔피언십" not in html


def test_existing_tournament_share_page_and_its_image_are_unmodified():
    """Requirement 4: adding the short URL must never modify the
    existing /share/2026090002/ page or its representative image."""
    before_tournament_page = SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8")
    before_image_hash = _sha256(R1_OG_IMAGE)

    _rebuild()

    assert SHARE_TOURNAMENT_PAGE.read_text(encoding="utf-8") == before_tournament_page
    assert _sha256(R1_OG_IMAGE) == before_image_hash, "the R1 OG image file must not be modified"


def test_root_generic_share_pre_and_r1_pages_are_unaffected():
    """Adding the short-URL route must never modify root HOME, the
    generic /share/ page, PRE, or R1 -- 156_build_home_page.py must
    only ever write DOCS_INDEX, SHARE_PAGE, SHARE_TOURNAMENT_PAGE, and
    the new SHORT_SHARE_PAGE."""
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
