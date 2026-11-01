"""Add the S-OIL Championship 3R summary video to production HOME.

Follows the exact section pattern already used (on an earlier, never-merged
branch) for the 2R video: a plain "home-section" (not inside the leaderboard
panel) titled "제20회 S-OIL 챔피언십 3R 요약", containing one <video> tag
pointing at the asset copied into docs/assets/tournaments/2026100001/.

Placement: directly after the hero card's closing </section> and before the
"home-r3-records" full-results table section added by script 285 -- i.e.
between the hero and the table, mirroring where the 2R video sat relative to
its own home-r2-records table on that earlier branch.

Idempotent: refuses if the video section already exists, and asserts the
video tag count increases by exactly one.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
GAME_CODE = "2026100001"

ANCHOR = '<section class="home-section panel leaderboard-panel" id="home-r3-records">'

VIDEO_SECTION = (
    '<section class="home-section" id="s-oil-r3-video">'
    '<div class="section-heading"><div><p class="section-label">영상</p>'
    '<h2>제20회 S-OIL 챔피언십 3R 요약</h2></div></div>'
    '<p class="meta">3R 공식 결과 영상입니다.</p>'
    '<video controls playsinline style="display:block;width:100%;max-width:100%;height:auto" '
    f'src="/assets/tournaments/{GAME_CODE}/neo-golf-data-r3.mp4" '
    'aria-label="제20회 S-OIL 챔피언십 3R 요약 영상"></video></section>'
)


def main() -> None:
    html = DOCS_INDEX.read_text(encoding="utf-8")
    if "s-oil-r3-video" in html:
        raise SystemExit("video section already present -- refusing to duplicate")
    if ANCHOR not in html:
        raise SystemExit("home-r3-records section start not found verbatim")

    before_videos = html.count("<video")
    html2 = html.replace(ANCHOR, VIDEO_SECTION + ANCHOR, 1)
    assert html2 != html
    assert html2.count("<video") == before_videos + 1, "expected exactly one new <video> tag"
    assert "id=\"s-oil-r3-video\"" in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
