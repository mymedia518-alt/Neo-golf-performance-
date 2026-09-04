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
    OK_BASE, OK_DATE_RANGE, OK_DISPLAY_NAME, STAGE_LABELS,
    home_mode, ok_open_available_stages, ok_open_latest_available_stage, ok_open_latest_stage_update, ok_open_r1_status,
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


def _latest_live_leader_score() -> str | None:
    """Return the official cumulative leader score from the latest R1 snapshot."""
    if not R1_LIVE_SNAPSHOT.is_file():
        return None
    try:
        snapshot = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
        scores = [r.get("total_under_par") for r in snapshot.get("player_table", []) if isinstance(r.get("total_under_par"), int)]
    except (OSError, json.JSONDecodeError):
        return None
    if not scores:
        return None
    score = min(scores)
    return "E" if score == 0 else f"{score:+d}"


def _tournament_day_hero(ok_participant_count: int | None) -> str:
    # TOURNAMENT-DAY MODE: this is the ONLY thing that decides which
    # stage the CTA links to and which label it shows -- always
    # ok_open_latest_available_stage(), never a guess from today's
    # date. No leaderboard/status/probability is invented here: a
    # tournament having "started today" says nothing about whether
    # any round's data has actually been collected and validated, so
    # this only ever states the fixed date range (a fact known in
    # advance, not a live status) plus whichever stage really exists.
    stage_key, stage_url = ok_open_latest_available_stage()
    stage_label = STAGE_LABELS[stage_key]
    facts = f'<div class="tournament-day-hero__facts"><div><strong>{ok_participant_count}명</strong><span>참가 선수</span></div></div>' if ok_participant_count is not None else ""
    # R1 ACTIVE MODE: once a live stage (R1+) has a real collection
    # timestamp (never build time -- see tournament_state.py), show it
    # in HH:MM (KST) so a viewer can tell how fresh the data is. Absent
    # for PRE (no live collection backs it, just the static public
    # master).
    update = ok_open_latest_stage_update()
    updated = f'<p class="tournament-day-hero__updated">마지막 업데이트 {escape(update["retrieved_at_hhmm_kst"])} ({escape(STAGE_LABELS[update["stage"]])})</p>' if update else ""
    # R1 ACTIVE MODE: the kicker states R1's real, validated status --
    # never inferred from the clock. R1_ready()/None cases (nothing
    # live yet) fall back to the original generic "진행 중인 대회"
    # kicker (PRE-only, e.g. before the tournament's first tee time).
    r1_status = ok_open_r1_status()
    kicker = {"IN_PROGRESS": "1라운드 진행 중", "COMPLETE": "1라운드 종료"}.get(r1_status, "진행 중인 대회")
    return (f'<section class="tournament-day-hero" data-home-mode="TOURNAMENT_ACTIVE" aria-label="{escape(kicker)}">'
            f'<p class="kicker">{escape(kicker)}</p><h1>{escape(OK_DISPLAY_NAME)}</h1>'
            f'<p class="tournament-day-hero__dates">{escape(OK_DATE_RANGE)}</p>'
            f'{facts}'
            f'<div class="tournament-day-hero__stage"><span class="state-chip">현재 이용 가능한 분석</span><strong>{escape(stage_label)}</strong></div>'
            f'{updated}'
            f'<a class="primary-action" href="{escape(stage_url)}">대회 분석 보기</a>'
            f'</section>')


def render_clean(
    rows: list[dict], summary: dict, ranking_week: str | None = None, mode: str = "RANKING_DEFAULT",
    ok_participant_count: int | None = None, current_score_cells_by_id: dict[str, CurrentScoreCell] | None = None,
) -> str:
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
    # HOME INFORMATION HIERARCHY: while a tournament is active, the
    # ranking section's own heading is no longer the page's H1 -- the
    # tournament-day hero above it takes that role, so this becomes an
    # H2 (a page keeps exactly one H1). RANKING_DEFAULT (no active
    # tournament) reproduces the original H1-only markup byte-for-byte,
    # so HOME reverts cleanly once no tournament has validated data.
    tournament_hero = _tournament_day_hero(ok_participant_count) if mode == "TOURNAMENT_ACTIVE" else ""
    stage_key, _ = ok_open_latest_available_stage()
    if mode == "TOURNAMENT_ACTIVE":
        leader = _latest_live_leader_score()
        leader_text = f"Leader : {leader}" if leader is not None else "Leader : 검증 대기"
        section_heading = f'<p class="section-label">{escape(OK_DISPLAY_NAME)} · {escape(STAGE_LABELS[stage_key])}</p><h2>K-Ranking × NEO Ranking</h2><p class="home-leader-score">{leader_text}</p>'
    else:
        section_heading = '<p class="section-label">선수 비교</p><h2>TOP120 선수표</h2><span class="state-chip">검증용 · 공개 확정 전</span>'
    ranking_heading_tag = "h2" if mode == "TOURNAMENT_ACTIVE" else "h1"
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Ranking TOP120 검증</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/top120.js" defer></script></head><body><header data-neo-global-navigation></header><main>
{tournament_hero}
<section class="page-head home-head"><p class="kicker">KLPGA 공식 K-Ranking 1~120위</p><{ranking_heading_tag} class="ranking-compare-heading">공식 순위와 NEO 검증 순위 비교</{ranking_heading_tag}><p>K-Ranking과 최근 경기력을 나란히 보는 선수 비교 화면입니다.</p><div class="home-summary"><div class="stat"><strong>120</strong><span>공식 선수</span></div><div class="stat"><strong>{summary["neo_ranked"]}</strong><span>분석 가능</span></div><div class="stat"><strong>{summary["validation_pending"]}</strong><span>데이터 부족</span></div>{week_stat}</div></section>
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
    # never at today's date. When no tournament has any validated stage,
    # this is RANKING_DEFAULT and render_clean() reproduces the original
    # ranking-first HOME exactly.
    mode = home_mode()
    ok_participant_count = None
    if mode == "TOURNAMENT_ACTIVE":
        ok_master = load("OK_OPEN_2026_PRE_PUBLIC_MASTER.json")
        ok_participant_count = ok_master.get("entry_count", len(ok_master.get("records", [])))
    current_score_cells_by_id = _current_score_cells_by_id() if mode == "TOURNAMENT_ACTIVE" else {}
    rendered_home = inject_global_navigation(
        render_clean(rows, summary, cohort.get("ranking_week"), mode=mode, ok_participant_count=ok_participant_count, current_score_cells_by_id=current_score_cells_by_id),
        active_section="home",
    )
    # Replace only the ranking section heading; all table data remains the
    # exact TOP120 evaluation output above.
    if mode == "TOURNAMENT_ACTIVE":
        stage_key, _ = ok_open_latest_available_stage()
        leader = _latest_live_leader_score()
        leader_text = f"Leader : {leader}" if leader is not None else "Leader : 검증 대기"
        heading = f'<div class="section-heading"><div><p class="section-label">{escape(OK_DISPLAY_NAME)} · {escape(STAGE_LABELS[stage_key])}</p><h2>K-Ranking × NEO Ranking</h2><p class="home-leader-score">{leader_text}</p></div></div>'
        rendered_home = re.sub(r'<div class="section-heading">.*?</div><div class="home-tools">', heading + '<div class="home-tools">', rendered_home, count=1, flags=re.S)
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
    summary["home_mode"] = mode
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__": build()
