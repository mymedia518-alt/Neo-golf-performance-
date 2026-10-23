"""HOME stage-mirror update: once 아이스버그골프·서울신문 오픈 (game_code
2026100003) has a real FR (official final result) page, HOME must
mirror THAT stage -- same principle scripts/245 (R1) and scripts/256
(R2) already established, continued one stage later (same ownership-
guard call via klpga.website_v2.home_ownership_guard, same header/
footer reuse, only the mirrored page body changes from R2 to FR).

This is the sole writer of docs/index.html for this tournament's FR
stage; the FR page builder (scripts/258) itself never writes
docs/index.html, exactly like scripts/244/255 never did for R1/R2.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    COMPOSITE_HOME_OWNER,
    CURRENT_TOURNAMENT_OWNER,
    TOP120_OWNER,
    assert_home_write_allowed,
    embed_game_code,
    embed_owner,
    extract_owner,
)

sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util as _ilu  # noqa: E402

_spec = _ilu.spec_from_file_location(
    "_hj_archive_scaffold", ROOT / "scripts" / "build_tournament_archive_and_hj_scaffold.py"
)
_hj_archive_scaffold = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_hj_archive_scaffold)
global_header = _hj_archive_scaffold.global_header
FOOTER = _hj_archive_scaffold.FOOTER

GAME_CODE = "2026100003"
CONTENT = ROOT / "content" / "website_v2"
FR_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "fr" / "index.html"
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

tourney = json.loads((CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
EVENT_NAME = tourney["event_name"]


def _stage_main_html() -> str:
    if not FR_PAGE.is_file():
        raise SystemExit(f"no real published page at {FR_PAGE} -- run scripts/258 first")
    html = FR_PAGE.read_text(encoding="utf-8")
    if "<main>" not in html or "</main>" not in html:
        raise SystemExit(f"{FR_PAGE} has no <main>...</main> body to mirror")
    return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"


def _stage_description() -> str:
    html = FR_PAGE.read_text(encoding="utf-8")
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    return m.group(1) if m else "KLPGA 공식 데이터 기반 골프 분석"


def build() -> None:
    main_html = _stage_main_html()
    # HOME-only addition (operator instruction, 2026-10-23): a season-wide
    # KLPGA prize-money ranking video, not specific to this tournament --
    # inserted only into the HOME mirror, never into the real FR page
    # itself (/tournaments/2026/2026100003/fr/ stays untouched, exactly as
    # scripts/244/255/258 already never write to it from here). Placed
    # right before the leaderboard panel, after this tournament's own FR
    # review video. The video's own on-screen captions already cite their
    # source/as-of date per slide (KLPGA 공식 기록, 2026.10.18 종료 대회
    # 기준) -- no additional claim is made here beyond what it shows.
    main_html = main_html.replace(
        '<section class="panel leaderboard-panel" id="fr">',
        "<section class='panel' id='season-prize-video'>"
        "<p class='note'>NEO GOLF DATA</p><h2>2026 시즌 KLPGA 상금 순위</h2>"
        "<p class='note'>대회별 상금 순위를 정리한 영상입니다. 출처: KLPGA 공식 기록 (영상 내 각 슬라이드에 기준일 표시).</p>"
        "<video controls playsinline style='display:block;width:100%;max-width:100%;height:auto' "
        "src='/assets/clips/klpga-2026-prize-money-top20.mp4'></video>"
        "</section>"
        '<section class="panel leaderboard-panel" id="fr">',
        1,
    )
    main_html = main_html.replace(
        "</main>",
        '<section class="page-intro"><h2>지난 대회 기록</h2>'
        '<p>NEO가 분석했던 모든 대회는 <a href="/tournaments/">대회 기록</a>에서 다시 볼 수 있습니다.</p></section>'
        "</main>",
    )
    description = _stage_description()

    head = (
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {EVENT_NAME}</title>'
        f'<meta name="description" content="{description}">'
        '<link rel="canonical" href="https://neogolfdata.com/">'
        '<meta property="og:title" content="NEO GOLF DATA">'
        f'<meta property="og:description" content="{description}">'
        '<meta property="og:url" content="https://neogolfdata.com/">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css">'
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        "</head>"
    )
    body = f"<body>{global_header('home')}{main_html}{FOOTER}</body>"
    html = f'<!doctype html><html lang="ko">{head}{body}</html>'

    html = embed_owner(html, CURRENT_TOURNAMENT_OWNER)
    html = embed_game_code(html, GAME_CODE)

    # OPERATOR ROLLBACK (2026-10-21): the fixed six-section composite HOME
    # (COMPOSITE_HOME_OWNER, see home_ownership_guard.py's OWNER
    # SUPERSESSION 2 note) went live before it was finished -- operator
    # instruction is to roll root HOME back to mirroring the Iceberg FR
    # page (this script's original, pre-composite job) until the
    # composite HOME is actually ready. Accept a transfer from whichever
    # owner currently holds root HOME (composite-home-v1 is the expected
    # real case here, but top120-v1/current-tournament-v1 stay accepted
    # too since this script's own prior behavior already allowed them
    # implicitly via re-running itself) -- never a blind bypass, still
    # hard-stops on any unrecognized owner or a different game_code.
    existing_owner = extract_owner(DOCS_INDEX.read_text(encoding="utf-8")) if DOCS_INDEX.is_file() else None
    transfer_from = existing_owner if existing_owner in (TOP120_OWNER, COMPOSITE_HOME_OWNER, CURRENT_TOURNAMENT_OWNER) else CURRENT_TOURNAMENT_OWNER
    assert_home_write_allowed(
        DOCS_INDEX, CURRENT_TOURNAMENT_OWNER, repo_root=REPO_ROOT,
        allow_transfer_from=transfer_from, writer_game_code=GAME_CODE,
    )
    DOCS_INDEX.write_text(html, encoding="utf-8")
    print(json.dumps({
        "written": str(DOCS_INDEX),
        "bytes": len(html),
        "mirrors": str(FR_PAGE),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
