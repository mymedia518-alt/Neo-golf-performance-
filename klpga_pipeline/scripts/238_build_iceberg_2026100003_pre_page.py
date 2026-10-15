"""Build the 아이스버그골프·서울신문 오픈 (game_code 2026100003) PRE page,
replicating docs/tournaments/2026/2026100005/pre/index.html's (scripts/
190_build_hitejinro_pre_page.py, itself replicating the Hana/KB
reference verbatim) exact HTML structure and CSS byte-for-byte -- only
tournament-specific text, the 108-row entry table's content, and the
stage-nav link states differ. No new sections, no new CSS classes are
introduced, matching this project's existing "self-contained
per-tournament builder, structure copied verbatim" convention.

Source of truth: ONLY klpga_pipeline/content/website_v2/2026100003_*.json
(TOURNAMENT_INFO, ENTRY_KRANKING_JOIN -- built by scripts/237 from
ENTRY_SNAPSHOT + KRANKING_TOP120, all three mirrored directly from the
validated `reader/2026100003` branch, NEO Sync, all 7 validation
checks PASS -- see reports/2026100003/REVIEW_REPORT_V1.md on that
branch). No other source is read.

NEO 경기력 band: reuses klpga.neo_win.hitejinro_player_metrics's
generic load_current_form_by_id()/neo_band_by_id() helpers verbatim
(they take a bare list of player_ids and read each one's own committed
content/website_v2/knowledge_engine/player_intelligence/<id>/latest.json
-- no gameCode coupling in their logic at all) -- NOT a new, parallel
implementation.

5 M4 probability columns (컷 통과확률/TOP20/TOP10/TOP5/우승확률): NOW REAL
(operator-directed investigation). scripts/193's own module docstring
established that the M4 model requires a populated relational
historical warehouse (tournament_master/player_event/player_round)
that had never existed in this repository/sandbox -- true until this
session. scripts/241_build_m4_training_warehouse.py builds that
warehouse for real, from 10 distinct completed KLPGA regular-tour
gameCodes collected via the SAME already-registered neo-sync.yml route
this branch uses for a new tournament, just with stage="results"
(real official round-by-round scores, never synthesized -- see that
script's own docstring for the full evidence trail). scripts/242_build_
iceberg_2026100003_pre_m4.py then runs the EXISTING, unmodified M4
procedure (ported line-for-line from 193/130, same candidate id "M4",
same features, same n_simulations=60000) against that warehouse and
writes ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json.

This build reads that file directly with a small LOCAL loader (below),
deliberately NOT klpga.neo_win.hitejinro_player_metrics.load_m4_by_id():
that shared function's own gameCode guard compares doc["gameCode"]
against its OWN module-level constant ("2026100005", 하이트진로's own),
which would silently reject every real 2026100003 record and fall back
to empty -- confirmed by direct call. The local loader here checks the
same guard against THIS game_code instead, and applies the identical
analysis_status=='PASS'-only filter 193's own output already encodes --
not a new rule.

103 of 108 entrants (analysis_status=='PASS') get the model's real,
monotonic (win<=top5<=top10<=top20) probabilities; 8 WHOSE OWN PRIOR
EVENT COUNT in the training corpus is genuinely zero (analysis_
status=='DATA_INSUFFICIENT' -- amateurs/rookies with no record in
these 10 tournaments) render 데이터 부족, the SAME label and SAME
meaning NEO 경기력 already uses for a player's own missing input data
-- no longer the "whole model never run" case 예측 미산출 described, so
that distinct wording is retired now that it would be misleading
(these two columns' absences are now the SAME kind of absence: a
specific player's own missing history, not an unrun model).

NEITHER the cut-probability model NOR this build applies, infers, or
displays any specific cut-rule THRESHOLD (e.g. "top 60 and ties") for
2026100003 -- the official source never confirmed one (raw/2026100003/
game_list.json's own expectCutRank=0, unset). 컷 통과확률 is a logistic
model's own probability estimate fit on each of the 10 training
tournaments' real, already-observed made_cut outcomes (player_event.
made_cut, straight from the official round leaderboard -- a player who
never played a later round is 0) -- it never reads or needs this
tournament's own specific cut line to be computed. Applying an
unconfirmed cut RULE to this tournament (e.g. labeling who is "in" or
"out") remains something this build does not do.
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

from klpga.website_v2.model_publication_gate import assert_no_blocked_probability_output  # noqa: E402
from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402
from klpga.website_v2.previous_tournament_link import (  # noqa: E402
    previous_tournament_meta_html,
    resolve_previous_tournament_link,
)
from klpga.neo_win.hitejinro_player_metrics import (  # noqa: E402
    load_current_form_by_id as _load_current_form_by_id,
    neo_band_by_id as _neo_band_by_id,
    pct as _pct,
)

GAME_CODE = "2026100003"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"


def _load_m4_by_id(path: Path) -> dict[str, dict]:
    """Local loader (see module docstring for why this isn't
    hitejinro_player_metrics.load_m4_by_id()): same contract --
    {player_code: record} for every entrant scripts/242's real M4
    output marks analysis_status=='PASS', {} if the file is missing or
    its own gameCode doesn't match THIS tournament."""
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("gameCode") != GAME_CODE:
        return {}
    return {
        str(r["playerCode"]): r
        for r in doc.get("records", [])
        if r.get("analysis_status") == "PASS"
    }
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"

