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
import re
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
R1_PAGE_PATH = TOURNAMENT_DOCS_ROOT / "r1" / "index.html"

TOTAL_COLS = 7  # official result columns plus the four published R1 forecast columns


def main():
    r2 = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    by_name = {r["player_name"]: r for r in identity["records"]}

    # Preserve the probabilities exactly as published at the end of R1.
    # Never recalculate historical forecasts after observing the R2 result.
    r1_html = R1_PAGE_PATH.read_text(encoding="utf-8")
    forecast_by_name = {}
    for row in re.findall(r"<tr>(.*?)</tr>", r1_html, flags=re.DOTALL):
        name_match = re.search(r'class="player-name"[^>]*>(.*?)</span>', row)
        if not name_match:
            continue
        player_name = name_match.group(1).strip()
        values = []
        for label in ("컷 통과확률", "TOP20", "TOP10", "우승확률"):
            value_match = re.search(r'data-label="' + label + r'">([\\s\\S]*?)</td>', row)
            if not value_match:
                raise ValueError(f"R1 forecast missing {label}: {player_name}")
            values.append(re.sub(r"<[^>]+>", "", value_match.group(1)).strip())
        if player_name in forecast_by_name:
            raise ValueError(f"Duplicate player in R1 forecast: {player_name}")
        forecast_by_name[player_name] = values

    expected_names = {
        p["player_name"]
        for bucket in (r2["advanced_to_r3"], r2["missed_cut"], r2["withdrawn"])
        for p in bucket
    }
    if expected_names != set(forecast_by_name):
        raise ValueError(
            "R1 forecast/R2 official field mismatch: "
            f"missing={sorted(expected_names - set(forecast_by_name))}, "
            f"extra={sorted(set(forecast_by_name) - expected_names)}"
        )

    def forecast_cells(player_name):
        labels = ("R1 컷 예측", "R1 TOP20", "R1 TOP10", "R1 우승확률")
        return "".join(
            f'<td class="win" data-label="{label}">{value}</td>'
            for label, value in zip(labels, forecast_by_name[player_name])
        )

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
            + forecast_cells(p["player_name"])
            + "</tr>"
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
            + forecast_cells(p["player_name"])
            + "</tr>"
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
                + forecast_cells(p["player_name"])
                + "</tr>"
            )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>R1+R2 포인트</th>"
        "<th>R1 컷 예측</th><th>R1 TOP20</th><th>R1 TOP10</th><th>R1 우승확률</th></tr></thead><tbody>"
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
        "<section class=\"panel\"><h2>2R 최종 결과 · R1 예측 검증</h2>"
        f"<p>{leader['player_name']} 단독 선두 <strong>+{leader['cum36_points']}</strong> "
        f"· 컷 통과 {r2['advanced_count']}명이 3R에 진출합니다.</p>"
        + table_html
        + "<p class=\"meta\">※ 컷 통과 선수의 3R 예측은 "
        f"<a href=\"/tournaments/2026/{GAME_CODE}/r3/\">3R 예측 보기</a>에서 확인할 수 있습니다. "
        "확률은 R1 종료 시 공개했던 예측값이며 2R 종료 후 재계산하지 않았습니다. 선수별 공식 결과와 컷·기권 상태를 함께 표시합니다.</p>"
        "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 2R 최종 결과·컷 통과 · NEO GOLF DATA",
        description=f"KLPGA 공식 2R 최종 결과와 R1 종료 시 공개 예측 검증: 전체 {r2['field_size']}명, 컷 통과 {r2['advanced_count']}명, 컷 탈락 {r2['missed_cut_count']}명",
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
