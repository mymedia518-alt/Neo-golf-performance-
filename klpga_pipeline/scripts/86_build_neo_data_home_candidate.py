"""Build the non-production NEO DATA HOME candidate and preserved routes."""
from __future__ import annotations

import json
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ranking import join_home_rows, load_json  # noqa: E402

CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home"


def _cell_number(value, state: str) -> str:
    if value is None:
        return f'<span class="pending" title="{escape(state)}">검증 대기</span>'
    return f'<span data-public-number data-validation-state="{escape(state)}">{escape(str(value))}</span>'


def render_home(rows: list[dict], summary: dict) -> str:
    body = []
    for row in rows:
        feature = row["features"] or {}
        recent = "검증 대기"
        if feature:
            recent = (f'<span data-public-number data-validation-state="{escape(feature["validation_state"])}" '
                      f'title="최근 5개 {feature["recent_5_sg"]:+.3f} · 최근 10개 {feature["recent_10_sg"]:+.3f} · '
                      f'장기 {feature["long_term_sg"]:+.3f} · 표본 {feature["sample_count"]}개">'
                      f'{feature["recent_5_sg"]:+.2f} <small>({feature["sample_count"]}개)</small></span>')
        body.append(
            f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" '
            f'data-k-rank="{row["k_rank"] if row["k_rank"] is not None else 999999}">'
            f'<td>{_cell_number(row["neo_rank"], row["neo_ranking_state"])}</td>'
            f'<td>{_cell_number(row["k_rank"], row["k_ranking_state"])}</td>'
            f'<th scope="row">{escape(row["player_name"])}</th><td>{recent}</td>'
            f'<td><span class="validation-state">{("SG 확인" if feature else "SG 검증 대기")}</span></td></tr>'
        )
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOME · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/home.js" defer></script></head><body>
<header class="site-header"><div class="site-header__inner"><a class="wordmark" href="/">NEO GOLF DATA</a><nav class="global-nav" aria-label="주요 메뉴"><a class="global-nav__link" aria-current="page" href="/">HOME</a><a class="global-nav__link" href="/tournaments/">TOURNAMENTS</a><a class="global-nav__link" href="/deep-dive/">DEEP DIVE</a><a class="global-nav__link" href="/about/">ABOUT</a></nav></div></header>
<main><section class="page-head home-head"><p class="kicker">KLPGA 정규투어 선수 데이터</p><h1>선수 랭킹 허브</h1><p>대회별 우승 확률과 분리된 상시 선수 화면입니다. NEO Ranking 공식은 검증 완료 전까지 공개하지 않습니다.</p><div class="home-summary"><strong>{summary["population_count"]}</strong><span>canonical 선수</span><strong>{summary["k_ranking_join_success"]}</strong><span>K-Ranking 연결</span></div></section>
<section class="product-section" aria-labelledby="ranking-heading"><div class="section-heading"><div><p class="section-label">NEO RANKING</p><h2 id="ranking-heading">전체 선수</h2></div><span class="state-chip">공식 미확정 · 검증 대기</span></div>
<div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력" autocomplete="off"><label for="home-sort">정렬</label><select id="home-sort"><option value="name">선수명</option><option value="k-rank">K-Ranking</option></select><output id="home-count">{summary["population_count"]}명</output></div>
<div class="table-scroll"><table class="data-table home-table"><thead><tr><th>NEO Ranking</th><th>K-Ranking</th><th>선수명</th><th>최근 경기력<br><small>최근 5개 SG</small></th><th>데이터 상태</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p class="note">K-Ranking: 공식 KLPGA 2026년 35주 스냅샷을 player_id로 연결. 현재 artifact는 OK 오픈 참가자 범위이므로 미연결 선수의 순위는 만들지 않습니다. 최근 경기력은 corrected SG warehouse의 대회별 최종 누적값입니다.</p></section>
<section class="product-section evidence-section"><h2>검증 상태</h2><p>정규투어 최근 100개 대회의 canonical player_master를 사용했습니다. 이 historical population과 현재 정규투어 등록 선수 명부의 동일성은 repository 증거로 확인되지 않아 모집단 상태를 BLOCK으로 유지합니다.</p><dl><dt>NEO 공식</dt><dd>{escape(summary["neo_formula_state"])}</dd><dt>공개 순위</dt><dd>0명</dd><dt>검증 대기</dt><dd>{summary["neo_ranking_pending"]}명</dd></dl></section></main>
<footer class="site-footer"><div class="site-footer__inner"><p><strong>NEO GOLF DATA</strong> · 검증되지 않은 숫자는 공개하지 않습니다.</p></div></footer></body></html>'''


def render_tournaments() -> str:
    return '''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TOURNAMENTS · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css"></head><body>
