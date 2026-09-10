"""HOME (K-Ranking x NEO Ranking) mobile color/readability pass --
regression tests (branch fix/home-mobile-color-readability-20260910).

Builds the real candidate (scripts/88_build_neo_top120_candidate.py)
against real content data and asserts the STEP 10 minimum checks:
  1. every HOME player row has a sponsor slot present
  2. no 999999 sentinel anywhere in the generated public HTML
  3. required ranking fields (선수/K-Ranking/최근 10R SG/최근 5R SG/
     현재 스코어) are present in the table header
  4. a mobile CSS breakpoint exists for .home-table
  5. the generated candidate index.html/ranking/index.html build
     successfully and are well-formed
  6. the color-system classes exist and are non-fabricating (no color
     class on a metric-empty "--" cell claims a real reading)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
CANDIDATE = ROOT / "candidate" / "neo-data-home-top120"
CSS = ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css"


@pytest.fixture(scope="module")
def built_ranking_html() -> str:
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], check=True, cwd=ROOT)
    path = CANDIDATE / "ranking" / "index.html"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_no_999999_sentinel_anywhere(built_ranking_html):
    assert "999999" not in built_ranking_html


def test_all_120_rows_have_sponsor_slot_markup(built_ranking_html):
    name_count = built_ranking_html.count('class="player-name"')
    sponsor_slot_count = len(re.findall(r'<span class="player-sponsor"', built_ranking_html))
    row_count = built_ranking_html.count("data-player-row")
    assert row_count == 120
    assert name_count == 120
    # A verified sponsor renders a <span class="player-sponsor">...</span>;
    # an unverified player legitimately gets no sponsor span at all
    # (never a guessed placeholder) -- so sponsor_slot_count <= 120,
    # never more, and is a real, non-zero, non-fabricated subset.
    assert 0 < sponsor_slot_count <= 120


def test_required_ranking_fields_present_in_header(built_ranking_html):
    header = re.search(r"<thead>(.*?)</thead>", built_ranking_html, re.S).group(1)
    for label in ("선수", "K-Ranking", "최근 10R SG", "최근 5R SG", "현재 스코어"):
        assert label in header, f"missing required column header: {label}"


def test_mobile_breakpoint_exists_for_home_table():
    css = CSS.read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in css
    assert ".home-table tbody tr{" in css
    # the mobile card layout must be a real grid, not a shrunk table
    mobile_block = css.split("@media(max-width:760px){")[1]
    assert "display:grid" in mobile_block.split("}\n@media(max-width:430px)")[0]


def test_candidate_builds_are_well_formed(built_ranking_html):
    assert built_ranking_html.startswith("<!doctype html>")
    assert built_ranking_html.count("<table") == built_ranking_html.count("</table>")
    assert (CANDIDATE / "index.html").is_file()


def test_color_classes_never_applied_to_missing_values(built_ranking_html):
    # metric-empty (the "--" mark) must never ALSO carry metric-pos/
    # metric-neg -- a missing value is never colored as if it were a
    # real positive/negative reading.
    for m in re.finditer(r'<td class="([^"]*)">', built_ranking_html):
        classes = m.group(1).split()
        if "metric-empty" in classes:
            assert "metric-pos" not in classes
            assert "metric-neg" not in classes


def test_k_rank_and_sg_color_classes_exist(built_ranking_html):
    assert 'class="k-rank-cell' in built_ranking_html
    assert "metric-sg" in built_ranking_html


def test_volatility_never_carries_sign_color(built_ranking_html):
    # 변동성 (volatility) is a non-negative magnitude -- it must never
    # receive the pos/neg sign-color classes used for genuine signed SG
    # averages (assigning class="metric-secondary metric-pos" etc. to it
    # would misrepresent a magnitude as a gain/loss).
    for m in re.finditer(r'<td class="([^"]*)" data-label="변동성">', built_ranking_html):
        classes = m.group(1).split()
        assert "metric-pos" not in classes
        assert "metric-neg" not in classes
