"""Update production HOME's existing "이번 대회" area from the stale,
fully-embedded 1R table to a compact 3R leaderboard summary (leader +
top-10-and-ties), with a link to the full R3 page. Content-only change
to docs/index.html, following the same pattern already used this
session to add the S-OIL R2 video section -- same owner marker
(<meta name="neo-home-owner" content="interim-video-home-v1">, see
klpga_pipeline/src/klpga/website_v2/home_ownership_guard.py) left
untouched, same surrounding sections (brand intro, R2 video) left
untouched.

Replaces:
  - the featured-tournament hero card's link/label/CTA text (pointed at
    the old "#home-r1-records" anchor and said "1R 기록이 아래로
    이어집니다") with a new "#home-r3-summary" anchor and 3R wording.
  - the old <section id="home-r1-records"> (a full 96-row 1R table,
    copy-pasted wholesale from the R1 page) with a new, compact
    <section id="home-r3-summary"> showing only rank/player/total for
    the top 10-and-ties (11 real rows, scripts/282's own tie-rank
    algorithm) plus a "3R 전체 결과 보기 →" link to the real R3 page.
    Uses the plain .data/.leaderboard-table classes already used
    elsewhere on this exact page (not the --iceberg-r1 modifier, which
    forces a 700px-min-width horizontal-scroll table meant for a wide,
    many-column table -- unnecessary and visually wrong for a 3-column
    summary) so it still reflows via the site's existing generic
    mobile card layout, not a new one.

Source of truth: SOIL_2026100001_R3_OFFICIAL_V1.json (scripts/282),
reused verbatim -- no recomputation, no values not already verified
there.
"""
from __future__ import annotations

import sys
from html import escape as _esc
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
GAME_CODE = "2026100001"
R3_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_R3_OFFICIAL_V1.json"

sys.path.insert(0, str(PIPELINE_ROOT / "src"))
import json  # noqa: E402

OLD_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-r1-records" '
    'aria-label="제20회 S-OIL 챔피언십 1R 기록으로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">1R 기록이 아래로 이어집니다 ↓</p></a>'
)
NEW_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-r3-summary" '
    'aria-label="제20회 S-OIL 챔피언십 3R 결과로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">3R 결과가 아래로 이어집니다 ↓</p></a>'
)

OLD_SECTION_START = '<section class="home-section panel leaderboard-panel" id="home-r1-records">'
OLD_SECTION_END = (
    "</p></section>"
)


def _rank_labels(rows: list[dict]) -> dict[str, str]:
    labels: dict[str, str] = {}
    i = 0
    while i < len(rows):
        j = i
        while j < len(rows) and rows[j]["total_score"] == rows[i]["total_score"]:
            j += 1
        label = str(i + 1) if j - i == 1 else f"TT{i + 1}"
        for k in range(i, j):
            labels[rows[k]["player_id"]] = label
        i = j
    return labels


def _top10_with_ties(rows: list[dict]) -> list[dict]:
    cutoff = 0
    i = 0
    while i < len(rows):
        j = i
        while j < len(rows) and rows[j]["total_score"] == rows[i]["total_score"]:
            j += 1
        if i >= 10:
            break
        cutoff = j
        i = j
    return rows[:cutoff]


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    if OLD_CARD not in html:
        raise SystemExit("hero card text not found verbatim -- refusing to guess a replacement point")
    if OLD_SECTION_START not in html:
        raise SystemExit("home-r1-records section start not found verbatim")

    r3 = json.loads(R3_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert r3["field_count"] == 68
    rows = sorted(r3["records"], key=lambda r: r["total_score"])
    rank_labels = _rank_labels(rows)
    top = _top10_with_ties(rows)
    assert len(top) >= 10

    row_html = []
    for r in top:
        to_par = r["score_to_par"]
        to_par_cell = f"{to_par:+d}" if to_par else "0"
        row_html.append(
            "<tr>"
            f"<td data-label='순위'>{rank_labels[r['player_id']]}</td>"
            f"<th scope='row' style='text-align:left;white-space:nowrap'>{_esc(r['player_name'])}</th>"
            f"<td data-label='합계'>{to_par_cell}</td>"
            "</tr>"
        )

    new_section = (
        '<section class="home-section panel leaderboard-panel" id="home-r3-summary">'
        f"<div class=\"leaderboard-head\"><h2>3R 공식 결과 <small>상위 {len(top)}명</small></h2></div>"
        "<div class='table-wrap'><table class='data leaderboard-table'>"
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th></tr></thead>"
        "<tbody>" + "".join(row_html) + "</tbody></table></div>"
        f"<p class='meta'>3R 공식 결과입니다. <a href='/tournaments/2026/{GAME_CODE}/r3/'>3R 전체 결과 보기 →</a></p>"
        "</section>"
    )

    start = html.find(OLD_SECTION_START)
    end = html.find(OLD_SECTION_END, start)
    if end == -1:
        raise SystemExit("could not find end of home-r1-records section")
    end += len(OLD_SECTION_END)
    old_section_full = html[start:end]

    old_css = (
        "#home-r1-records{scroll-margin-top:1rem}"
        "#home-r1-records tbody td.r1-score{color:#c6d5b4}"
        "#home-r1-records tbody td.cut-probability{color:var(--green);font-weight:inherit}"
    )
    new_css = "#home-r3-summary{scroll-margin-top:1rem}"
    if old_css not in html:
        raise SystemExit("home-r1-records CSS block not found verbatim")

    old_js_target = "getElementById('home-r1-records')"
    new_js_target = "getElementById('home-r3-summary')"
    if old_js_target not in html:
        raise SystemExit("auto-scroll JS target not found verbatim")

    html2 = html.replace(OLD_CARD, NEW_CARD, 1)
    html2 = html2.replace(old_section_full, new_section, 1)
    html2 = html2.replace(old_css, new_css, 1)
    html2 = html2.replace(old_js_target, new_js_target, 1)
    assert html2 != html
    assert "home-r1-records" not in html2
    assert "home-r3-summary" in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print(json.dumps({
        "written": str(DOCS_INDEX),
        "top_rows": len(top),
        "leader": top[0]["player_name"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
