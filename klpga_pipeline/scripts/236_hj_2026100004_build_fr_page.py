"""Build the FR (final round / official final results) page for HJ
2026100004.

4R is officially over (HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json --
see its fr_official_final_evidence array for the evidence chain). The
page's single results table shows BOTH the official final result
(R1/R2/R3/4R points, final total, real rank) AND, in the same row per
player, the pre-4R NEO forecast (TOP20/TOP10/TOP5/win probability)
so a reader can compare prediction vs. outcome player-by-player
without cross-referencing two tables (operator instruction,
2026-10-11).

The forecast values come straight from HJ_2026100004_POST_R3_
STABLEFORD_MONTE_CARLO_V1_RESULTS.json (the real 60,000-run Monte
Carlo output generated 2026-10-10 from verified 3R input, already
public on this exact page before today) -- read, never recomputed or
adjusted to match the real outcome. Columns are explicitly prefixed
"4R 시작 전" so they can never be mistaken for a live/current forecast.
No SG field is read, on any page.

Primary row order is by REAL official final points (not by forecast
win probability), matching how every other round page on this
tournament ranks by actual score.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.hj_2026100004_round_pages import (
    GAME_CODE,
    TOURNAMENT_DOCS_ROOT,
    image_section_html,
    name_cell,
    page_shell,
    rank_labels,
    stage_nav_html,
)

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
FR_OFFICIAL_PATH = CONTENT / "HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json"
FORECAST_PATH = CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
FR_SUMMARY_IMAGE_FILENAME = "neo-golf-data-fr-summary.png"

FORECAST_PUBLIC_FIELDS = {"top20_pct", "top10_pct", "top5_pct", "win_pct"}
FORECAST_LABEL = "4R 시작 전 예측"


def main():
    final = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    forecast = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    forecast_by_name = {p["player_name"]: p for p in forecast["players"]}

    assert final["field_size"] == len(final["final_players"]) == 61
    final_names = {p["player_name"] for p in final["final_players"]}
    assert len(final_names) == len(final["final_players"]) == 61, "duplicate player name in official final results"
    assert len(forecast_by_name) == len(forecast["players"]) == 61, "duplicate player name in forecast"
    missing_forecast = final_names - set(forecast_by_name)
    extra_forecast = set(forecast_by_name) - final_names
    assert not missing_forecast, f"official final player(s) with no forecast match: {missing_forecast}"
    assert not extra_forecast, f"forecast player(s) with no official final match: {extra_forecast}"

    players = sorted(final["final_players"], key=lambda p: -p["final_points"])
    ranks = rank_labels([p["final_points"] for p in players])

    rows_html = []
    for rank, p in zip(ranks, players):
        fc = forecast_by_name[p["player_name"]]
        fpub = {k: v for k, v in fc.items() if k in FORECAST_PUBLIC_FIELDS}
        assert fpub["win_pct"] <= fpub["top5_pct"] + 1e-9, f"{p['player_name']}: win_pct > top5_pct"
        assert fpub["top5_pct"] <= fpub["top10_pct"] + 1e-9, f"{p['player_name']}: top5_pct > top10_pct"
        assert fpub["top10_pct"] <= fpub["top20_pct"] + 1e-9, f"{p['player_name']}: top10_pct > top20_pct"

        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=fc["nationality"], name=p["player_name"], sponsor=fc["official_sponsor"])
            + f"<td data-label=\"R1\">+{p['r1_points']}</td>"
            f"<td data-label=\"R2\">+{p['r2_points']}</td>"
            f"<td data-label=\"R3\">+{p['r3_points']}</td>"
            f"<td data-label=\"4R\">{'+' if p['r4_points'] >= 0 else ''}{p['r4_points']}</td>"
            f"<td data-label=\"최종 포인트\"><strong>{'+' if p['final_points'] >= 0 else ''}{p['final_points']}</strong></td>"
            f"<td class=\"win\" data-label=\"{FORECAST_LABEL} TOP20\">{fpub['top20_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"{FORECAST_LABEL} TOP10\">{fpub['top10_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"{FORECAST_LABEL} TOP5\">{fpub['top5_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"{FORECAST_LABEL} 우승확률\">{fpub['win_pct'] * 100:.2f}%</td>"
            "</tr>"
        )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table leaderboard-table--hj-fr-final\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>R3</th><th>4R</th><th>최종 포인트</th>"
        f"<th>{FORECAST_LABEL} TOP20</th><th>{FORECAST_LABEL} TOP10</th>"
        f"<th>{FORECAST_LABEL} TOP5</th><th>{FORECAST_LABEL} 우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )

    winner = players[0]
    runner_up_points = players[1]["final_points"]
    margin = winner["final_points"] - runner_up_points
    winner_forecast_win_pct = forecast_by_name[winner["player_name"]]["win_pct"]

    intro = (
        "<section class=\"page-intro\"><p class=\"eyebrow\">공식 최종 결과 · FR</p>"
        "<h1>HJ중공업·동부건설 챔피언십</h1>"
        "<p>변형 스테이블포드 · 2026.10.08–11 · 에이원CC · Par 72</p>"
        f"<p class=\"meta\">KLPGA 공식 기록 기준 최종 결과 · 전체 {len(players)}명 · {FORECAST_LABEL} 확률 비교 포함</p>"
        "</section>"
    )

    summary_alt = (
        f"{FORECAST_LABEL} 요약: {winner['player_name']} 우승확률 "
        f"{winner_forecast_win_pct * 100:.1f}% 1위"
    )

    body = (
        "<section class=\"panel\"><h2>공식 최종 순위 · {}명</h2>".format(len(players))
        + f"<p><strong>{winner['player_name']}</strong> 우승 "
        f"<strong>{'+' if winner['final_points'] >= 0 else ''}{winner['final_points']}</strong>"
        f" · 2위와 {margin}점 차</p>"
        + f"<p>'R1'~'최종 포인트'는 KLPGA 공식 최종 결과이고, '{FORECAST_LABEL}' 열은 4R이 시작되기 전 "
        "검증된 3R 입력으로 공개했던 NEO 예측입니다. 예측 수치는 공개 당시 값 그대로이며, "
        "실제 결과가 나온 뒤에도 다시 계산하거나 결과에 맞춰 바꾸지 않습니다.</p>"
        + table_html
        + "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        + image_section_html(FR_SUMMARY_IMAGE_FILENAME, summary_alt, section_id="fr-summary")
        + f"<p><a href=\"/tournaments/2026/{GAME_CODE}/r3/\">3R 최종 결과 보기</a></p>"
        + "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 공식 최종 결과 · NEO GOLF DATA",
        description=f"HJ중공업·동부건설 챔피언십 KLPGA 공식 최종 결과 전체 {len(players)}명 (우승 {winner['player_name']} {winner['final_points']}) · {FORECAST_LABEL} 확률 비교",
        canonical_suffix="fr",
        breadcrumb_label="FR",
        intro_html=intro,
        stage_nav=stage_nav_html("fr", live_stages={"pre", "r1", "r2", "r3", "fr"}),
        body_html=body,
    )

    out_dir = TOURNAMENT_DOCS_ROOT / "fr"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "players": len(players), "winner": winner["player_name"], "winner_points": winner["final_points"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
