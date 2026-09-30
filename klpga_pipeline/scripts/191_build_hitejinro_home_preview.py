"""HOME integration -- CANDIDATE PREVIEW ONLY, never writes to the live
docs/index.html.

Why this is a preview and not a live flip: `docs/index.html` is
currently, legitimately owned by the Hana Financial Group Championship
(game_code 2026090002) under CURRENT_TOURNAMENT_OWNER (see
klpga.website_v2.home_ownership_guard, klpga.website_v2.
hana_home_stage_router, scripts/156_build_home_page.py). Per a live
recheck of docs/tournaments/2026/2026090002/ in this session, Hana is
currently at stage R1 (real R2/R3/final pages exist on disk but are not
yet wired into HOME's stage router / the publication allow-list) --
NOT at FINAL. Swapping root HOME away from an in-progress, different,
unrelated tournament's live coverage to an unrelated new tournament's
PRE page is an editorial/business decision with real visitor-facing
consequences, not a data-completeness or code question -- outside what
this build should decide unilaterally. This script instead produces
exactly what HOME WOULD look like if/when that transfer is approved,
at a non-live path, so the actual flip (once approved) is a one-line
change: point DOCS_INDEX at REPO_ROOT/docs/index.html instead of this
preview path, and pass CURRENT_TOURNAMENT_OWNER as writer_owner via
klpga.website_v2.home_ownership_guard.assert_home_write_allowed exactly
as scripts/156 already does for Hana (same owner id -- both are "the
current tournament" -- so the guard itself raises no conflict; the
open question is purely editorial: should 2026100005 supersede
2026090002 as "current" while Hana is still mid-tournament).

Mirrors scripts/156_build_home_page.py's own build() shell/mechanism
byte-for-byte (head/header/footer, and the literal
"<main>...</main>" mirror-from-the-real-published-stage-page technique
from klpga.website_v2.hana_home_stage_router.current_stage_main_html)
-- only the embedded tournament (2026100005's own real, already-built
PRE page) and its nav target differ.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

GAME_CODE = "2026100005"
URL_BASE = f"/tournaments/2026/{GAME_CODE}/"
STAGE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
OUT_PAGE = ROOT / "candidate" / "2026100005-home-preview" / "index.html"

tourney = json.loads((ROOT / "content" / "website_v2" / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
TOURNAMENT_NAME = tourney["event_name"]


def _stage_main_html() -> str:
    """Same technique as hana_home_stage_router.current_stage_main_html:
    read the real, already-published stage page's own <main>...</main>
    verbatim -- never rebuilt/resimulated."""
    if not STAGE_PAGE.is_file():
        raise SystemExit(f"no real published page at {STAGE_PAGE} -- run scripts/190 first")
    html = STAGE_PAGE.read_text(encoding="utf-8")
    if "<main>" not in html or "</main>" not in html:
        raise SystemExit(f"{STAGE_PAGE} has no <main>...</main> body to mirror")
    return "<main>" + html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"


def build() -> None:
    current_stage_href = f"{URL_BASE}pre/"
    main_html = _stage_main_html()

    head = (
        f'<head><meta name="neo-home-owner" content="current-tournament-v1">'
        f'<meta name="neo-stage-publication-ready" content="true"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {TOURNAMENT_NAME}</title>'
        f'<meta property="og:title" content="NEO GOLF DATA">'
        f'<meta property="og:description" content="KLPGA 공식 데이터 기반 골프 분석">'
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

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE), "note": "CANDIDATE PREVIEW ONLY -- docs/index.html was not touched"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
