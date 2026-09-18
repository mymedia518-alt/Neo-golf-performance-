"""HANA R2 -- build the public Round 2 results page at
docs/tournaments/2026/2026090002/r2/index.html.

Sourced from the real, immutable 2026090002_R2_FROZEN_EVIDENCE.json
(scripts/158) and 2026090002_POST_R2_FINAL_FORECAST.json (scripts/159,
built via klpga.neo_win.post_r2_forecast.run_post_r2_forecast -- the
same generic production Monte Carlo engine KB uses, n_simulations=
60000, remaining_rounds=2, real R1+R2 scores).

POPULATION (operator's explicit R2 requirement -- deliberately
DIFFERENT from KB's own r2_real_page.py convention, which excludes
CUT rows from its table entirely): every real-score R2 leaderboard row
(102 -- both cut-survivors AND cut-missed) is shown in the score table.
WD (3, real: 최예본/리 슈잉/박혜준) are excluded entirely. Only the 64
official cut-survivors (status=="ACTIVE" in the freeze, the same
population run_post_r2_forecast itself simulated) get real TOP20/TOP10/
TOP5/우승확률 numbers; the 38 cut-missed rows show "—" in those four
cells -- never a fabricated 0%.

Markup/CSS classes/shared helpers are the same ones scripts/151 (Hana
R1) already established and klpga.website_v2.round_page_contract /
probability_format already validate elsewhere -- no new template
system, no new CSS.

LIVE RED TEAM FIX (design parity): an earlier version of this page
added R2-only design elements not present on R1 -- an extra hero
meta line and an explanatory paragraph above the table. Both are
removed: R2's page container/hero/stage-nav/table header/row height/
player-sponsor rendering/typography/borders/probability typography
now match R1's exactly, component for component. Only the column SET
itself (순위/선수/1R/2R/합계/TOP20/TOP10/TOP5/우승확률, reflecting
R2's own two-round-plus-cut data) and the CUT badge (reusing the
site's existing .status-badge class, never a new style) differ from
R1, by necessity of what stage this page reports.

COPY-ONLY FOLLOWUP (operator instruction): the hero's
"R3 종료 후 업데이트" note is real, forward-looking, publicly useful
copy -- same role as R1's own "2R 종료 후 업데이트" note, same
markup/position/style (`<p class="round-update-note">`, a sibling of
the hero's inner `<div>`) -- restored here, distinct from the
explanatory-paragraph removal above (which was internal validation
copy, not a stage-progress note). The leaderboard heading also now
states the cut-survivor count next to the row count
("R2 결과 102명 · 컷 통과 64명"), rendered from `len(active_rows)` --
the same already-verified freeze-evidence made-cut population used
for the probability columns -- never a separate hardcoded number.

MODEL PROMOTION (operator instruction, 2026-09-18): the probability
columns now source from 2026090002_POST_R3_CANDIDATE_FREEZE_V1.json
(scripts/166_hana_post_r3_candidate_freeze.py) instead of
2026090002_POST_R2_FINAL_FORECAST.json -- the walk-forward-validated
BASE+R1SG+R2SG model (research/hana-current-sg-model-validation-
20260918, commit 2975036), gated PASS on all 5 pre-registered
criteria (p<0.05, bootstrap CI excludes zero, both SG coefficients
negative, chronological split-half sign-stable). Same 64 official cut
survivors, same actual R1/R2 scores, same PRE-frozen historical
expected/spread, same remaining_rounds=2/n_simulations=60000/seed as
the original forecast -- the ONLY difference is the validated
additive current-SG update to each player's expected_round_score_to_
par. 2026090002_POST_R2_FINAL_FORECAST.json itself is never modified;
this page simply now reads the newer, gated candidate file.

COLUMN RESTRUCTURE (operator instruction, 2026-09-18): the public
column set is now 순위/선수/합계/1R/2R/3R/4R/토탈/TOP20/TOP10/TOP5/우승.
합계 stays the to-par notation (E/-N/+N) it always was; 1R/2R/토탈 are
now the player's REAL official raw strokes for that round (not to-par),
and 3R/4R always render EMPTY_MARK since those rounds have not been
played yet. The raw strokes are never fabricated or derived by PAR
arithmetic: they are read directly, read-only, by re-parsing the SAME
already-ingested official raw evidence scripts/158 itself parsed to
build the (untouched) 2026090002_R2_FROZEN_EVIDENCE.json (content/
website_v2/incoming_evidence/2026090002/HANA_2026090002_R2_OFFICIAL_
RAW.html), via the same trusted klpga.parsers.leaderboard_parser. This
adds a read of that raw file to this script; it never writes to or
mutates the frozen evidence artifact itself. Cross-checked before use:
every one of the 102 non-WD players has a real round1_score/round2_
score/total_strokes triple in the raw parse, round1_score+round2_score
== total_strokes for all 102, and total_strokes-144 == the frozen
evidence's own r2_total_under_par for all 102 (144 = 2 rounds * PAR 72)
-- i.e. the raw strokes and the already-frozen to-par evidence are two
independently-consistent views of the same real result, not two
different numbers.

Probability cells drop the trailing "%" and the header drops the word
"확률" (헤더 "우승확률" -> "우승", 값 "54.3%" -> "54.3") per operator
instruction -- purely a display-string change; the underlying
win_pct/top5_pct/top10_pct/top20_pct values themselves are untouched
(format_public_probability's own 1-decimal/"<0.1"/"0" rounding rules
are unchanged, only the trailing "%" is stripped at render time).

Model/forecast/probability/population/seed/simulation-count/routing
are unchanged by this task -- 2026090002_POST_R3_CANDIDATE_FREEZE_V1.json
is read exactly as before, never recomputed.
"""
from __future__ import annotations

