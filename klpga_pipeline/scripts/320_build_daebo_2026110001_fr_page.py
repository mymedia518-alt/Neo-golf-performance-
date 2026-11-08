"""Build the official FINAL result page for 대보 하우스디 챔피언십
(game_code 2026110001) -- docs/tournaments/2026/2026110001/fr/index.html.

Source of truth: DAEBO_2026110001_FR_OFFICIAL_V1.json (scripts/316):
real final rank (KLPGA's own finish order, including real scorecard
ties) and R1-R3 scores for the 59 real finishers, plus 방신실's real
WD (withdrew during Round 2, absent from the field entirely per
KLPGA's own rules -- shown separately below the main table, never
folded into the ranked field).

SCOPE: this tournament was 3 rounds (R1, R2, FR -- no separate "R3"
label; the final round is always labelled FR on this site, matching
the live page's own convention), unlike S-OIL's 4-round event.

No forecast/win-probability columns appear on this page. Unlike
S-OIL's FR page (scripts/292), which could show a frozen pre-FR
forecast next to the real outcome, Daebo's own per-round live
probability snapshots (scripts/307's output) were overwritten round by
round on the live/2026110001 branch before the retention bug was found
and fixed (see .github/workflows/daebo-2026110001-live-cycle.yml) --
the actual pre-FR forecast snapshot no longer exists anywhere, so this
page shows only the real, verified official record rather than
fabricate or approximate a forecast comparison that isn't backed by a
real preserved snapshot.

This tournament also never had separate static PRE/R1/R2/R3 pages
(it used the new real-time "live" page instead of this project's
older per-stage static-page pattern), so this page's stage-nav links
only to LIVE and FR, not a full PRE/R1/R2/R3/FR set.
"""
from __future__ import annotations

import hashlib
import json
import sys
from html import escape as _esc
from pathlib import Path

_SITE_ORIGIN = "https://neogolfdata.com"

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402

GAME_CODE = "2026110001"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "fr" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

ENTRY_SNAPSHOT_PATH = CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
FR_OFFICIAL_PATH = CONTENT / f"DAEBO_{GAME_CODE}_FR_OFFICIAL_V1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    tourney = _load(TOURNAMENT_INFO_PATH)
    entry = _load(ENTRY_SNAPSHOT_PATH)
    fr_official = _load(FR_OFFICIAL_PATH)
    assert tourney["game_code"] == GAME_CODE
    assert fr_official["verification_pass"], "FR official data failed its own verification -- refusing to build the page"

    entry_by_id = {str(r["player_code"]): r for r in entry["records"]}
    official_by_id = {r["player_id"]: r for r in fr_official["records"]}
    assert len(official_by_id) == fr_official["field_count"] == 59

    withdrawals = fr_official["withdrawals_detail"]
    assert len(withdrawals) == fr_official["withdrawals"] == 1
    assert fr_official["roster_total"] == len(official_by_id) + len(withdrawals) == 60

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    rows_sorted = sorted(official_by_id.values(), key=lambda r: r["final_rank_numeric"])

    def _flag_cell(pid: str) -> str:
        country_code = entry_by_id.get(pid, {}).get("nationality", "KOR")
        if country_code in FLAG_ASSETS:
            return (
                f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
                f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            )
        return ""

    def _name_cell(pid: str, name: str) -> str:
        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        base = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(name)}</span>"
        linked = linked_player_name_cell(pid, base)
        return (
            f"{_flag_cell(pid)}{linked}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
        )

    rows_html = []
    for r in rows_sorted:
        pid = r["player_id"]
        rank_cell = f"T{r['final_rank']}" if r["final_tie"] else r["final_rank"]
        to_par = r["score_to_par"]
        to_par_cell = f"{to_par:+d}" if to_par else "0"
        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{_name_cell(pid, r['player_name'])}</th>"
            f"<td data-label='합계'><strong>{to_par_cell}</strong></td>"
            f"<td data-label='R1'>{r['r1_score']}</td>"
            f"<td data-label='R2'>{r['r2_score']}</td>"
            f"<td data-label='FR'>{r['r3_score']}</td>"
            "</tr>"
        )

    wd_rows_html = []
    for w in withdrawals:
        pid = w["player_id"]
        wd_rows_html.append(
            "<tr class='is-eliminated'>"
            "<td data-label='순위'>&mdash;</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{_name_cell(pid, w['player_name'])}</th>"
            f"<td data-label='합계'>기권</td>"
            f"<td colspan='3' data-label='비고'>{_esc(w['withdrew_during'])} 중 기권</td>"
            "</tr>"
        )

    event_name = tourney["event_name"]
    start = tourney["start_date"]
    end = tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    # Matches the live page's own established course naming
    # ("서원밸리CC 서원힐스") rather than the raw course_name field alone.
    course_line = "서원밸리CC 서원힐스"
    if tourney.get("is_stroke_play"):
        course_line += " · 스트로크 플레이"

    winner_name = fr_official["winner_player_name"]
    winner_to_par = fr_official["winner_score_to_par"]
    winner_to_par_str = f"{winner_to_par:+d}" if winner_to_par else "0"

    seo_description = f"{event_name} 공식 최종 결과 · 우승 {winner_name} {winner_to_par_str} · NEO GOLF DATA"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/fr/"

    factual_sha256 = _sha256(FR_OFFICIAL_PATH)

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 공식 최종 결과</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        f'<meta property="og:title" content="NEO GOLF DATA · {_esc(event_name)} 공식 최종 결과">'
        f'<meta property="og:description" content="{_esc(seo_description)}">'
        f'<meta property="og:url" content="{canonical_url}">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css">'
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        '<meta name="neo-publication-mode" content="factual-only">'
        f'<meta name="neo-game-code" content="{GAME_CODE}">'
        '<meta name="neo-round-number" content="3">'
        f'<meta name="neo-factual-sha256" content="{factual_sha256}">'
        '</head><body><header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><img class="neo-brand-logo" src="/assets/neo-logo.png" alt="NEO GOLF DATA" width="362" height="160">'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        '<a href="/tournaments/" class="is-active" aria-current="page">대회 기록</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span>{_esc(event_name)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<span aria-current="page">FR</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">공식 최종 결과</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f"<p class='meta'>{_esc(course_line)}</p>"
        f"<p class='meta'><strong>{_esc(winner_name)}</strong> 우승 · 최종 {winner_to_par_str} · 72홀 정규승부(플레이오프 없음)</p>"
        f"<p class='meta'>이전 대회 <a href='/tournaments/2026/2026100001/fr/'>제20회 S-OIL 챔피언십</a></p></div></section>"
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/live/">LIVE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/fr/" aria-current="page">FR</a></li>'
        "</ol></nav>"
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="fr">'
        f"<div class=\"leaderboard-head\"><h2>최종 결과 <small>{len(rows_sorted)}명 완주 · {len(withdrawals)}명 기권</small></h2></div>"
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1">'
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>FR</th></tr></thead>"
        "<tbody>" + "".join(rows_html) + "".join(wd_rows_html) + "</tbody></table></div>"
        f'<p><a href="https://klpga.co.kr/web/tourRecord/scoreRecord?gameCode={GAME_CODE}" rel="noopener">KLPGA 공식 기록 원문 ↗</a></p>'
        '</section>'
    )

    footer = (
        "</main>"
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        '<a href="/tournaments/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    print(json.dumps({
        "written": str(OUT_PAGE),
        "field": len(rows_sorted),
        "withdrawals": len(withdrawals),
        "winner": winner_name,
        "winner_to_par": winner_to_par_str,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
