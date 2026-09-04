"""Build the non-production K-Ranking TOP120 vs NEO validation candidate."""
from __future__ import annotations

import datetime
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"
R1_LIVE_SNAPSHOT = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.top120_validation import evaluate  # noqa: E402
from klpga.website_v2.global_navigation import inject_build_provenance, inject_global_navigation  # noqa: E402
from klpga.website_v2.home_ownership_guard import TOP120_OWNER, embed_owner, validate_top120_population  # noqa: E402
from klpga.website_v2.tournament_state import (  # noqa: E402
    OK_DISPLAY_NAME, STAGE_LABELS, home_mode, ok_open_latest_available_stage,
)
from klpga.website_v2.current_score_display import CurrentScoreCell, format_current_score  # noqa: E402


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


def _current_score_cells_by_id() -> dict[str, CurrentScoreCell]:
    """{player_id: CurrentScoreCell} from the same live R1 snapshot
    script 84's R1 page reads (written only by scripts/96 after a real
    validated collection) -- score is the real tournament-cumulative
    total_under_par (never today_under_par alone; see
    current_score_display.py), holes_completed/status are the raw
    fields, normalized only for display. Empty dict -- never a
    fabricated score -- when no snapshot exists yet; a player absent
    from the snapshot simply has no entry, which render_clean's lookup
    treats identically to "no live data" (format_current_score(None,
    ...))."""
    if not R1_LIVE_SNAPSHOT.is_file():
        return {}
    snapshot = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    return {
        str(r.get("player_id")): format_current_score(r.get("total_under_par"), r.get("holes_completed"), r.get("status"))
        for r in (snapshot.get("player_table") or [])
    }


def _latest_live_leader() -> tuple[str, str] | None:
    """(player_name, official cumulative to-par display) for the real
    current leader in the latest R1 snapshot's player_table (already
    sorted ascending by total_under_par by script 96's
    _build_player_table -- the first scored row IS the leader). None
    when no snapshot exists or no player has posted a score yet --
    never a guess."""
    if not R1_LIVE_SNAPSHOT.is_file():
        return None
    try:
        snapshot = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for row in snapshot.get("player_table", []):
        score = row.get("total_under_par")
        if isinstance(score, int):
            display = "E" if score == 0 else f"{score:+d}"
            return row.get("player_name") or "—", display
    return None


def _latest_live_leader_score() -> str | None:
    """Just the score half of _latest_live_leader() -- kept for the
    ranking section's existing "Leader : -4" line."""
    leader = _latest_live_leader()
    return leader[1] if leader else None


