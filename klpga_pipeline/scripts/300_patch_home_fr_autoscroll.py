"""Turn production HOME's "최종 결과" (home-fr-records) table into a
continuously auto-scrolling ticker (operator instruction: "홈화면에
있는 4R 순위를 스크롤업 형식으로 해줘. 자동으로 멈추지 않고 계속
올라가는 걸로 속도는 알맞게").

Technique (no JS framework, matches the page's existing vanilla-JS IIFE
convention used for the hero auto-scroll-to-anchor script):
  1. The table-wrap is height-capped with overflow-y:hidden (scoped to
     #home-fr-records only -- the real FR tournament page's identical
     table is never touched).
  2. The tbody's 68 rows are duplicated into a second, aria-hidden=true
     tbody right after the first, so the scrollable content is exactly
     2x one real pass -- this is what makes the loop seamless.
  3. A small requestAnimationFrame loop continuously increases
     scrollTop at a constant, time-based (not frame-based) speed, and
     subtracts exactly half of scrollHeight whenever it reaches that
     point -- an invisible wrap-around, since the content there is
     byte-identical to the top. It never stops. Respects
     prefers-reduced-motion for users who've opted into that at the OS
     level (standard accessibility practice; does not change behavior
     for anyone else).

Does not touch the "시드 버블존" panel, the hero card, or any other
section. Does not change the leaderboard-table/table-wrap CSS classes
used site-wide -- only adds new rules scoped under the #home-fr-records
ID so the real FR page (docs/tournaments/2026/2026100001/fr/) is
unaffected.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

SECTION_START = '<section class="home-section panel leaderboard-panel" id="home-fr-records">'

AUTOSCROLL_CSS = (
    "#home-fr-records .table-wrap{max-height:26rem;overflow-y:hidden}"
    "#home-fr-records .table-wrap:after{content:none}"
)

AUTOSCROLL_JS = (
    "<script>(function(){"
    "var wrap=document.querySelector('#home-fr-records .table-wrap');"
    "if(!wrap)return;"
    "var reduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;"
    "if(reduceMotion)return;"
    "var half=0;"
    "function measure(){half=wrap.scrollHeight/2}"
    "measure();"
    "window.addEventListener('resize',measure);"
    "var speed=32;" # px per second
    # pos is kept as an independent float accumulator, never read back
    # from wrap.scrollTop: scrollTop rounds to integer pixels, so
    # repeatedly doing `scrollTop += fraction` would read back an
    # already-rounded value each frame and compound into roughly double
    # the intended speed (verified empirically: this exact bug measured
    # ~60px/s instead of the intended 32px/s before this fix).
    "var pos=wrap.scrollTop;"
    "var last=null;"
    "function step(ts){"
    "if(last!==null){"
    "var dt=(ts-last)/1000;"
    "pos+=speed*dt;"
    "if(half>0&&pos>=half){pos-=half}"
    "wrap.scrollTop=pos"
    "}"
    "last=ts;"
    "window.requestAnimationFrame(step)"
    "}"
    "window.requestAnimationFrame(step)"
    "})();</script>"
)


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")

    section_start = html.find(SECTION_START)
    assert section_start != -1, "home-fr-records section start not found verbatim"
    section_end = html.find("</section>", section_start) + len("</section>")
    section = html[section_start:section_end]

    tbody_open = "<tbody>"
    tbody_close = "</tbody>"
    t_start = section.find(tbody_open)
    assert t_start != -1, "tbody not found in home-fr-records section"
    t_end = section.find(tbody_close, t_start)
    assert t_end != -1, "closing tbody not found in home-fr-records section"
    assert section.count(tbody_open) == 1, f"expected exactly 1 tbody, found {section.count(tbody_open)}"

    rows_html = section[t_start + len(tbody_open):t_end]
    row_count = rows_html.count("<tr>")
    assert row_count == 68, f"expected 68 rows in home-fr-records tbody, found {row_count}"

    original_total_tr = section.count("<tr>")  # row_count body rows + 1 thead row
    new_tbody = f"<tbody>{rows_html}</tbody><tbody aria-hidden=\"true\">{rows_html}</tbody>"
    new_section = section[:t_start] + new_tbody + section[t_end + len(tbody_close):]
    assert new_section.count("<tr>") == original_total_tr + row_count

    html2 = html[:section_start] + new_section + html[section_end:]
    assert html2 != html

    style_close = "</style></head>"
    assert html2.count(style_close) == 1, f"expected exactly 1 '{style_close}', found {html2.count(style_close)}"
    html2 = html2.replace(style_close, AUTOSCROLL_CSS + style_close, 1)

    assert html2.count("</body></html>") == 1
    html2 = html2.replace("</body></html>", AUTOSCROLL_JS + "</body></html>", 1)

    assert html2 != html
    assert html2.count('id="home-fr-records"') == 1
    assert AUTOSCROLL_JS in html2
    assert AUTOSCROLL_CSS in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
