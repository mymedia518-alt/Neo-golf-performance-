"""Build the real NEO GOLF DATA homepage at docs/index.html.

CORRECTION (operator-flagged): earlier this branch's `docs/index.html`
was overwritten by a scratchpad "HOME mirror" script that copied R1's
entire leaderboard <main> body onto root HOME -- so the homepage root
literally became a second copy of the R1 results page. That is wrong:
R1's results must live ONLY at
docs/tournaments/2026/2026090002/r1/index.html, and root HOME must be
its own real first screen: brand hero + a single "현재 대회" card
(name/date/venue + PRE/R1/R2/R3/FR stage links) -- never a player
table.

Markup/CSS are 100% reused from what 151_build_hana_r1_page.py already
established for this tournament (same global-header block, same
.hero/.panel/.stage-nav classes, same footer/sr-data block) -- no new
CSS, no new visual language, just a different, smaller composition of
already-existing components. No player leaderboard markup appears
anywhere in this file.

og:title/description/url/type + twitter:card are homepage-generic
(NEO GOLF DATA brand identity, never a specific tournament's name) --
per explicit operator instruction. og:image is intentionally omitted:
the only image files in docs/assets/ (우승 (3).png and
kb-2026090003-r3-forecast-vs-final.png) are byte-identical to the KB
FINAL tournament's own result image, which must never be used as the
homepage's representative image; no other real, publicly-accessible
representative image exists in this repo yet.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

TOURNAMENT_NAME = "하나금융그룹 챔피언십"
TOURNAMENT_DATE_META = "2026.09.17 — 09.20"
TOURNAMENT_VENUE_META = "더헤븐 · West, South · Par 72 · 72홀 스트로크 플레이"
GAME_CODE = "2026090002"
URL_BASE = f"/tournaments/2026/{GAME_CODE}/"

# Real, currently-published stages only (docs/tournaments/2026/2026090002/
# has exactly pre/ and r1/ today) -- R2/R3/FR render as disabled
# placeholders, the exact same convention R1's own stage-nav already
# uses for its own not-yet-published stages.
_PUBLISHED_STAGES = {"pre", "r1"}
_STAGE_LABELS = [("pre", "사전 분석 PRE"), ("r1", "R1"), ("r2", "R2"), ("r3", "R3"), ("fr", "FR")]
_CURRENT_STAGE = "r1"


def _stage_nav_html() -> str:
    items = []
    for stage, label in _STAGE_LABELS:
        if stage in _PUBLISHED_STAGES:
            current = ' aria-current="page"' if stage == _CURRENT_STAGE else ""
            items.append(f'<li class="stage-nav__item"><a class="stage-nav__link" href="{URL_BASE}{stage}/"{current}>{label}</a></li>')
        else:
            items.append(f'<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">{label}</span></li>')
    return f'<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">{"".join(items)}</ol></nav>'


def build() -> None:
    current_stage_href = f"{URL_BASE}{_CURRENT_STAGE}/"
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta name="neo-home-owner" content="current-tournament-v1"><meta name="neo-stage-publication-ready" content="true"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEO GOLF DATA</title><meta property="og:title" content="NEO GOLF DATA"><meta property="og:description" content="KLPGA 공식 데이터 기반 골프 분석"><meta property="og:url" content="https://neogolfdata.com/"><meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image"><link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css"></head><body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span><span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span><span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a><nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/" class="is-active" aria-current="page">홈</a><a href="{current_stage_href}">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header><main><section class="hero" id="home-hero"><div><p class="eyebrow">NEO GOLF DATA</p><h1>KLPGA 공식 데이터 기반 골프 분석</h1><p class="meta">공식 기록만 사용하며, 확인되지 않은 정보는 추정하지 않습니다.</p></div></section><section class="panel" id="current-tournament" data-tournament-card="current" data-game-code="{GAME_CODE}"><div class="leaderboard-head"><h2>이번 대회</h2></div><p class="eyebrow">{_CURRENT_STAGE.upper()} 진행중</p><h3><a href="{current_stage_href}">{TOURNAMENT_NAME}</a></h3><p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">{TOURNAMENT_VENUE_META}</p>{_stage_nav_html()}</section></main><nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="{current_stage_href}">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav><footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>"""

    assert "leaderboard-table" not in html, "homepage must never carry a player leaderboard table"
    assert "우승 (3).png" not in html and "kb-2026090003" not in html, "homepage must never reference the KB FINAL image"

    DOCS_INDEX.write_text(html, encoding="utf-8")
    print("wrote", DOCS_INDEX)


if __name__ == "__main__":
    build()
