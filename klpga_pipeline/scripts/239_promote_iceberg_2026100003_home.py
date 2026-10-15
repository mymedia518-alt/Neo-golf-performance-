"""HOME ownership transfer: 아이스버그골프·서울신문 오픈 (game_code
2026100003) becomes the current tournament, replacing HJ중공업·동부건설
챔피언십 (2026100004) -- same technique as scripts/192_promote_
hitejinro_home.py's own real transfer (Hana -> 하이트진로), generalized
to reuse build_tournament_archive_and_hj_scaffold.py's own global_header()/
FOOTER (the CURRENT shared header/nav/footer every live page already
uses, including HJ's own HOME) instead of 192's own hand-copied, now
slightly stale header markup (192 predates the 2026-10-07 nav-label
simplification) -- so HOME keeps the exact nav/style every other page
on the site has today, per the operator's explicit instruction to
leave HOME's layout/style/nav unchanged and only swap the current-
tournament content.

Mirrors scripts/238's own real, already-built PRE page's <main>...
</main> body verbatim (including its breadcrumb) -- never rebuilt or
reworded here, same "HOME mirrors the real published stage page"
principle as klpga.website_v2.build_tournament_archive_and_hj_
scaffold._build_home_stage_mirror.

OWNERSHIP TRANSFER (see klpga.website_v2.home_ownership_guard's own
docstring, "no bypass parameter for this check by design"): the
existing docs/index.html currently carries game_code=2026100004 (HJ).
This is a deliberate, one-directional transfer TO a genuinely new
current tournament, so this call intentionally OMITS writer_game_code
-- the documented escape hatch for exactly this situation (passing it
would unconditionally hard-stop on the now-expected game_code
mismatch). The new HTML this script writes embeds game_code=2026100003
via embed_game_code, so every subsequent re-run of THIS script (not
192, not a different stale builder) passes the normal, game-code-aware
check going forward.
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
PRE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

tourney = json.loads((CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
EVENT_NAME = tourney["event_name"]


def _stage_main_html() -> str:
    if not PRE_PAGE.is_file():
        raise SystemExit(f"no real published page at {PRE_PAGE} -- run scripts/238 first")
    html = PRE_PAGE.read_text(encoding="utf-8")
    if "<main>" not in html or "</main>" not in html:
        raise SystemExit(f"{PRE_PAGE} has no <main>...</main> body to mirror")
    return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"


def _stage_description() -> str:
    html = PRE_PAGE.read_text(encoding="utf-8")
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    return m.group(1) if m else "KLPGA 공식 데이터 기반 골프 분석"


def build() -> None:
    main_html = _stage_main_html()
    # Same "지난 대회 기록" closing section every HOME stage-mirror already
    # carries (klpga.website_v2.build_tournament_archive_and_hj_scaffold.
    # _build_home_stage_mirror) -- spliced inside </main>, not appended
    # after it.
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
        # Same header/body left-edge alignment fix every other page's
        # own head already carries on this branch.
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        "</head>"
    )
    body = f"<body>{global_header('home')}{main_html}{FOOTER}</body>"
    html = f'<!doctype html><html lang="ko">{head}{body}</html>'

    html = embed_owner(html, CURRENT_TOURNAMENT_OWNER)
    html = embed_game_code(html, GAME_CODE)

    # OWNERSHIP TRANSFER: deliberately no writer_game_code here -- see
    # module docstring. allow_transfer_from=CURRENT_TOURNAMENT_OWNER
    # matches the existing owner CLASS (HJ's HOME is also "current-
    # tournament-v1"), which is exactly the legitimate same-class
    # transfer this guard exists to allow.
    assert_home_write_allowed(
        DOCS_INDEX, CURRENT_TOURNAMENT_OWNER, repo_root=REPO_ROOT, allow_transfer_from=CURRENT_TOURNAMENT_OWNER,
    )
    DOCS_INDEX.write_text(html, encoding="utf-8")
    print(json.dumps({
        "written": str(DOCS_INDEX),
        "bytes": len(html),
        "note": "REAL working-tree write -- not committed or pushed. git checkout -- docs/index.html restores HJ's prior FR mirror if needed.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
