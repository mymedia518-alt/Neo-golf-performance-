"""Remove the S-OIL R3 video section from production HOME (operator
instruction: "홈화면에 3R 영상은 안나오게 해줘").

Surgical, single-pattern removal only: the whole "s-oil-r3-video"
<section> (script 287) is deleted verbatim, byte-for-byte. The video
asset file itself, the R3 tournament page's own video section, and the
FR video section on HOME are all left untouched -- this only removes
the one section from HOME.

Idempotent: refuses if the section is not found exactly once.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

SECTION = (
    '<section class="home-section" id="s-oil-r3-video">'
    '<div class="section-heading"><div><p class="section-label">영상</p>'
    '<h2>제20회 S-OIL 챔피언십 3R 요약</h2></div></div>'
    '<p class="meta">3R 공식 결과 영상입니다.</p>'
    '<video controls playsinline style="display:block;width:100%;max-width:100%;height:auto" '
    'src="/assets/tournaments/2026100001/neo-golf-data-r3.mp4" '
    'aria-label="제20회 S-OIL 챔피언십 3R 요약 영상"></video></section>'
)


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    count = html.count(SECTION)
    assert count == 1, f"expected exactly 1 R3 video section, found {count}"

    before_videos = html.count("<video")
    html2 = html.replace(SECTION, "", 1)
    assert html2 != html
    assert html2.count("<video") == before_videos - 1, "expected exactly one <video> tag removed"
    assert "s-oil-r3-video" not in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