# P0 MODEL SAFETY PATCH (same gate klpga.website_v2.model_publication_gate
# enforces for root HOME / the HJ scaffold, and the same pattern scripts/84
# already established for R1 LIVE): ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json
# carries "publication_class": "VALIDATION_MODEL_NOT_PRODUCTION" -- a
# successfully executed simulation is not sufficient for publication, only
# a flip of that model's own status to VALIDATED is. While False, the
# cut/TOP20/TOP10/TOP5/win probability columns are omitted entirely (never
# rendered as 0%, "데이터 부족", or any other placeholder that implies a
# confirmed, operational prediction) -- same as scripts/84's own
# MODEL_VALIDATED_FOR_PUBLICATION gate.
MODEL_VALIDATED_FOR_PUBLICATION = False
PROBABILITY_WITHHELD_NOTE = (
    "컷 통과확률·TOP20·TOP10·TOP5·우승확률은 시뮬레이션 점검으로 검증 완료 전까지 비공개 처리됩니다. "
    "NEO 경기력은 가장 최근 완료 대회(제26회 하이트진로 챔피언십, 10/4 종료) 결과가 아직 반영되지 않은 "
    "이전 시점 기준이며, 새 기준으로 갱신되는 대로 업데이트됩니다."
)


def main() -> None:
    tourney = _load("TOURNAMENT_INFO.json")
    kranking_join = _load("ENTRY_KRANKING_JOIN.json")
    records = kranking_join["records"]
    assert len(records) == 108, f"expected exactly 108 official entries, found {len(records)}"
    assert tourney["game_code"] == GAME_CODE

    def _sort_key(r):
        if r["official_k_rank"] is not None:
            return (0, r["official_k_rank"], "")
        return (1, 0, r["player_name"])

    rows_data = sorted(records, key=_sort_key)

    all_ids = [r["player_code"] for r in rows_data]
    sponsor_cache = cross_tournament_verified_sponsor_cache()
    current_form_by_id = _load_current_form_by_id(all_ids)
    neo_band_by_id = _neo_band_by_id(current_form_by_id)
    m4_by_id = _load_m4_by_id(M4_CANDIDATE_PATH)

    rows_html = []
    for r in rows_data:
        pid = r["player_code"]
        k_rank_cell = str(r["official_k_rank"]) if r["official_k_rank"] is not None else "—"
        if not MODEL_VALIDATED_FOR_PUBLICATION:
            cut_cell = top20_cell = top10_cell = top5_cell = win_cell = None
        elif pid in m4_by_id:
            m4 = m4_by_id[pid]
            cut_cell = _pct(m4["cut_probability"])
            top20_cell = _pct(m4["top20_probability"])
            top10_cell = _pct(m4["top10_probability"])
            top5_cell = _pct(m4["top5_probability"])
            win_cell = _pct(m4["win_probability"])
        else:
            cut_cell = top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP

        if pid in neo_band_by_id:
            label, score = neo_band_by_id[pid]
            band_cell = (
                f"<span class='band' role='img' aria-label='NEO 경기력 {label}' "
                f"data-neo-score='{score:.2f}'>{label}</span>"
            )
        else:
            band_cell = f"<span class='band' role='img' aria-label='NEO 경기력 데이터 부족'>{_NOWRAP}</span>"

        country_code = r["nationality"]
        if country_code in FLAG_ASSETS:
            flag_cell = (
                f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
                f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            )
        else:
            flag_cell = ""

        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        name_cell = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(r['player_name'])}</span>"
        name_cell = linked_player_name_cell(pid, name_cell)
        prob_cells = (
            ""
            if not MODEL_VALIDATED_FOR_PUBLICATION
            else (
                f"<td class='win' data-label='컷 통과확률'>{cut_cell}</td>"
                f"<td class='win' data-label='TOP20'>{top20_cell}</td>"
                f"<td class='win' data-label='TOP10'>{top10_cell}</td>"
                f"<td class='win' data-label='TOP5'>{top5_cell}</td>"
                f"<td class='win' data-label='우승확률'>{win_cell}</td>"
            )
        )
        rows_html.append(
            f"<tr><th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}"
            f"{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='KLPGA K-RANKING'>{k_rank_cell}</td>"
            f"<td data-label='NEO 경기력'>{band_cell}</td>"
            f"{prob_cells}</tr>"
        )

    event_name = tourney["event_name"]
    start = tourney["start_date"]  # YYYYMMDD
    end = tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    course_line = f"{tourney['course_name']} · {tourney['out_course_text']}, {tourney['in_course_text']}"
    if tourney.get("is_stroke_play"):
        course_line += " · 스트로크 플레이"

    previous = resolve_previous_tournament_link()
    previous_meta_html = previous_tournament_meta_html()

    seo_description = f"{event_name} 사전 분석 · {course_line} · {date_range} · NEO GOLF DATA 우승확률 예측"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/pre/"
    provenance_html = (
        f"<p class='meta provenance'>예측 기준 사전(PRE) 모델 · "
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
        '<link rel="stylesheet" href="../../../../assets/neo.css">'
        # Same header/body left-edge alignment fix propagated to every
        # other page's own head this branch already carries (HJ round
        # pages, HOME, HJ hub, HJ PRE) -- without it the brand mark
        # sits left of <main>'s own padded content on this page too.
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        '</head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
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
        '<span aria-current="page">PRE</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">PRE 분석</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f'<p class="meta">{_esc(course_line)}</p>'
        f'{provenance_html}'
        f'{previous_meta_html}</div>'
        '<p class="round-update-note">1R 종료 후 업데이트</p></section>'
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

    validation_notice = (
        "<div class='fixture-notice'>"
        "<p style='margin:0;font-weight:700;line-height:1.7'>" + PROBABILITY_WITHHELD_NOTE + "</p>"
        "</div>"
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="pre">'
        '<div class="leaderboard-head"><h2>PRE 참가 선수 <small>108명</small></h2></div>'
        + validation_notice +
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>선수</th><th>KLPGA K-RANKING</th>"
        "<th class='band-head'>NEO 경기력 "
        "<button type='button' class='info-control' aria-label='NEO 경기력 설명' aria-expanded='false' aria-controls='neo-info'>ⓘ</button>"
        "<span id='neo-info' class='info-popover' role='tooltip' tabindex='-1'>최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다.</span></th>"
        + ("<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>" if MODEL_VALIDATED_FOR_PUBLICATION else "") +
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )

    info_js = (
        "<script>(function(){const b=document.querySelector('.info-control'),p=document.getElementById('neo-info');"
        "if(!b||!p)return;function close(){p.classList.remove('is-open');b.setAttribute('aria-expanded','false')}"
        "function place(){if(window.innerWidth<=760)return;const r=b.getBoundingClientRect();"
        "let left=Math.min(r.left,window.innerWidth-p.offsetWidth-16);left=Math.max(16,left);"
        "p.style.left=left+'px';p.style.top=(r.bottom+6)+'px'}"
        "b.addEventListener('click',function(){const open=p.classList.toggle('is-open');"
        "b.setAttribute('aria-expanded',String(open));if(open){place();p.focus()}});"
        "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&p.classList.contains('is-open'))close()});"
        "document.addEventListener('click',function(e){if(!b.contains(e.target)&&!p.contains(e.target))close()});"
        "window.addEventListener('scroll',close,true);window.addEventListener('resize',close)})();</script>"
    )

    footer = (
        '</main>' + info_js +
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer

    assert_no_blocked_probability_output(
        html, model_validated=MODEL_VALIDATED_FOR_PUBLICATION, label=f"{GAME_CODE} PRE"
    )

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    print(json.dumps({
        "written": str(OUT_PAGE),
        "rows": len(rows_data),
        "k_rank_matched": sum(1 for r in rows_data if r["official_k_rank"] is not None),
        "k_rank_unmatched": sum(1 for r in rows_data if r["official_k_rank"] is None),
        "sponsor_matched": sum(1 for r in rows_data if r["player_code"] in sponsor_cache),
        "neo_band_connected": len(neo_band_by_id),
        "neo_band_data_insufficient": len(rows_data) - len(neo_band_by_id),
        "previous_tournament": previous[0] if previous else None,
        "m4_connected": len(m4_by_id),
        "m4_data_insufficient": len(rows_data) - len(m4_by_id),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
