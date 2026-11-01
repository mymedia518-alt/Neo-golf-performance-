"""Remove the "KLPGA 공식 기록 원문 ↗" link from HOME's "최종 결과"
(home-fr-records) section (operator instruction: "KLPGA 공식 기록
원문 ↗ 이건 삭제해줘").

Surgical, single-pattern removal only: the one <p><a ...>KLPGA 공식
기록 원문 ↗</a></p> paragraph that script 295 spliced in from the real
FR tournament page's own table section. Scoped to HOME only -- the
real FR tournament page (docs/tournaments/2026/2026100001/fr/) keeps
its own identical link untouched, since that page is the actual
official-results page where linking back to the KLPGA source makes
sense; this was only ever a byproduct of HOME's verbatim table splice.

Idempotent: refuses if the link is not found exactly once.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

LINK_PARAGRAPH = (
    '<p><a href="https://klpga.co.kr/web/tourRecord/scoreRecord?gameCode=2026100001" '
    'rel="noopener">KLPGA 공식 기록 원문 ↗</a></p>'
)


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    count = html.count(LINK_PARAGRAPH)
    assert count == 1, f"expected exactly 1 KLPGA official-record link paragraph on HOME, found {count}"

    html2 = html.replace(LINK_PARAGRAPH, "", 1)
    assert html2 != html
    assert "KLPGA 공식 기록 원문" not in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
