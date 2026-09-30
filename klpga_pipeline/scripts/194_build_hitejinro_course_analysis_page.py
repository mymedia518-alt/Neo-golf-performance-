"""Build a Course Analysis page for the HITE JINRO Championship (game_code
2026100005) from the real, already-generated content/website_v2/
knowledge_engine/tournament_dna/2026100005/TournamentDNA.json (see
scripts/tournament_dna_generator's own output and 193's sibling
investigation notes for how that file was produced).

NO NEW CSS, NO NEW COMPONENT MARKUP: every element below reuses a
pattern already live on this site --
  - header/breadcrumb/hero/footer/info-js: byte-identical shell to
    scripts/190_build_hitejinro_pre_page.py (itself byte-identical to
    the live Hana PRE page).
  - "watch_list" -> `<ul class="mover-list">`, the exact component
    scripts/109_build_kb_r1_page.py's real, live "PRE -> R1" movement
    section already uses for "a list of players with a directional
    delta" (see that script's own comment: "Reuses the site's own
    existing .mover-list/.delta pattern").
  - player name/sponsor -> klpga.website_v2.player_identity.
    render_player_identity, the one shared helper every other page
    already uses for this.
  - field composition / verdict -> the same `<section class="panel">`
    + plain `<p>`/`<ul>` shell used throughout the site, never a new
    grid/card layout.

WHERE THIS PAGE IS NOT YET LINKED FROM (a real, remaining decision,
not a data gap): the site's top nav has no "코스분석"/course-analysis
slot, and this tournament's own approved PRE page
(docs/tournaments/2026/2026100005/pre/index.html) has an explicitly
documented "no new sections" contract (see that script's own module
docstring, matching the live Hana PRE page byte-for-byte) that this
script deliberately does not touch. This page is built and ready at
its own URL; wiring a link to it into an already-approved page's
structure is an IA decision, not something this script decides for
itself.

course_dna / winning_profile / best_fits / danger_holes /
opportunity_holes are honestly empty in the source JSON (하이트진로 has
zero prior editions recorded in the historical warehouse) -- rendered
as one honest sentence, never invented content or an empty confusing
section.
"""
from __future__ import annotations

import json
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_identity import render_player_identity  # noqa: E402
from klpga.website_v2.player_link import player_report_exists  # noqa: E402

GAME_CODE = "2026100005"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "course-analysis" / "index.html"
DNA_PATH = CONTENT / "knowledge_engine" / "tournament_dna" / GAME_CODE / "TournamentDNA.json"


def main() -> None:
    dna = json.loads(DNA_PATH.read_text(encoding="utf-8"))
    tourney = json.loads((CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    event_name = tourney["event_name"]

    identity = dna["identity"]
    course_dna = dna["course_dna"]
    field_composition = dna["field_composition"]
    watch_list = dna["watch_list"]
    verdict = dna["verdict"]["summary"]
    story = dna["story"]

    if course_dna["axes"]:
        course_dna_html = "".join(
            f"<li><span>{_esc(a['label'])}</span><span class='delta'>{a['avg_sg']:+.2f} SG "
            f"({a['percentile']:.0f}백분위)</span></li>"
            for a in course_dna["axes"]
        )
        course_dna_section = (
            f"<h3>코스 DNA <small>과거 {course_dna['sample_events']}회 기준</small></h3>"
            f"<ul class='mover-list'>{course_dna_html}</ul>"
        )
    else:
        course_dna_section = (
            "<h3>코스 DNA</h3>"
            "<p class='note'>이 대회는 실제 과거 기록 0회를 근거로 분석되었습니다 -- "
            "하이트진로 챔피언십(블루헤런)의 이전 개최 이력이 이 저장소의 히스토리 웨어하우스에 없어, "
            "코스 특성/우승 프로필/유형 적합도는 아직 계산할 수 없습니다.</p>"
        )

    field_html = "".join(
        f"<li><span>{_esc(fc['label'])}</span><span class='delta'>{fc['count']}명</span></li>"
        for fc in field_composition
    )

    def _watch_row(w: dict) -> str:
        # Same contract every other page's player links already use --
        # a name only ever links when player_link.player_report_exists()
        # confirms a real, committed, production-ready report exists
        # (see that module's own docstring). None of the 546 committed
        # Player Intelligence latest.json docs found this session have
        # been promoted to a released docs/player/<id>/ page yet except
        # 10097, so this correctly renders every other name unlinked
        # rather than a broken href.
        href = f"/player/{w['player_id']}/" if player_report_exists(w["player_id"]) else None
        identity_html = render_player_identity(w["player_name"], "", quote="'", href=href)
        return (
            f"<li>{identity_html}"
            f"<span class='delta'>{_esc(w['component_label'])} {w['direction']} {w['delta']:+.2f} SG</span></li>"
        )

    watch_html = "".join(_watch_row(w) for w in watch_list)

    story_html = "".join(f"<li>{_esc(s)}</li>" for s in story)

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 코스 분석</title>'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../../assets/neo.css"></head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">대회</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main>'
        '<nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">{_esc(event_name)}</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<span aria-current="page">코스 분석</span></nav>'
        '<section class="hero" id="course-analysis-hero"><div><p class="eyebrow">코스 분석</p>'
        f'<h1>{_esc(event_name)}</h1>'
        f'<p class="meta">{_esc(identity["venue"] or "")}</p>'
        f'<p class="meta">{_esc(verdict)}</p></div></section>'
    )

    body = (
        '<section class="panel" id="course-dna">' + course_dna_section + '</section>'
        '<section class="panel" id="field-composition"><h2>참가 선수 유형 구성</h2>'
        f"<ul class='mover-list'>{field_html}</ul>"
        f"<p class='note'>미분류 {dna['field_unclassified']}명 포함, 총 {identity['field_size']}명</p>"
        '</section>'
        '<section class="panel" id="watch-list"><h2>최근 경기력 변동 선수</h2>'
        f"<ul class='mover-list'>{watch_html}</ul>"
        '</section>'
        '<section class="panel" id="story"><h2>요약</h2>'
        f"<ul>{story_html}</ul>"
        '</section>'
    )

    info_js = ""  # no info-popover on this page -- no equivalent control exists here

    footer = (
        '</main>' + info_js +
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )

    html = header + body + footer
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE), "note": "NOT linked from any nav or the approved PRE page -- see module docstring"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
