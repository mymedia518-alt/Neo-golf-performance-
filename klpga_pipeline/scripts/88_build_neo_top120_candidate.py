"""Build the non-production K-Ranking TOP120 vs NEO validation candidate."""
from __future__ import annotations

import csv
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
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.top120_validation import evaluate  # noqa: E402
from klpga.website_v2.global_navigation import inject_build_provenance, inject_global_navigation  # noqa: E402
from klpga.website_v2.home_ownership_guard import TOP120_OWNER, embed_owner, validate_top120_population  # noqa: E402
from klpga.website_v2.tournament_state import (  # noqa: E402
    OK_DISPLAY_NAME, STAGE_LABELS, home_mode, ok_open_latest_available_stage,
)
from klpga.website_v2.current_score_display import CurrentScoreCell, format_current_score  # noqa: E402
from klpga.website_v2.tournament_chronology import build_home_tournament_chronology  # noqa: E402
from klpga.website_v2.tournament_cards import render_tournament_cards_html  # noqa: E402
from klpga.website_v2.player_identity import render_player_identity, verified_sponsor, normalize_player_sponsor_mentions  # noqa: E402
from klpga.tournament_context import SITE_REGISTRY_PATH, load_active_tournament_context, load_tournament_context  # noqa: E402

# NEO TOURNAMENT PIPELINE: resolved from the shared context instead of
# this script's own hardcoded literals -- see src/klpga/tournament_context.py.
_CONTEXT = load_active_tournament_context()
R1_LIVE_SNAPSHOT = _CONTEXT.artifact_path("r1_live_snapshot")


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
    # script 86 consumes the active tournament candidate produced by script
    # 84. Rebuild it first so a prior explicit future-tournament PRE build
    # cannot leave shared candidate output pointed at the wrong route.
    path84 = ROOT / "scripts" / "84_build_ok_open_pre_website_candidate.py"
    spec84 = importlib.util.spec_from_file_location("active_tournament_site_builder", path84)
    if spec84 is None or spec84.loader is None:
        raise RuntimeError(f"cannot load active tournament builder: {path84}")
    module84 = importlib.util.module_from_spec(spec84)
    spec84.loader.exec_module(module84)
    module84.build(_CONTEXT.game_code)
    path = ROOT / "scripts" / "86_build_neo_data_home_candidate.py"
    spec = importlib.util.spec_from_file_location("neo_data_home_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load preserved HOME builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build()


def show(value, digits=2) -> str:
    # PUBLIC UI Phase 8 correction (FAIL 1): a missing/unapproved metric
    # renders as "--" -- never an internal validation-state label.
    return "—" if value is None else f"{value:.{digits}f}"


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


def _official_sponsor_by_id(context=None) -> dict[str, str]:
    """PUBLIC UI Phase 8 (sponsor rule): {player_id: sponsor} from the
    currently active tournament's own official current_player_master
    artifact -- the only real, official-profile-sourced sponsor data
    this repo has. Only PASS-identity rows with a real, non-empty
    current_official_sponsor are included; every other player simply
    has no entry here, which the caller treats identically to "sponsor
    not verified" (blank cell) -- never a guess, never a stale/foreign
    tournament's roster."""
    context = context or _CONTEXT
    path = context.artifact_path("current_player_master")
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for row in data.get("records") or []:
        sponsor = verified_sponsor(row)
        if sponsor:
            out[str(row.get("player_id"))] = sponsor
    return out


def _official_sponsor_by_name(context=None) -> dict[str, str]:
    """PUBLIC UI correction (GLOBAL SPONSOR RULE): {player_name:
    sponsor} from the same official, identity-validated player master
    as _official_sponsor_by_id() -- used to normalize already-built
    HTML (a completed tournament's archived pages, e.g.) that shows a
    bare player name with no player_id attribute to join on. A player
    who is not also in this active tournament's field simply has no
    entry here -- never a guess, never a foreign roster."""
    context = context or _CONTEXT
    path = context.artifact_path("current_player_master")
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for row in data.get("records") or []:
        sponsor = verified_sponsor(row)
        name = row.get("current_official_player_name")
        if sponsor and name:
            out[str(name)] = sponsor
    return out


def _known_player_names(context=None) -> set[str]:
    """PUBLIC UI correction (GLOBAL SPONSOR RULE): the broad "this bare
    text is a real player name" roster used to decide WHICH bare-text
    identity-display matches the promotion-time normalizer wraps --
    distinct from _official_sponsor_by_name() (only players with a
    verified sponsor), because a genuine player with no known sponsor
    still needs the two-slot structure, never skipped. Combines every
    real, project-tracked player roster this repo has: the top-120
    K-Ranking master (the broadest verified list), the active
    tournament's own official field, and any other registered
    tournament's own tracked roster CSV (e.g. KG Ladies Open's
    finalists) -- never a guess at what "looks like" a name."""
    names: set[str] = set()
    top120_path = CONTENT / "HOME_PLAYER_MASTER_TOP120.json"
    if top120_path.is_file():
        try:
            data = json.loads(top120_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for row in data.get("records") or []:
            name = row.get("player_name")
            if name:
                names.add(str(name))
    context = context or _CONTEXT
    ok_path = context.artifact_path("current_player_master")
    if ok_path.is_file():
        try:
            data = json.loads(ok_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for row in data.get("records") or []:
            name = row.get("current_official_player_name")
            if name:
                names.add(str(name))
    for roster_csv in (ROOT / "data" / "roster").glob("*.csv"):
        try:
            with roster_csv.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    name = row.get("player_name")
                    if name:
                        names.add(str(name))
        except OSError:
            continue
    return names


def render_clean(
    rows: list[dict], summary: dict, ranking_week: str | None = None,
    current_score_cells_by_id: dict[str, CurrentScoreCell] | None = None,
    sponsor_by_id: dict[str, str] | None = None,
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
        # The validation model remains available internally, but has no
        # publication approval. Public NEO values therefore stay explicit
        # missing values regardless of what the internal evaluation contains.
        f = {}
        neo = None
        def val(key):
            return "—"
        # R1 ACTIVE MODE: 현재 스코어 -- real tournament-total-to-par
        # PLUS current-round hole progress, joined by player_id from the
        # same live snapshot the R1 page itself reads (scripts/96).
        # format_current_score(None, ...) (== "—", NO_DATA) for a player
        # with no live row (not in the field, hasn't teed off yet, or no
        # tournament is currently active) -- never a guess. Sort reads
        # the structured data-current-* attributes below, never the
        # display string (see top120.js).
        cell = (current_score_cells_by_id or {}).get(str(row["player_id"])) or format_current_score(None, None, None)
        # PUBLIC UI Phase 8 (sponsor rule): shown directly under the
        # player name only when an official-profile sponsor was
        # actually verified for this player -- absent entirely (no
        # placeholder markup at all) otherwise, never a guessed value.
        sponsor = (sponsor_by_id or {}).get(str(row["player_id"]))
        identity_cell = render_player_identity(row["player_name"], sponsor)
        cells.append(
            f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" data-k-rank="{row["official_k_rank"]}" data-neo-rank="{neo if neo else ""}" '
            f'data-current-score="{cell.sort_score if cell.sort_score is not None else ""}" data-current-hole="{cell.sort_holes if cell.sort_holes is not None else ""}" data-current-status="{cell.sort_status}">'
            f'<td>{row["official_k_rank"]}</td><td>{neo or "—"}</td><th scope="row">{identity_cell}</th><td>{val("recent_5_sg")}</td><td>{val("recent_10_sg")}</td><td>{val("long_term_sg")}</td><td>{val("volatility")}</td><td>{escape(cell.display)}</td></tr>'
        )
    week_stat = f'<div class="stat"><strong>{escape(ranking_week)}</strong><span>기준 주차</span></div>' if ranking_week else ""
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Ranking TOP120</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/top120.js" defer></script></head><body><header data-neo-global-navigation></header><main>
<section class="page-head home-head"><p class="kicker">KLPGA 공식 K-Ranking 1~120위</p><h1 class="ranking-compare-heading">K-Ranking과 NEO Ranking</h1><p>KLPGA 공식 순위와 NEO 지표를 함께 보는 선수 화면입니다.</p><div class="home-summary"><div class="stat"><strong>120</strong><span>공식 선수</span></div><div class="stat"><strong>—</strong><span>NEO Ranking</span></div><div class="stat"><strong>—</strong><span>NEO 지표</span></div>{week_stat}</div></section>
<section class="ranking-help" aria-label="순위 안내"><div><dt>K-Ranking</dt><dd>KLPGA가 매주 발표하는 공식 순위</dd></div><div><dt>NEO Ranking</dt><dd>—</dd></div><div><dt>최근 경기력</dt><dd>—</dd></div><div><dt>SG</dt><dd>필드 평균 대비 얻거나 잃은 타수</dd></div></section>
<section class="product-section"><div class="section-heading"><div><p class="section-label">선수 비교</p><h2>TOP120 선수표</h2></div></div><div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력"><label for="home-sort">정렬</label><select id="home-sort"><option value="k-rank">K-Ranking</option><option value="neo-rank">NEO Ranking</option><option value="name">선수명</option><option value="current-score">현재 스코어</option></select><output id="home-count">120명</output></div><div class="table-scroll" tabindex="0" aria-label="선수표 가로 스크롤"><table class="data-table home-table"><thead><tr><th>K-Ranking</th><th>NEO Ranking</th><th>선수</th><th>최근 5개</th><th>최근 10개</th><th>장기 SG</th><th>변동성</th><th>현재 스코어</th></tr></thead><tbody>{''.join(cells)}</tbody></table></div></section></main><footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'''
    return document


def _neo_lab_html() -> str:
    """PUBLIC UI Phase 8: NEO LAB explains methodology in plain,
    user-facing language -- never internal pipeline-state vocabulary
    (VALIDATING/NOT PUBLISHED/PASS/BLOCKED), never raw QA row counts
    (population size, K-Rank join counts, warehouse event counts) that
    only mean something to someone reading the pipeline's own internal
    dashboards. The underlying fact this page communicates (NEO's own
    ranking formula has not cleared publication yet) is real and
    genuinely useful to a visitor -- it is stated honestly, just never
    with a developer-status badge attached to it."""
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>NEO LAB · NEO GOLF DATA</title>'
            '<link rel="stylesheet" href="/assets/neo-site.css"></head>'
            '<body><header data-neo-global-navigation></header><main>'
            '<section class="page-head"><p class="kicker">NEO LAB</p>'
            '<h1>NEO는 숫자를 어떻게 만드나요</h1>'
            '<p>NEO GOLF DATA가 공식 기록을 확인하고 검증하는 방식을 설명합니다.</p></section>'
            '<section class="product-section"><h2>공식 기록만 사용합니다</h2>'
            '<p>모든 순위와 기록은 KLPGA 공식 자료를 기준으로 합니다. 확인되지 않은 정보는 추정하지 않고 빈칸으로 남깁니다.</p></section>'
            '<section class="product-section"><h2>NEO 검증 순위</h2>'
            '<p>NEO 검증 순위는 최근 경기력을 참고용으로 비교하는 지표이며, 아직 공식 순위를 대체하지 않습니다. '
            '검증이 끝난 항목부터 순서대로 공개하며, 공개 기준을 통과하지 못한 지표는 이 페이지에도, 다른 어떤 페이지에도 표시하지 않습니다.</p></section>'
            '<section class="product-section"><h2>스폰서 표기</h2>'
            '<p>선수 이름 아래 스폰서는 KLPGA 공식 프로필에서 확인된 경우에만 표시합니다. 확인되지 않은 스폰서는 표시하지 않습니다.</p></section>'
            '</main><footer class="site-footer"><div class="site-footer__inner"><p>NEO GOLF DATA</p></div></footer></body></html>')


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
    for route in ("tournaments", "about", "deep-dive", "archive"):
        shutil.copytree(preserved / route, OUTPUT / route)
    ok_root = OUTPUT / _CONTEXT.url_base.strip("/")
    for page in ok_root.rglob("index.html"):
        html = page.read_text(encoding="utf-8")
        html = html.replace('href="../../../../assets/neo.css"', 'href="/assets/neo.css"')
        html = html.replace('href="../../../assets/neo.css"', 'href="/assets/neo.css"')
        page.write_text(html, encoding="utf-8", newline="\n")

    registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})
    chronology = build_home_tournament_chronology(registry, _CONTEXT)
    current_facts = chronology.get("current")
    current_context = load_tournament_context(current_facts.game_code) if current_facts else None
    current_stage_page = None
    if current_context is not None:
        tier2_path = current_context.artifact_path("tier2_publication_gate")
        master_path = current_context.artifact_path("pre_public_master")
        tier2 = json.loads(tier2_path.read_text(encoding="utf-8")) if tier2_path.is_file() else {}
        if master_path.is_file() and tier2.get("overall_state") == "PASS":
            path84 = ROOT / "scripts" / "84_build_ok_open_pre_website_candidate.py"
            spec84 = importlib.util.spec_from_file_location("tournament_pre_site_builder", path84)
            if spec84 is None or spec84.loader is None:
                raise RuntimeError(f"cannot load PRE website builder: {path84}")
            module84 = importlib.util.module_from_spec(spec84)
            spec84.loader.exec_module(module84)
            built84 = module84.build(current_context.game_code)
            source_route = built84 / current_context.url_base.strip("/")
            destination_route = OUTPUT / current_context.url_base.strip("/")
            shutil.copytree(source_route, destination_route, dirs_exist_ok=True)
            # LIVE FAILURE FIX: the same neo.css relative-path repair
            # applied to ok_root above (lines ~332-336) is required
            # here too. That loop only covers _CONTEXT's own tree (the
            # operationally active tournament, e.g. OK Open) -- but
            # `current_context` (the chronology "current" tournament,
            # e.g. KB while it is only upcoming) can be a DIFFERENT
            # tournament, and this exact page's content is about to be
            # read verbatim as root HOME below. A relative
            # "../../../../assets/neo.css" is correct at this page's
            # own nested URL (4 levels deep) but 404s once the same
            # bytes become "/" (0 levels deep) -- confirmed the real
            # cause of production HOME's broken/unstyled layout.
            for page in destination_route.rglob("index.html"):
                html = page.read_text(encoding="utf-8")
                html = html.replace('href="../../../../assets/neo.css"', 'href="/assets/neo.css"')
                html = html.replace('href="../../../assets/neo.css"', 'href="/assets/neo.css"')
                page.write_text(html, encoding="utf-8", newline="\n")
            current_stage_page = destination_route / "pre" / "index.html"
            import dataclasses
            chronology["current"] = dataclasses.replace(
                current_facts, url_base=f"{current_context.url_base}pre/"
            )

    # PUBLIC UI correction (GLOBAL SPONSOR RULE, Red Team FAIL A): EVERY
    # promoted route is normalized here at promotion time -- including
    # already-generated ones (they already carry both slots; the
    # already-wrapped guard makes this a no-op for them), frozen/legacy
    # pages this pipeline no longer regenerates (a completed
    # tournament's archived stage pages), and any orphaned page with no
    # current generator at all -- so a bare player-name mention, from
    # whatever produced it, always ends up with the two-slot structure.
    # archive/beta001/ (scripts/86's sanitized public copy of the frozen
    # evidence, never the raw evidence bytes themselves -- those live
    # only at klpga_pipeline/evidence/beta001/artifacts/, never under
    # docs/) is normalized exactly like every other public route below.
    sponsor_by_name = _official_sponsor_by_name(current_context)
    known_names = _known_player_names(current_context)
    for page in OUTPUT.rglob("index.html"):
        html = page.read_text(encoding="utf-8")
        normalized = normalize_player_sponsor_mentions(html, sponsor_by_name, known_names=known_names)
        if normalized != html:
            page.write_text(normalized, encoding="utf-8", newline="\n")

    mode = "TOURNAMENT_PRE" if current_stage_page is not None else "RANKING_DEFAULT"
    current_score_cells_by_id = {}
    sponsor_by_id = _official_sponsor_by_id(current_context)

    # A registry may describe stage pages without a bare tournament hub.
    # Resolve a card link to an actually generated stage, while chronology
    # identity and ordering remain exclusively calendar driven.
    import dataclasses
    for slot, facts in list(chronology.items()):
        if facts is None or not facts.url_base:
            continue
        bare_index = OUTPUT / facts.url_base.strip("/") / "index.html"
        if bare_index.is_file():
            continue
        reg = registry.get(facts.game_code) or {}
        stages = list((reg.get("hub_card") or {}).get("nav_stages") or reg.get("stage_order") or [])
        resolved_url = ""
        for stage in reversed(stages):
            candidate = OUTPUT / facts.url_base.strip("/") / stage / "index.html"
            if candidate.is_file():
                resolved_url = f"{facts.url_base}{stage}/"
                break
        chronology[slot] = dataclasses.replace(facts, url_base=resolved_url)

    # PUBLIC UI Phase 8 -- HOME's three tournament cards (지난/이번/다음
    # 대회), resolved generically from the site registry + whichever
    # tournament is currently active. Rendered once, reused on whichever
    # branch below actually becomes root HOME.
    tournament_cards_html = render_tournament_cards_html(chronology)

    # RANKING PAGE -- HOME TOURNAMENT OWNERSHIP FIX: this is now ALWAYS
    # published at its own stable URL (/ranking/), the permanent
    # K-Ranking x NEO Ranking access point, regardless of tournament
    # state. During TOURNAMENT_ACTIVE it must NOT also be what /
    # renders (see the root HOME block below) -- a tournament hero glued
    # above this exact table was the REJECTED prior "fix".
    ranking_html = render_clean(rows, summary, cohort.get("ranking_week"), current_score_cells_by_id=current_score_cells_by_id, sponsor_by_id=sponsor_by_id)
    if mode == "TOURNAMENT_ACTIVE":
        stage_key, _ = ok_open_latest_available_stage()
        leader = _latest_live_leader_score()
        leader_text = f"Leader : {leader}" if leader is not None else "Leader : 검증 대기"
        heading = f'<div class="section-heading"><div><p class="section-label">{escape(OK_DISPLAY_NAME)} · {escape(STAGE_LABELS[stage_key])}</p><h2>K-Ranking × NEO Ranking</h2><p class="home-leader-score">{leader_text}</p></div></div>'
        ranking_html = re.sub(r'<div class="section-heading">.*?</div><div class="home-tools">', heading + '<div class="home-tools">', ranking_html, count=1, flags=re.S)
    # PUBLIC UI Phase 8: the dedicated /ranking/ page now marks its own
    # "ranking" nav item active (a real, distinct top-level destination)
    # rather than borrowing "home" -- every page still carries exactly
    # one active nav item (see
    # test_p0_negative_regression.test_every_header_has_exactly_one_active_nav_item),
    # it is just the correct one now that RANKING has its own tab.
    ranking_page_html = inject_global_navigation(ranking_html, active_section="ranking")
    ranking_page_html = ranking_page_html.replace("</body>", '<a class="sr-only" href="/">NEO GOLF DATA</a></body>')
    (OUTPUT / "ranking").mkdir()
    (OUTPUT / "ranking" / "index.html").write_text(ranking_page_html, encoding="utf-8", newline="\n")

    # ROOT HOME -- PRODUCT RECOVERY V1 (HOME/PRE ROLE AUDIT correction):
    # HOME is the permanent, player-centric NEO product entry page and
    # must NEVER compose a tournament stage's own page body -- that was
    # the prior "HOME TOURNAMENT OWNERSHIP FIX" rule, now explicitly
    # superseded. / always renders the same ranking content as
    # /ranking/ (still the one stable K-Ranking x NEO Ranking URL),
    # with the three tournament cards attached right after the shared
    # header as compact secondary navigation -- current tournament's
    # own PRE/R1/R2/FINAL pages stay on their own dedicated routes
    # under /tournaments/..., never copied into /.
    rendered_home = inject_global_navigation(ranking_html, active_section="home")
    rendered_home = rendered_home.replace("</body>", '<a class="sr-only" href="/">NEO GOLF DATA</a></body>')
    rendered_home, header_count = re.subn(r"(</header>)", rf"\1{tournament_cards_html}", rendered_home, count=1)
    if header_count != 1:
        raise RuntimeError("root HOME must have exactly one </header> to attach the tournament cards after")
    rendered_home = embed_owner(rendered_home, TOP120_OWNER)
    (OUTPUT / "index.html").write_text(rendered_home, encoding="utf-8", newline="\n")
    neo_lab_html = inject_global_navigation(_neo_lab_html(), active_section="neo-lab")
    (OUTPUT / "neo-lab").mkdir()
    (OUTPUT / "neo-lab" / "index.html").write_text(neo_lab_html, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css", OUTPUT / "assets" / "neo-site.css")
    shutil.copyfile(preserved / "assets" / "neo-site.js", OUTPUT / "assets" / "neo-site.js")
    shutil.copyfile(preserved / "assets" / "neo.css", OUTPUT / "assets" / "neo.css")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "top120.js", OUTPUT / "assets" / "top120.js")
    public_dataset = {
        "ranking_week": cohort.get("ranking_week"),
        "official_source": cohort.get("official_source"),
        "players": [
            {
                "player_id": str(row["player_id"]),
                "player_name": row["player_name"],
                "official_k_rank": row["official_k_rank"],
                "sponsor": sponsor_by_id.get(str(row["player_id"])) or "",
            }
            for row in rows
        ],
    }
    (OUTPUT / "data" / "neo-top120-evaluation.json").write_text(json.dumps(public_dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
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