import json
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.round_score_format import format_to_par  # noqa: E402
from klpga.website_v2.round_page_contract import assert_cumulative_score_is_relative_to_par  # noqa: E402
from klpga.website_v2.home_ownership_guard import assert_not_root_home  # noqa: E402
from klpga.website_v2.probability_format import format_public_probability  # noqa: E402
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402

R2_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r2" / "index.html"
assert_not_root_home(R2_PAGE, repo_root=REPO_ROOT)

RAW_HTML_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R2_OFFICIAL_RAW.html"

TOURNAMENT_NAME = "하나금융그룹 챔피언십"
TOURNAMENT_DATE_META = "2026.09.17 — 09.20"
TOURNAMENT_WINNER_META = "2025 우승 이다연 · 279타(-9)"
TOURNAMENT_VENUE_META = "더헤븐 · West, South · Par 72"
EMPTY_MARK = "—"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _load_country_by_id() -> dict[str, str]:
    match = _load("HANA_2026090002_ENTRY_FLAG_MATCH_V2.json")
    country_by_id = {r["player_id"]: r["country_code"] for r in match["records"]}
    for r in _load("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json")["records"]:
        pid = r["player_id"]
        if pid not in country_by_id:
            country_by_id[pid] = r["country_code"]
    return country_by_id


def _load_sponsor_by_id() -> dict[str, str]:
    """Same sources/merge logic as scripts/151's own _load_sponsor_by_id
    -- duplicated here (not imported), per this project's established
    self-contained-builder convention (each tournament-page builder
    stays independent, see docs/OPERATING_RULES.md rule 4)."""
    sources: list[tuple[str, str, str, set[str]]] = [
        ("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V3.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_R1_LEADERBOARD"}),
    ]
    sponsor_by_id: dict[str, str] = {}
    for filename, list_key, status_key, allowed in sources:
        path = CONTENT / filename
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for r in data[list_key]:
            if r.get(status_key) not in allowed:
                continue
            sponsor = r.get("sponsor")
            if not sponsor:
                continue
            pid = str(r["player_id"])
            existing = sponsor_by_id.get(pid)
            if existing is not None and existing != sponsor:
                continue
            sponsor_by_id[pid] = sponsor
    return sponsor_by_id


def _player_cell(pid: str, name: str, country_by_id: dict[str, str], sponsor_by_id: dict[str, str]) -> str:
    flag_cell = ""
    country_code = country_by_id.get(pid)
    if country_code:
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
        )
    sponsor = sponsor_by_id.get(pid)
    sponsor_text = _esc(sponsor) if sponsor else ""
    sponsor_cell = f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
    return (
        f"{flag_cell}<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(name)}</span>"
        f"{sponsor_cell}"
    )


def _load_raw_scores_by_id() -> dict[str, tuple[int, int, int]]:
    """(round1_score, round2_score, total_strokes) per player_id, read
    read-only by re-parsing the SAME already-ingested official raw R2
    evidence scripts/158 itself parsed -- never mutates or rewrites
    2026090002_R2_FROZEN_EVIDENCE.json, never a second source of truth
    for status/rank (those still come from the frozen evidence only)."""
    html = RAW_HTML_PATH.read_text(encoding="utf-8")
    rows = parse_round_leaderboard_html(html, game_code="2026090002", round_number=2)
    return {
        r.player_code: (r.round1_score, r.round2_score, r.total_strokes)
        for r in rows
        if r.round1_score is not None and r.round2_score is not None and r.total_strokes is not None
    }


