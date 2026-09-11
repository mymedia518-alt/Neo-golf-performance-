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
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.top120_validation import evaluate  # noqa: E402
from klpga.website_v2.global_navigation import inject_build_provenance, inject_global_navigation  # noqa: E402
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER, TOP120_OWNER, embed_owner, validate_top120_population,
)
from klpga.website_v2.current_score_display import CurrentScoreCell, format_current_score  # noqa: E402
from klpga.website_v2.tournament_chronology import build_home_tournament_chronology  # noqa: E402
from klpga.website_v2.player_identity import (  # noqa: E402
    cross_tournament_verified_sponsor_cache, normalize_player_sponsor_mentions,
    render_player_identity, sponsor_with_cross_tournament_fallback, verified_sponsor,
)
from klpga.tournament_context import (  # noqa: E402
    SITE_REGISTRY_PATH, candidate_dir, load_active_tournament_context, load_tournament_context,
)

OUTPUT = candidate_dir("neo-data-home-top120")

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
    """PUBLIC UI Phase 8 (sponsor rule) + PRODUCT PRESENTATION RECOVERY
    (OWNER DECISION: the sponsor contract is GLOBAL -- every public
    page displaying a player name applies the same resolution, HOME
    included): {player_id: sponsor}, built from the SAME generic,
    six-point-gated cross-tournament resolver script 84 uses for KB
    PRE (klpga.website_v2.player_identity) -- never a HOME-specific
    duplicate of that logic.

    `context`'s own current_player_master is the DIRECT evidence
    source for whichever TOP120 players are also in its field (direct
    evidence always takes precedence there; a genuine "checked, none"
    result on that record is never overwritten). A TOP120 player who
    is not in that field has no direct record to consult at all -- for
    them the shared cross-tournament cache (itself gated identically:
    PASS identity + a real official_source per source record,
    conflicting sources dropped to blank rather than guessed) applies
    directly, since it is the only evidence that exists anywhere for
    that player. Every other player simply has no entry here, which
    the caller treats identically to "sponsor not verified" (blank
    slot, never a guess, never a stale/foreign tournament's roster)."""
    context = context or _CONTEXT
    path = context.artifact_path("current_player_master")
    cache = cross_tournament_verified_sponsor_cache(exclude_paths={path} if path.is_file() else set())
    out: dict[str, str] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for row in data.get("records") or []:
            sponsor = sponsor_with_cross_tournament_fallback(row, cache)
            if sponsor:
                out[str(row.get("player_id"))] = sponsor
    for player_id, sponsor in cache.items():
        out.setdefault(player_id, sponsor)
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
        # PRODUCT PRESENTATION RECOVERY (HOME METRIC AVAILABILITY AUDIT):
        # two genuinely different things were both rendering as "—"
        # here, for two genuinely different reasons --
        #
        #   1. The composite NEO Ranking (row["neo_validation_rank"]) is
        #      a validation-only model score: NEO_RANKING_VALIDATION_MODEL_V1
        #      .json's own publication_class is
        #      "VALIDATION_MODEL_NOT_PRODUCTION" and weight_status is
        #      "HEURISTIC_FOR_EVALUATION_NOT_FITTED_OR_APPROVED" -- the
        #      SAME rule home_ranking.py's FORMULA_STATE enforces for the
        #      persistent HOME population. Publication-blocked (Class B)
        #      -- stays hidden, no exception, and the column itself is
        #      removed below rather than left as 120 dash rows.
        #
        #   2. recent_5_sg/recent_10_sg/long_term_sg/volatility are a
        #      DIFFERENT thing: each is a plain average/stdev read
        #      straight off the corrected SG warehouse
        #      (home_ranking.build_features's own
        #      "validation_state": "PASS_CORRECTED_SG_WAREHOUSE") --
        #      not a model, not a formula, not ranked. KB PRE already
        #      publishes exactly this class of metric under the same
        #      non-official "최근 5R SG" label (see the SG LABEL DECISION
        #      contract in scripts/84 / test_product_recovery_v1.py).
        #      These were blanket-blocked by this renderer alone, not by
        #      any real publication gate on the data -- Class A. They
        #      render for real now; a player genuinely below the
        #      eligibility sample threshold (row["features"] is None,
        #      "sg_join_state": "DATA_INSUFFICIENT") legitimately still
        #      shows "—" (Class C, honestly unavailable for that player).
        features = row.get("features") or {}
        def val(key, digits=2):
            return show(features.get(key), digits)
        # MOBILE COLOR/READABILITY PASS (20260910): a presentational
        # sign class only, applied exclusively to genuine signed SG
        # averages (positive = strokes gained = good, negative = lost =
        # bad -- true for recent_10_sg/recent_5_sg/long_term_sg). Never
        # applied to volatility (a non-negative magnitude, not a
        # gained/lost value) or to 현재 스코어 (to-par follows the
        # opposite, golf-specific convention -- under par is good --
        # and already has its own display treatment elsewhere). Reads
        # the same already-computed float the number itself renders
        # from; classifies its sign only, never recomputes it.
        def sg_cell(key, label, extra_class=""):
            raw = features.get(key)
            sign = "metric-empty" if raw is None else ("metric-pos" if raw > 0 else "metric-neg" if raw < 0 else "")
            cls = " ".join(c for c in (extra_class, sign) if c)
            cls_attr = f' class="{cls}"' if cls else ""
            return f"<td{cls_attr} data-label=\"{escape(label)}\">{show(raw)}</td>"
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
        # OWNER VISUAL REVIEW FAIL, item 4 (HOME VISUAL HIERARCHY):
        # 선수(Player) leads, then K-Ranking, then the two primary
        # recent-form metrics in priority order (10R before 5R, per the
        # owner's explicit ordering) -- 장기 SG/변동성 stay real data,
        # just visually secondary (class="metric-secondary", styled
        # smaller/muted in CSS, never dropped), and 현재 스코어 (live
        # tournament data, distinct from the SG features) stays last.
        cells.append(
            f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" data-k-rank="{row["official_k_rank"]}" '
            f'data-current-score="{cell.sort_score if cell.sort_score is not None else ""}" data-current-hole="{cell.sort_holes if cell.sort_holes is not None else ""}" data-current-status="{cell.sort_status}">'
            f'<th scope="row">{identity_cell}</th><td class="k-rank-cell" data-label="K-Ranking">{row["official_k_rank"]}</td>'
            + sg_cell("recent_10_sg", "최근 10R SG", "metric-sg")
            + sg_cell("recent_5_sg", "최근 5R SG", "metric-sg")
            + sg_cell("long_term_sg", "장기 SG", "metric-secondary")
            + f'<td class="metric-secondary" data-label="변동성">{val("volatility")}</td><td data-label="현재 스코어">{escape(cell.display)}</td></tr>'
        )
    # PLAYER-FIRST HOME (PRODUCTION HOME REGRESSION ROOT-CAUSE + REPAIR,
    # 20260911): the primary content -- the player table -- now renders
    # FIRST, immediately after the shared header, with no intro/coverage
    # block ahead of it. The removed "page-head home-head" block (kicker
    # + H1 "K-Ranking과 NEO Ranking" + coverage-count stats like "118
    # 최근 SG 연결"/"108 최근 10R SG 확보") was internal data-pipeline
    # coverage reporting, not user-facing product copy -- it does not
    # come back in any form. The player-comparison heading is promoted
    # to the page's one H1 in place of the removed one. The K-Ranking/
    # NEO Ranking/SG glossary ("ranking-help") is still genuinely useful
    # context, so it is kept, just moved below the table instead of
    # blocking it.
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K-Ranking TOP120</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/top120.js" defer></script></head><body><header data-neo-global-navigation></header><main>
<section class="product-section home-primary"><div class="section-heading"><div><p class="section-label">선수 비교</p><h1>TOP120 선수표</h1></div></div><div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력"><label for="home-sort">정렬</label><select id="home-sort"><option value="k-rank">K-Ranking</option><option value="name">선수명</option><option value="current-score">현재 스코어</option></select><output id="home-count">120명</output></div><div class="table-scroll" tabindex="0" aria-label="선수표 가로 스크롤"><table class="data-table home-table"><thead><tr><th>선수</th><th>K-Ranking</th><th>최근 10R SG</th><th>최근 5R SG</th><th class="metric-secondary">장기 SG</th><th class="metric-secondary">변동성</th><th>현재 스코어</th></tr></thead><tbody>{''.join(cells)}</tbody></table></div></section>
<section class="ranking-help" aria-label="순위 안내"><div><dt>K-Ranking</dt><dd>KLPGA가 매주 발표하는 공식 순위</dd></div><div><dt>NEO Ranking</dt><dd>검증 중 · 공개 전</dd></div><div><dt>최근 경기력</dt><dd>최근 10·5라운드 평균 SG로 비교</dd></div><div><dt>SG</dt><dd>필드 평균 대비 얻거나 잃은 타수</dd></div></section>
</main><footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'''
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


def resolve_chronology_stages(chronology: dict, registry: dict, output: Path):
    """HOME STATE ROUTER, decision step 1: resolve every chronology slot
    -- "current" most importantly -- to whichever of its own real,
    already-generated stage pages exists under `output` right now.
    Pure/read-only: never builds, never writes, never guesses (a slot
    with nothing real generated yet resolves to url_base=""). Generic
    across any registered tournament via its own registry
    nav_stages/stage_order, not hardcoded to any one tournament.
    Returns a NEW dict (input `chronology` is not mutated)."""
    import dataclasses
    resolved = dict(chronology)
    for slot, facts in list(resolved.items()):
        if facts is None or not facts.url_base:
            continue
        bare_index = output / facts.url_base.strip("/") / "index.html"
        if bare_index.is_file():
            continue
        reg = registry.get(facts.game_code) or {}
        stages = list((reg.get("hub_card") or {}).get("nav_stages") or reg.get("stage_order") or [])
        resolved_url = ""
        for stage in reversed(stages):
            candidate = output / facts.url_base.strip("/") / stage / "index.html"
            if candidate.is_file():
                resolved_url = f"{facts.url_base}{stage}/"
                break
        resolved[slot] = dataclasses.replace(facts, url_base=resolved_url)
    return resolved


def resolve_active_stage_page(chronology: dict, output: Path) -> Path | None:
    """HOME STATE ROUTER, decision step 2: given an ALREADY-RESOLVED
    chronology (see resolve_chronology_stages), the one path/None root
    HOME's state comes from -- a real Path only when "current" resolved
    to a real, already-generated stage page; None (-> the TOP120
    player-first fallback) otherwise, including when there is no
    current tournament at all, or its own current-tournament-specific
    PRE-forced-build path (see build() below) also found nothing."""
    current_facts = chronology.get("current")
    if current_facts is not None and current_facts.url_base:
        return output / current_facts.url_base.strip("/") / "index.html"
    return None


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
    # SPONSOR OFFICIAL-EVIDENCE RECOVERY V2 regression fix: this MUST go
    # through candidate_dir() like every other build output (see
    # tests/conftest.py's own KLPGA_CANDIDATE_ROOT_OVERRIDE comment) --
    # a hardcoded ROOT/candidate/neo-data-home literal here bypassed that
    # test-isolation redirect, so under pytest this read from whatever
    # STALE content happened to already be sitting in the real,
    # non-isolated candidate/neo-data-home/ (created by some earlier,
    # non-isolated `python scripts/86_....py` invocation) while
    # refresh_preserved_candidate()'s own script-86 build (called just
    # above) correctly wrote its FRESH output to the isolated temp
    # override instead -- a real, silent read/write path mismatch, not
    # a lockdown-specific issue. Confirmed: with no stale leftover
    # present, pytest failed outright (FileNotFoundError); with stale
    # lockdown-placeholder leftovers present, pytest silently copied
    # them forward -- both symptoms of the same root cause.
    preserved = candidate_dir("neo-data-home")
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

    # HOME STATE ROUTER (PRODUCTION HOME PRODUCT POLICY CORRECTION,
    # 20260911): resolve_chronology_stages() answers "does 'current'
    # already have a real, already-generated stage page?" BEFORE
    # deciding whether a PRE-only forced build is even needed below --
    # see tests/test_home_state_router.py for the 12 required
    # state-routing cases exercised directly against these two
    # functions (import dataclasses is still needed here for the
    # current-tournament-specific PRE-forced-build path just below).
    import dataclasses
    chronology = resolve_chronology_stages(chronology, registry, OUTPUT)

    current_facts = chronology.get("current")
    current_context = load_tournament_context(current_facts.game_code) if current_facts else None
    active_stage_page = resolve_active_stage_page(chronology, OUTPUT)
    if active_stage_page is None and current_context is not None:
        # Nothing generated yet for the current tournament -- if its own
        # publication gate has passed, build PRE (the only stage that
        # can ever be the very first one) so a brand-new "이번 대회" is
        # not silently left with no HOME content at all.
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
            active_stage_page = destination_route / "pre" / "index.html"
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

    current_score_cells_by_id = {}
    sponsor_by_id = _official_sponsor_by_id(current_context)

    # RANKING PAGE -- HOME TOURNAMENT OWNERSHIP FIX: this is now ALWAYS
    # published at its own stable URL (/ranking/), the permanent
    # K-Ranking x NEO Ranking access point, regardless of tournament
    # state. It is never what / renders during an active tournament --
    # see the root HOME block below.
    ranking_html = render_clean(rows, summary, cohort.get("ranking_week"), current_score_cells_by_id=current_score_cells_by_id, sponsor_by_id=sponsor_by_id)
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

    # ROOT HOME -- HOME STATE ROUTER (PRODUCTION HOME PRODUCT POLICY
    # CORRECTION, 20260911): / is state-dependent, decided ONLY by
    # active_stage_page (resolved above from real, verified evidence --
    # never guessed, never a hardcoded tournament, never an invented
    # time window):
    #   - active_stage_page is a real path -> a real active tournament
    #     exists -> / becomes THAT tournament's own already-published,
    #     already-gated stage page verbatim (its header/nav refreshed to
    #     mark "홈" active instead of whatever section it marked on its
    #     own dedicated route -- inject_global_navigation() already
    #     refreshes a marked header in place, this is exactly what it is
    #     for), owned by CURRENT_TOURNAMENT_OWNER.
    #   - active_stage_page is None -> no active tournament -> / falls
    #     back to the permanent player-first NEO Ranking/K-Ranking HOME
    #     (render_clean(), same content as /ranking/, no tournament
    #     cards -- the PRODUCT RECOVERY V1 predecessor of this comment
    #     attached the three cards (지난/이번/다음 대회) right after the
    #     header as "compact secondary navigation" on EVERY load, which
    #     is exactly the tournament-landing-page structure this
    #     fallback state must not have; tournament access when there is
    #     no active tournament is the existing "대회" nav item's job),
    #     owned by TOP120_OWNER.
    # Either way there is exactly one writer of docs/index.html (this
    # function) and exactly one decision point (active_stage_page).
    if active_stage_page is not None:
        stage_html = active_stage_page.read_text(encoding="utf-8")
        stage_html = stage_html.replace('href="../../../../assets/neo.css"', 'href="/assets/neo.css"')
        stage_html = stage_html.replace('href="../../../assets/neo.css"', 'href="/assets/neo.css"')
        rendered_home = inject_global_navigation(stage_html, active_section="home")
        rendered_home = rendered_home.replace("</body>", '<a class="sr-only" href="/">NEO GOLF DATA</a></body>')
        rendered_home = embed_owner(rendered_home, CURRENT_TOURNAMENT_OWNER)
    else:
        rendered_home = inject_global_navigation(ranking_html, active_section="home")
        rendered_home = rendered_home.replace("</body>", '<a class="sr-only" href="/">NEO GOLF DATA</a></body>')
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
    summary["home_mode"] = "CURRENT_TOURNAMENT_HOME" if active_stage_page is not None else "RANKING_DEFAULT"
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__": build()
