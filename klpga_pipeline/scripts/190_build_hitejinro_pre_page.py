"""Build the HITE JINRO Championship (game_code 2026100005) PRE page,
replicating docs/tournaments/2026/2026090002/pre/index.html's (Hana's
own build, itself replicating the 2026090003/pre reference verbatim
per 139_build_hana_pre_kb_structure.py's own docstring) exact HTML
structure and CSS byte-for-byte -- only tournament-specific text, the
108-row entry table's content, and the stage-nav link states differ.
No new sections, no new CSS classes are introduced, matching this
project's existing "self-contained per-tournament builder, structure
copied verbatim" convention (see 139/151/160/174/181's own headers).

Source of truth: ONLY klpga_pipeline/content/website_v2/2026100005_*.json
(TOURNAMENT_INFO, ENTRY_SNAPSHOT, ENTRY_KRANKING_JOIN), all mirrored
directly from the validated `reader/2026100005` branch (NEO Sync run
#6, all 7 validation checks PASS -- see reports/2026100005/REVIEW_REPORT_V1.md
on that branch). No other source is read.

WHAT IS NOW CONNECTED (2026-09-30, operator instruction: "do not stop
until every available dataset is connected"):

- Sponsor: klpga.website_v2.player_identity.cross_tournament_verified_
  sponsor_cache() -- the existing, generic, official-source-backed
  identity pipeline (never a new lookup invented for this build). It
  scans every OTHER tournament's own *_CURRENT_PLAYER_MASTER.json for
  already-PASS-identity-verified sponsor facts for the SAME player_id
  (a real person's sponsor doesn't reset between tournaments) plus
  OPERATOR_REPORTED_SPONSOR_EVIDENCE_V*.json, dropping any player_id
  whose value disagrees across sources. 84 of 108 entrants matched a
  real, verified sponsor this way; the other 24 render an empty slot
  (never a guess), exactly matching 139's own established rule for a
  player_id with no verified sponsor anywhere.
- NEO 경기력: computed directly from each entrant's own already-
  committed content/website_v2/knowledge_engine/player_intelligence/
  <id>/latest.json -> current_form (recent_5_sg/recent_10_sg/
  long_term_sg/volatility) -- the SAME raw inputs and SAME published
  weights (0.35/0.25/0.25/-0.10 "consistency") as this repo's own NEO
  Ranking V1 formula (docs/NEO_RANKING_V1_REDTEAM_BACKTEST.md), but
  z-scored across THIS tournament's own real 108-player field (not a
  cross-event cohort), quintile-banded exactly like 139's own
  documented band logic. This is not "publishing NEO Ranking" (that
  standalone product/page remains NEO_RANKING_PUBLICATION=BLOCKED per
  its own red-team gate) -- it is reusing its one transparent, already-
  evidenced scoring formula on real per-player SG data already
  committed to this repo, for one existing PRE-page field, the same
  way 139 always populated this exact column from whatever model was
  available to it. 101 of 108 entrants have complete current_form data
  and get a real band; 7 (6 with partial/no current_form + 1 amateur
  with no committed Player Intelligence doc at all -- see
  _load_current_form_by_id()) honestly render 데이터 부족 -- per-player,
  never defaulted for the whole field.
- "이전 대회" (previous tournament): klpga.website_v2.tournament_
  chronology.resolve_tournament_chronology(), the same real, pure,
  date-only resolver HOME's own hub-card pipeline uses -- never a
  hardcoded "Hana" literal. As of today it resolves "last" to Hana
  (game_code 2026090002, real end_date 2026-09-20 < today), linked to
  its own real, live PRE page. No live Hana/KB PRE page has ever had
  this element in its own markup (confirmed: grepped the real
  reference file, found nothing) -- there is no "exact Hana template"
  copy for this piece, so it is added as a single small hero fact line
  using only an already-established markup pattern (a plain <p
  class="meta"> with a link), not a new component.

- 컷 통과확률/TOP20/TOP10/TOP5/우승확률 (the 5 M4 probability columns):
  connected, 2026-09-30, via _load_m4_by_id() reading scripts/193's own
  output (M4_CANDIDATE_PATH = content/website_v2/HITEJINRO_2026100005_
  PRE_M4_CANDIDATE_V1.json) -- pure additive wiring, zero changes to
  193 itself. Renders each of the 5 real probabilities (cut_probability/
  top20_probability/top10_probability/top5_probability/win_probability)
  as a percentage ONLY for a playerCode whose record has
  analysis_status=='PASS'; a player missing from the file, or present
  with analysis_status=='DATA_INSUFFICIENT', still renders 데이터 부족 --
  the same per-player "absent, not guessed" rule NEO 경기력 already
  follows above, never a whole-field fallback. 193 itself requires a
  populated RELATIONAL historical warehouse (player_event/player_round
  in data/klpga.sqlite, .gitignore'd, not committed by design -- see
  193's own module docstring for exactly what that warehouse is and how
  it's produced) to run; if that file has never been generated in a
  given environment, M4_CANDIDATE_PATH simply doesn't exist yet and
  _load_m4_by_id() returns {}, so this build reproduces its pre-
  2026-09-30 behavior (데이터 부족 for all 108) exactly, not a crash.

WHAT REMAINS DELIBERATELY OMITTED, AND WHY (no-fabrication rule):

- data-neo-score attribute on the band span: omitted for the 7 데이터
  부족 rows specifically (present, real, for the other 101) -- no
  underlying score exists for those 7, and it is invisible metadata,
  not rendered text, so omitting it changes no UX/layout.
- "2025 우승 ..." hero fact line: omitted entirely (not left with a
  placeholder). No prior-year 하이트진로 챔피언십 winner fact exists
  anywhere in this repository or in reader/2026100005 to report.
  Hana's own hero line for this fact is real historical data specific
  to that tournament; inventing an equivalent line here would be
  fabrication. This is a self-contained <p class="meta"> the
  reference markup does not require to be present.
- Par / hole-count ("72홀 스트로크 플레이"): omitted. TOURNAMENT_INFO
  confirms is_stroke_play=true (rendered) and course_name/out-in
  labels (rendered), but no par value or explicit hole count for
  Blue Heron is present in the official getGameList response this
  repo collected -- inventing "Par 72"/"72홀" the way Hana's hero
  states them would be a guess this project's rules forbid.
- Country flag <img> for player_code 13386 (에리카 윤 스미스(I),
  nationality=USA): omitted (no <img> tag emitted for this one row's
  flag cell) rather than either fabricating an SVG or pointing at a
  path that does not exist -- docs/assets/flags/ has no USA.svg
  (confirmed: 8 files, KOR/CHN/THA/JPN/PHI/TPE/AUS/NZL only). All 107
  other entrants' flags render normally (KOR/CHN/THA all have real
  assets).
- Stage nav: R1/R2/R3/FR all render as the same disabled placeholder
  the reference page itself starts from -- none of those pages exist
  yet for this game_code.

K-RANKING: sourced from 2026100005_ENTRY_KRANKING_JOIN.json, itself a
direct join of the 108 official entrants against the full 747-player
official K-Ranking table (k-rankings.klpga.co.kr/allplayer.jsp,
2026-W39) by official player_code -- no player_master/warehouse
dependency, matching this repo's own established "K-RANKING
BEYOND-TOP-120 RESTORATION" precedent (scripts/140). 105 of 108
entrants have a real official_k_rank; 3 are genuinely absent from the
747-player table (render "-"), consistent with 140's own "no number
is ever guessed for those" rule.

Row order: mirrors 139's own convention exactly -- k_rank ascending
first, then the no-k_rank remainder in a stable, ranking-free order
(by name), since without a win-probability model there is no
neo_score to break ties with the way 139 does for its own no-k_rank
group.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape as _esc
from pathlib import Path

_SITE_ORIGIN = "https://neogolfdata.com"
_KST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402
from klpga.website_v2.previous_tournament_link import (  # noqa: E402
    previous_tournament_meta_html,
    resolve_previous_tournament_link,
)
from klpga.neo_win.hitejinro_player_metrics import (  # noqa: E402
    M4_CANDIDATE_PATH,
    load_current_form_by_id as _load_current_form_by_id,
    load_m4_by_id as _load_m4_by_id_shared,
    neo_band_by_id as _neo_band_by_id,
    pct as _pct,
)

GAME_CODE = "2026100005"


def _load_m4_by_id() -> dict[str, dict]:
    """Thin wrapper passing THIS module's own M4_CANDIDATE_PATH (which
    tests monkeypatch) into the shared loader, rather than calling it
    bare -- the shared function closes over its OWN module's global by
    default, so a bare call would silently ignore a patched path here."""
    return _load_m4_by_id_shared(M4_CANDIDATE_PATH)
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


# "이전 대회" link resolution lives in ONE place only now --
# klpga.website_v2.previous_tournament_link -- so every stage page
# (PRE here, R1/R2/R3/FR in 196-199) resolves it identically. See that
# module's own docstring for the 2026-10-01 bug this replaced (used to
# hardcode "pre/" even once the previous tournament had a real FINAL
# page published).


_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"


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
    m4_by_id = _load_m4_by_id()

    rows_html = []
    for r in rows_data:
        pid = r["player_code"]
        k_rank_cell = str(r["official_k_rank"]) if r["official_k_rank"] is not None else "—"
        if pid in m4_by_id:
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
        rows_html.append(
            f"<tr><th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}"
            f"{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='KLPGA K-RANKING'>{k_rank_cell}</td>"
            f"<td data-label='NEO 경기력'>{band_cell}</td>"
            f"<td class='win' data-label='컷 통과확률'>{cut_cell}</td>"
            f"<td class='win' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='win' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='win' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='win' data-label='우승확률'>{win_cell}</td></tr>"
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
        '<link rel="stylesheet" href="../../../../assets/neo.css"></head><body>'
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

    # BUG FIX (2026-10-01, R1 종료 operation): these 4 used to be
    # unconditionally hardcoded disabled -- correct only while none of
    # them had ever been published. Checked against the real file on
    # disk now (same "evidence must exist" discipline as
    # klpga.website_v2.previous_tournament_link), so this stays correct
    # for R2/R3/FR too once scripts/197-199 publish them, with no
    # further hand-edit needed (unlike Hana's own hand-patched 161/175/182).
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
        '<div class="leaderboard-head"><h2>PRE 참가 선수 <small>108명</small></h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>선수</th><th>KLPGA K-RANKING</th>"
        "<th class='band-head'>NEO 경기력 "
        "<button type='button' class='info-control' aria-label='NEO 경기력 설명' aria-expanded='false' aria-controls='neo-info'>ⓘ</button>"
        "<span id='neo-info' class='info-popover' role='tooltip' tabindex='-1'>최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다.</span></th>"
        "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
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
        "m4_source": str(M4_CANDIDATE_PATH) if m4_by_id else "not found -- 데이터 부족 for all 108, see module docstring",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
