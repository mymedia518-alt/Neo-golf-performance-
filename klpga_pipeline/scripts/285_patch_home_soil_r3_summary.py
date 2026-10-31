"""Update production HOME's existing "이번 대회" area from the R2
full-results table (added by the operator's own "Show S-OIL R2 results
on homepage" commit) to the R3 full-results table, following the exact
same pattern that commit already established: splice the round page's
own <section class="panel leaderboard-panel" id="...">...</section>
verbatim into HOME, just adding "home-section" to its class list and
prefixing its id with "home-" -- same table, same columns, same 68
rows as the real R3 page, not a trimmed summary. A clear, separate
"3R 전체 결과 보기 →" link to the dedicated R3 page is added right
after the heading (operator-requested; the R2 precedent had no such
link, every row already being visible made it moot for that round --
asked for here, so added here, not inferred from precedent).

No video section is touched or added: production HOME currently has
no S-OIL video of any kind (only the unrelated season-wide KLPGA
prize-money video elsewhere on the page, which this script never
touches).

Source of truth: docs/tournaments/2026/2026100001/r3/index.html's own
table section, copied byte-for-byte (not re-rendered or hand-typed),
so HOME's numbers can never drift from the real R3 page's.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
R3_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026100001" / "r3" / "index.html"
GAME_CODE = "2026100001"

OLD_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-r2-records" '
    'aria-label="제20회 S-OIL 챔피언십 2R 기록으로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">2R 기록이 아래로 이어집니다 ↓</p></a>'
)
NEW_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-r3-records" '
    'aria-label="제20회 S-OIL 챔피언십 3R 기록으로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">3R 기록이 아래로 이어집니다 ↓</p></a>'
)

OLD_SECTION_START = '<section class="home-section panel leaderboard-panel" id="home-r2-records">'


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    if OLD_CARD not in html:
        raise SystemExit("hero card text not found verbatim -- refusing to guess a replacement point")
    if OLD_SECTION_START not in html:
        raise SystemExit("home-r2-records section start not found verbatim")

    start = html.find(OLD_SECTION_START)
    end = html.find("</section>", start) + len("</section>")
    old_section_full = html[start:end]

    r3_html = R3_PAGE.read_text(encoding="utf-8")
    r3_start = r3_html.find('<section class="panel leaderboard-panel" id="r3">')
    r3_end = r3_html.find("</section>", r3_start) + len("</section>")
    r3_section = r3_html[r3_start:r3_end]
    assert r3_section.count("<tr>") == 69, f"expected 69 <tr> (1 head + 68 body), found {r3_section.count('<tr>')}"

    r3_section = r3_section.replace(
        '<section class="panel leaderboard-panel" id="r3">',
        '<section class="home-section panel leaderboard-panel" id="home-r3-records">',
        1,
    )
    link_html = f"<p class='section-link-row'><a href='/tournaments/2026/{GAME_CODE}/r3/'>3R 전체 결과 보기 →</a></p>"
    head_marker = "</div><div class=\"table-wrap table-wrap--iceberg-r1\">"
    assert r3_section.count(head_marker) == 1
    new_section = r3_section.replace(head_marker, "</div>" + link_html + '<div class="table-wrap table-wrap--iceberg-r1">', 1)

    old_css = "#home-r2-records{scroll-margin-top:1rem}"
    new_css = "#home-r3-records{scroll-margin-top:1rem}"
    if old_css not in html:
        raise SystemExit("home-r2-records CSS rule not found verbatim")

    old_js_target = "getElementById('home-r2-records')"
    new_js_target = "getElementById('home-r3-records')"
    if old_js_target not in html:
        raise SystemExit("auto-scroll JS target not found verbatim")

    html2 = html.replace(OLD_CARD, NEW_CARD, 1)
    html2 = html2.replace(old_section_full, new_section, 1)
    html2 = html2.replace(old_css, new_css, 1)
    html2 = html2.replace(old_js_target, new_js_target, 1)
    assert html2 != html
    assert "home-r2-records" not in html2
    assert "home-r3-records" in html2
    assert html2.count("<video") == html.count("<video"), "no video should be added or removed by this patch"

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