def main() -> None:
    freeze = _load("2026090002_R2_FROZEN_EVIDENCE.json")
    forecast = _load("2026090002_POST_R3_CANDIDATE_FREEZE_V1.json")
    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}

    all_records = freeze["records"]
    score_rows = [r for r in all_records if r["status"] != "WD"]
    assert len(score_rows) == 102, f"expected 102 non-WD R2 score rows, got {len(score_rows)}"
    active_rows = [r for r in score_rows if r["status"] == "ACTIVE"]
    assert len(active_rows) == 64, f"expected 64 cut-survivor rows, got {len(active_rows)}"
    assert len(forecast_by_id) == 64, f"expected 64 forecast records, got {len(forecast_by_id)}"

    raw_scores_by_id = _load_raw_scores_by_id()
    missing_raw = [r["player_id"] for r in score_rows if r["player_id"] not in raw_scores_by_id]
    if missing_raw:
        raise RuntimeError(f"REFUSING: {len(missing_raw)} non-WD player(s) have no real raw R1/R2 stroke evidence: {missing_raw}")
    for r in score_rows:
        r1_raw, r2_raw, total_raw = raw_scores_by_id[r["player_id"]]
        if r1_raw + r2_raw != total_raw:
            raise RuntimeError(f"REFUSING: raw score arithmetic mismatch for {r['player_name']}: {r1_raw}+{r2_raw}!={total_raw}")
        if r["r2_total_under_par"] is not None and (total_raw - 144) != r["r2_total_under_par"]:
            raise RuntimeError(
                f"REFUSING: raw total {total_raw} (par 144) disagrees with frozen r2_total_under_par "
                f"{r['r2_total_under_par']} for {r['player_name']}"
            )

    country_by_id = _load_country_by_id()
    sponsor_by_id = _load_sponsor_by_id()

    def _sort_key(r):
        return (r["r2_total_under_par"] is None, r["r2_total_under_par"], int(r["player_id"]))

    rank_counts: dict[int, int] = {}
    for r in score_rows:
        if r["r2_total_under_par"] is not None:
            rank_counts[r["r2_total_under_par"]] = rank_counts.get(r["r2_total_under_par"], 0) + 1

    sorted_rows = sorted(score_rows, key=_sort_key)
    ranks: dict[str, str] = {}
    current_rank = 0
    prev_total = object()
    for i, r in enumerate(sorted_rows):
        total_key = r["r2_total_under_par"]
        if total_key is None:
            ranks[r["player_id"]] = "—"
            continue
        if total_key != prev_total:
            current_rank = i + 1
            prev_total = total_key
        ranks[r["player_id"]] = f"T{current_rank}" if rank_counts.get(total_key, 0) > 1 else str(current_rank)

    rows_html = []
    for r in sorted_rows:
        pid = r["player_id"]
        is_active = r["status"] == "ACTIVE"
        total_key = r["r2_total_under_par"]
        rank_cell = ranks[pid]
        player_cell = _player_cell(pid, r["player_name"], country_by_id, sponsor_by_id)

        total_display = format_to_par(total_key) if total_key is not None else EMPTY_MARK
        if total_display != EMPTY_MARK:
            assert_cumulative_score_is_relative_to_par(total_display, label="합계", player=r["player_name"])

        r1_raw, r2_raw, total_raw = raw_scores_by_id[pid]
        r1_display = str(r1_raw)
        r2_display = str(r2_raw)
        total_raw_display = str(total_raw)

        # Reuses the site's already-established .status-badge class (see
        # neo.css: "Non-ACTIVE status (CUT/WD/DQ) badge, next to the
        # player name") -- never a new, R2-only badge style.
        status_badge = "" if is_active else "<span class='status-badge'>CUT</span>"

        frow = forecast_by_id.get(pid)
        if is_active and frow is not None:
            # PROBABILITY DISPLAY FORMAT (operator instruction, column
            # restructure): strip the trailing "%" at render time only
            # -- format_public_probability's own rounding contract
            # (1 decimal / "<0.1" / "0" / real-zero) is unchanged, the
            # underlying win_pct/top5_pct/top10_pct/top20_pct values are
            # untouched, only the displayed string loses its "%" suffix.
            top20 = format_public_probability(frow["top20_pct"]).rstrip("%")
            top10 = format_public_probability(frow["top10_pct"]).rstrip("%")
            top5 = format_public_probability(frow["top5_pct"]).rstrip("%")
            win = format_public_probability(frow["win_pct"]).rstrip("%")
        else:
            top20 = top10 = top5 = win = EMPTY_MARK

        rows_html.append(
            f"<tr><td data-label='순위'>{_esc(rank_cell)}</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}{status_badge}</th>"
            f"<td data-label='합계'>{_esc(total_display)}</td>"
            f"<td data-label='1R'>{_esc(r1_display)}</td>"
            f"<td data-label='2R'>{_esc(r2_display)}</td>"
            f"<td data-label='3R'>{EMPTY_MARK}</td>"
            f"<td data-label='4R'>{EMPTY_MARK}</td>"
            f"<td data-label='토탈'>{_esc(total_raw_display)}</td>"
            f"<td class='{'win' if top20 != EMPTY_MARK else 'metric-empty'}' data-label='TOP20'>{_esc(top20)}</td>"
            f"<td class='{'win' if top10 != EMPTY_MARK else 'metric-empty'}' data-label='TOP10'>{_esc(top10)}</td>"
            f"<td class='{'win' if top5 != EMPTY_MARK else 'metric-empty'}' data-label='TOP5'>{_esc(top5)}</td>"
            f"<td class='{'win' if win != EMPTY_MARK else 'metric-empty'}' data-label='우승'>{_esc(win)}</td>"
            f"</tr>"
        )

    final_rows = rows_html

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEO GOLF DATA · {TOURNAMENT_NAME}</title><link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../../assets/neo.css"></head><body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span><span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span><span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a><nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/2026/2026090002/r2/" class="is-active" aria-current="page">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header><main><style>@media(max-width:760px){{.hana-tourinfo-sep{{display:none}}.hana-tourinfo-holes{{display:block}}}}
/* R2 COLUMN RESTRUCTURE (operator instruction, 2026-09-18): 합계/1R/2R/3R/4R/토탈
   packed tighter on mobile -- centered, minimal side padding -- while player
   name/sponsor keep their existing readability; TOP20/TOP10/TOP5/우승 and
   순위/선수 are untouched. Horizontal scroll (table-wrap--flat-scroll's own
   existing min-width:700px + "옆으로 밀어" hint) stays the mechanism for
   fitting all 12 columns -- no column is ever hidden. */
