"""HOME stage-mirror update: once 아이스버그골프·서울신문 오픈 (game_code
2026100003) has a real R1 page, HOME must mirror THAT stage, not the
stale PRE copy scripts/239 wrote before R1 existed -- same "HOME
mirrors the real published stage page" principle, same ownership-guard
call, same header/footer reuse. The only diff from scripts/239 is which
page body gets mirrored (R1 instead of PRE) and the stage-aware
"다음 업데이트" note scripts/239's PRE mirror didn't need.
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
    CURRENT_TOURNAMENT_OWNER,
    assert_home_write_allowed,
    embed_game_code,
    embed_owner,
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
R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html"
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

tourney = json.loads((CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
EVENT_NAME = tourney["event_name"]


def _stage_main_html() -> str:
    if not R1_PAGE.is_file():
        raise SystemExit(f"no real published page at {R1_PAGE} -- run scripts/244 first")
    html = R1_PAGE.read_text(encoding="utf-8")
    if "<main>" not in html or "</main>" not in html:
        raise SystemExit(f"{R1_PAGE} has no <main>...</main> body to mirror")
    return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"


def _stage_description() -> str:
    html = R1_PAGE.read_text(encoding="utf-8")
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    return m.group(1) if m else "KLPGA 공식 데이터 기반 골프 분석"


def build() -> None:
    main_html = _stage_main_html()
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

    # Same game_code (2026100003) as the HOME scripts/239 already wrote --
    # this is a same-tournament stage refresh, not an ownership transfer,
    # so writer_game_code IS passed (the normal, game-code-aware path).
    assert_home_write_allowed(
        DOCS_INDEX, CURRENT_TOURNAMENT_OWNER, repo_root=REPO_ROOT, writer_game_code=GAME_CODE,
    )
    DOCS_INDEX.write_text(html, encoding="utf-8")
    print(json.dumps({
        "written": str(DOCS_INDEX),
        "bytes": len(html),
        "mirrors": str(R1_PAGE),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
