"""LIVE RED TEAM FIX: root HOME must mirror Hana's real, evidence-backed
CURRENT stage -- not a hardcoded R1 duplicate. Before this fix, HOME
always embedded R1's own leaderboard regardless of which stage was
actually live, so a visitor clicking "홈" while R2 was the real current
stage still landed back on stale R1 data with no way forward. See
klpga.website_v2.hana_home_stage_router (hana_current_stage() /
current_stage_main_html()) for the real, evidence-based stage
detection this test exercises.

156_build_home_page.py now reads its <main> content directly from
whichever stage's own real page is currently current -- verbatim,
never recomputed -- so this test compares HOME's body against that
same real page's own <main> region, byte for byte.

R3 -> FINAL PIPELINE UPDATE (operator instruction, 2026-09-19): the
real current stage has advanced to r3 (2026090002_R3_FROZEN_EVIDENCE.
json + 2026090002_POST_R4_FINAL_PREVIEW.json both now exist, built
from real official R3 evidence and the already-validated/promoted
R1SG_R2SG model reused exactly as promoted). These tests are updated
to the new real current-stage page (R3, 64 rows, no cut event) --
mirroring the same "current stage advances, tests track real evidence"
pattern already established when R1 -> R2 previously advanced this
same HOME.

FINAL BUILD UPDATE (2026-09-20): the real current stage has advanced
to `final` -- the write-once FinalTruth artifact
(2026090002_FINAL_TRUTH.json, scripts/178, built from the real official
4R leaderboard capture) now exists AND the real FINAL page
(docs/tournaments/2026/2026090002/final/index.html, scripts/181) has
been published -- see hana_home_stage_router.hana_current_stage()'s own
`final` check. These tests are updated to the new real current-stage
page (FINAL, 64 rows: 63 ACTIVE + 1 WD) -- the same "current stage
advances, tests track real evidence" pattern, now applied one stage
further."""
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
R3_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r3" / "index.html"
FINAL_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "final" / "index.html"

_MAIN_RE = re.compile(r"<main>.*?</main>", re.S)
_TBODY_RE = re.compile(r"<tbody>(.*?)</tbody>", re.S)
_ROW_RE = re.compile(r"<tr>.*?</tr>", re.S)


def _rebuild() -> None:
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "156_build_home_page.py")], check=True, cwd=str(KLPGA_ROOT))


def _rows(html: str) -> list[str]:
    match = _TBODY_RE.search(html)
    assert match, "no <tbody> found"
    return _ROW_RE.findall(match.group(1))


def test_home_current_stage_is_final():
    from klpga.website_v2.hana_home_stage_router import hana_current_stage
    sys.path.insert(0, str(KLPGA_ROOT / "src"))
    assert hana_current_stage() == "final"


def test_home_and_final_main_content_are_byte_identical():
    _rebuild()
    home_html = HOME_PAGE.read_text(encoding="utf-8")
    final_html = FINAL_PAGE.read_text(encoding="utf-8")
    home_main = _MAIN_RE.search(home_html)
    final_main = _MAIN_RE.search(final_html)
    assert home_main and final_main
    assert home_main.group(0) == final_main.group(0), (
        "HOME's <main> must mirror the current stage (final) page's own <main> verbatim"
    )


def test_home_and_final_leaderboard_rows_are_byte_identical():
    _rebuild()
    home_rows = _rows(HOME_PAGE.read_text(encoding="utf-8"))
    final_rows = _rows(FINAL_PAGE.read_text(encoding="utf-8"))
    assert len(home_rows) == 64, f"homepage must show all 64 FINAL rows (63 ACTIVE + 1 WD), got {len(home_rows)}"
    assert len(final_rows) == 64, f"FINAL page itself must show 64 rows, got {len(final_rows)}"
    assert home_rows == final_rows


def test_home_page_shows_leaderboard_without_extra_navigation():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "leaderboard-table" in html, "homepage must embed the current-stage leaderboard table directly"
    assert html.count("<tr>") >= 64


def test_home_page_header_clearly_identifies_tournament_and_round():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "하나금융그룹 챔피언십" in html
    assert "FINAL" in html


def test_home_page_tournaments_nav_points_at_final():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert '<a href="/tournaments/2026/2026090002/final/">대회</a>' in html


def test_home_page_keeps_all_stage_links():
    html = HOME_PAGE.read_text(encoding="utf-8")
    for label in ("사전 분석 PRE", "R1", "R2", "R3", "FINAL"):
        assert label in html


def test_home_page_shows_the_real_winner():
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "김민선7" in html


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
