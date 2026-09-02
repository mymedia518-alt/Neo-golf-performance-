"""Build the non-production K-Ranking TOP120 vs NEO validation candidate."""
from __future__ import annotations

import json
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.top120_validation import evaluate  # noqa: E402


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def show(value, digits=2) -> str:
    return "검증 대기" if value is None else f"{value:.{digits}f}"


def render(rows: list[dict], summary: dict) -> str:
    table = []
    for row in rows:
        f = row["features"] or {}
        neo = row["neo_validation_rank"]
        state = "검증 모델" if neo else "검증 대기"
        coverage = f'{f.get("sample_count", 0)}개 대회' if f else "DATA INSUFFICIENT"
        table.append(f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" data-k-rank="{row["official_k_rank"]}" data-neo-rank="{neo or 999999}">'
                     f'<td>{row["official_k_rank"]}</td><td>{neo or "검증 대기"}</td><th scope="row">{escape(row["player_name"])}</th>'
                     f'<td>{show(f.get("recent_5_sg"))}</td><td>{show(f.get("recent_10_sg"))}</td><td>{show(f.get("long_term_sg"))}</td><td>{show(f.get("volatility"))}</td>'
                     f'<td><span class="validation-state">{state} · {coverage}</span></td></tr>')
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Ranking TOP120 검증 · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/top120.js" defer></script></head><body>
<header class="site-header"><div class="site-header__inner"><a class="wordmark" href="/">NEO GOLF DATA</a><nav class="global-nav"><a class="global-nav__link" aria-current="page" href="/">HOME</a><a class="global-nav__link" href="/tournaments/">TOURNAMENTS</a><a class="global-nav__link" href="/deep-dive/">DEEP DIVE</a><a class="global-nav__link" href="/about/">ABOUT</a></nav></div></header><main>
<section class="page-head"><p class="kicker">K-Ranking TOP 120</p><h1>공식 순위와 NEO 검증 모델 비교</h1><p>2026년 35주 공식 K-Ranking 1~120위 cohort입니다. NEO 순위는 방법론 검증 전용이며 production ranking이 아닙니다.</p><div class="home-summary"><strong>120</strong><span>공식 cohort</span><strong>{summary["neo_ranked"]}</strong><span>검증 모델 산출</span></div></section>
<section class="product-section"><div class="section-heading"><div><p class="section-label">VALIDATION MODEL</p><h2>선수 비교표</h2></div><span class="state-chip">production 아님</span></div><div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력"><label for="home-sort">정렬</label><select id="home-sort"><option value="k-rank">K-Ranking</option><option value="neo-rank">NEO 검증 순위</option><option value="name">선수명</option></select><output id="home-count">120명</output></div>
<div class="table-scroll"><table class="data-table home-table"><thead><tr><th>K-Rank</th><th>NEO Rank</th><th>선수</th><th>최근5</th><th>최근10</th><th>장기 SG</th><th>변동성</th><th>데이터 상태</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>
<p class="note">모집단: 공식 KLPGA K-Ranking 1~120위. SG: corrected warehouse를 player_id로만 연결. 결측값에 0이나 평균을 대입하지 않습니다.</p></section></main><footer class="site-footer"><div class="site-footer__inner">NEO GOLF DATA · VALIDATION MODEL</div></footer></body></html>'''


def build() -> dict:
    cohort = load("HOME_PLAYER_MASTER_TOP120.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    rows, summary = evaluate(cohort, load("historical_sg_warehouse_corrected.json"), config)
    ranked = [row for row in rows if row["rank_delta"] is not None]
    summary["maximum_risers"] = [{"player_name": r["player_name"], "k_rank": r["official_k_rank"], "neo_rank": r["neo_validation_rank"], "rank_delta": r["rank_delta"]} for r in sorted(ranked, key=lambda r: (-r["rank_delta"], r["player_id"]))[:10]]
    summary["maximum_fallers"] = [{"player_name": r["player_name"], "k_rank": r["official_k_rank"], "neo_rank": r["neo_validation_rank"], "rank_delta": r["rank_delta"]} for r in sorted(ranked, key=lambda r: (r["rank_delta"], r["player_id"]))[:10]]
    dataset = {"schema_version": "neo_top120_evaluation_v1", "publication_class": config["publication_class"], "cohort_provenance": cohort["official_source"], "model": config, "summary": summary, "records": rows}
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True); (OUTPUT / "assets").mkdir(); (OUTPUT / "data").mkdir()
    preserved = ROOT / "candidate" / "neo-data-home"
    for route in ("tournaments", "about", "deep-dive"):
        shutil.copytree(preserved / route, OUTPUT / route)
    (OUTPUT / "index.html").write_text(render(rows, summary), encoding="utf-8")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", OUTPUT / "assets" / "neo-site.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "top120.js", OUTPUT / "assets" / "top120.js")
    (OUTPUT / "data" / "neo-top120-evaluation.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__": build()
