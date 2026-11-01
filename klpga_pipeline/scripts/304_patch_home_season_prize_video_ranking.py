"""Rebuild HOME's #season-prize-video panel (consolidated; supersedes
the earlier draft, never committed, that this replaces outright).

  - Left: the S-OIL final-prize video, enlarged, always side-by-side
    with the right column at every width (no mobile stacking). Poster
    image is the real 1-second video frame (ffmpeg-extracted).
  - Right: a live, auto-scrolling NEO 랭킹 list (1-100), fetched
    client-side from /data/neo-ranking-2026-11-01.json -- the exact
    same data file feeding /ranking/, so the two pages' numbers can
    never drift. No number is hardcoded.

Column ratio: 2fr:3fr at >=768px, 5fr:6fr below. Both columns'
height is driven by the video's own 9:16 aspect-ratio box (grid
default align-items:stretch); the ranking list auto-scrolls inside
that fixed height via its own flex:1;min-height:0;overflow:hidden
area. Heading+meta blocks on both sides reserve identical height
(h2 min-height for 2 lines, bottom-aligned text) so the video and the
ranking box start at the same Y regardless of each side's actual
title/description length.

Player names are never truncated (white-space:nowrap, no ellipsis,
flex-shrink:0). At narrow RANKING-PANEL widths (not viewport widths --
via a CSS container query scoped to the ranking panel itself) less
important elements are dropped in order: sponsor tag under 520px of
panel width, then the score bar under 380px, always leaving room for
the full player name. The sponsor/name overlap bug from the previous
draft is fixed by giving the sponsor span its own shrink/ellipsis
budget while the name itself never shrinks.

Scoped entirely under #season-prize-video (new CSS selectors) and the
existing .neo-home-media-grid/.neo-home-media-item rules (used nowhere
else on the site, confirmed) -- no other section or page is touched.
The seed-bubble-zone image file itself is left on disk, only removed
from this page.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

POSTER_PATH = REPO_ROOT / "docs" / "assets" / "clips" / "soil-2026-final-335-poster.jpg"

OLD_GRID_CSS = (
    ".neo-home-media-grid{display:grid;grid-template-columns:minmax(15rem,.36fr) minmax(0,1fr);"
    "gap:clamp(1.25rem,2.5vw,2.5rem);align-items:start}"
    ".neo-home-media-item{min-width:0;margin:0}"
    ".neo-home-media-item .section-heading{margin-bottom:.45rem}"
    ".neo-home-media-item .meta{min-height:2.8em;margin:.35rem 0 .6rem}"
    ".neo-home-media-item video,.neo-home-media-item img{display:block;width:100%;height:auto;margin-top:.4rem}"
    ".neo-home-media-item img{border:1px solid var(--line)}"
)

NEW_GRID_CSS = (
    "#season-prize-video .neo-home-media-grid{display:grid;grid-template-columns:2fr 3fr;"
    "gap:clamp(1rem,2.5vw,2.5rem);align-items:stretch}"
    "@media(max-width:767px){#season-prize-video .neo-home-media-grid{grid-template-columns:5fr 6fr;"
    "gap:.6rem}}"
    "#season-prize-video .neo-home-media-item{min-width:0;margin:0;display:flex;flex-direction:column}"
    "#season-prize-video .neo-home-media-item__head{display:flex;flex-direction:column;justify-content:flex-end;"
    "min-height:5.6rem}"
    "#season-prize-video .neo-home-media-item .section-heading{margin-bottom:.45rem;flex-direction:column;align-items:flex-start}"
    "#season-prize-video .neo-home-media-item .section-heading h2{margin:.25rem 0 0}"
    "#season-prize-video .neo-home-media-item .meta{margin:.35rem 0 .6rem}"
    "#season-prize-video .neo-home-media-item video,#season-prize-video .neo-home-media-item img{"
    "display:block;width:100%;height:auto;margin-top:.4rem}"
    "#season-prize-video .neo-home-media-item--video video{aspect-ratio:9/16;height:auto;border-radius:6px}"
    "#season-prize-video .neo-home-media-item--video{container-type:inline-size;container-name:neo-video-panel}"
    "#season-prize-video .neo-home-media-item--ranking{container-type:inline-size;container-name:neo-ranking-panel;"
    "border-left:1px solid var(--line);padding-left:clamp(.6rem,2.5vw,1.5rem)}"
    "#season-prize-video .neo-home-media-item--video h2,"
    "#season-prize-video .neo-home-media-item--ranking h2{"
    "font-size:clamp(16px,7.2cqi,28px);line-height:1.25}"
    "#season-prize-video .neo-home-media-item--video h2 span,"
    "#season-prize-video .neo-home-media-item--ranking h2 span{display:block;white-space:nowrap}"
    "#season-prize-video .neo-home-media-item--video .meta,"
    "#season-prize-video .neo-home-media-item--ranking .meta{"
    "font-size:clamp(12px,3.6cqi,15px);white-space:nowrap;overflow:hidden}"
    "#season-prize-video .neo-home-ranking{position:relative;flex:1;min-height:0;overflow:hidden;"
    "margin-top:.4rem;background:var(--accent-soft);border:1px solid var(--gold);border-radius:6px}"
    "#season-prize-video .neo-home-ranking__scroll{position:absolute;inset:0;overflow-y:auto;"
    "overscroll-behavior:contain;-webkit-overflow-scrolling:touch;scrollbar-width:none}"
    "#season-prize-video .neo-home-ranking__scroll::-webkit-scrollbar{width:0;height:0}"
    "#season-prize-video .neo-home-ranking::before,#season-prize-video .neo-home-ranking::after{"
    "content:'';position:absolute;left:0;right:0;height:2.4rem;pointer-events:none;z-index:2}"
    "#season-prize-video .neo-home-ranking::before{top:0;background:linear-gradient(var(--accent-soft),rgba(31,42,20,0))}"
    "#season-prize-video .neo-home-ranking::after{bottom:0;background:linear-gradient(rgba(31,42,20,0),var(--accent-soft))}"
    "#season-prize-video .neo-home-ranking__list{list-style:none;margin:0;padding:0}"
    "#season-prize-video .neo-home-ranking__row{display:grid;"
    "grid-template-columns:2.3rem minmax(0,1fr) 4.5rem 4rem;align-items:center;gap:.55rem;"
    "padding:.5rem .85rem;border-bottom:1px solid rgba(216,171,92,.14);font-size:.88rem}"
    "#season-prize-video .neo-home-ranking__row:nth-child(even){background:rgba(216,171,92,.055)}"
    "#season-prize-video .neo-home-ranking__rank{font-weight:800;color:var(--muted);font-variant-numeric:tabular-nums}"
    "#season-prize-video .neo-home-ranking__row--top .neo-home-ranking__rank{color:var(--gold)}"
    "#season-prize-video .neo-home-ranking__name{display:flex;align-items:baseline;gap:.4rem;min-width:0}"
    "#season-prize-video .neo-home-ranking__name strong{font-weight:700;color:var(--ink);white-space:nowrap;flex-shrink:0}"
    "#season-prize-video .neo-home-ranking__name span{color:var(--muted);font-size:.8em;white-space:nowrap;"
    "overflow:hidden;text-overflow:ellipsis;min-width:0;flex-shrink:1}"
    "#season-prize-video .neo-home-ranking__bar{position:relative;height:.38rem;background:rgba(216,171,92,.12);"
    "border-radius:999px;overflow:hidden;min-width:2.5rem}"
    "#season-prize-video .neo-home-ranking__bar span{position:absolute;inset:0 auto 0 0;background:var(--green);border-radius:999px}"
    "#season-prize-video .neo-home-ranking__score{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;"
    "color:var(--ink);white-space:nowrap}"
    "#season-prize-video .neo-home-ranking__footer{display:flex;flex-wrap:wrap;align-items:center;"
    "justify-content:space-between;gap:.6rem 1rem;margin-top:.75rem;font-size:.92rem;color:var(--muted)}"
    "#season-prize-video .neo-home-ranking__cta{display:inline-flex;align-items:center;gap:.3rem;"
    "padding:.5rem 1.1rem;border:1px solid var(--gold);border-radius:999px;color:var(--gold);"
    "font-weight:700;text-decoration:none;white-space:nowrap;flex-shrink:0}"
    "#season-prize-video .neo-home-ranking__cta:hover,#season-prize-video .neo-home-ranking__cta:focus-visible{"
    "background:rgba(216,171,92,.12)}"
    "@container neo-ranking-panel (max-width:520px){"
    "#season-prize-video .neo-home-ranking__name span{display:none}"
    "}"
    "@container neo-ranking-panel (max-width:380px){"
    "#season-prize-video .neo-home-ranking__row{grid-template-columns:1.9rem minmax(0,1fr) 3.6rem}"
    "#season-prize-video .neo-home-ranking__bar{display:none}"
    "}"
)

OLD_MOBILE_CSS = "@media(max-width:760px){.neo-home-media-grid{grid-template-columns:minmax(0,1fr)}}"

OLD_SECTION = (
    '<section class="home-section" id="season-prize-video"><div class="neo-home-media-grid">'
    '<figure class="neo-home-media-item"><div class="section-heading"><div>'
    '<p class="section-label">영상</p><h2>S-OIL 챔피언십 최종, 시드가 갈린 335만 원</h2></div></div>'
    '<p class="meta">2026년 11월 1일 최종 상금순위 기준</p>'
    '<video controls autoplay muted playsinline loop preload="auto" '
    'src="/assets/clips/soil-2026-final-335.mp4" '
    'aria-label="S-OIL 챔피언십 최종, 시드가 갈린 335만 원 영상"></video></figure>'
    '<figure class="neo-home-media-item"><div class="section-heading"><div>'
    '<p class="section-label">시드 경쟁</p><h2>2026년 시드 버블존</h2></div></div>'
    '<p class="meta">58~68위 선수의 시드 유지 가능성 · 남은 대회 2개</p>'
    '<img src="/assets/klpga-2026-seed-bubble-zone.jpg" '
    'alt="2026년 시드 버블존. 58위부터 68위 선수의 시드 유지 가능성과 60위 기준선" '
    'loading="lazy" decoding="async"></figure></div></section>'
)

NEW_SECTION = (
    '<section class="home-section" id="season-prize-video"><div class="neo-home-media-grid">'
    '<figure class="neo-home-media-item neo-home-media-item--video">'
    '<div class="neo-home-media-item__head"><div class="section-heading"><div>'
    '<p class="section-label">영상</p><h2><span>S-OIL 챔피언십 최종,</span>'
    '<span>시드가 갈린 335만 원</span></h2></div></div>'
    '<p class="meta">2026년 11월 1일 최종 상금순위 기준</p></div>'
    '<video controls autoplay muted playsinline loop preload="metadata" '
    'poster="/assets/clips/soil-2026-final-335-poster.jpg" '
    'src="/assets/clips/soil-2026-final-335.mp4" '
    'aria-label="S-OIL 챔피언십 최종, 시드가 갈린 335만 원 영상"></video></figure>'
    '<figure class="neo-home-media-item neo-home-media-item--ranking">'
    '<div class="neo-home-media-item__head"><div class="section-heading"><div>'
    '<p class="section-label">NEO 랭킹</p><h2><span>2026 시즌</span><span>NEO 랭킹</span></h2></div></div>'
    "<p class='meta'>2026년 11월 1일 기준 · S-OIL 챔피언십 반영</p></div>"
    '<div class="neo-home-ranking" id="homeNeoRanking">'
    '<div class="neo-home-ranking__scroll" id="homeNeoRankingScroll">'
    '<ol class="neo-home-ranking__list" id="homeNeoRankingList" '
    'aria-label="2026 시즌 NEO 랭킹, 자동으로 스크롤됩니다"></ol>'
    "</div></div>"
    "<p class='neo-home-ranking__footer'><span>NEO 랭킹은 경기력을 봅니다.</span>"
    '<a class="neo-home-ranking__cta" href="/ranking/">전체 보기 →</a></p>'
    "</figure></div></section>"
)

HEAD_ALIGN_JS = (
    "<script>(function(){"
    "var heads=document.querySelectorAll('#season-prize-video .neo-home-media-item__head');"
    "if(heads.length<2)return;"
    "function align(){"
    "heads.forEach(function(h){h.style.minHeight='0'});"
    "var max=0;"
    "heads.forEach(function(h){max=Math.max(max,h.getBoundingClientRect().height)});"
    "heads.forEach(function(h){h.style.minHeight=max+'px'});"
    "}"
    "align();"
    "window.addEventListener('resize',function(){"
    "clearTimeout(window.__neoHeadAlignT);"
    "window.__neoHeadAlignT=setTimeout(align,120)"
    "});"
    "if(document.fonts&&document.fonts.ready){document.fonts.ready.then(align)}"
    "})();</script>"
)

HOME_RANKING_JS = (
    "<script>(function(){"
    "var LIST_ID='homeNeoRankingList';var SCROLL_ID='homeNeoRankingScroll';"
    "var list=document.getElementById(LIST_ID);var scrollEl=document.getElementById(SCROLL_ID);"
    "if(!list||!scrollEl)return;"
    "fetch('/data/neo-ranking-2026-11-01.json').then(function(r){"
    "if(!r.ok)throw new Error('ranking data unavailable');return r.json()"
    "}).then(function(data){"
    "var players=(data.players||[]).filter(function(p){return p.status==='정식 순위'});"
    "players.sort(function(a,b){return a.rank-b.rank});"
    "if(!players.length)return;"
    "var scores=players.map(function(p){return p.score});"
    "var max=Math.max.apply(null,scores);var min=Math.min.apply(null,scores);"
    "var span=max-min||1;"
    "function esc(s){return String(s==null?'':s).replace(/[&<>\"']/g,function(c){"
    "return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]"
    "})}"
    "function rowHtml(p){"
    "var pct=Math.max(2,((p.score-min)/span*100));"
    "var topClass=p.rank<=3?' neo-home-ranking__row--top':'';"
    "return \"<li class='neo-home-ranking__row\"+topClass+\"'>\"+"
    "\"<span class='neo-home-ranking__rank'>\"+p.rank+\"</span>\"+"
    "\"<span class='neo-home-ranking__name'><strong>\"+esc(p.name)+\"</strong>\"+"
    "(p.sponsor?\"<span>\"+esc(p.sponsor)+\"</span>\":'')+\"</span>\"+"
    "\"<span class='neo-home-ranking__bar'><span style='width:\"+pct.toFixed(1)+\"%'></span></span>\"+"
    "\"<span class='neo-home-ranking__score'>\"+p.score.toFixed(3)+\"</span>\"+"
    "\"</li>\""
    "}"
    "var rowsHtml=players.map(rowHtml).join('');"
    "list.innerHTML=rowsHtml+rowsHtml;"
    "var reduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;"
    "if(reduceMotion)return;"
    "var firstRow=list.querySelector('.neo-home-ranking__row');"
    "if(!firstRow)return;"
    "var rowHeight=firstRow.getBoundingClientRect().height||40;"
    "var speed=rowHeight/1.5;" # px per second: ~1.5s to scroll past one row
    "var half=0;"
    "function measure(){half=scrollEl.scrollHeight/2}"
    "measure();"
    "window.addEventListener('resize',measure);"
    "var paused=false;var pos=scrollEl.scrollTop;var last=null;"
    "function step(ts){"
    "if(!paused&&last!==null){"
    "var dt=(ts-last)/1000;"
    "pos+=speed*dt;"
    "if(half>0&&pos>=half){pos-=half}"
    "scrollEl.scrollTop=pos"
    "}else if(paused){"
    "pos=scrollEl.scrollTop"
    "}"
    "last=ts;"
    "window.requestAnimationFrame(step)"
    "}"
    "window.requestAnimationFrame(step);"
    "scrollEl.addEventListener('pointerenter',function(){paused=true});"
    "scrollEl.addEventListener('pointerleave',function(){paused=false});"
    "scrollEl.addEventListener('touchstart',function(){paused=true},{passive:true});"
    "scrollEl.addEventListener('touchend',function(){paused=false},{passive:true});"
    "}).catch(function(err){"
    "list.innerHTML=\"<li class='neo-home-ranking__row'><span class='neo-home-ranking__name'>"
    "<strong>랭킹을 불러오지 못했습니다</strong></span></li>\""
    "})"
    "})();</script>"
)


def main() -> None:
    assert POSTER_PATH.is_file(), f"poster image not found at {POSTER_PATH} -- run ffmpeg extraction first"

    html = DOCS_INDEX.read_text(encoding="utf-8")

    assert html.count(OLD_GRID_CSS) == 1, f"expected exactly 1 match of the original grid CSS, found {html.count(OLD_GRID_CSS)}"
    assert html.count(OLD_MOBILE_CSS) == 1, f"expected exactly 1 match of the original mobile CSS, found {html.count(OLD_MOBILE_CSS)}"
    assert html.count(OLD_SECTION) == 1, f"expected exactly 1 match of the original season-prize-video section, found {html.count(OLD_SECTION)}"

    html2 = html.replace(OLD_GRID_CSS, NEW_GRID_CSS, 1)
    # the old mobile-stacking rule is deleted outright (always side-by-side now)
    html2 = html2.replace(OLD_MOBILE_CSS, "", 1)
    html2 = html2.replace(OLD_SECTION, NEW_SECTION, 1)

    assert html2.count("</body></html>") == 1
    html2 = html2.replace("</body></html>", HEAD_ALIGN_JS + HOME_RANKING_JS + "</body></html>", 1)

    assert html2 != html
    assert "klpga-2026-seed-bubble-zone.jpg" not in html2, "seed bubble zone image reference should be removed from HOME"
    assert "homeNeoRankingList" in html2
    assert "/data/neo-ranking-2026-11-01.json" in html2
    assert "soil-2026-final-335-poster.jpg" in html2
    assert "@container neo-ranking-panel" in html2
    assert "neo-home-media-item__head" in html2
    assert "<h2><span>S-OIL 챔피언십 최종,</span><span>시드가 갈린 335만 원</span></h2>" in html2
    assert "<h2><span>2026 시즌</span><span>NEO 랭킹</span></h2>" in html2

    DOCS_INDEX.write_text(html2, encoding="utf-8")
    print("written", str(DOCS_INDEX))


if __name__ == "__main__":
    main()
