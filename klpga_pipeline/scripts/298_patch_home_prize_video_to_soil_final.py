"""Replace production HOME's "영상" panel (season-prize-money video,
id="season-prize-video") title/caption/src with the S-OIL Championship
final prize-money-seed-cutline video, per operator instruction.

Surgical, single-pattern replacement only: the <h2>, the <p class='meta'>,
and the <video>'s src + aria-label inside the LEFT figure of the
"neo-home-media-grid" are swapped. The video tag's own attributes
(controls, autoplay, muted, playsinline, loop, preload="auto") and the
RIGHT figure (2026년 시드 버블존 / seed bubble zone table image) are
byte-for-byte untouched. No poster attribute is added -- the original
had none, and the instruction is to keep attributes as-is, only swap
src.

The old video asset (klpga-2026-prize-money-top20.mp4, 2026-10-18 cut)
is kept on disk, never deleted -- only HOME's reference moves to the
new file.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

OLD = (
    '<figure class="neo-home-media-item"><div class="section-heading"><div>'
    '<p class="section-label">영상</p><h2>2026 시즌 KLPGA 상금 순위</h2></div></div>'
    '<p class="meta">2026년 10월 18일 기준 상금 순위입니다.</p>'
    '<video controls autoplay muted playsinline loop preload="auto" '
    'src="/assets/clips/klpga-2026-prize-money-top20.mp4" '
    'aria-label="2026 시즌 KLPGA 상금 순위 영상"></video></figure>'
)
NEW = (
    '<figure class="neo-home-media-item"><div class="section-heading"><div>'
    '<p class="section-label">영상</p><h2>S-OIL 챔피언십 최종, 시드가 갈린 335만 원</h2></div></div>'
    '<p class="meta">2026년 11월 1일 최종 상금순위 기준</p>'
    '<video controls autoplay muted playsinline loop preload="auto" '
    'src="/assets/clips/soil-2026-final-335.mp4" '
    'aria-label="S-OIL 챔피언십 최종, 시드가 갈린 335만 원 영상"></video></figure>'
)


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    count = html.count(OLD)
    assert count == 1, f"expected exactly 1 match of the current prize-video figure, found {count}"

    html2 = html.replace(OLD, NEW, 1)
    assert html2 != html
    assert "klpga-2026-prize-money-top20.mp4" not in html2, "old video src should no longer be referenced"
    assert "soil-2026-final-335.mp4" in html2
    assert html2.count("<video") == html.count("<video"), "video count must not change"
    # The right-hand 시드 버블존 figure must be untouched.
    assert '2026년 시드 버블존' in html2
    assert html2.count('class="neo-home-media-grid"') == html.count('class="neo-home-media-grid"') == 1

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
