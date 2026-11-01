"""Add the S-OIL Championship FR (final round) summary video to
production HOME.

Follows the exact section pattern already used for the R3 video
(script 287): a plain "home-section" (not inside the leaderboard
panel) titled "제20회 S-OIL 챔피언십 최종 결과 영상", containing one
<video> tag pointing at the asset copied into
docs/assets/tournaments/2026100001/.

Placement: directly before the "home-fr-records" full-results table
section (script 295), i.e. right after the existing R3 video section,
which is left untouched as a historical highlight -- so the order on
HOME reads hero -> R3 video -> FR video -> final results table.

Idempotent: refuses if the video section already exists, and asserts
the video tag count increases by exactly one.

RETIRED (operator instruction, following script 299's removal of this
same section): the top "s-oil-fr-video" panel turned out to duplicate
the lower "season-prize-video" panel once that one was also updated to
an S-OIL final-result video (script 298) -- the operator asked for the
top one to come down permanently, not just once. Because this script's
own idempotency check only guards against re-inserting while the
section is STILL present, re-running it after 299 has removed the
section would silently re-add it. This script is kept for its audit
history (never deleted) but now hard-refuses to run at all for
2026100001 -- see RETIRED_NOTE below. If the operator ever wants this
panel back, that is a new, explicit decision, not a side effect of
re-running an old script.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
GAME_CODE = "2026100001"

RETIRED_NOTE = (
    "script 296 is retired for game_code 2026100001: the top "
    "'s-oil-fr-video' HOME panel it adds was permanently removed by "
    "script 299 (operator instruction -- duplicated the lower "
    "'season-prize-video' panel). Refusing to run; see this script's "
    "own module docstring for the full history."
)

ANCHOR = '<section class="home-section panel leaderboard-panel" id="home-fr-records">'

VIDEO_SECTION = (
    '<section class="home-section" id="s-oil-fr-video">'
    '<div class="section-heading"><div><p class="section-label">영상</p>'
    '<h2>제20회 S-OIL 챔피언십 최종 결과 영상</h2></div></div>'
    '<p class="meta">공식 최종 결과 영상입니다.</p>'
    '<video controls playsinline style="display:block;width:100%;max-width:100%;height:auto" '
    f'src="/assets/tournaments/{GAME_CODE}/neo-golf-data-fr.mp4" '
    'aria-label="제20회 S-OIL 챔피언십 최종 결과 영상"></video></section>'
)


def main() -> None:
    raise SystemExit(RETIRED_NOTE)
    html = DOCS_INDEX.read_text(encoding="utf-8")
    if "s-oil-fr-video" in html:
        raise SystemExit("video section already present -- refusing to duplicate")
    if ANCHOR not in html:
        raise SystemExit("home-fr-records section start not found verbatim")

    before_videos = html.count("<video")
    html2 = html.replace(ANCHOR, VIDEO_SECTION + ANCHOR, 1)
    assert html2 != html
    assert html2.count("<video") == before_videos + 1, "expected exactly one new <video> tag"
    assert 'id="s-oil-fr-video"' in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
