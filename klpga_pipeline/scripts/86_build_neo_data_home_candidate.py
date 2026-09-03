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
from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402

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
<header data-neo-global-navigation></header>
<main><section class="page-head home-head"><p class="kicker">KLPGA 정규투어 선수 데이터</p><h1>선수 랭킹 허브</h1><p>대회별 우승 확률과 분리된 상시 선수 화면입니다. NEO Ranking 공식은 검증 완료 전까지 공개하지 않습니다.</p><div class="home-summary"><strong>{summary["population_count"]}</strong><span>canonical 선수</span><strong>{summary["k_ranking_join_success"]}</strong><span>K-Ranking 연결</span></div></section>
<section class="product-section" aria-labelledby="ranking-heading"><div class="section-heading"><div><p class="section-label">NEO RANKING</p><h2 id="ranking-heading">전체 선수</h2></div><span class="state-chip">공식 미확정 · 검증 대기</span></div>
<div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력" autocomplete="off"><label for="home-sort">정렬</label><select id="home-sort"><option value="name">선수명</option><option value="k-rank">K-Ranking</option></select><output id="home-count">{summary["population_count"]}명</output></div>
<div class="table-scroll"><table class="data-table home-table"><thead><tr><th>NEO Ranking</th><th>K-Ranking</th><th>선수명</th><th>최근 경기력<br><small>최근 5개 SG</small></th><th>데이터 상태</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p class="note">K-Ranking: 공식 KLPGA 2026년 35주 스냅샷을 player_id로 연결. 현재 artifact는 OK 오픈 참가자 범위이므로 미연결 선수의 순위는 만들지 않습니다. 최근 경기력은 corrected SG warehouse의 대회별 최종 누적값입니다.</p></section>
<section class="product-section evidence-section"><h2>검증 상태</h2><p>정규투어 최근 100개 대회의 canonical player_master를 사용했습니다. 이 historical population과 현재 정규투어 등록 선수 명부의 동일성은 repository 증거로 확인되지 않아 모집단 상태를 BLOCK으로 유지합니다.</p><dl><dt>NEO 공식</dt><dd>{escape(summary["neo_formula_state"])}</dd><dt>공개 순위</dt><dd>0명</dd><dt>검증 대기</dt><dd>{summary["neo_ranking_pending"]}명</dd></dl></section></main>
<footer class="site-footer"><div class="site-footer__inner"><p><strong>NEO GOLF DATA</strong> · 검증되지 않은 숫자는 공개하지 않습니다.</p></div></footer></body></html>'''


def render_tournaments_clean() -> str:
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>대회 · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css"></head><body><header data-neo-global-navigation></header><main><section class="page-head compact"><p class="kicker">대회</p><h1>대회 분석 허브</h1><p>검증된 대회의 기간과 상태, 분석 단계를 확인합니다.</p></section><section class="product-section"><div class="tournament-row"><div><span class="state-chip">종료</span><h2>제15회 KG 레이디스 오픈</h2><p class="note">2026.08.27–8.30 · 우승 신다인 · 271 (-17)</p></div><div><strong>분석 단계</strong><small><a href="/tournaments/2026/kg-ladies-open/pre/">사전</a> · <a href="/tournaments/2026/kg-ladies-open/r1/">R1</a> · <a href="/tournaments/2026/kg-ladies-open/r2/">R2</a> · <a href="/tournaments/2026/kg-ladies-open/r3/">R3</a> · <a href="/tournaments/2026/kg-ladies-open/final/">최종</a></small><a class="row-cta" href="/tournaments/2026/kg-ladies-open/final/">예측 기록 보기 →</a></div></div></section><section class="product-section"><div class="tournament-row"><div><span class="state-chip">예정</span><h2>OK저축은행 읏맨 오픈</h2><p class="note">2026.09.04–09.06 · 포천아도니스 · 54홀 스트로크 플레이</p></div><div><strong>분석 단계</strong><small><a href="/tournaments/2026/ok-savings-bank-open/pre/">사전</a> · <span class="stage-pending" title="아직 시작 전">R1</span> · <span class="stage-pending" title="아직 시작 전">R2</span> · <span class="stage-pending" title="아직 시작 전">최종</span></small><a class="row-cta" href="/tournaments/2026/ok-savings-bank-open/pre/">사전 분석 보기 →</a></div></div></section></main><footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'''


