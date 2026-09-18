"""LIVE RED TEAM FIX: root HOME must mirror Hana's real, evidence-backed
CURRENT stage -- not a hardcoded R1 duplicate. Before this fix, HOME
always embedded R1's own leaderboard regardless of which stage was
actually live, so a visitor clicking "홈" while R2 was the real current
stage still landed back on stale R1 data with no way forward. See
klpga.website_v2.hana_home_stage_router (hana_current_stage() /
current_stage_main_html()) for the real, evidence-based stage
detection this test exercises.

156_build_home_page.py now reads its <main> content directly from
whichever stage's own real page is currently current (r2, since its
gated post_r2_final_forecast artifact exists) -- verbatim, never
recomputed -- so this test compares HOME's body against that same real
page's own <main> region, byte for byte."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"
SCRIPTS_DIR = KLPGA_ROOT / "scripts"

HOME_PAGE = REPO_ROOT / "docs" / "index.html"
R2_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r2" / "index.html"

_MAIN_RE = re.compile(r"<main>.*?</main>", re.S)
_TBODY_RE = re.compile(r"<tbody>(.*?)</tbody>", re.S)
_ROW_RE = re.compile(r"<tr>.*?</tr>", re.S)


def _rebuild() -> None:
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "156_build_home_page.py")], check=True, cwd=str(KLPGA_ROOT))


def _rows(html: str) -> list[str]:
    match = _TBODY_RE.search(html)
    assert match, "no <tbody> found"
    return _ROW_RE.findall(match.group(1))


def test_home_current_stage_is_r2():
    from klpga.website_v2.hana_home_stage_router import hana_current_stage
    sys.path.insert(0, str(KLPGA_ROOT / "src"))
    assert hana_current_stage() == "r2"


def test_home_and_r2_main_content_are_byte_identical():
    _rebuild()
    home_html = HOME_PAGE.read_text(encoding="utf-8")
    r2_html = R2_PAGE.read_text(encoding="utf-8")
    home_main = _MAIN_RE.search(home_html)
    r2_main = _MAIN_RE.search(r2_html)
    assert home_main and r2_main
    assert home_main.group(0) == r2_main.group(0), (
        "HOME's <main> must mirror the current stage (r2) page's own <main> verbatim"
    )


def test_home_and_r2_leaderboard_rows_are_byte_identical():
    _rebuild()
    home_rows = _rows(HOME_PAGE.read_text(encoding="utf-8"))
    r2_rows = _rows(R2_PAGE.read_text(encoding="utf-8"))
    assert len(home_rows) == 102, f"homepage must show all 102 R2 score rows, got {len(home_rows)}"
    assert len(r2_rows) == 102, f"R2 page itself must show 102 rows, got {len(r2_rows)}"
    assert home_rows == r2_rows


def test_home_page_shows_leaderboard_without_extra_navigation():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "leaderboard-table" in html, "homepage must embed the current-stage leaderboard table directly"
    assert html.count("<tr>") >= 102


def test_home_page_header_clearly_identifies_tournament_and_round():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "하나금융그룹 챔피언십" in html
    assert "R2 결과" in html


def test_home_page_tournaments_nav_points_at_r2():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert '<a href="/tournaments/2026/2026090002/r2/">대회</a>' in html


def test_home_page_keeps_all_five_stage_links():
    html = HOME_PAGE.read_text(encoding="utf-8")
    for label in ("사전 분석 PRE", "R1", "R2", "R3", "FR"):
        assert label in html


def test_pre_r1_r2_pages_and_json_data_untouched_by_home_rebuild():
    """Rebuilding the homepage must never touch PRE/R1/R2's own pages or
    any JSON data file -- 156 only ever writes docs/index.html and,
    since the /share/ cache-bust route was added, the 3 share routes."""
    source = (SCRIPTS_DIR / "156_build_home_page.py").read_text(encoding="utf-8")
    assert "write_text" in source
    write_targets = sorted(set(re.findall(r"(\w+)\.write_text\(", source)))
    assert write_targets == ["DOCS_INDEX", "SHARE_PAGE", "SHARE_TOURNAMENT_PAGE", "SHORT_SHARE_PAGE"], (
        f"156_build_home_page.py must only ever call write_text on these four targets, found writes to: {write_targets}"
    )