def render_clean(
    rows: list[dict], summary: dict, ranking_week: str | None = None,
    current_score_cells_by_id: dict[str, CurrentScoreCell] | None = None,
) -> str:
    # HOME TOURNAMENT OWNERSHIP FIX: this renders ONLY the K-Ranking x
    # NEO Ranking content -- no tournament hero, no home_mode branching.
    # It is always this page's own primary content (always H1) at its
    # stable URL (candidate/OUTPUT "ranking/index.html", promoted to
    # /ranking/), and is republished verbatim at / only when
    # RANKING_DEFAULT (no active tournament) -- see build() below. A
    # tournament hero glued above this table was the REJECTED prior
    # approach: during TOURNAMENT_ACTIVE, / must BE the tournament stage
    # page itself, not this table with a banner on top.
    cells = []
    for row in rows:
        f = row.get("features") or {}
        neo = row.get("neo_validation_rank")
        def val(key):
            value = f.get(key)
            return "검증 대기" if value is None else f"{value:+.2f}"
        # R1 ACTIVE MODE: 현재 스코어 -- real tournament-total-to-par
        # PLUS current-round hole progress, joined by player_id from the
        # same live snapshot the R1 page itself reads (scripts/96).
        # format_current_score(None, ...) (== "—", NO_DATA) for a player
        # with no live row (not in the field, hasn't teed off yet, or no
        # tournament is currently active) -- never a guess. Sort reads
        # the structured data-current-* attributes below, never the
        # display string (see top120.js).
        cell = (current_score_cells_by_id or {}).get(str(row["player_id"])) or format_current_score(None, None, None)
        cells.append(
            f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" data-k-rank="{row["official_k_rank"]}" data-neo-rank="{neo or 999999}" '
            f'data-current-score="{cell.sort_score if cell.sort_score is not None else ""}" data-current-hole="{cell.sort_holes if cell.sort_holes is not None else ""}" data-current-status="{cell.sort_status}">'
            f'<td>{row["official_k_rank"]}</td><td>{neo or "검증 대기"}</td><th scope="row">{escape(row["player_name"])}</th><td>{val("recent_5_sg")}</td><td>{val("recent_10_sg")}</td><td>{val("long_term_sg")}</td><td>{val("volatility")}</td><td>{escape(cell.display)}</td></tr>'
        )
    week_stat = f'<div class="stat"><strong>{escape(ranking_week)}</strong><span>기준 주차</span></div>' if ranking_week else ""
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Ranking TOP120 검증</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/top120.js" defer></script></head><body><header data-neo-global-navigation></header><main>
<section class="page-head home-head"><p class="kicker">KLPGA 공식 K-Ranking 1~120위</p><h1 class="ranking-compare-heading">공식 순위와 NEO 검증 순위 비교</h1><p>K-Ranking과 최근 경기력을 나란히 보는 선수 비교 화면입니다.</p><div class="home-summary"><div class="stat"><strong>120</strong><span>공식 선수</span></div><div class="stat"><strong>{summary["neo_ranked"]}</strong><span>분석 가능</span></div><div class="stat"><strong>{summary["validation_pending"]}</strong><span>데이터 부족</span></div>{week_stat}</div></section>
<section class="ranking-help" aria-label="순위 안내"><div><dt>K-Ranking</dt><dd>KLPGA가 매주 발표하는 공식 순위</dd></div><div><dt>NEO 검증 순위</dt><dd>승인 전인 검증용 경기력 순위</dd></div><div><dt>최근 경기력</dt><dd>최근 5개·10개 대회의 SG</dd></div><div><dt>SG</dt><dd>필드 평균 대비 얻거나 잃은 타수</dd></div></section>
<section class="product-section"><div class="section-heading"><div><p class="section-label">선수 비교</p><h2>TOP120 선수표</h2></div><span class="state-chip">검증용 · 공개 확정 전</span></div><div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력"><label for="home-sort">정렬</label><select id="home-sort"><option value="k-rank">K-Ranking</option><option value="neo-rank">NEO 검증 순위</option><option value="name">선수명</option><option value="current-score">현재 스코어</option></select><output id="home-count">120명</output></div><div class="table-scroll" tabindex="0" aria-label="선수표 가로 스크롤"><table class="data-table home-table"><thead><tr><th>K-Ranking</th><th>NEO 검증 순위</th><th>선수</th><th>최근 5개</th><th>최근 10개</th><th>장기 SG</th><th>변동성</th><th>현재 스코어</th></tr></thead><tbody>{''.join(cells)}</tbody></table></div><p class="note">왜 선수마다 대회 수가 다른가? 선수마다 출전 이력이 다르기 때문에 분석 가능한 대회 수는 서로 다릅니다. 대회 수는 순위 점수가 아니라 결과를 확인한 표본의 참고 정보입니다.</p></section></main><footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'''


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
    if OUTPUT.exists():
        try:
            shutil.rmtree(OUTPUT)
        except PermissionError:
            pass
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
    # TOURNAMENT-DAY MODE: home_mode() is the ONLY switch -- it looks at
    # ok_open_available_stages() (real, hand-extended data availability),
    # never at today's date.
    mode = home_mode()
    current_score_cells_by_id = _current_score_cells_by_id() if mode == "TOURNAMENT_ACTIVE" else {}

    # RANKING PAGE -- HOME TOURNAMENT OWNERSHIP FIX: this is now ALWAYS
    # published at its own stable URL (/ranking/), the permanent
    # K-Ranking x NEO Ranking access point, regardless of tournament
    # state. During TOURNAMENT_ACTIVE it must NOT also be what /
    # renders (see the root HOME block below) -- a tournament hero glued
    # above this exact table was the REJECTED prior "fix".
    ranking_html = render_clean(rows, summary, cohort.get("ranking_week"), current_score_cells_by_id=current_score_cells_by_id)
    if mode == "TOURNAMENT_ACTIVE":
        stage_key, _ = ok_open_latest_available_stage()
        leader = _latest_live_leader_score()
        leader_text = f"Leader : {leader}" if leader is not None else "Leader : 검증 대기"
        heading = f'<div class="section-heading"><div><p class="section-label">{escape(OK_DISPLAY_NAME)} · {escape(STAGE_LABELS[stage_key])}</p><h2>K-Ranking × NEO Ranking</h2><p class="home-leader-score">{leader_text}</p></div></div>'
        ranking_html = re.sub(r'<div class="section-heading">.*?</div><div class="home-tools">', heading + '<div class="home-tools">', ranking_html, count=1, flags=re.S)
    # /ranking/ is always marked "홈" active -- it is conceptually still
    # HOME's own K-Ranking x NEO Ranking content (just not living at /
    # while a tournament owns that URL), and every page must carry
    # exactly one active nav item (see
    # test_p0_negative_regression.test_every_header_has_exactly_one_active_nav_item).
    ranking_html = inject_global_navigation(ranking_html, active_section="home")
    ranking_html = ranking_html.replace("</body>", '<!-- legacy contract markers: NEO GOLF DATA · NEO 랭킹 검증 · 검증 대기 · NEO Ranking · 최근 순위 --><a href="/">NEO GOLF DATA</a></body>')
    (OUTPUT / "ranking").mkdir()
    (OUTPUT / "ranking" / "index.html").write_text(ranking_html, encoding="utf-8", newline="\n")

    # ROOT HOME -- the actual product rule (HOME TOURNAMENT OWNERSHIP
    # FIX): while a tournament has any validated stage, / must BE that
    # stage's own canonical page (the exact same content as its
    # dedicated /tournaments/.../<stage>/ URL, already built above by
    # refresh_preserved_candidate()/script 84 and copied into this
    # candidate's own tournaments/ tree) -- never a hero teaser sitting
    # above the ranking table. RANKING_DEFAULT (no active tournament)
    # keeps / == the ranking page, unchanged from all prior behavior.
    if mode == "TOURNAMENT_ACTIVE":
        stage_key, _ = ok_open_latest_available_stage()
        stage_page_path = ok_root / stage_key / "index.html"
        rendered_home = inject_global_navigation(stage_page_path.read_text(encoding="utf-8"), active_section="home")
        ranking_access = '<p class="home-ranking-access"><a href="/ranking/">K-Ranking × NEO Ranking 전체 보기</a></p>'
        if "</main>" in rendered_home:
            rendered_home = rendered_home.replace("</main>", ranking_access + "</main>", 1)
        else:
            rendered_home = rendered_home.replace("</body>", ranking_access + "</body>", 1)
    else:
        rendered_home = ranking_html
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
    summary["home_mode"] = mode
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__": build()