def build() -> dict:
    population = load_json(CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    ranking = load_json(CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json")
    warehouse = load_json(CONTENT / "historical_sg_warehouse_corrected.json")
    rows, summary = join_home_rows(population, ranking, warehouse)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(REPO / "docs", OUTPUT)
    ok_source = ROOT / "candidate" / "website-v2-ok-open-pre" / "tournaments" / "2026" / "ok-savings-bank-open"
    shutil.copytree(ok_source, OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open", dirs_exist_ok=True)
    # KG Ladies Open PRE/R3/FINAL: already-built, manifest-verified real
    # content from the beta001 pipeline (candidate/website-v2/). R1/R2
    # already arrive via the docs/ copytree above; only the closed
    # stages missing from docs/ need pulling in here. No data is
    # recomputed — these files are copied byte-for-byte, same pattern
    # already used for OK Open above.
    kg_source = ROOT / "candidate" / "website-v2" / "tournaments" / "2026" / "kg-ladies-open"
    kg_dest = OUTPUT / "tournaments" / "2026" / "kg-ladies-open"
    for stage in ("pre", "r3", "final"):
        stage_source = kg_source / stage
        if not (stage_source / "index.html").is_file():
            raise FileNotFoundError(f"verified KG {stage.upper()} source missing: {stage_source}")
        shutil.copytree(stage_source, kg_dest / stage, dirs_exist_ok=True)
    # The tournament-overview page ("개요") is the real target of every
    # stage page's title/breadcrumb link back to the tournament; it
    # already exists as verified content in candidate/website-v2/ but
    # was never pulled into this tree, leaving those links broken.
    if not (kg_source / "index.html").is_file():
        raise FileNotFoundError(f"verified KG overview source missing: {kg_source / 'index.html'}")
    shutil.copyfile(kg_source / "index.html", kg_dest / "index.html")
    # "원본 기록 보기" (view original record) on each stage page links to
    # /protected/beta001/<stage>.html -- the real, sha256-verified raw
    # evidence artifact migration.py already produces alongside every
    # stage. Never previously copied into docs/, so this 404s today for
    # the R1/R2 pages already live in production; pulling it in here
    # fixes the link for R1/R2/R3 alike, using only already-verified
    # evidence bytes.
    protected_source = ROOT / "candidate" / "website-v2" / "protected" / "beta001"
    protected_dest = OUTPUT / "protected" / "beta001"
    for stage in ("r1", "r2", "r3"):
        stage_file = protected_source / f"{stage}.html"
        if not stage_file.is_file():
            raise FileNotFoundError(f"verified KG {stage.upper()} evidence artifact missing: {stage_file}")
        protected_dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage_file, protected_dest / f"{stage}.html")
    (OUTPUT / "tournaments" / "index.html").write_text(render_tournaments_clean(), encoding="utf-8", newline="\n")
    deep_dive_source = ROOT / "candidate" / "website-v2" / "deep-dive"
    if not (deep_dive_source / "index.html").is_file():
        raise FileNotFoundError(f"validated DEEP DIVE source missing: {deep_dive_source}")
    shutil.copytree(deep_dive_source, OUTPUT / "deep-dive", dirs_exist_ok=True)
    # ABOUT: the docs/ copytree above carries over a structurally
    # disconnected legacy page (its own inline CSS/fonts/GA tag, no
    # shared global nav -- flagged in the Phase 0 audit). The real,
    # shared-nav, compact ABOUT page already exists as verified content
    # in candidate/website-v2/ (built by migration.py); use that instead.
    about_source = ROOT / "candidate" / "website-v2" / "about"
    if not (about_source / "index.html").is_file():
        raise FileNotFoundError(f"validated ABOUT source missing: {about_source}")
    shutil.rmtree(OUTPUT / "about", ignore_errors=True)
    shutil.copytree(about_source, OUTPUT / "about", dirs_exist_ok=True)
    (OUTPUT / "index.html").write_text(render_home(rows, summary), encoding="utf-8")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", OUTPUT / "assets" / "neo-site.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.js", OUTPUT / "assets" / "neo-site.js")
    neo_css = (ROOT / "candidate" / "website-v2-ok-open-pre" / "assets" / "neo.css").read_text(encoding="utf-8")
    (OUTPUT / "assets" / "neo.css").write_text(neo_css, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "home.js", OUTPUT / "assets" / "home.js")
    for page in OUTPUT.rglob("index.html"):
        relative = page.relative_to(OUTPUT)
        top = relative.parts[0] if relative.parts != (relative.name,) else None
        active_section = {"tournaments": "tournaments", "deep-dive": "deep-dive", "about": "about"}.get(top)
        if active_section is None and relative.name == "index.html" and len(relative.parts) == 1:
            active_section = "home"
        rendered = inject_global_navigation(page.read_text(encoding="utf-8"), active_section=active_section)
        rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
        page.write_text(rendered, encoding="utf-8", newline="\n")
    (OUTPUT / "data").mkdir(exist_ok=True)
    (OUTPUT / "data" / "home-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"WROTE candidate: {OUTPUT / 'index.html'}")
    return summary


if __name__ == "__main__":
    build()