<header class="site-header"><div class="site-header__inner"><a class="wordmark" href="/">NEO GOLF DATA</a><nav class="global-nav" aria-label="주요 메뉴"><a class="global-nav__link" href="/">HOME</a><a class="global-nav__link" aria-current="page" href="/tournaments/">TOURNAMENTS</a><a class="global-nav__link" href="/deep-dive/">DEEP DIVE</a><a class="global-nav__link" href="/about/">ABOUT</a></nav></div></header>
<main><section class="page-head"><p class="kicker">TOURNAMENTS</p><h1>대회 분석 허브</h1><p>검증된 대회 분석 페이지만 제공합니다.</p></section>
<section class="product-section" aria-labelledby="kg-heading"><h2 id="kg-heading">KG 레이디스 오픈</h2><p><a href="/tournaments/2026/kg-ladies-open/r1/">1라운드 분석</a> · <a href="/tournaments/2026/kg-ladies-open/r2/">2라운드 분석</a></p></section>
<section class="product-section" aria-labelledby="ok-heading"><h2 id="ok-heading">OK저축은행 읏맨 오픈</h2><p><a href="/tournaments/2026/ok-savings-bank-open/pre/">대회 전 분석</a> · <a href="/tournaments/2026/ok-savings-bank-open/r1/">1라운드</a> · <a href="/tournaments/2026/ok-savings-bank-open/r2/">2라운드</a> · <a href="/tournaments/2026/ok-savings-bank-open/final/">최종 분석</a></p></section></main>
<footer class="site-footer"><div class="site-footer__inner"><p><strong>NEO GOLF DATA</strong> · 검증된 데이터와 분석을 제공합니다.</p></div></footer></body></html>'''


def build() -> dict:
    population = load_json(CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    ranking = load_json(CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json")
    warehouse = load_json(CONTENT / "historical_sg_warehouse_corrected.json")
    rows, summary = join_home_rows(population, ranking, warehouse)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(REPO / "docs", OUTPUT)
    ok_source = ROOT / "candidate" / "website-v2-ok-open-pre" / "tournaments" / "2026" / "ok-savings-bank-open"
    shutil.copytree(ok_source, OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open")
    (OUTPUT / "tournaments" / "index.html").write_text(render_tournaments(), encoding="utf-8", newline="\n")
    deep_dive_source = ROOT / "candidate" / "website-v2" / "deep-dive"
    if not (deep_dive_source / "index.html").is_file():
        raise FileNotFoundError(f"validated DEEP DIVE source missing: {deep_dive_source}")
    shutil.copytree(deep_dive_source, OUTPUT / "deep-dive", dirs_exist_ok=True)
    (OUTPUT / "index.html").write_text(render_home(rows, summary), encoding="utf-8")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", OUTPUT / "assets" / "neo-site.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.js", OUTPUT / "assets" / "neo-site.js")
    neo_css = (ROOT / "candidate" / "website-v2-ok-open-pre" / "assets" / "neo.css").read_text(encoding="utf-8")
    (OUTPUT / "assets" / "neo.css").write_text(neo_css, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "home.js", OUTPUT / "assets" / "home.js")
    (OUTPUT / "data").mkdir(exist_ok=True)
    (OUTPUT / "data" / "home-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"WROTE candidate: {OUTPUT / 'index.html'}")
    return summary


if __name__ == "__main__":
    build()
