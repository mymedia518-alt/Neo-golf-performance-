"""HANA R1 -- build the public Round 1 results page at
docs/tournaments/2026/2026090002/r1/index.html.

Sourced from HANA_2026090002_R1_ANALYSIS_V1.json (itself built from
the real R1-conditioned NEO_R1_MODEL_V1 output, see
149_build_hana_r1_analysis.py / 152_apply_r1_model_to_hana.py) --
순위(rank) / 선수(player identity) / 1R 스코어(round score) / NEO 경기력
/ 컷 통과율 / TOP20 / TOP10 / TOP5 / 우승확률 / 상태(WD). Per explicit
operator decision, cut-passing possibility (an official-cut-line based
projection) is still excluded -- no official cut rule for this
tournament exists yet -- but the model's own P(made_cut) tier, labeled
here as "컷 통과율" alongside TOP20/TOP10/TOP5/우승확률, IS shown: it is
a real R1-conditioned model output, not a guessed cut-line rank.

Markup/CSS classes are adapted from Hana PRE's own current structure
(139_build_hana_pre_kb_structure.py) for visual consistency -- same
breadcrumb/hero/stage-nav/table-wrap shell, same flag+name+sponsor
player-cell pattern, same "데이터 부족" nowrap span convention -- never
a new, divergent template. No CSS file is touched; only classes/inline
styles the PRE page already established are reused.

Per explicit instruction, this script NEVER reads or writes anything
under docs/tournaments/2026/2026090002/pre/ -- the PRE page and its
stage-nav are left completely untouched.
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

R1_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
assert_not_root_home(R1_PAGE, repo_root=REPO_ROOT)

TOURNAMENT_NAME = "하나금융그룹 챔피언십"
TOURNAMENT_DATE_META = "2026.09.17 — 09.20"
TOURNAMENT_WINNER_META = "2025 우승 이다연 · 279타(-9)"
TOURNAMENT_VENUE_META = "더헤븐 · West, South · Par 72"

_NOWRAP_INSUFFICIENT = "<span style='white-space:nowrap'>데이터 부족</span>"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _load_country_by_id() -> dict[str, str]:
    match = _load("HANA_2026090002_ENTRY_FLAG_MATCH_V2.json")
    country_by_id = {r["player_id"]: r["country_code"] for r in match["records"]}
    # 양서후(10867) has no PRE-stage entry -- recovered directly from the
    # official R1 leaderboard, see 153_recover_hana_r1_new_entrant_identity.py.
    # This supersedes the earlier "no flag record" observation for her.
    for r in _load("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json")["records"]:
        pid = r["player_id"]
        assert pid not in country_by_id, f"unexpected: {pid} already has a PRE-stage flag record"
        country_by_id[pid] = r["country_code"]
    return country_by_id


def _load_sponsor_by_id() -> dict[str, str]:
    """Same merge logic/sources as 139_build_hana_pre_kb_structure.py's
    own _load_sponsor_by_id() -- duplicated here (not imported) because
    139 is intentionally never imported by other build scripts (each
    tournament-page builder stays self-contained, see
    docs/OPERATING_RULES.md rule 4). Additionally merges
    HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json for 양서후
    (10867), whose sponsor is sourced directly from the R1 official
    leaderboard rather than the cross-tournament cache."""
    sources: list[tuple[str, str, str, set[str]]] = [
        ("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V3.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_R1_LEADERBOARD"}),
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


def _player_cell(pid: str, name: str, country_by_id: dict[str, str], sponsor_by_id: dict[str, str]) -> str:
    flag_cell = ""
    country_code = country_by_id.get(pid)
    if country_code:
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
        )
    # PRE's own established invariant (139_build_hana_pre_kb_structure.py):
    # the sponsor <span> is emitted for every player, empty when
    # unverified -- never omitted, never a guessed name.
    sponsor = sponsor_by_id.get(pid)
    sponsor_text = _esc(sponsor) if sponsor else ""
    sponsor_cell = f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
    return (
        f"{flag_cell}<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(name)}</span>"
        f"{sponsor_cell}"
    )


def _prob_cell(rec: dict, key: str, label: str) -> str:
    val = rec[key]
    if val == "데이터 부족":
        return f"<td data-label='{label}'>{_NOWRAP_INSUFFICIENT}</td>"
    return f"<td class='win' data-label='{label}'>{_esc(val)}</td>"


def main() -> None:
    r1_result = _load("HANA_2026090002_R1_PLAYER_RESULT_V1.json")
    analysis = _load("HANA_2026090002_R1_ANALYSIS_V1.json")
    records = r1_result["records"]
    analysis_by_id = {r["player_id"]: r for r in analysis["records"]}
    assert len(records) == 108
    assert len(analysis_by_id) == 108

    country_by_id = _load_country_by_id()
    sponsor_by_id = _load_sponsor_by_id()

    def _sort_key(r):
        return (r["rank"] is None, r["rank"] if r["rank"] is not None else 0, int(r["player_id"]))

    # The official R1 raw data-rank attribute (the source of rank_display /
    # tie_flag in HANA_2026090002_R1_PLAYER_RESULT_V1.json) is a plain
    # number with no "T" marker even for genuine ties -- confirmed by
    # inspecting the raw HTML directly. The tie itself, however, is 100%
    # real and already present in the verified rank field: e.g. rank 1 is
    # independently held by both 박민지(8772) and 성유진(8881). Per explicit
    # instruction (with worked examples T1/T3/T7 that match these exact
    # real duplicate-rank groups), the "T" prefix is applied here as a
    # standard leaderboard tie notation derived strictly from the already-
    # verified official rank numbers -- no new data is introduced, and the
    # underlying JSON files are not modified.
    rank_counts: dict[int, int] = {}
    for r in records:
        if r["status"] != "WD" and r["rank"] is not None:
            rank_counts[r["rank"]] = rank_counts.get(r["rank"], 0) + 1

    rows_html = []
    for r in sorted(records, key=_sort_key):
        pid = r["player_id"]
        arec = analysis_by_id[pid]
        is_wd = r["status"] == "WD"
        if is_wd or r["rank"] is None:
            rank_cell = "—"
        elif rank_counts[r["rank"]] > 1:
            rank_cell = f"T{r['rank']}"
        else:
            rank_cell = str(r["rank"])
        # To-par only (no raw stroke count) -- e.g. "69 (-3)" -> "-3",
        # "72 (E)" -> "E", "73 (+1)" -> "+1". WD players show "WD" here
        # instead of a dash -- the status column was removed, so this is
        # now the sole visible WD indicator.
        score_display = "WD" if is_wd else format_to_par(r["total_under_par"])
        if not is_wd and score_display != "—":
            assert_cumulative_score_is_relative_to_par(score_display, label="1R", player=r["official_display_name"])
        player_cell = _player_cell(pid, r["official_display_name"], country_by_id, sponsor_by_id)

        band = arec["neo_performance_band"]
        band_cell = _NOWRAP_INSUFFICIENT if band == "데이터 부족" else f"<span class='band' role='img' aria-label='NEO 경기력 {_esc(band)}'>{_esc(band)}</span>"

        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}</th>"
            f"<td data-label='1R'>{_esc(score_display)}</td>"
            f"<td data-label='NEO 경기력'>{band_cell}</td>"
            f"{_prob_cell(arec, 'cut_probability', '컷 통과율')}"
            f"{_prob_cell(arec, 'top20_probability', 'TOP20')}"
            f"{_prob_cell(arec, 'top10_probability', 'TOP10')}"
            f"{_prob_cell(arec, 'top5_probability', 'TOP5')}"
            f"{_prob_cell(arec, 'win_probability', '우승확률')}"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEO GOLF DATA · {TOURNAMENT_NAME}</title><link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../../assets/neo.css"></head><body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span><span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span><span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a><nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/2026/2026090002/r1/" class="is-active" aria-current="page">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header><main><style>@media(max-width:760px){{.hana-tourinfo-sep{{display:none}}.hana-tourinfo-holes{{display:block}}}}</style><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>{TOURNAMENT_NAME}</span><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">R1</span></nav><section class="hero" id="tournament"><div><p class="eyebrow">R1 결과</p><h1>{TOURNAMENT_NAME}</h1><p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">{TOURNAMENT_WINNER_META}</p><p class="meta">{TOURNAMENT_VENUE_META}<span class="hana-tourinfo-sep"> · </span><span class="hana-tourinfo-holes">72홀 스트로크 플레이</span></p></div><p class="round-update-note">2R 종료 후 업데이트</p></section><nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list"><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/">사전 분석 PRE</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r1/" aria-current="page">R1</a></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li></ol></nav><section class="panel leaderboard-panel" id="r1"><div class="leaderboard-head"><h2>R1 결과 <small>108명</small></h2></div><div class="table-wrap table-wrap--flat-scroll"><table class="data leaderboard-table leaderboard-table--flat-scroll"><thead><tr><th>순위</th><th>선수</th><th>1R</th><th>NEO 경기력</th><th>컷 통과율</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div></section></main><nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/2026/2026090002/r1/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav><footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>"""

    assert_not_root_home(R1_PAGE, repo_root=REPO_ROOT)
    R1_PAGE.parent.mkdir(parents=True, exist_ok=True)
    R1_PAGE.write_text(html, encoding="utf-8")
    print("wrote", R1_PAGE)
    print("rows:", len(rows_html))


if __name__ == "__main__":
    main()
