#!/usr/bin/env python3
"""Build the Hana Financial Group Championship (game_code 2026090002)
PRE page, replicating docs/tournaments/2026/2026090003/pre/index.html's
exact HTML structure and CSS verbatim -- only the tournament info and
the 108-player table content are Hana-specific. No new sections, no
new CSS classes are introduced.

AMATEUR KGA-BASIS REVIEW (2026-09-16): 3 named amateur (A) entrants
(오수민 0809(A), 양윤서 0801(A), 권은 0906(A)) previously showed real M4
probabilities that were actually computed from historical KLPGA
Strokes Gained averages substituted for their missing current_official_
sg -- an improper basis, since KLPGA SG must never be estimated for an
amateur. No genuine KGA (대한골프협회) official ranking/record data for
these players exists in this repo or was reachable live (every KGA
domain is blocked by this environment's egress policy) -- see
HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json for the full investigation
per player. Per the explicit no-fabrication rule, all three are now
forced to DATA_INSUFFICIENT (see _load_amateur_kga_insufficient_ids())
rather than kept on that improper basis or given any new estimated
probability. Their K-Ranking sort position is unaffected: 양윤서 (k_rank
52) stays at her numeric position; 오수민/권은 (no k_rank) join the
existing name-sorted DATA_INSUFFICIENT trailing group, unchanged
mechanism from before. CORRECTION (same day): forcing these 3 to
DATA_INSUFFICIENT does NOT remove them from the NEO 경기력 quintile
band pool -- that pool/its thresholds stay the original 103-player
computation unconditionally, so the other 100 real players' band
labels are byte-for-byte unchanged from before this review. Only the
3 amateurs' own row output is overridden to 데이터 부족 (their band
entry in band_by_id is simply never read).

HERO STATUS BADGE REMOVAL (2026-09-16): the standalone `<strong
class="status">PRE</strong>` badge that used to sit in the hero section
is removed -- the stage-nav's own "사전 분석 PRE" item (already the
current-stage indicator via aria-current="page") is the single source
of stage state now, not a second, redundant badge. R1/R2/R3/FR stage-
nav placeholders and the no-FINAL-yet policy are unchanged.

PUBLIC-UI SG REDACTION (2026-09-16): the public table intentionally
omits a "최근 5R SG" column -- that internal-only metric is never
rendered on this public page. The underlying season-SG evidence file
and its analysis are untouched on disk (HANA_2026090002_SEASON_SG_
SORTED_V1.json, loaded below as `sg_sorted`/`by_id_sg`) -- only the
public-facing render step for that column was removed, matching this
build's existing "fix the source, never hand-patch the generated
HTML" convention. The public table is now 8 columns.

Inputs (all real, operator-committed evidence -- see each file's own
provenance fields):
  - HANA_2026090002_OFFICIAL_ENTRY_LIST_V1.json   (108 official entries,
    player_id + name + entry_category, KLPGA entry/tourInfo pages)
  - HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json (K-Ranking, joined by
    player_id)
  - HANA_2026090002_SEASON_SG_SORTED_V1.json      (season SG rank --
    loaded and still validated below for player_id-set consistency,
    but its season_sg_rank value is internal-only and never rendered
    on the public page; see PUBLIC-UI SG REDACTION above)
  - HANA_2026090002_PRE_M4_60000_CANDIDATE_V1.json (M4 win-model,
    60,000-simulation Monte Carlo; neo_rank/neo_score_display +
    cut/top20/top10/top5/win probabilities + analysis_status per player)

Column mapping (8 public columns, in order):
  선수            -> [official flag image] official_display_name [official
                     sponsor]. Flag: country_code from
                     HANA_2026090002_ENTRY_FLAG_MATCH_V1.json (itself
                     extracted only from the official KLPGA entry page's
                     own /country/XXX.png paths -- see that file's own
                     `source`/`validation` fields). Sponsor: only players
                     with a VERIFIED_OFFICIAL sponsor record somewhere in
                     the repo (KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3 /
                     HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2 /
                     OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2, joined by
                     player_id) get a sponsor value; every other player's
                     sponsor slot is blank, never guessed.
  KLPGA K-RANKING -> k_rank; "-" if this specific player has none
  NEO 경기력       -> quintile band of win_probability among the 103
                     PASS players (documented below); "데이터 부족" for
                     the 5 DATA_INSUFFICIENT players. The band span also
                     carries the M4 file's own neo_score_display value,
                     formatted to exactly two decimal places, as a
                     data-neo-score attribute -- present without adding
                     a new visible column or changing the KB reference's
                     cell markup/CSS.
  컷 통과확률/TOP20/TOP10/TOP5/우승확률
                  -> M4 probabilities; "데이터 부족" (all 5 cells) for
                     the 5 DATA_INSUFFICIENT players

Row order (per explicit instruction, superseding the earlier neo_rank
sort): HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1's own k_rank, ascending.
Players with a real k_rank come first, in K-Ranking order. Players
without a k_rank sort last, broken into two sub-groups: the 18
domestic no-k_rank players first (win_probability descending, this
build's existing tie-break convention), then the 5 DATA_INSUFFICIENT
foreign entrants as their own trailing group (sorted by name for a
stable, ranking-free order, since their probabilities are explicitly
unreliable).

Monotonicity gate (CUT >= TOP20 >= TOP10 >= TOP5 >= WIN): checked and
reported, never silently clipped/corrected -- see printed summary.

"데이터 부족" cells never wrap to a second line: the CSS file itself is
never touched, so each such cell's text is wrapped in an inline
white-space:nowrap span instead.
"""
from __future__ import annotations

