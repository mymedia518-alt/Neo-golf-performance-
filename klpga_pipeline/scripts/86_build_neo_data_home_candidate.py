"""Build the non-production NEO DATA HOME candidate and preserved routes."""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from datetime import date as _date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ranking import join_home_rows, load_json  # noqa: E402
from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402
from klpga.website_v2.tournament_state import ok_open_available_stages  # noqa: E402
from klpga.website_v2.player_identity import render_player_identity, verified_sponsor, normalize_player_sponsor_mentions  # noqa: E402
from klpga.website_v2.official_schedule import load_official_schedule  # noqa: E402
from klpga.tournament_context import (  # noqa: E402
    CONTENT_DIR,
    candidate_dir,
    load_active_tournament_context,
    load_tournament_context,
    SITE_REGISTRY_PATH,
)

CONTENT = ROOT / "content" / "website_v2"
OUTPUT = candidate_dir("neo-data-home")


def _official_sponsor_by_name() -> dict[str, str]:
    """PUBLIC UI correction (GLOBAL SPONSOR RULE): {player_name:
    sponsor} from the official, identity-validated player master --
    used to normalize already-built HTML (a completed tournament's
    archived pages, e.g.) that shows a bare player name with no
    player_id attribute to join on. Mirrors scripts/88's own helper of
    the same name exactly, since this candidate needs the identical
    global-sponsor-rule pass scripts/88 already applies to its own
    output tree."""
    path = _CONTEXT.artifact_path("current_player_master")
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


def _known_player_names() -> set[str]:
    """PUBLIC UI correction (GLOBAL SPONSOR RULE): the broad "this bare
    text is a real player name" roster -- mirrors scripts/88's own
    helper of the same name exactly (see that docstring for the full
    rationale)."""
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
    ok_path = _CONTEXT.artifact_path("current_player_master")
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

# PUBLIC ARCHIVE correction (Red Team FAIL D): the frozen R1 evidence's
# own published heading uses a developer-facing English label ("R1 DATA
# UNAVAILABLE") ahead of its own already-honest Korean parenthetical.
# This is a text-only substitution applied to the SANITIZED public copy
# only -- the frozen evidence bytes at evidence/beta001/artifacts/ are
# never touched (see the sha256 check at build time).
_R1_DATA_UNAVAILABLE_HEADING_RE = re.compile(r"R1 DATA UNAVAILABLE\s*\(([^)]*)\)")
# The frozen evidence's own bare <header>...</header> (its pre-global-
# nav-system wordmark/round-status block, no attributes, no
# data-neo-global-navigation marker) would otherwise sit right
# alongside the canonical global header inject_global_navigation()
# adds -- a visible duplicate header on the public copy. Stripped only
# from the in-memory sanitized derivative; the frozen bytes on disk are
# never touched by this.
_LEGACY_ARCHIVE_HEADER_RE = re.compile(r"<header>.*?</header>", re.S)


def _sanitize_public_archive_text(html: str) -> str:
    html = _LEGACY_ARCHIVE_HEADER_RE.sub("", html)
    return _R1_DATA_UNAVAILABLE_HEADING_RE.sub(r"\1", html)
# NEO TOURNAMENT PIPELINE: resolved from the shared context instead of
# this script's own hardcoded literal -- see src/klpga/tournament_context.py.
_CONTEXT = load_active_tournament_context()


def _cell_number(value, state: str) -> str:
    # PUBLIC/CANDIDATE TEXT correction: a missing value renders as "--",
    # never an internal validation-state phrase -- data-validation-state
    # stays as a non-visible machine attribute only.
    if value is None:
        return f'<span class="pending" data-validation-state="{escape(state)}">—</span>'
    return f'<span data-public-number data-validation-state="{escape(state)}">{escape(str(value))}</span>'


def _sponsor_by_name() -> dict[str, str]:
    """Same official, identity-validated player master every other
    sponsor lookup in this pipeline uses -- see
    klpga.website_v2.player_identity.verified_sponsor()."""
    path = _CONTEXT.artifact_path("current_player_master")
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for r in data.get("records") or []:
        sponsor = verified_sponsor(r)
        name = r.get("current_official_player_name")
        if sponsor and name:
            out[str(name)] = sponsor
    return out


