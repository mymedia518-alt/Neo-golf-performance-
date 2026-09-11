"""R2 PUBLIC TABLE -- PROBABILITY COLUMN ORDER HOTFIX (base dd4640f).

    순위 | 선수 | 합계 | 2R | TOP20 | TOP10 | TOP5 | 우승

Desktop and mobile are the SAME markup (klpga.neo_win.r2_real_page's
leaderboard table; CSS alone reflows it for narrow viewports via each
cell's own data-label attribute -- there is no second, mobile-specific
template), so proving the header order and every row's data-label
sequence against the REAL, committed generated page covers both at
once. Every check here reads docs/tournaments/2026/2026090003/r2/
index.html directly."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
REAL_PAGE_PATH = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html"

REQUIRED_ORDER = ["순위", "선수", "합계", "2R", "Top20", "Top10", "Top5", "우승"]


def _real_html() -> str:
    assert REAL_PAGE_PATH.is_file(), f"real R2 page not found at {REAL_PAGE_PATH}"
    return REAL_PAGE_PATH.read_text(encoding="utf-8")


def _rows(html: str) -> list[str]:
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return re.findall(r"<tr data-player-id='[^']+'>((?:(?!</tr>).)*)</tr>", body)


def test_header_column_order_is_exactly_top20_top10_top5_win_last():
    html = _real_html()
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == REQUIRED_ORDER


def test_every_row_data_label_order_matches_the_header_desktop_and_mobile():
    """desktop AND mobile: the mobile reflow (CSS `.leaderboard-table
    tbody td::before{content:attr(data-label)}` caption, and the
    `--r2-full` grid's positional nth-child(5..8) layout) both follow
    whichever order the `<td>` elements themselves are in -- so a row's
    own data-label sequence IS the order both surfaces render in."""
    html = _real_html()
    rows = _rows(html)
    assert rows, "no rendered rows found"
    for row in rows:
        labels = re.findall(r"data-label='([^']+)'", row)
        assert labels == REQUIRED_ORDER


def test_win_is_still_the_last_column():
    html = _real_html()
    for row in _rows(html):
        labels = re.findall(r"data-label='([^']+)'", row)
        assert labels[-1] == "우승"


def test_population_still_71_active_players_unchanged_by_the_reorder():
    html = _real_html()
    rows = _rows(html)
    assert len(rows) == 71


def test_player_order_and_probability_values_unchanged_by_the_reorder():
    """The column reorder is presentation-only: every player's rendered
    rank/name/total/2R/probability VALUES (just relocated to their new
    column position) must be byte-identical to before this hotfix."""
    import subprocess

    old = subprocess.run(
        ["git", "show", "dd4640f:docs/tournaments/2026/2026090003/r2/index.html"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    ).stdout
    new = _real_html()

    def parse_rows(html):
        body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        entries = re.findall(r"<tr data-player-id='([^']+)'>((?:(?!</tr>).)*)</tr>", body)
        out = {}
        for pid, row in entries:
            def cell(label):
                m = re.search(rf"data-label='{label}'[^>]*>(.*?)</td>", row)
                return m.group(1) if m else None
            out[pid] = {
                "rank": cell("순위"), "total": cell("합계"), "r2": cell("2R"),
                "top5": cell("Top5"), "top10": cell("Top10"), "top20": cell("Top20"), "win": cell("우승"),
            }
        return out

    old_rows = parse_rows(old)
    new_rows = parse_rows(new)
    assert set(old_rows) == set(new_rows)
    for pid in old_rows:
        assert old_rows[pid] == new_rows[pid], f"player {pid}: value diverged, not just reordered"
