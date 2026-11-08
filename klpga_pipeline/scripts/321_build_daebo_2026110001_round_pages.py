"""Build static per-round win-probability pages for 대보 하우스디 챔피언십
(game_code 2026110001) -- docs/tournaments/2026/2026110001/r1/index.html
and .../r2/index.html.

Source of truth: DAEBO_2026110001_LIVE_PROBABILITY_R{1,2}_V1.json --
the real round-end snapshots scripts/307_build_live_probability.py
produced live during the tournament. These were overwritten on the
live/2026110001 branch by the next round's build (a retention bug in
daebo-2026110001-live-cycle.yml, fixed after the tournament ended) and
recovered 2026-11-08 from GitHub's still-live dangling commits before
they aged out -- see each file's own "recovery_note" field. Content is
byte-identical to what the live page actually showed at the time.

This is a REFERENCE_ESTIMATE model output (see sg_live_v1.py), never
independently Red Team reviewed -- NOT an official KLPGA ranking. Every
page here repeats that disclosure in its <title>/<meta description>
and carries `noindex`, exactly like the live page did while the
tournament was running.

방신실 withdrew during Round 2 at holes_completed=1. The R2 snapshot's
own "probabilities" list still carries a stray all-zero row for her
(a genuine artifact of the live model's own historical output, not
something manufactured here) alongside the correct "eliminated_players"
WD entry; this script keeps the WD entry and drops the duplicate zero
row rather than showing her twice, since that is strictly a cleaner
rendering of the same underlying facts, not a changed one. She is
absent entirely from the R1 page (she had not withdrawn yet).

Round 1 has no "round_scores" list in its snapshot (that field was
only added starting Round 2's build) -- this script synthesizes a
single-entry round_scores from current_total_to_par for R1 so the "1R"
column renders consistently with R2's own real round_scores list.
"""
from __future__ import annotations

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

GAME_CODE = "2026110001"
EVENT_NAME = "대보 하우스디 챔피언십"
DATE_RANGE = "2026.11.06 — 11.08"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

ROUNDS = {
    1: {
        "path": CONTENT / f"DAEBO_{GAME_CODE}_LIVE_PROBABILITY_R1_V1.json",
        "out": REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",
        "label": "1R",
        "stage": "R1",
    },
    2: {
        "path": CONTENT / f"DAEBO_{GAME_CODE}_LIVE_PROBABILITY_R2_V1.json",
        "out": REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html",
        "label": "2R",
        "stage": "R2",
    },
}


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _fmt_to_par(value) -> str:
    if value is None:
        return "—"
    if value == 0:
        return "E"
    return f"+{value}" if value > 0 else str(value)


def _flag_cell(nationality: str) -> str:
    if nationality in FLAG_ASSETS:
        return (
            f"<img src='/assets/flags/{nationality}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
        )
    return ""


def _name_cell(p: dict) -> str:
    base = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(p['player_name'])}</span>"
    linked = linked_player_name_cell(p["player_id"], base)
    sponsor_text = _esc(p.get("sponsor") or "")
    return (
        f"{_flag_cell(p.get('nationality', ''))}{linked}"
        f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
    )


