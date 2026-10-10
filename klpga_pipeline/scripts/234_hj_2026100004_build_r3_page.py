"""Build the official R3 result page for HJ 2026100004.

R3 is officially over (see content/website_v2/
HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json for the full evidence trail).
This page shows the FINAL, OFFICIAL R1+R2+R3 cumulative result for all
108 entrants: the 61 active players who played all three rounds, the 46
who missed the R2 cut (unchanged from the R2 page, they never played
R3), and the 1 withdrawal. No player's record is deleted or hidden;
CUT/WD are shown as their own distinct status, never merged into the
active field.

This replaces this script's PRIOR job (a pre-R3 forecast page, built
from the POST-R2 Monte Carlo output) -- R3 has since actually happened,
so re-publishing that forecast AS A FORECAST would be stale/misleading.
The R3->FR forecast lives on its own page
(236_hj_2026100004_build_fr_page.py).

Operator report (2026-10-10): "3R 페이지에 네오 예측들이 다 어디로
사라진거야?" -- the first version of this rewrite dropped the old
pre-R3 forecast entirely instead of carrying it forward as a dated
verification column, unlike 233_hj_2026100004_build_r2_page.py (which
keeps R1's own forecast next to R2's real result under "R1 예측
검증"). Fixed the same way here: the 61 active rows also show the
"2R 예측 검증" columns (TOP20/TOP10/우승확률 as published right after
R2 ended, from HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS
.json, read-only, never recalculated with R3 hindsight) next to their
real R1/R2/R3 scores -- clearly dated "2R ~" so it reads as a
historical prediction being checked against the real outcome, not as
R3's own upcoming forecast (that distinction is why FR exists as a
separate page). CUT/WD rows never had a post-R2 forecast (that
forecast only covers the 61 who survived the cut) and show "—".

No SG data of any kind is read or rendered by this script.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.hj_2026100004_round_pages import (
    GAME_CODE,
    TOURNAMENT_DOCS_ROOT,
    cut_divider_row,
    name_cell,
    page_shell,
    rank_labels,
    stage_nav_html,
    video_section_html,
)

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
R3_OFFICIAL_PATH = CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json"
POST_R2_FORECAST_PATH = CONTENT / "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
IDENTITY_PATH = CONTENT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
R3_VIDEO_FILENAME = "neo-golf-data-3r.mp4"


def format_points(value):
    """Format Stableford points without producing ambiguous '+-N' labels."""
    if value is None:
        return "—"
    return f"+{value}" if value > 0 else str(value)


def format_pct(value):
    return f"{value * 100:.1f}%" if value is not None else "—"


def main():
    r3 = json.loads(R3_OFFICIAL_PATH.read_text(encoding="utf-8"))
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    by_name = {r["player_name"]: r for r in identity["records"]}

    post_r2_forecast = json.loads(POST_R2_FORECAST_PATH.read_text(encoding="utf-8"))
    forecast_by_name = {p["player_name"]: p for p in post_r2_forecast["players"]}
    if set(forecast_by_name) != {p["player_name"] for p in r3["active_players"]}:
        raise ValueError(
            "POST_R2 forecast field does not exactly match R3's 61 active players: "
            f"missing={ {p['player_name'] for p in r3['active_players']} - set(forecast_by_name) }, "
            f"extra={set(forecast_by_name) - {p['player_name'] for p in r3['active_players']} }"
        )

    active = sorted(r3["active_players"], key=lambda p: -p["cum54_points"])
    missed = sorted(r3["missed_cut"], key=lambda p: -((p["r1_points"] or 0) + (p["r2_points"] or 0)))
    withdrawn = r3["withdrawn"]

    active_ranks = rank_labels([p["cum54_points"] for p in active])
    missed_ranks_base = len(active)
    missed_scores = [(p["r1_points"] or 0) + (p["r2_points"] or 0) for p in missed]
    missed_labels = rank_labels(missed_scores)
    missed_ranks = []
    for i, label in enumerate(missed_labels):
        if label.startswith("T"):
            missed_ranks.append(f"T{int(label[1:]) + missed_ranks_base}")
        else:
            missed_ranks.append(str(int(label) + missed_ranks_base))

    total_cols = 9  # 순위, 선수, R1, R2, R3, 합계, 2R TOP20, 2R TOP10, 2R 우승확률

    def forecast_cells(player_name):
        fc = forecast_by_name.get(player_name)
        if fc is None:
            return (
                "<td class=\"win\" data-label=\"2R TOP20\">—</td>"
                "<td class=\"win\" data-label=\"2R TOP10\">—</td>"
                "<td class=\"win\" data-label=\"2R 우승확률\">—</td>"
            )
        return (
            f"<td class=\"win\" data-label=\"2R TOP20\">{format_pct(fc['top20_pct'])}</td>"
            f"<td class=\"win\" data-label=\"2R TOP10\">{format_pct(fc['top10_pct'])}</td>"
            f"<td class=\"win\" data-label=\"2R 우승확률\">{format_pct(fc['win_pct'])}</td>"
        )

    rows_html = []
    for rank, p in zip(active_ranks, active):
        ident = by_name[p["player_name"]]
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=ident["nationality"], name=p["player_name"], sponsor=ident["official_sponsor"])
            + f"<td data-label=\"R1\">{format_points(p['r1_points'])}</td>"
            + f"<td data-label=\"R2\">{format_points(p['r2_points'])}</td>"
            + f"<td data-label=\"R3\">{format_points(p['r3_points'])}</td>"
            + f"<td data-label=\"합계\">{format_points(p['cum54_points'])}</td>"
            + forecast_cells(p["player_name"])
            + "</tr>"
        )

    rows_html.append(cut_divider_row(f"컷 탈락 (CUT) -- {len(missed)}명", total_cols))
    for rank, p in zip(missed_ranks, missed):
        ident = by_name[p["player_name"]]
        score = (p["r1_points"] or 0) + (p["r2_points"] or 0)
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=ident["nationality"], name=p["player_name"], sponsor=ident["official_sponsor"], status_badge="CUT")
            + f"<td data-label=\"R1\">{format_points(p['r1_points'])}</td>"
            + f"<td data-label=\"R2\">{format_points(p['r2_points'])}</td>"
            + "<td data-label=\"R3\">—</td>"
            + f"<td data-label=\"합계\">{format_points(score)}</td>"
            + forecast_cells(p["player_name"])
            + "</tr>"
        )

    if withdrawn:
        rows_html.append(cut_divider_row(f"기권 (WD) -- {len(withdrawn)}명", total_cols))
        for p in withdrawn:
            ident = by_name[p["player_name"]]
            score_label = format_points(p.get("r1_points"))
            rows_html.append(
                "<tr>"
                "<td data-label=\"순위\">—</td>"
                + name_cell(nationality=ident["nationality"], name=p["player_name"], sponsor=ident["official_sponsor"], status_badge="WD")
                + f"<td data-label=\"R1\">{score_label}</td>"
                + "<td data-label=\"R2\">—</td>"
                + "<td data-label=\"R3\">—</td>"
                + f"<td data-label=\"합계\">{score_label}</td>"
                + forecast_cells(p["player_name"])
                + "</tr>"
            )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>R3</th><th>합계</th>"
        "<th>2R TOP20</th><th>2R TOP10</th><th>2R 우승확률</th>"
        "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table></div>"
    )

    leader = active[0]
    intro = (
        "<section class=\"page-intro\"><p class=\"eyebrow\">공식 결과 · 3R (최종)</p>"
        "<h1>HJ중공업·동부건설 챔피언십</h1>"
        "<p>변형 스테이블포드 · 2026.10.08–11 · 에이원CC · Par 72</p>"
        f"<p class=\"meta\">KLPGA 공식 리더보드 기준 3R 최종 · 전체 {r3['field_size']}명 · "
        f"3R 진출 {r3['active_count']}명 · 컷 탈락 {r3['missed_cut_count']}명 · 기권 {r3['wd_count']}명</p>"
        "</section>"
    )

    body = (
        video_section_html(R3_VIDEO_FILENAME)
        + "<section class=\"panel\"><h2>3R 최종 결과 · 2R 예측 검증</h2>"
        f"<p>{leader['player_name']} 단독 선두 <strong>{format_points(leader['cum54_points'])}</strong> "
        f"· {r3['active_count']}명이 4R에 진출합니다.</p>"
        + table_html
        + f"<p><a href=\"/tournaments/2026/{GAME_CODE}/fr/\">4R 예측 보기 ↗</a></p>"
        "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 3R 최종 결과 · NEO GOLF DATA",
        description=f"KLPGA 공식 3R 최종 결과: 4R 진출 {r3['active_count']}명, 컷 탈락 {r3['missed_cut_count']}명",
        canonical_suffix="r3",
        breadcrumb_label="3R",
        intro_html=intro,
        stage_nav=stage_nav_html("r3", live_stages={"pre", "r1", "r2", "r3", "fr"}),
        body_html=body,
    )

    out_dir = TOURNAMENT_DOCS_ROOT / "r3"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "active": len(active), "missed_cut": len(missed), "withdrawn": len(withdrawn)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
