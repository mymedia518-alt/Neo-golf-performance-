"""Build the 3R forecast page for HJ 2026100004 (the 61 official R2 survivors).

Reads ONLY the public-safe fields from content/website_v2/
HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json: cut status
(trivially passed, by construction), TOP20, TOP10, win probability.
top5_pct is present in that source file but is NEVER read here -- it
must never reach any public page. No SG field is read either.

Row order/rank is based on each player's REAL official R1+R2 score (not
on forecast win probability), matching how the R1 page ranks by actual
current score rather than by model output.
"""
from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.hj_2026100004_round_pages import (
    GAME_CODE,
    TOURNAMENT_DOCS_ROOT,
    name_cell,
    page_shell,
    rank_labels,
    stage_nav_html,
    video_section_html,
)

R3_VIDEO_FILENAME = "neo-golf-data-3r.mp4"

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
FORECAST_PATH = CONTENT / "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
R2_OFFICIAL_PATH = CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json"
R1_PAGE_PATH = TOURNAMENT_DOCS_ROOT / "r1" / "index.html"

ALLOWED_PUBLIC_FIELDS = {"player_code", "player_name", "official_sponsor", "nationality", "real_cum36_points", "top20_pct", "top10_pct", "win_pct"}


def load_r1_cut_predictions() -> dict[str, str]:
    """Read the frozen R1-page cut probabilities used for the 2R forecast."""
    html = R1_PAGE_PATH.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for row in re.findall(r'<tr>(.*?)</tr>', html, flags=re.DOTALL):
        name = re.search(r'class="player-name"[^>]*>(.*?)</span>', row)
        probability = re.search(r'data-label="컷 통과확률">([^<]+)</td>', row)
        if name and probability:
            player_name = unescape(name.group(1).strip())
            if player_name in values:
                raise ValueError(f"duplicate R1 cut prediction for {player_name}")
            values[player_name] = probability.group(1).strip()
    if len(values) != 108:
        raise ValueError(f"expected 108 R1 cut predictions, found {len(values)}")
    return values



def main():
    forecast = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    r2 = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert forecast["advanced_to_r3_count"] == r2["advanced_count"] == len(forecast["players"]) == 61
    cut_predictions = load_r1_cut_predictions()

    players = sorted(forecast["players"], key=lambda p: -p["real_cum36_points"])
    ranks = rank_labels([p["real_cum36_points"] for p in players])

    rows_html = []
    for rank, p in zip(ranks, players):
        public = {k: v for k, v in p.items() if k in ALLOWED_PUBLIC_FIELDS}
        cut_prediction = cut_predictions.get(public["player_name"])
        if cut_prediction is None:
            raise ValueError(f"missing R1 cut prediction for {public['player_name']}")
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=public["nationality"], name=public["player_name"], sponsor=public["official_sponsor"])
            + f"<td data-label=\"R1+R2 포인트\">+{public['real_cum36_points']}</td>"
            f'<td class="win" data-label="2R 컷 예측">{cut_prediction}</td>'
            f"<td class=\"win\" data-label=\"TOP20\">{public['top20_pct'] * 100:.1f}%</td>"
            f"<td class=\"win\" data-label=\"TOP10\">{public['top10_pct'] * 100:.1f}%</td>"
            f"<td class=\"win\" data-label=\"우승확률\"><strong>{public['win_pct'] * 100:.1f}%</strong></td>"
            "</tr>"
        )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        '<th>순위</th><th>선수</th><th>R1+R2 포인트</th><th>2R 컷 예측</th><th>TOP20</th><th>TOP10</th><th>우승확률</th>'
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )

    leader = players[0]
    leader_win = next(p for p in forecast["players"] if p["player_name"] == leader["player_name"])["win_pct"]
    intro = (
        "<section class=\"page-intro\"><p class=\"eyebrow\">공식 결과 기반 예측 · 3R</p>"
        "<h1>HJ중공업·동부건설 챔피언십</h1>"
        "<p>변형 스테이블포드 · 2026.10.08–11 · 에이원CC · Par 72</p>"
        f"<p class=\"meta\">2R 공식 컷 통과 {len(players)}명 대상 3R·4R 예측</p>"
        "</section>"
    )

    body = (
        video_section_html(R3_VIDEO_FILENAME)
        + "<section class=\"panel\"><h2>3R 예측 · 컷 통과 61명</h2>"
        f"<p>{leader['player_name']} 단독 선두 <strong>+{leader['real_cum36_points']}</strong> "
        f"· 우승확률 {leader_win * 100:.1f}%</p>"
        + table_html
        + "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        + "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 3R 예측 · NEO GOLF DATA",
        description=f"2R 공식 컷 통과 {len(players)}명 대상 NEO 3R 예측 (2R 컷 예측/TOP20/TOP10/우승확률)",
        canonical_suffix="r3",
        breadcrumb_label="3R",
        intro_html=intro,
        stage_nav=stage_nav_html("r3", live_stages={"pre", "r1", "r2", "r3"}),
        body_html=body,
    )

    out_dir = TOURNAMENT_DOCS_ROOT / "r3"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "players": len(players)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