def build_round(round_number: int) -> None:
    cfg = ROUNDS[round_number]
    doc = json.loads(cfg["path"].read_text(encoding="utf-8"))
    assert doc["game_code"] == GAME_CODE
    assert doc["current_round"] == round_number
    assert doc["round_complete"], f"round {round_number} snapshot is not marked complete -- refusing to archive a partial round"

    rounds_total = doc["rounds_total"]
    show_total = round_number > 1

    eliminated = doc.get("eliminated_players") or []
    eliminated_ids = {p["player_id"] for p in eliminated}
    active = [p for p in doc["probabilities"] if p["player_id"] not in eliminated_ids]
    active.sort(key=lambda p: -p["win_probability"])

    round_headers = "".join(f"<th>{i + 1}R</th>" for i in range(round_number))
    total_header = "<th>합계</th>" if show_total else ""

    rows_html = []
    for p in active:
        holes = p.get("holes_completed")
        progress = "완료" if (holes is not None and holes >= 18) else (f"{holes}H" if holes is not None else "—")
        round_scores = p.get("round_scores") or [p["current_total_to_par"]]
        round_cells = "".join(
            f"<td data-label='{i + 1}R'>{_fmt_to_par(s)}</td>" for i, s in enumerate(round_scores)
        )
        total_cell = f"<td data-label='합계'>{_fmt_to_par(p['current_total_to_par'])}</td>" if show_total else ""
        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{_esc(str(p.get('rank_display', '')))}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{_name_cell(p)}</th>"
            f"<td data-label='진행'>{progress}</td>"
            f"{round_cells}{total_cell}"
            f"<td data-label='TOP20'>{_fmt_pct(p['top20_probability'])}</td>"
            f"<td data-label='TOP10'>{_fmt_pct(p['top10_probability'])}</td>"
            f"<td data-label='TOP5'>{_fmt_pct(p['top5_probability'])}</td>"
            f"<td class='winpct' data-label='우승확률'><strong>{_fmt_pct(p['win_probability'])}</strong></td>"
            "</tr>"
        )

    wd_rows_html = []
    for w in eliminated:
        label = {"WD": "기권", "DQ": "실격", "CUT": "컷 탈락"}.get(str(w.get("status", "")).upper(), "제외")
        empty_round_cells = "".join(f"<td data-label='{i + 1}R'>—</td>" for i in range(round_number))
        empty_total_cell = "<td data-label='합계'>—</td>" if show_total else ""
        wd_rows_html.append(
            "<tr class='is-eliminated'>"
            "<td data-label='순위'>—</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{_name_cell(w)}</th>"
            f"<td data-label='진행'>{label}</td>"
            f"{empty_round_cells}{empty_total_cell}"
            "<td data-label='TOP20'>—</td><td data-label='TOP10'>—</td><td data-label='TOP5'>—</td>"
            "<td data-label='우승확률'>—</td>"
            "</tr>"
        )

    field_count = len(active) + len(eliminated)
    stage_label = cfg["stage"]
    seo_title = f"NEO GOLF DATA · {EVENT_NAME} {round_number}라운드 종료 시점 우승확률 (참고 예상)"
    seo_description = (
        f"{EVENT_NAME} {round_number}라운드 종료 시점 우승확률 참고 예상입니다. "
        "공식 순위가 아니며 독립 검증을 거치지 않은 실험적 모델입니다."
    )
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/{stage_label.lower()}/"

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        f'<title>{_esc(seo_title)}</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        '<meta name="robots" content="noindex">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css">'
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}"
        ".live-table td.winpct{font-weight:900;color:var(--gold,#d8ab5c)}"
        ".live-table tr.is-eliminated td,.live-table tr.is-eliminated th{color:var(--muted)}</style>"
        '<meta name="neo-publication-mode" content="reference-estimate-only">'
        f'<meta name="neo-game-code" content="{GAME_CODE}">'
        f'<meta name="neo-round-number" content="{round_number}">'
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
        f'<span>{_esc(EVENT_NAME)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span aria-current="page">{stage_label}</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">우승확률<span class="eyebrow-badge">참고 예상</span></p>'
        f'<h1>{_esc(EVENT_NAME)}</h1><p class="meta">{DATE_RANGE} · {stage_label} 종료 시점</p>'
        "<p class='meta'>서원밸리CC 서원힐스 · 스트로크 플레이</p>"
        "<p class='meta'>참고 예상 수치입니다 — 공식 순위가 아니며 독립 Red Team 검증을 거치지 않은 실험적 모델입니다.</p></div></section>"
    )

    r1_current = ' aria-current="page"' if stage_label == "R1" else ""
    r2_current = ' aria-current="page"' if stage_label == "R2" else ""
    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link"{r1_current} href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link"{r2_current} href="/tournaments/2026/{GAME_CODE}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/live/">LIVE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/fr/">FR</a></li>'
        "</ol></nav>"
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="probability">'
        f"<div class=\"leaderboard-head\"><h2>{stage_label} 종료 시점 우승확률 <small>{field_count}명</small></h2></div>"
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1 live-table">'
        f"<thead><tr><th>순위</th><th>선수</th><th>진행</th>{round_headers}{total_header}<th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead>"
        "<tbody>" + "".join(rows_html) + "".join(wd_rows_html) + "</tbody></table></div>"
        '</section>'
    )

    footer = (
        "</main>"
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        '<a href="/tournaments/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer
    cfg["out"].parent.mkdir(parents=True, exist_ok=True)
    cfg["out"].write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({
        "written": str(cfg["out"]),
        "round": round_number,
        "active": len(active),
        "eliminated": len(eliminated),
    }, ensure_ascii=False, indent=2))


def main() -> None:
    build_round(1)
    build_round(2)


if __name__ == "__main__":
    main()
