"""Build the official R2 result + cut-classification page for HJ 2026100004.

R2 is officially over (see content/website_v2/
HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json for the full evidence
trail). This page shows the FINAL, OFFICIAL R1+R2 cumulative result for
all 108 entrants and marks which ones passed the cut, missed it, or
withdrew -- per the operator's instruction, no player's R1/R2 record is
deleted or hidden, cut status is shown as its own distinct state (not
merged with R3 participation), and WD/DQ statuses are shown as their own
official status, never relabeled as CUT.

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
)

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
R2_OFFICIAL_PATH = CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json"
IDENTITY_PATH = CONTENT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"

TOTAL_COLS = 3  # 순위 / 선수 / R1+R2 포인트


def main():
    r2 = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    by_name = {r["player_name"]: r for r in identity["records"]}

    advanced = sorted(r2["advanced_to_r3"], key=lambda p: -p["cum36_points"])
    missed = sorted(r2["missed_cut"], key=lambda p: -((p["r1_points"] or 0) + (p["r2_points"] or 0)))
    withdrawn = r2["withdrawn"]

    adv_ranks = rank_labels([p["cum36_points"] for p in advanced])
    missed_ranks_base = len(advanced)
    missed_scores = [(p["r1_points"] or 0) + (p["r2_points"] or 0) for p in missed]
    missed_labels = rank_labels(missed_scores)
    missed_ranks = []
    for i, label in enumerate(missed_labels):
        if label.startswith("T"):
            missed_ranks.append(f"T{int(label[1:]) + missed_ranks_base}")
        else:
            missed_ranks.append(str(int(label) + missed_ranks_base))

    rows_html = []
    for rank, p in zip(adv_ranks, advanced):
        ident = by_name[p["player_name"]]
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=ident["nationality"], name=p["player_name"], sponsor=ident["official_sponsor"])
            + f"<td data-label=\"R1+R2 포인트\">+{p['cum36_points']}</td>"
            "</tr>"
        )

    rows_html.append(cut_divider_row(f"컷 탈락 (CUT) -- {len(missed)}명", TOTAL_COLS))
    for rank, p in zip(missed_ranks, missed):
        ident = by_name[p["player_name"]]
        score = (p["r1_points"] or 0) + (p["r2_points"] or 0)
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=ident["nationality"], name=p["player_name"], sponsor=ident["official_sponsor"], status_badge="CUT")
            + f"<td data-label=\"R1+R2 포인트\">+{score}</td>"
            "</tr>"
        )

    if withdrawn:
        rows_html.append(cut_divider_row(f"기권 (WD) -- {len(withdrawn)}명", TOTAL_COLS))
        for p in withdrawn:
            ident = by_name[p["player_name"]]
            score_label = f"+{p['r1_points']}" if p.get("r1_points") is not None else "—"
            rows_html.append(
                "<tr>"
                "<td data-label=\"순위\">—</td>"
                + name_cell(nationality=ident["nationality"], name=p["player_name"], sponsor=ident["official_sponsor"], status_badge="WD")
                + f"<td data-label=\"R1+R2 포인트\">{score_label}</td>"
                "</tr>"
            )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>R1+R2 포인트</th></tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table></div>"
    )

    leader = advanced[0]
    intro = (
        "<section class=\"page-intro\"><p class=\"eyebrow\">공식 결과 · 2R (최종)</p>"
        "<h1>HJ중공업·동부건설 챔피언십</h1>"
        "<p>변형 스테이블포드 · 2026.10.08–09 · 에이원CC · Par 72</p>"
        f"<p class=\"meta\">KLPGA 공식 리더보드 기준 2R 최종 · 전체 {r2['field_size']}명 · "
        f"컷 통과 {r2['advanced_count']}명 · 컷 탈락 {r2['missed_cut_count']}명 · 기권 {r2['wd_count']}명</p>"
        "</section>"
    )

    body = (
        "<section class=\"panel\"><h2>2R 최종 결과 · 컷 통과 선수</h2>"
        f"<p>{leader['player_name']} 단독 선두 <strong>+{leader['cum36_points']}</strong> "
        f"· 컷 통과 {r2['advanced_count']}명이 3R에 진출합니다.</p>"
        + table_html
        + "<p class=\"meta\">※ 컷 통과 선수의 3R 예측은 "
        f"<a href=\"/tournaments/2026/{GAME_CODE}/r3/\">3R 예측 보기</a>에서 확인할 수 있습니다. "
        "선수의 1R·2R 기록은 삭제되지 않으며, 컷 탈락·기권 상태만 별도로 표시됩니다.</p>"
        "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 2R 최종 결과·컷 통과 · NEO GOLF DATA",
        description=f"KLPGA 공식 2R 최종 결과: 전체 {r2['field_size']}명 중 컷 통과 {r2['advanced_count']}명, 컷 탈락 {r2['missed_cut_count']}명",
        canonical_suffix="r2",
        breadcrumb_label="2R",
        intro_html=intro,
        stage_nav=stage_nav_html("r2", live_stages={"pre", "r1", "r2", "r3"}),
        body_html=body,
    )

    out_dir = TOURNAMENT_DOCS_ROOT / "r2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "advanced": len(advanced), "missed_cut": len(missed), "withdrawn": len(withdrawn)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
