"""Update production HOME's "이번 대회" area from the R3 full-results
table (script 285) to the FR (final) full-results table, following the
exact same splice pattern already established for the R2->R3
transition: the round page's own <section class="panel leaderboard-panel"
id="fr">...</section> is spliced verbatim into HOME, just adding
"home-section" to its class list and prefixing its id with "home-" --
same table, same columns, same 68 rows as the real FR page, not a
trimmed summary.

The hero card's anchor/label and the "최종 결과 전체 보기 →" link text
are updated to match (3R -> 최종 결과), and the CSS scroll-margin rule
+ JS auto-scroll target are updated to the new section id.

No video section is touched or added/removed: the existing "3R 요약"
video stays exactly where it is, as a historical highlight -- nothing
in this task asks for a new FR video, and removing real content outside
this task's scope is avoided.

Source of truth: docs/tournaments/2026/2026100001/fr/index.html's own
table section, copied byte-for-byte (not re-rendered or hand-typed), so
HOME's numbers can never drift from the real FR page's.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
FR_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026100001" / "fr" / "index.html"
GAME_CODE = "2026100001"

OLD_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-r3-records" '
    'aria-label="제20회 S-OIL 챔피언십 3R 기록으로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">3R 기록이 아래로 이어집니다 ↓</p></a>'
)
NEW_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-fr-records" '
    'aria-label="제20회 S-OIL 챔피언십 최종 결과로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">최종 결과가 아래로 이어집니다 ↓</p></a>'
)

OLD_SECTION_START = '<section class="home-section panel leaderboard-panel" id="home-r3-records">'


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    if OLD_CARD not in html:
        raise SystemExit("hero card text not found verbatim -- refusing to guess a replacement point")
    if OLD_SECTION_START not in html:
        raise SystemExit("home-r3-records section start not found verbatim")

    start = html.find(OLD_SECTION_START)
    end = html.find("</section>", start) + len("</section>")
    old_section_full = html[start:end]

    fr_html = FR_PAGE.read_text(encoding="utf-8")
    fr_start = fr_html.find('<section class="panel leaderboard-panel" id="fr">')
    fr_end = fr_html.find("</section>", fr_start) + len("</section>")
    fr_section = fr_html[fr_start:fr_end]
    assert fr_section.count("<tr>") == 69, f"expected 69 <tr> (1 head + 68 body), found {fr_section.count('<tr>')}"

    fr_section = fr_section.replace(
        '<section class="panel leaderboard-panel" id="fr">',
        '<section class="home-section panel leaderboard-panel" id="home-fr-records">',
        1,
    )
    link_html = f"<p class='section-link-row'><a href='/tournaments/2026/{GAME_CODE}/fr/'>최종 결과 전체 보기 →</a></p>"
    head_marker = "</div><div class=\"table-wrap table-wrap--iceberg-r1\">"
    assert fr_section.count(head_marker) == 1
    new_section = fr_section.replace(head_marker, "</div>" + link_html + '<div class="table-wrap table-wrap--iceberg-r1">', 1)

    old_css = "#home-r3-records{scroll-margin-top:1rem}"
    new_css = "#home-fr-records{scroll-margin-top:1rem}"
    if old_css not in html:
        raise SystemExit("home-r3-records CSS rule not found verbatim")

    old_js_target = "getElementById('home-r3-records')"
    new_js_target = "getElementById('home-fr-records')"
    if old_js_target not in html:
        raise SystemExit("auto-scroll JS target not found verbatim")

    html2 = html.replace(OLD_CARD, NEW_CARD, 1)
    html2 = html2.replace(old_section_full, new_section, 1)
    html2 = html2.replace(old_css, new_css, 1)
    html2 = html2.replace(old_js_target, new_js_target, 1)
    assert html2 != html
    assert "home-r3-records" not in html2
    assert "home-fr-records" in html2
    assert html2.count("<video") == html.count("<video"), "no video should be added or removed by this patch"

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
