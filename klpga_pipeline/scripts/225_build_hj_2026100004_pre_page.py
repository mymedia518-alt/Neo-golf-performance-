"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) PRE page.

Reuses the exact page shell (head/meta, global header+nav, breadcrumb,
hero, stage-nav, footer, the "이전 대회" resolver, the flag+name+sponsor
row markup) byte-for-byte from scripts/190_build_hitejinro_pre_page.py
-- no new design, no new CSS class. Only the leaderboard columns differ,
because only one data layer is actually ready to publish for this event:

- KLPGA K-RANKING: not yet acquired (scripts/220, blocked) -- omitted
  entirely, not rendered as "데이터 부족" for all 108 (operator
  instruction: a missing column must never hold up or pad out the page).
- NEO 경기력 / win-probability (M4 cut/TOP20/TOP10/TOP5/우승): never
  built for this event -- explicitly prohibited (no win-probability
  generation) -- omitted entirely, not a "데이터 부족" column either.

So the table has exactly two columns: 선수 (flag+name+sponsor, same
markup as 190) and Stableford 사전평가 (the frozen V1 pre_event_rank,
"#N" only -- never a 0-100 score).

Source of truth (read-only, never recomputed here):
  content/website_v2/STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json
  (sha256 575fd58e...), already-frozen last turn. 106/108 ranked
  (104 OK + 2 DATA_LIMITED_THIN_SAMPLE, still ranked but visibly
  marked "표본 적음"); 2 DATA_LIMITED_NO_PRIOR_DATA get no rank number
  at all -- rendered in a separately-headed block, never spliced into
  the ranked order with a guessed position.

Name/sponsor/nationality come from the SAME frozen snapshot file (it
already carries official_sponsor/nationality per the canonical identity
reconciliation) -- no second identity lookup, no risk of drifting from
the frozen numbers next to each name.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from html import escape as _esc
from pathlib import Path

_SITE_ORIGIN = "https://neogolfdata.com"
_KST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import render_player_identity  # noqa: E402
from klpga.website_v2.previous_tournament_link import (  # noqa: E402
    previous_tournament_meta_html,
    resolve_previous_tournament_link,
)

GAME_CODE = "2026100004"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
SNAPSHOT_PATH = CONTENT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

STABLEFORD_EXPLANATION_HTML = (
    "<div class='fixture-notice'>"
    "<strong>이번 대회는 변형 스테이블포드 방식으로 진행됩니다.</strong> "
    "버디 +2, 이글 +5, 보기 -1, 더블보기 이상 -3. "
    "NEO는 선수들의 대회 전 기록을 이 점수제에 다시 대입해 "
    "이번 대회에서 어떤 선수의 경기 스타일이 더 높은 가치를 갖는지 평가합니다."
    "</div>"
)


def build() -> dict:
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    records = snapshot["records"]
    assert snapshot["target_game_code"] == GAME_CODE
    field_size = tourney["field_size"]
    assert len(records) == field_size, f"expected {field_size} entrants, found {len(records)}"

    ranked = [r for r in records if r["pre_event_rank"] is not None]
    ranked.sort(key=lambda r: r["pre_event_rank"])
    unranked = [r for r in records if r["pre_event_rank"] is None]
    unranked.sort(key=lambda r: r["player_name"])

    def _row(r: dict) -> str:
        pid = r["player_code"]
        country_code = r["nationality"]
        if country_code in FLAG_ASSETS:
            flag_cell = (
                f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
                f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            )
        else:
            flag_cell = ""
        identity_html = render_player_identity(
            r["player_name"], r.get("official_sponsor") or None, quote="'"
        )
        # render_player_identity's two spans default to block display;
        # this page's row is a single flag+name+sponsor line, same
        # inline override 190 already applies for the identical reason.
        identity_html = identity_html.replace(
            "class='player-name'", "class='player-name' style='display:inline;vertical-align:middle'"
        ).replace(
            "class='player-sponsor'",
            "class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'",
        )
        name_cell = linked_player_name_cell(pid, flag_cell + identity_html)

        if r["pre_event_rank"] is not None:
            rank_cell = f"#{r['pre_event_rank']}"
            if r["data_status"] == "DATA_LIMITED_THIN_SAMPLE":
                rank_cell += " <span style='color:var(--muted);font-size:.82em'>표본 적음</span>"
        else:
            rank_cell = "<span style='color:var(--muted)'>데이터 부족</span>"

        return (
            f"<tr><th scope='row' style='white-space:nowrap;text-align:left'>{name_cell}</th>"
            f"<td data-label='Stableford 사전평가'>{rank_cell}</td></tr>"
        )

    rows_html = [_row(r) for r in ranked]
    if unranked:
        rows_html.append(
            "<tr><td colspan='2' style='color:var(--muted);padding-top:.9rem'>"
            "신규 출전 — 대회 전 기록 없음</td></tr>"
        )
        rows_html.extend(_row(r) for r in unranked)

    event_name = tourney["event_name"]
    start = tourney["start_date"]  # YYYYMMDD
    end = tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    course_line = f"{tourney['course_name']} · Par {tourney['course_par']}"

    previous = resolve_previous_tournament_link()
    previous_meta_html = previous_tournament_meta_html()

    seo_description = f"{event_name} 사전 분석 · {course_line} · {date_range} · NEO GOLF DATA Stableford 사전평가"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/pre/"
    provenance_html = (
        f"<p class='meta provenance'>Stableford 사전평가 기준 · "
        f"페이지 업데이트 {datetime.now(_KST).strftime('%Y-%m-%d %H:%M')} KST</p>"
    )

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 사전 분석</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        f'<meta property="og:title" content="NEO GOLF DATA · {_esc(event_name)} 사전 분석">'
        f'<meta property="og:description" content="{_esc(seo_description)}">'
        f'<meta property="og:url" content="{canonical_url}">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css"></head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/" class="is-active" aria-current="page">대회</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span>{_esc(event_name)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<span aria-current="page">PRE</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">PRE 분석</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f'<p class="meta">{_esc(course_line)}</p>'
        f'{provenance_html}'
        f'{previous_meta_html}</div>'
        '<p class="round-update-note">1R 종료 후 업데이트</p></section>'
        f'{STABLEFORD_EXPLANATION_HTML}'
    )

    _round_items = []
    for key, label in (("r1", "R1"), ("r2", "R2"), ("r3", "R3"), ("fr", "FR")):
        if (REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / key / "index.html").is_file():
            _round_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='/tournaments/2026/{GAME_CODE}/{key}/'>{label}</a></li>")
        else:
            _round_items.append(f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>{label}</span></li>")

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/" aria-current="page">사전 분석 PRE</a></li>'
        + "".join(_round_items) +
        '</ol></nav>'
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="pre">'
        f'<div class="leaderboard-head"><h2>PRE 참가 선수 <small>{field_size}명</small></h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>선수</th><th>Stableford 사전평가</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )

    footer = (
        '</main>'
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer

    return {
        "html": html,
        "field_size": field_size,
        "ranked_count": len(ranked),
        "thin_sample_count": sum(1 for r in ranked if r["data_status"] == "DATA_LIMITED_THIN_SAMPLE"),
        "no_prior_data_count": len(unranked),
        "previous_tournament": previous[0] if previous else None,
    }


def main() -> int:
    result = build()
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(result["html"], encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k != "html"}, ensure_ascii=False, indent=2))
    print(f"Wrote {OUT_PAGE} ({len(result['html'])} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
