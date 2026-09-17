"""Operator instruction: root HOME must show the current tournament's
R1 leaderboard directly (all 108 players, no extra click required),
and its displayed data must be 100% identical to the dedicated R1
page's own leaderboard -- same rank/T-tie notation, same flags, same
sponsors, same To-Par-only score, same NEO 경기력/컷 통과율/TOP20/TOP10/
TOP5/우승확률 values, in the same player order.

156_build_home_page.py and 151_build_hana_r1_page.py each read the
same source JSON independently (self-contained-builder convention --
see 156's module docstring) and apply the identical formatting rules.
This test proves that independence didn't cause any drift: it builds
both pages for real and compares their rendered <tbody> content
directly, cell for cell."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"
SCRIPTS_DIR = KLPGA_ROOT / "scripts"

HOME_PAGE = REPO_ROOT / "docs" / "index.html"
R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"

_TBODY_RE = re.compile(r"<tbody>(.*?)</tbody>", re.S)
_ROW_RE = re.compile(r"<tr>.*?</tr>", re.S)


def _rebuild_both() -> None:
    for script in ("156_build_home_page.py", "151_build_hana_r1_page.py"):
        subprocess.run([sys.executable, str(SCRIPTS_DIR / script)], check=True, cwd=str(KLPGA_ROOT))


def _rows(html_path: Path) -> list[str]:
    html = html_path.read_text(encoding="utf-8")
    match = _TBODY_RE.search(html)
    assert match, f"no <tbody> found in {html_path}"
    return _ROW_RE.findall(match.group(1))


def test_home_and_r1_leaderboard_rows_are_byte_identical():
    _rebuild_both()
    home_rows = _rows(HOME_PAGE)
    r1_rows = _rows(R1_PAGE)
    assert len(home_rows) == 108, f"homepage must show all 108 R1 rows, got {len(home_rows)}"
    assert len(r1_rows) == 108, f"R1 page itself must show 108 rows, got {len(r1_rows)}"
    assert home_rows == r1_rows, (
        "homepage leaderboard rows diverge from the R1 page's own rows -- "
        "every rank/name/flag/sponsor/score/probability cell must match exactly"
    )


def test_home_page_shows_leaderboard_without_extra_navigation():
    """Requirement 1: visiting root HOME must show the R1 leaderboard
    immediately, with no extra click to a separate R1 URL needed."""
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "leaderboard-table" in html, "homepage must embed the R1 leaderboard table directly"
    assert html.count("<tr>") >= 108


def test_home_page_header_clearly_identifies_tournament_and_round():
    """Requirement 5: the top of the homepage must clearly show the
    tournament name and that this is R1 results."""
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert "하나금융그룹 챔피언십" in html
    assert "R1 결과" in html


def test_home_page_rank_column_uses_t_prefix_for_ties():
    """Requirement 3: tied ranks must show a T prefix."""
    html = HOME_PAGE.read_text(encoding="utf-8")
    assert re.search(r"data-label='순위'>T\d+<", html), (
        "expected at least one T-prefixed tied rank on the homepage leaderboard"
    )


def test_home_page_round_score_is_to_par_only_never_raw_strokes():
    """Requirement 4: 1R score column must show To-Par notation only
    (E / +N / -N), never a raw stroke count like '69 (-3)'."""
    html = HOME_PAGE.read_text(encoding="utf-8")
    cells = re.findall(r"data-label='1R'>([^<]*)<", html)
    assert cells, "no 1R score cells found on the homepage"
    for cell in cells:
        assert cell in ("WD", "—") or re.fullmatch(r"E|[+-]\d{1,2}", cell), (
            f"1R cell {cell!r} is not pure To-Par notation -- raw strokes must never appear"
        )


def test_home_page_keeps_all_five_stage_links():
    """Requirement 6: PRE/R1/R2/R3/FR stage menu must remain present."""
    html = HOME_PAGE.read_text(encoding="utf-8")
    for label in ("사전 분석 PRE", "R1", "R2", "R3", "FR"):
        assert label in html


def test_pre_r1_pages_and_json_data_untouched_by_home_rebuild():
    """Requirement 7: rebuilding the homepage must never touch the PRE
    page, the R1 original page's own file identity/content beyond its
    own builder's normal output, the PRE archive, or any JSON data
    file -- 156 only ever writes docs/index.html and, since the /share/
    cache-bust route was added, docs/share/index.html (see
    test_hana_share_page.py)."""
    source = (SCRIPTS_DIR / "156_build_home_page.py").read_text(encoding="utf-8")
    assert '"content" / "website_v2"' in source or "CONTENT" in source
    assert "write_text" in source
    write_targets = sorted(set(re.findall(r"(\w+)\.write_text\(", source)))
    assert write_targets == ["DOCS_INDEX", "SHARE_PAGE", "SHARE_TOURNAMENT_PAGE", "SHORT_SHARE_PAGE"], (
        f"156_build_home_page.py must only ever call write_text on these four targets, found writes to: {write_targets}"
    )
