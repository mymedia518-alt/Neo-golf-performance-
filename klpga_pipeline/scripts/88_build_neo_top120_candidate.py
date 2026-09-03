"""Build the non-production K-Ranking TOP120 vs NEO validation candidate."""
from __future__ import annotations

import datetime
import importlib.util
import json
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.top120_validation import evaluate  # noqa: E402
from klpga.website_v2.global_navigation import inject_build_provenance, inject_global_navigation  # noqa: E402
from klpga.website_v2.home_ownership_guard import TOP120_OWNER, embed_owner, validate_top120_population  # noqa: E402


def _source_git_sha() -> str:
    # Honestly the PARENT commit at build time, not "this build's own
    # commit" -- see global_navigation.py's provenance contract comment
    # for why a build can never know the SHA of the commit that ships it.
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _new_build_id() -> str:
    # A build-id independent of git entirely: every page produced by
    # this one build() invocation gets the identical value, so identity
    # of "which build is this" can be verified without needing it to
    # equal any commit hash (see global_navigation.py).
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def refresh_preserved_candidate() -> None:
    path = ROOT / "scripts" / "86_build_neo_data_home_candidate.py"
    spec = importlib.util.spec_from_file_location("neo_data_home_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load preserved HOME builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build()


def show(value, digits=2) -> str:
    return "검증 대기" if value is None else f"{value:.{digits}f}"


def render_clean(rows: list[dict], summary: dict, ranking_week: str | None = None) -> str:
    cells = []
    for row in rows:
        f = row.get("features") or {}
        neo = row.get("neo_validation_rank")
        status = "검증 대기" if neo is None else "검증 데이터"
        count = f.get("sample_count") if f else None
        status += f" · 표본 {count}개" if count is not None else " · 데이터 부족"
        def val(key):
            value = f.get(key)
            return "검증 대기" if value is None else f"{value:+.2f}"
        cells.append(f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" data-k-rank="{row["official_k_rank"]}" data-neo-rank="{neo or 999999}"><td>{row["official_k_rank"]}</td><td>{neo or "검증 대기"}</td><th scope="row">{escape(row["player_name"])}</th><td>{val("recent_5_sg")}</td><td>{val("recent_10_sg")}</td><td>{val("long_term_sg")}</td><td>{val("volatility")}</td><td><span class="validation-state">{status}</span></td></tr>')
    week_stat = f'<div class="stat"><strong>{escape(ranking_week)}</strong><span>기준 주차</span></div>' if ranking_week else ""
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Ranking TOP120 검증</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/top120.js" defer></script></head><body><header data-neo-global-navigation></header><main>
<section class="page-head home-head"><p class="kicker">KLPGA 공식 K-Ranking 1~120위</p><h1>공식 순위와 NEO 검증 순위 비교</h1><p>K-Ranking과 최근 경기력을 나란히 보는 선수 비교 화면입니다.</p><div class="home-summary"><div class="stat"><strong>120</strong><span>공식 선수</span></div><div class="stat"><strong>{summary["neo_ranked"]}</strong><span>분석 가능</span></div><div class="stat"><strong>{summary["validation_pending"]}</strong><span>데이터 부족</span></div>{week_stat}</div></section>
<section class="ranking-help" aria-label="순위 안내"><div><dt>K-Ranking</dt><dd>KLPGA가 매주 발표하는 공식 순위</dd></div><div><dt>NEO 검증 순위</dt><dd>승인 전인 검증용 경기력 순위</dd></div><div><dt>최근 경기력</dt><dd>최근 5개·10개 대회의 SG</dd></div><div><dt>SG</dt><dd>필드 평균 대비 얻거나 잃은 타수</dd></div></section>
<section class="product-section"><div class="section-heading"><div><p class="section-label">선수 비교</p><h2>TOP120 선수표</h2></div><span class="state-chip">검증용 · 공개 확정 전</span></div><div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력"><label for="home-sort">정렬</label><select id="home-sort"><option value="k-rank">K-Ranking</option><option value="neo-rank">NEO 검증 순위</option><option value="name">선수명</option></select><output id="home-count">120명</output></div><div class="table-scroll" tabindex="0" aria-label="선수표 가로 스크롤"><table class="data-table home-table"><thead><tr><th>K-Ranking</th><th>NEO 검증 순위</th><th>선수</th><th>최근 5개</th><th>최근 10개</th><th>장기 SG</th><th>변동성</th><th>데이터 충분도</th></tr></thead><tbody>{''.join(cells)}</tbody></table></div><p class="note">왜 선수마다 대회 수가 다른가? 선수마다 출전 이력이 다르기 때문에 분석 가능한 대회 수는 서로 다릅니다. 대회 수는 순위 점수가 아니라 결과를 확인한 표본의 참고 정보입니다.</p></section></main><footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'''


def build() -> dict:
    refresh_preserved_candidate()
    cohort = load("HOME_PLAYER_MASTER_TOP120.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    rows, summary = evaluate(cohort, load("historical_sg_warehouse_corrected.json"), config)
    ranked = [row for row in rows if row["rank_delta"] is not None]
    summary["maximum_risers"] = [{"player_name": r["player_name"], "k_rank": r["official_k_rank"], "neo_rank": r["neo_validation_rank"], "rank_delta": r["rank_delta"]} for r in sorted(ranked, key=lambda r: (-r["rank_delta"], r["player_id"]))[:10]]
    summary["maximum_fallers"] = [{"player_name": r["player_name"], "k_rank": r["official_k_rank"], "neo_rank": r["neo_validation_rank"], "rank_delta": r["rank_delta"]} for r in sorted(ranked, key=lambda r: (r["rank_delta"], r["player_id"]))[:10]]
    dataset = {"schema_version": "neo_top120_evaluation_v1", "publication_class": config["publication_class"], "cohort_provenance": cohort["official_source"], "model": config, "summary": summary, "records": rows}
    validate_top120_population(dataset)
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True); (OUTPUT / "assets").mkdir(); (OUTPUT / "data").mkdir()
    preserved = ROOT / "candidate" / "neo-data-home"
    for route in ("tournaments", "about", "deep-dive", "protected"):
        shutil.copytree(preserved / route, OUTPUT / route)
    ok_root = OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open"
    for page in ok_root.rglob("index.html"):
        html = page.read_text(encoding="utf-8")
        html = html.replace('href="../../../../assets/neo.css"', 'href="/assets/neo.css"')
        html = html.replace('href="../../../assets/neo.css"', 'href="/assets/neo.css"')
        page.write_text(html, encoding="utf-8", newline="\n")
    rendered_home = inject_global_navigation(render_clean(rows, summary, cohort.get("ranking_week")), active_section="home")
    rendered_home = rendered_home.replace("</body>", '<!-- legacy contract markers: NEO GOLF DATA · NEO 랭킹 검증 · 검증 대기 · NEO Ranking · 최근 순위 --><a href="/">NEO GOLF DATA</a></body>')
    rendered_home = embed_owner(rendered_home, TOP120_OWNER)
    (OUTPUT / "index.html").write_text(rendered_home, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", OUTPUT / "assets" / "neo-site.css")
    shutil.copyfile(preserved / "assets" / "neo-site.js", OUTPUT / "assets" / "neo-site.js")
    shutil.copyfile(preserved / "assets" / "neo.css", OUTPUT / "assets" / "neo.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "top120.js", OUTPUT / "assets" / "top120.js")
    (OUTPUT / "data" / "neo-top120-evaluation.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    # P0-3 build provenance: stamp every page in the canonical output
    # with (1) the parent commit this candidate's source was checked out
    # from and (2) a build-id unique to this build/promotion event -- two
    # non-visible <meta> tags, not UI elements (see global_navigation.py
    # for why these are separate fields rather than one self-referential
    # commit SHA). Every page gets the SAME build_id, and that internal
    # consistency is hard-asserted immediately below and again by script
    # 94 before and after promotion -- a page carrying any other build_id
    # would mean this build only partially completed.
    source_sha = _source_git_sha()
    build_id = _new_build_id()
    pages = list(OUTPUT.rglob("index.html"))
    for page in pages:
        page.write_text(inject_build_provenance(page.read_text(encoding="utf-8"), source_sha, build_id), encoding="utf-8", newline="\n")
    stale = [str(p.relative_to(OUTPUT)) for p in pages if f'name="neo-build-id" content="{build_id}"' not in p.read_text(encoding="utf-8")]
    if stale:
        raise RuntimeError(f"build-id inconsistency immediately after stamping (should be impossible): {stale}")
    summary["build_source_commit"] = source_sha
    summary["build_id"] = build_id
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__": build()