import json
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026090002"
REFERENCE_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090003" / "pre" / "index.html"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _pct(p: float) -> str:
    return f"{p * 100:.1f}%"


_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"


def _load_country_by_id() -> dict[str, str]:
    """playerCode -> country_code (e.g. 'KOR'), sourced only from
    HANA_2026090002_ENTRY_FLAG_MATCH_V1.json -- itself extracted purely
    from the official KLPGA entry page's own /country/XXX.png flag
    paths (never estimated from player names; see that file's own
    `source`/`validation` fields for the full verification trail)."""
    match = _load("HANA_2026090002_ENTRY_FLAG_MATCH_V1.json")
    return {r["player_id"]: r["country_code"] for r in match["records"]}


def _load_sponsor_by_id() -> dict[str, str]:
    """playerCode -> official sponsor, merged from every VERIFIED_OFFICIAL
    evidence source already in the repo (same identity-join-by-player_id
    convention this codebase already uses -- see e.g.
    KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json's own
    "verified_cross_tournament_or_operator_reported_count" field: an
    official sponsor is the PLAYER's attribute, not a tournament-
    specific one, so a value verified for the same player_id elsewhere
    is reused here rather than re-guessed). A player_id with no
    verified sponsor anywhere is simply absent from the returned dict
    -- the caller renders an empty sponsor slot, never a guess. Any
    disagreement between sources for the same player_id is a hard
    failure, never silently resolved."""
    sources: list[tuple[str, str, str, set[str]]] = [
        ("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
    ]
    sponsor_by_id: dict[str, str] = {}
    for filename, list_key, status_key, allowed in sources:
        data = _load(filename)
        for r in data[list_key]:
            if r.get(status_key) not in allowed:
                continue
            sponsor = r.get("sponsor")
            if not sponsor:
                continue
            pid = str(r["player_id"])
            existing = sponsor_by_id.get(pid)
            assert existing is None or existing == sponsor, (
                f"conflicting verified sponsor for player_id {pid}: {existing!r} vs {sponsor!r} ({filename})"
            )
            sponsor_by_id[pid] = sponsor
    return sponsor_by_id


def _load_amateur_kga_insufficient_ids() -> set[str]:
    """playerCode set forced to DATA_INSUFFICIENT regardless of the M4
    model's own PASS status, sourced from
    HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json. That file documents,
    per named amateur entrant, that the M4 model had actually reached
    PASS by substituting historical KLPGA Strokes Gained averages for
    the missing current_official_sg -- an improper basis for an amateur
    (KLPGA SG must never be estimated for amateurs) -- and that no
    genuine KGA (대한골프협회) official ranking/record data was found in
    this repo or reachable live to compute a legitimate replacement
    probability. Never hardcoded here as bare player IDs -- always
    loaded from that evidence file so the reasoning stays inspectable."""
    analysis = _load("HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json")
    return {
        r["player_id"] for r in analysis["records"]
        if r["decision"] == "DATA_INSUFFICIENT"
    }


def main() -> None:
    entry = _load("HANA_2026090002_OFFICIAL_ENTRY_LIST_V1.json")
    player_input = _load("HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json")
    sg_sorted = _load("HANA_2026090002_SEASON_SG_SORTED_V1.json")
    m4 = _load("HANA_2026090002_PRE_M4_60000_CANDIDATE_V1.json")
    amateur_kga_insufficient_ids = _load_amateur_kga_insufficient_ids()

    entry_ids = {r["player_id"] for r in entry["records"]}
    input_ids = {r["player_id"] for r in player_input["records"]}
    m4_ids = {r["playerCode"] for r in m4["records"]}
    assert entry_ids == input_ids == m4_ids, "player_id sets diverge across Hana source files"
    assert len(entry_ids) == 108 == len(entry["records"]), "expected exactly 108 unique official entries"

    by_id_input = {r["player_id"]: r for r in player_input["records"]}
    by_id_sg = {r["player_id"]: r for r in sg_sorted["records"]}
    by_id_m4 = {r["playerCode"]: r for r in m4["records"]}
    country_by_id = _load_country_by_id()
    assert set(country_by_id) == entry_ids, "country_code coverage diverges from the 108 official entries"
    sponsor_by_id = _load_sponsor_by_id()

    # ---- Monotonicity gate: CUT >= TOP20 >= TOP10 >= TOP5 >= WIN ----
    # Checked and reported here, never silently clipped/corrected.
    violations = []
    for r in m4["records"]:
        vals = (r["cut_probability"], r["top20_probability"], r["top10_probability"], r["top5_probability"], r["win_probability"])
        if not all(a >= b - 1e-9 for a, b in zip(vals, vals[1:])):
            violations.append((r["playerCode"], r["playerName"], vals))

    # ---- NEO 경기력 band: quintile of win_probability among PASS players ----
    # Documented, transparent rule (this repo's own original KB band
    # algorithm could not be located in this branch's history to
    # replicate exactly) -- equal-count quintiles over the 103
    # analyzable players, highest win_probability first.
    # NOTE (2026-09-16, reverted same day): forcing 3 amateur entrants to
    # DATA_INSUFFICIENT was briefly also implemented by excluding them
    # from this quintile pool -- mathematically defensible (their basis
    # was improper to begin with) but it shifted 7 other real players'
    # displayed band label even though those players' own win_probability
    # never changed. Per explicit instruction, the original 103-player
    # pool/thresholds are preserved unconditionally: the 3 amateurs stay
    # IN this pool (their own band is simply never rendered, since
    # `insufficient` below overrides their row to 데이터 부족 regardless
    # of what band_by_id says for them), so every other real PASS
    # player's label is byte-for-byte identical to before this file's
    # amateur-KGA review existed.
    pass_ids_by_win = [
        r["playerCode"] for r in sorted(
            (r for r in m4["records"] if r["analysis_status"] == "PASS"),
            key=lambda r: -r["win_probability"],
        )
    ]
    n = len(pass_ids_by_win)
    band_labels = ["최상위", "상위", "중위", "하위", "최하위"]
    band_by_id: dict[str, str] = {}
    for i, pid in enumerate(pass_ids_by_win):
        band_by_id[pid] = band_labels[min(4, i * 5 // n)]

    rows_data = []
    for pid in entry_ids:
        inp = by_id_input[pid]
        sg = by_id_sg[pid]
        rec = by_id_m4[pid]
        insufficient = rec["analysis_status"] != "PASS" or pid in amateur_kga_insufficient_ids
        rows_data.append({
            "player_id": pid,
            "name": inp["official_display_name"],
            "country_code": country_by_id[pid],
            "sponsor": sponsor_by_id.get(pid, ""),
            "k_rank": inp.get("k_rank"),
            "neo_rank": rec["neo_rank"],
            "neo_score": rec["neo_score_display"],
            "band": "데이터 부족" if insufficient else band_by_id[pid],
            "sg_rank": None if sg.get("season_sg_status") != "확인" else sg.get("season_sg_rank"),
            "insufficient": insufficient,
            "cut": rec["cut_probability"],
            "top20": rec["top20_probability"],
            "top10": rec["top10_probability"],
            "top5": rec["top5_probability"],
            "win": rec["win_probability"],
        })

    # Row order (explicit instruction): k_rank ascending; no-k_rank
    # players last, with the 5 DATA_INSUFFICIENT foreign entrants forming
    # their own trailing sub-group after the other no-k_rank players.
    def _sort_key(r):
        if r["k_rank"] is not None:
            return (0, r["k_rank"], 0, "")
        if r["insufficient"]:
            return (2, 0, 0, r["name"])
        return (1, 0, -r["win"], "")

    rows_data.sort(key=_sort_key)

    rows_html = []
    for r in rows_data:
        k_rank_cell = str(r["k_rank"]) if r["k_rank"] is not None else "—"
        neo_score_str = f"{r['neo_score']:.2f}"
        band_text = f"<span style='white-space:nowrap'>{r['band']}</span>" if r["insufficient"] else r["band"]
        band_cell = (
            f"<span class='band' role='img' aria-label='NEO 경기력 {r['band']}' "
            f"data-neo-score='{neo_score_str}'>{band_text}</span>"
        )
        if r["insufficient"]:
            cut_cell = top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP
        else:
            cut_cell, top20_cell, top10_cell, top5_cell, win_cell = (
                _pct(r["cut"]), _pct(r["top20"]), _pct(r["top10"]), _pct(r["top5"]), _pct(r["win"])
            )
        # Flag-left / name / sponsor-right, all on one line, horizontally
        # centered within the cell: neo.css sets .leaderboard-table tbody
        # th[scope=row] to text-align:left (both desktop and the mobile
        # card layout), and neo-site.css sets .player-name/.player-sponsor
        # to display:block site-wide (stacked layout, used elsewhere) --
        # so inline style overrides on just these generated elements are
        # required (text-align:center on the <th> itself beats both the
        # desktop and mobile CSS rules in one shot, since an inline style
        # always outranks a stylesheet rule regardless of media query;
        # display:inline on the two spans lets them sit beside the flag
        # on one row). Same technique as this file's own _NOWRAP span --
        # an inline style scoped to the generated markup only, never a
        # CSS file edit. Vertical centering needs no override: a table
        # cell's UA-default vertical-align is already "middle", and
        # neither neo.css rule sets vertical-align on this element.
        flag_cell = (
            f"<img src='/assets/flags/{r['country_code']}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
        )
        sponsor_text = _esc(r["sponsor"]) if r["sponsor"] else ""
        rows_html.append(
            f"<tr><th scope='row' style='white-space:nowrap;text-align:center'>{flag_cell}"
            f"<span class='player-name' style='display:inline;vertical-align:middle'>{r['name']}</span>"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='KLPGA K-RANKING'>{k_rank_cell}</td>"
            f"<td data-label='NEO 경기력'>{band_cell}</td>"
            f"<td class='win' data-label='컷 통과확률'>{cut_cell}</td>"
            f"<td class='win' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='win' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='win' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='win' data-label='우승확률'>{win_cell}</td></tr>"
        )

    # Header + hero, adapted from the reference's own literal markup
    # (byte-for-byte structure/classes; only tournament-specific text
    # and hrefs are substituted).
    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>NEO GOLF DATA · 하나금융그룹 챔피언십</title>'
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
        '<span>하나금융그룹 챔피언십</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<span aria-current="page">PRE</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">PRE 분석</p>'
        '<h1>하나금융그룹 챔피언십</h1><p class="meta">2026.09.17 — 09.20</p>'
        '<p class="meta">2025 우승 이다연 · 279타(-9)</p></div>'
        '<p class="round-update-note">1R 종료 후 업데이트</p></section>'
    )

    # Stage-nav: brand-new tournament, only PRE exists yet -- every
    # forward stage is the same disabled placeholder the KB reference
    # itself started from, never a link to a page that does not exist.
    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/" aria-current="page">사전 분석 PRE</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R1</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li>'
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

    # info-popover JS, verbatim from the reference (no new script logic).
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
        "analysis_pass": sum(1 for r in rows_data if not r["insufficient"]),
        "data_insufficient": sum(1 for r in rows_data if r["insufficient"]),
        "monotonicity_violations": violations,
        "win_probability_sum": sum(r["win"] for r in rows_data),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