.leaderboard-table.leaderboard-table--flat-scroll tbody td:nth-child(n+3):nth-child(-n+8){{text-align:center}}
@media(max-width:760px){{
.leaderboard-table.leaderboard-table--flat-scroll thead th:nth-child(n+3):nth-child(-n+8),
.leaderboard-table.leaderboard-table--flat-scroll tbody td:nth-child(n+3):nth-child(-n+8){{padding-left:6px;padding-right:6px;text-align:center}}
}}
</style><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>{TOURNAMENT_NAME}</span><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">R2</span></nav><section class="hero" id="tournament"><div><p class="eyebrow">R2 결과</p><h1>{TOURNAMENT_NAME}</h1><p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">{TOURNAMENT_WINNER_META}</p><p class="meta">{TOURNAMENT_VENUE_META}<span class="hana-tourinfo-sep"> · </span><span class="hana-tourinfo-holes">72홀 스트로크 플레이</span></p></div><p class="round-update-note">R3 종료 후 업데이트</p></section><nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list"><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/">사전 분석 PRE</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r1/">R1</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r2/" aria-current="page">R2</a></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li></ol></nav><section class="panel leaderboard-panel" id="r2"><div class="leaderboard-head"><h2>R2 결과 <small>{len(score_rows)}명 · 컷 통과 {len(active_rows)}명</small></h2></div><div class="table-wrap table-wrap--flat-scroll"><table class="data leaderboard-table leaderboard-table--flat-scroll"><thead><tr><th>순위</th><th>선수</th><th>합계</th><th>1R</th><th>2R</th><th>3R</th><th>4R</th><th>토탈</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승</th></tr></thead><tbody>{''.join(final_rows)}</tbody></table></div></section></main><nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/2026/2026090002/r2/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav><footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>"""

    assert_not_root_home(R2_PAGE, repo_root=REPO_ROOT)
    R2_PAGE.parent.mkdir(parents=True, exist_ok=True)
    R2_PAGE.write_text(html, encoding="utf-8")
    print("wrote", R2_PAGE)
    print("rows:", len(final_rows), "active(with probability):", len(active_rows), "cut(no probability):", len(score_rows) - len(active_rows))


if __name__ == "__main__":
    main()
