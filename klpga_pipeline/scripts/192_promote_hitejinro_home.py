"""HOME integration -- REAL PRODUCTION WRITE to docs/index.html.

Explicit operator instruction (2026-09-30): "Do not wait for my
decisions... HOME: Prepare everything except commit." This script
performs the actual write scripts/191's candidate preview stopped
short of, through the same production path scripts/156_build_home_page.py
uses for Hana -- klpga.website_v2.home_ownership_guard.
assert_home_write_allowed(), writer_owner=CURRENT_TOURNAMENT_OWNER
(the same owner identity Hana's own HOME write already uses: both are
"the current tournament", so the guard raises no conflict -- see that
module's own docstring). Nothing here is committed or pushed; the
working tree write is fully reversible via `git checkout -- docs/index.html`
(current live content is commit dc7330b439c92162119d86d3192733005af47cb7
on this branch) up until an operator explicitly commits it.

EDITORIAL FACT THIS SCRIPT DOES NOT DECIDE, ONLY RECORDS: live HOME
currently mirrors Hana (game_code 2026090002) at stage R1, an
in-progress, unrelated tournament -- NOT at FINAL. This write replaces
that live mirror with 2026100005's real, validated PRE page. That
replacement is exactly what was explicitly instructed; this comment
exists so the fact is visible in the diff an operator reviews before
deciding to commit, not to re-litigate it.

Mirrors scripts/156_build_home_page.py's own head/body shell and the
literal <main>...</main> mirror-from-the-real-published-stage-page
technique (klpga.website_v2.hana_home_stage_router.
current_stage_main_html) byte-for-byte -- only the embedded tournament
and its nav target differ.

BUG FIX (2026-10-01, R1 종료 operation): STAGE_PAGE/current_stage_href
used to be hardcoded to "pre/" -- correct only while PRE was genuinely
the most advanced real stage. Now that R1 has really been published
(scripts/196, fed by scripts/200's real leaderboard parse), hardcoding
"pre/" would mirror a stale stage onto HOME forever, the exact
"HOME stuck on an old stage" failure klpga.website_v2.hana_home_stage_
router/kb_home_stage_router were already written to fix for the other
two tournaments. Reuses klpga.website_v2.previous_tournament_link.
latest_published_stage_url() -- the same "real file on disk, most
advanced first" check already used for the "이전 대회" link -- instead
of duplicating a second copy of that logic here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER,
    assert_home_write_allowed,
    embed_game_code,
    embed_owner,
)
from klpga.website_v2.previous_tournament_link import latest_published_stage_url  # noqa: E402

GAME_CODE = "2026100005"
URL_BASE = f"/tournaments/2026/{GAME_CODE}/"
CURRENT_STAGE_HREF = latest_published_stage_url(URL_BASE, repo_root=REPO_ROOT)
STAGE_PAGE = REPO_ROOT / "docs" / CURRENT_STAGE_HREF.strip("/") / "index.html"
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

tourney = json.loads((ROOT / "content" / "website_v2" / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
TOURNAMENT_NAME = tourney["event_name"]


def _stage_main_html() -> str:
    if not STAGE_PAGE.is_file():
        raise SystemExit(f"no real published page at {STAGE_PAGE} -- run scripts/190 first")
    html = STAGE_PAGE.read_text(encoding="utf-8")
    if "<main>" not in html or "</main>" not in html:
        raise SystemExit(f"{STAGE_PAGE} has no <main>...</main> body to mirror")
    return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"


def _stage_description() -> str | None:
    """Real <meta name="description"> already written onto the stage
    page HOME is mirroring (scripts/190/196-199's own SEO metadata) --
    reused verbatim, never a second, independently-worded copy. None
    if the stage page predates that field (never fabricates one)."""
    if not STAGE_PAGE.is_file():
        return None
    html = STAGE_PAGE.read_text(encoding="utf-8")
    import re
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    return m.group(1) if m else None


def build() -> None:
    current_stage_href = CURRENT_STAGE_HREF
    main_html = _stage_main_html()
    description = _stage_description() or "KLPGA 공식 데이터 기반 골프 분석"

    head = (
        f'<head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {TOURNAMENT_NAME}</title>'
        f'<meta name="description" content="{description}">'
        f'<link rel="canonical" href="https://neogolfdata.com/">'
        f'<meta property="og:title" content="NEO GOLF DATA">'
        f'<meta property="og:description" content="{description}">'
        f'<meta property="og:url" content="https://neogolfdata.com/">'
        f'<meta property="og:type" content="website">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css"></head>'
    )
    body = (
        f'<body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner">'
        f'<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        f'<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        f'<span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a>'
        f'<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/" class="is-active" aria-current="page">홈</a>'
        f'<a href="{current_stage_href}">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        f'<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        f'{main_html}'
        f'<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="{current_stage_href}">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        f'<footer class="site-footer"><div class="site-footer__inner">'
        f'<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body>'
    )
    html = f'<!DOCTYPE html>\n<html lang="ko">{head}{body}</html>'
    html = embed_owner(html, CURRENT_TOURNAMENT_OWNER)
    html = embed_game_code(html, GAME_CODE)

    # writer_game_code (added 2026-10-07, incident fix): see
    # home_ownership_guard.assert_home_write_allowed's own docstring --
    # allow_transfer_from=CURRENT_TOURNAMENT_OWNER alone cannot tell this
    # script's own (HiteJinro) HOME apart from a newer tournament's.
    assert_home_write_allowed(
        DOCS_INDEX, CURRENT_TOURNAMENT_OWNER, repo_root=REPO_ROOT, allow_transfer_from=CURRENT_TOURNAMENT_OWNER,
        writer_game_code=GAME_CODE,
    )
    DOCS_INDEX.write_text(html, encoding="utf-8")
    print(json.dumps({
        "written": str(DOCS_INDEX),
        "note": "REAL production write -- not committed. git checkout -- docs/index.html restores the prior Hana R1 mirror (commit dc7330b439c92162119d86d3192733005af47cb7) if needed.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