def render_home(rows: list[dict], summary: dict) -> str:
    sponsor_by_name = _sponsor_by_name()
    body = []
    for row in rows:
        feature = row["features"] or {}
        recent = "—"
        if feature:
            recent = (f'<span data-public-number data-validation-state="{escape(feature["validation_state"])}" '
                      f'title="최근 5개 {feature["recent_5_sg"]:+.3f} · 최근 10개 {feature["recent_10_sg"]:+.3f} · '
                      f'장기 {feature["long_term_sg"]:+.3f} · 표본 {feature["sample_count"]}개">'
                      f'{feature["recent_5_sg"]:+.2f} <small>({feature["sample_count"]}개)</small></span>')
        identity_cell = render_player_identity(row["player_name"], sponsor_by_name.get(row["player_name"]))
        body.append(
            f'<tr data-player-row data-player-name="{escape(row["player_name"].casefold())}" '
            f'data-k-rank="{row["k_rank"] if row["k_rank"] is not None else ""}">'
            f'<td>{_cell_number(row["neo_rank"], row["neo_ranking_state"])}</td>'
            f'<td>{_cell_number(row["k_rank"], row["k_ranking_state"])}</td>'
            f'<th scope="row">{identity_cell}</th><td>{recent}</td>'
            f'<td><span class="validation-state">{("확인됨" if feature else "—")}</span></td></tr>'
        )
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOME · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css"><script src="/assets/home.js" defer></script></head><body>
<header data-neo-global-navigation></header>
<main><section class="page-head home-head"><p class="kicker">KLPGA 정규투어 선수 데이터</p><h1>선수 랭킹 허브</h1><p>대회별 우승 확률과 분리된 상시 선수 화면입니다. NEO Ranking 공식은 준비가 끝날 때까지 공개하지 않습니다.</p></section>
<section class="product-section" aria-labelledby="ranking-heading"><div class="section-heading"><div><p class="section-label">NEO RANKING</p><h2 id="ranking-heading">전체 선수</h2></div></div>
<div class="home-tools"><label for="player-search">선수 검색</label><input id="player-search" type="search" placeholder="선수명 입력" autocomplete="off"><label for="home-sort">정렬</label><select id="home-sort"><option value="name">선수명</option><option value="k-rank">K-Ranking</option></select><output id="home-count"></output></div>
<div class="table-scroll"><table class="data-table home-table"><thead><tr><th>NEO Ranking</th><th>K-Ranking</th><th>선수명</th><th>최근 경기력<br><small>최근 5개 SG</small></th><th>데이터 상태</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p class="note">K-Ranking: 공식 KLPGA 2026년 35주 자료를 선수 기준으로 연결했습니다. 연결되지 않은 선수는 순위를 만들지 않습니다.</p></section>
<section class="product-section evidence-section"><h2>데이터 안내</h2><p>공식 기록만 사용하며, 확인되지 않은 정보는 추정하지 않고 빈칸으로 남깁니다. NEO 자체 순위는 아직 공개되지 않았습니다.</p></section></main>
<footer class="site-footer"><div class="site-footer__inner"><p><strong>NEO GOLF DATA</strong> · 확인되지 않은 숫자는 공개하지 않습니다.</p></div></footer></body></html>'''


STAGE_NAV_LABELS = {"pre": "사전", "r1": "R1", "r2": "R2", "r3": "R3", "final": "최종"}


def _tournament_row_html(*, display_name: str, status: str, meta_line: str, nav_stages: list[str],
                          available_stages: dict[str, str], cta_url: str, cta_label: str) -> str:
    nav_items = []
    for stage in nav_stages:
        url = available_stages.get(stage)
        label = STAGE_NAV_LABELS[stage]
        if url:
            nav_items.append(f'<a href="{escape(url)}">{label}</a>')
        else:
            nav_items.append(f'<span class="stage-pending" title="아직 시작 전">{label}</span>')
    return ('<section class="product-section"><div class="tournament-row"><div>'
            f'<span class="state-chip">{escape(status)}</span><h2>{escape(display_name)}</h2>'
            f'<p class="note">{escape(meta_line)}</p></div><div><strong>분석 단계</strong>'
            f'<small>{" · ".join(nav_items)}</small>'
            f'<a class="row-cta" href="{escape(cta_url)}">{escape(cta_label)}</a></div></div></section>')


_HUB_DASH = "—"


def _schedule_entries():
    """{game_code: ScheduleEntry} from the same official schedule
    (OFFICIAL_KLPGA_SCHEDULE.json) that
    klpga.website_v2.tournament_chronology already treats as the ONLY
    source of real calendar identity for HOME's 3-card widget (see
    that module's own docstring: "Pipeline stage freshness must never
    decide calendar identity in either direction -- only the official
    schedule's own start_date/end_date does now"). The tournament hub
    reuses the exact same signal so a tournament's hub-card status can
    never disagree with its own chronology card. Also carries the
    schedule's own real venue -- TournamentContext.venue only ever
    reflects TOURNAMENT_SITE_REGISTRY.json (not every tournament has a
    registry-level venue yet), so a tournament with a real, sourced
    schedule venue but no registry venue would otherwise render a
    dash for a fact that is genuinely already known."""
    schedule = load_official_schedule(CONTENT_DIR / "OFFICIAL_KLPGA_SCHEDULE.json")
    return {entry.game_code: entry for entry in schedule}


def _tournament_cards_html() -> str:
    """One card per known tournament (TOURNAMENT_SITE_REGISTRY.json's
    hub_card entries, in registry order -- see its _hub_card_comment).
    Three shapes of hub_card, each rendered differently:
      1. The currently active tournament (game_code == _CONTEXT.game_code):
         status/stage-availability computed live from TournamentContext
         + ok_open_available_stages(), the same real validated-state
         function every other live page reads -- but calendar
         completion (real schedule end_date) always overrides a stale
         "still in progress" reading once the tournament's real dates
         have passed (LIVE FAILURE FIX, Bug D).
      2. A completed tournament with recorded static facts (hub_card
         has "display_name"): uses its own recorded hub_card facts,
         since no live official-result artifact exists for a
         tournament that is already over.
      3. Any other tournament with a hub_card (only "nav_stages", no
         static facts -- e.g. a tournament with real pages published
         that is neither active nor completed-with-recorded-facts):
         resolved live from TournamentContext + the real schedule
         dates, exactly like branch 1, so it is never silently
         skipped (LIVE FAILURE FIX, Bug C) and never goes stale as
         more of its real stages are built."""
    registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig"))["tournaments"]
    schedule_entries = _schedule_entries()
    today_iso = _date.today().isoformat()
    cards = []
    for game_code, entry in registry.items():
        hub = entry.get("hub_card")
        if hub is None:
            continue
        url_base = entry["url_base"]
        nav_stages = hub["nav_stages"]
        if game_code == _CONTEXT.game_code:
            available = ok_open_available_stages()
            display_name = _CONTEXT.tournament_name
            schedule_entry = schedule_entries.get(game_code)
            calendar_ended = schedule_entry is not None and today_iso > schedule_entry.end_date
            status = "종료" if calendar_ended else ("진행중" if any(stage != "pre" for stage in available) else "예정")
            venue = _CONTEXT.venue or _HUB_DASH
            holes = f"{_CONTEXT.holes}홀" if _CONTEXT.holes else _HUB_DASH
            fmt = _CONTEXT.format or _HUB_DASH
            meta_line = f"{_CONTEXT.display_date_range} · {venue} · {holes} {fmt}"
            cta_stage = next((stage for stage in reversed(nav_stages) if stage in available), "pre")
            cta_label = "사전 분석 보기 →" if cta_stage == "pre" else "예측 기록 보기 →"
        elif "display_name" in hub:
            available = {stage: f"{url_base}{stage}/" for stage in nav_stages}
            display_name = hub["display_name"]
            status = hub["status"]
            meta_line = f'{hub["date_range"]} · {hub["result_line"]}'
            cta_stage = hub["cta_stage"]
            cta_label = "예측 기록 보기 →"
        else:
            ctx = load_tournament_context(game_code)
            available = {stage: f"{url_base}{stage}/" for stage in nav_stages}
            display_name = ctx.tournament_name
            schedule_entry = schedule_entries.get(game_code)
            if schedule_entry is not None and today_iso > schedule_entry.end_date:
                status = "종료"
            elif schedule_entry is not None and today_iso >= schedule_entry.start_date:
                status = "진행중"
            else:
                status = "예정"
            # venue prefers the registry (ctx.venue, same field the
            # active-tournament branch above uses) and falls back to
            # the official schedule's own real, sourced venue -- a
            # tournament with no registry-level venue yet is not
            # necessarily a tournament with NO known venue at all.
            venue = ctx.venue or (schedule_entry.venue if schedule_entry else None) or _HUB_DASH
            holes = f"{ctx.holes}홀" if ctx.holes else _HUB_DASH
            fmt = ctx.format or _HUB_DASH
            meta_line = f"{ctx.display_date_range} · {venue} · {holes} {fmt}"
            cta_stage = next((stage for stage in reversed(nav_stages) if stage in available), "pre")
            cta_label = "사전 분석 보기 →" if cta_stage == "pre" else "예측 기록 보기 →"
        cards.append(_tournament_row_html(
            display_name=display_name, status=status, meta_line=meta_line, nav_stages=nav_stages,
            available_stages=available, cta_url=available.get(cta_stage, f"{url_base}{cta_stage}/"), cta_label=cta_label,
        ))
    return "".join(cards)


def render_tournaments_clean() -> str:
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>대회 · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css"></head><body>'
            '<header data-neo-global-navigation></header><main>'
            '<section class="page-head compact"><p class="kicker">대회</p><h1>대회 분석 허브</h1>'
            '<p>검증된 대회의 기간과 상태, 분석 단계를 확인합니다.</p></section>'
            + _tournament_cards_html() +
            '</main><footer class="site-footer"><div class="site-footer__inner">'
            '<p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>')


def build() -> dict:
    population = load_json(CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    ranking = load_json(_CONTEXT.artifact_path("official_klpga_ranking"))
    warehouse = load_json(CONTENT / "historical_sg_warehouse_corrected.json")
    rows, summary = join_home_rows(population, ranking, warehouse)
    if OUTPUT.exists():
        try:
            shutil.rmtree(OUTPUT)
        except PermissionError:
            # Managed Windows worktrees may deny cleanup of prior generated
            # files; overwrite the deterministic outputs in place instead.
            pass
    shutil.copytree(REPO / "docs", OUTPUT, dirs_exist_ok=True)
    # SPONSOR OFFICIAL-EVIDENCE RECOVERY V2 regression fix: docs/ can be
    # in a MAIN ONLY LOCKDOWN state (every route but "/" replaced with
    # the "under construction" placeholder -- see
    # scripts/apply_public_site_lockdown.py). This candidate build's own
    # "closed stage" pages (KG r1/r2, OK r3, etc. -- see the copytree
    # calls below) were never meant to inherit that PUBLIC-facing
    # publication state; they are pulled from docs/ only because it
    # already carries their last real, correct content. When
    # docs_internal_archive/ exists (the lockdown's own preserved
    # originals, never deleted), overlay it on top of the docs/ bootstrap
    # so this candidate build always reflects real content regardless of
    # production's current public lockdown state -- production's own
    # docs/ is never touched or unlocked by this.
    archive_dir = REPO / "docs_internal_archive"
    if archive_dir.is_dir():
        shutil.copytree(archive_dir, OUTPUT, dirs_exist_ok=True)
    # HARD GUARANTEE (ARCHITECTURE correction): docs/ is only ever a
    # bootstrap SOURCE here, never trusted as already-correct -- any
    # protected/ this docs/ bootstrap copy carried forward (a stale
    # pre-correction leftover, or a manual edit) is scrubbed
    # unconditionally. The frozen beta001 evidence must never reach a
    # publishable route; see the archive/beta001/ generation below for
    # its sanitized public replacement.
    shutil.rmtree(OUTPUT / "protected", ignore_errors=True)
    registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig"))["tournaments"]
    ok_route = _CONTEXT.url_base.strip("/")
    ok_source = ROOT / "candidate" / "website-v2-ok-open-pre" / ok_route
    shutil.copytree(ok_source, OUTPUT / ok_route, dirs_exist_ok=True)
    # KG Ladies Open PRE/R3/FINAL: already-built, manifest-verified real
    # content from the beta001 pipeline (candidate/website-v2/). R1/R2
    # already arrive via the docs/ copytree above; only the closed
    # stages missing from docs/ need pulling in here. No data is
    # recomputed — these files are copied byte-for-byte, same pattern
    # already used for OK Open above.
    # The one completed, non-active tournament in the registry (KG
    # Ladies Open today) -- identified by NOT being the currently
    # active game_code, never by its own literal game_code.
    completed_game_code = next(gc for gc in registry if gc != _CONTEXT.game_code)
    kg_route = registry[completed_game_code]["url_base"].strip("/")
    kg_source = ROOT / "candidate" / "website-v2" / kg_route
    kg_dest = OUTPUT / kg_route
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
    # PUBLIC ARCHIVE (Red Team FAIL B correction): "원본 기록 보기" (view
    # original record) on each stage page links to /archive/beta001/
    # <stage>/ -- a SANITIZED public copy, never the raw frozen evidence
    # bytes directly. The immutable evidence itself (sha256-verified
    # against klpga_pipeline/evidence/beta001/manifest.json by
    # migration.py's own build) never lives under docs/ at all; this
    # block only ever reads it (never mutates the frozen source) to
    # build a public-facing derivative that carries the same global
    # header / sponsor-slot rule every other public route follows.
    protected_source = ROOT / "candidate" / "website-v2" / "protected" / "beta001"
    archive_dest = OUTPUT / "archive" / "beta001"
    for stage in ("r1", "r2", "r3"):
        stage_file = protected_source / f"{stage}.html"
        if not stage_file.is_file():
            raise FileNotFoundError(f"verified KG {stage.upper()} evidence artifact missing: {stage_file}")
        raw_html = stage_file.read_text(encoding="utf-8")
        # The frozen evidence is a headless content fragment (no
        # <!doctype>/<html>/<head>/<body>, and it carries its OWN legacy
        # <header>...</header> block). Text-sanitize and strip that
        # legacy header FIRST, then wrap in a minimal well-formed
        # document shell BEFORE inject_global_navigation runs, so the
        # canonical header has a real <body> to attach after (not the
        # <header> fallback path) and it never collides with the
        # evidence's own header. A real <head> also means the later
        # build-provenance stamping pass (scripts/88) can inject its
        # meta tags invisibly instead of falling back to prepending them
        # into the visible body. Deliberately not using render_page()
        # here -- it would inject its own header/footer chrome on top of
        # the evidence's own already-present footer.
        sanitized_fragment = _sanitize_public_archive_text(raw_html)
        wrapped = (
            "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>KG 레이디스 오픈 {stage.upper()} 원본 기록 · NEO GOLF DATA</title>"
            "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\"></head>"
            f"<body>{sanitized_fragment}</body></html>"
        )
        public_html = inject_global_navigation(wrapped, active_section="tournaments")
        # Sponsor-slot completion happens generically later in this
        # build (the same normalize_player_sponsor_mentions() pass that
        # runs over every candidate/neo-data-home page) -- this route
        # needs no special-case handling to get it.
        stage_dest = archive_dest / stage
        stage_dest.mkdir(parents=True, exist_ok=True)
        (stage_dest / "index.html").write_text(public_html, encoding="utf-8", newline="\n")
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
    # PUBLIC UI correction (GLOBAL SPONSOR RULE, Red Team FAIL A): every
    # page in this candidate's own tree gets the same normalize pass
    # scripts/88 applies to its own output -- including archive/beta001/
    # (the sanitized public copy of the frozen KG evidence), which
    # carries bare player-name buttons with no sponsor sibling until
    # this runs. Computed once, reused for every page below.
    sponsor_by_name = _official_sponsor_by_name()
    known_names = _known_player_names()
    for page in OUTPUT.rglob("index.html"):
        relative = page.relative_to(OUTPUT)
        top = relative.parts[0] if relative.parts != (relative.name,) else None
        # archive/beta001/<stage>/ (the sanitized public copy of the KG
        # frozen evidence) is a tournaments-section page for navigation
        # purposes -- without this mapping this blanket refresh pass
        # would overwrite the "tournaments" active-nav state the
        # archive-generation block above already set, wiping the
        # aria-current="page" marker back to none-active.
        active_section = {"tournaments": "tournaments", "archive": "tournaments", "deep-dive": "deep-dive", "about": "about"}.get(top)
        if active_section is None and relative.name == "index.html" and len(relative.parts) == 1:
            active_section = "home"
        rendered = inject_global_navigation(page.read_text(encoding="utf-8"), active_section=active_section)
        rendered = normalize_player_sponsor_mentions(rendered, sponsor_by_name, known_names=known_names)
        rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
        page.write_text(rendered, encoding="utf-8", newline="\n")
    (OUTPUT / "data").mkdir(exist_ok=True)
    (OUTPUT / "data" / "home-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"WROTE candidate: {OUTPUT / 'index.html'}")
    return summary


if __name__ == "__main__":
    build()
