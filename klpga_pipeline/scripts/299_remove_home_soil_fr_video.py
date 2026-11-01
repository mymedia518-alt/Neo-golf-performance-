"""Remove the top S-OIL FR video section from production HOME
(operator instruction: "홈화면에서 상단에 있는 영상은 내려줘. 두개가
똑같으니까" -- now that the lower "영상" panel near the seed bubble
zone also shows an S-OIL final-result video, the top one is a
duplicate).

Surgical, single-pattern removal only: the whole "s-oil-fr-video"
<section> (script 296) is deleted verbatim, byte-for-byte. The FR
tournament page's own video section, the video asset file itself, and
the lower "season-prize-video" panel (now showing the S-OIL final /
335만원 seed video, script 298) are all left untouched -- this only
removes the top section from HOME.

Idempotent: refuses if the section is not found exactly once.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

SECTION = (
    '<section class="home-section" id="s-oil-fr-video">'
    '<div class="section-heading"><div><p class="section-label">영상</p>'
    '<h2>제20회 S-OIL 챔피언십 최종 결과 영상</h2></div></div>'
    '<p class="meta">공식 최종 결과 영상입니다.</p>'
    '<video controls playsinline style="display:block;width:100%;max-width:100%;height:auto" '
    'src="/assets/tournaments/2026100001/neo-golf-data-fr.mp4" '
    'aria-label="제20회 S-OIL 챔피언십 최종 결과 영상"></video></section>'
)


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    count = html.count(SECTION)
    assert count == 1, f"expected exactly 1 top FR video section, found {count}"

    before_videos = html.count("<video")
    html2 = html.replace(SECTION, "", 1)
    assert html2 != html
    assert html2.count("<video") == before_videos - 1, "expected exactly one <video> tag removed"
    assert "s-oil-fr-video" not in html2
    assert "season-prize-video" in html2, "the lower video panel must remain untouched"

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
