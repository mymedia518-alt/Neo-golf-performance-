from __future__ import annotations

import importlib.util
import functools
import http.server
import json
import re
import threading
import urllib.request
from pathlib import Path

import pytest

from klpga.tournament_context import candidate_dir
from klpga.website_v2.top120_validation import evaluate, validate_cohort
from klpga.website_v2.tournament_state import OK_DISPLAY_NAME, home_mode, ok_open_available_stages, ok_open_latest_available_stage

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
# SPONSOR OFFICIAL-EVIDENCE RECOVERY V2 regression fix: must resolve
# through candidate_dir() (honors tests/conftest.py's
# KLPGA_CANDIDATE_ROOT_OVERRIDE) -- see the identical fix and rationale
# in test_public_sponsor_contract.py.
OUTPUT = candidate_dir("neo-data-home-top120")


def load(name): return json.loads((CONTENT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def _pinned_ok_open_window():
    """This module's HOME-OWNERSHIP tests below are about the SHAPE of
    "/" while a tournament is genuinely active (does it become the
    stage page, never a ranking-page-head-plus-hero) -- a concern
    orthogonal to whether OK Open's own real calendar window happens to
    still be open on whatever real date this suite is run. Pinning
    OK_END_DATE far in the future keeps that shape assertion stable
    across time without re-deriving it from wall-clock "today" (see
    test_home_falls_back_to_ranking_default_once_the_active_tournament_
    has_calendar_ended below for the complementary, deliberately real-
    calendar-aware test proving the opposite branch)."""
    from klpga.website_v2 import tournament_state
    mp = pytest.MonkeyPatch()
    mp.setattr(tournament_state, "OK_END_DATE", "2099-12-31")
    yield
    mp.undo()


@pytest.fixture(scope="module")
def built(_pinned_ok_open_window):
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder", path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.build()


def test_official_cohort_is_exact_contiguous_top120_with_unique_identity():
    document = load("HOME_PLAYER_MASTER_TOP120.json"); rows = validate_cohort(document)
    assert len(rows) == 120
    assert [r["official_k_rank"] for r in rows] == list(range(1, 121))
    assert len({r["official_k_rank"] for r in rows}) == 120
    assert len({r["player_id"] for r in rows}) == 120
    assert len({r["player_name"] for r in rows}) == 120
    assert all(r["player_name"] and r["official_source"] and r["ranking_week"] and r["retrieved_at"] and r["identity_validation_state"] for r in rows)


def test_population_source_is_not_a_tournament_entry_artifact():
    document = load("HOME_PLAYER_MASTER_TOP120.json")
    assert document["population_kind"] == "official_klpga_kranking_top120"
    assert "entry" not in document["population_selection"].lower()
    assert "OK_OPEN" not in document["official_source"]


def test_player_id_only_join_missing_sg_is_never_zero_imputed():
    cohort = {"population_kind":"official_klpga_kranking_top120","records":[{"official_k_rank":i,"player_id":str(i),"player_name":f"선수{i}","official_source":"https://official","retrieved_at":"2026-09-02T00:00:00Z","identity_validation_state":"PASS_OFFICIAL_PLAYER_ID"} for i in range(1,121)]}
    rows, summary = evaluate(cohort, {"records":[]}, load("NEO_RANKING_VALIDATION_MODEL_V1.json"))
    assert summary["sg_connected"] == summary["neo_ranked"] == 0
    assert all(r["features"] is None and r["validation_score"] is None and r["neo_validation_rank"] is None for r in rows)
    assert all(r["sg_join_state"] == "DATA_INSUFFICIENT" for r in rows)


def test_model_config_forbids_win_probability_and_is_explicitly_validation_only():
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    source = (ROOT / "src" / "klpga" / "website_v2" / "top120_validation.py").read_text(encoding="utf-8")
    assert config["publication_class"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    assert "win_probability" in config["forbidden_features"]
    assert "win_probability" not in source
    assert sum(v["weight"] for v in config["features"].values()) == pytest.approx(1.0)


def test_candidate_contract_and_pending_handling(built):
    # HOME TOURNAMENT OWNERSHIP FIX: the K-Ranking x NEO Ranking table is
    # now always published at its own stable route (/ranking/) -- this
    # is where its correctness is checked, regardless of whether /
    # itself currently shows the ranking page or the active tournament
    # (see the HOME-ownership tests further below).
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert html.count("data-player-row") == 120
    # PUBLIC UI Phase 8 correction (FAIL 1): "검증 대기"/"NEO 랭킹 검증" were
    # internal validation-state phrases (visible in the ranking table's
    # missing-value cells and a legacy contract-marker comment) and have
    # been removed from all generated HTML -- asserting their absence,
    # not their presence, is now the correct contract.
    assert "검증 대기" not in html and "NEO 랭킹 검증" not in html
    assert "검증 선수" not in html and "win_probability" not in html
    assert built == {**built, "cohort_count":120}
    dataset = json.loads((OUTPUT / "data" / "neo-top120-evaluation.json").read_text(encoding="utf-8"))
    assert dataset["ranking_week"] == "2026-W36"
    assert len(dataset["players"]) == 120
    assert all(set(r) == {"player_id", "player_name", "official_k_rank", "sponsor"} for r in dataset["players"])
    assert "VALIDATION_MODEL_NOT_PRODUCTION" not in json.dumps(dataset)
    for route in ("tournaments/index.html", "tournaments/2026/kg-ladies-open/r1/index.html", "tournaments/2026/kg-ladies-open/r2/index.html",
                  "tournaments/2026/ok-savings-bank-open/pre/index.html", "tournaments/2026/ok-savings-bank-open/final/index.html",
                  "about/index.html", "deep-dive/index.html"):
        assert (OUTPUT / route).is_file()


def test_ok_stage_assets_and_deep_dive_are_complete(built):
    assert (OUTPUT / "assets" / "neo.css").is_file()
    assert (OUTPUT / "assets" / "neo-site.js").is_file()
    # navigation.css was retired -- the canonical .neo-global-header/nav
    # component is styled entirely from neo-site.css now (a second,
    # separately-linked stylesheet just for the header was a drift risk,
    # not a real requirement -- see global_navigation.py).
    assert not (OUTPUT / "assets" / "navigation.css").exists()
    ok = OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open"
    for stage in ("pre", "r1", "r2", "final"):
        html = (ok / stage / "index.html").read_text(encoding="utf-8")
        assert 'href="/assets/neo.css"' in html
    deep = (OUTPUT / "deep-dive" / "index.html").read_text(encoding="utf-8")
    assert len(deep) > 1000 and "data-chart-series" in deep


def test_every_public_route_has_global_home_navigation(built):
    routes = (
        "index.html",
        "ranking/index.html",
        "tournaments/index.html",
        "deep-dive/index.html",
        "about/index.html",
        "tournaments/2026/kg-ladies-open/r1/index.html",
        "tournaments/2026/kg-ladies-open/r2/index.html",
        "tournaments/2026/ok-savings-bank-open/pre/index.html",
        "tournaments/2026/ok-savings-bank-open/r1/index.html",
        "tournaments/2026/ok-savings-bank-open/r2/index.html",
        "tournaments/2026/ok-savings-bank-open/final/index.html",
    )
    required = (
        'href="/">홈</a>',
        'href="/tournaments/">대회</a>',
        'href="/deep-dive/">딥다이브</a>',
        'href="/about/">소개</a>',
    )
    for route in routes:
        html = (OUTPUT / route).read_text(encoding="utf-8")
        assert 'href="/">NEO GOLF DATA</a>' in html, route
        assert all(link in html for link in required), route
        assert html.count('class="neo-global-header"') == 1, route
    css = (OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert ".neo-global-header__inner{display:flex" in css
    assert ".neo-global-nav{display:flex" in css and "overflow-x:auto" in css


def test_home_is_korean_first_and_table_alignment_is_explicit(built):
    # See test_candidate_contract_and_pending_handling: the ranking
    # table's permanent home is /ranking/, not necessarily /.
    # PRODUCTION HOME REGRESSION ROOT-CAUSE + REPAIR (20260911): the
    # "KLPGA 공식 K-Ranking 1~120위" kicker was part of the intro/
    # coverage-stat block that used to sit ahead of the player table on
    # both / and /ranking/ (they share render_clean()) -- removed
    # outright, not relocated, so this page is player-first too.
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert html.count("data-player-row") == 120
    # PUBLIC UI Phase 8 correction (FAIL 1): see
    # test_candidate_contract_and_pending_handling -- these are now
    # forbidden internal validation-state phrases, not required content.
    assert "NEO 랭킹 검증" not in html
    assert "검증 대기" not in html
    assert all(term in html for term in ("K-Ranking", "NEO Ranking", "최근 경기력"))
    assert "DATA INSUFFICIENT" not in html
    assert all(term not in html for term in (">HOME<", ">TOURNAMENTS<", ">DEEP DIVE<", ">ABOUT<", "production 아님"))
    css = (OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert ".home-table{width:100%;min-width:960px;table-layout:fixed}" in css
    # OWNER VISUAL REVIEW FAIL, item 4: player leads the visual
    # hierarchy and is column 1 (see
    # test_home_table_never_shows_a_blocked_neo_ranking_column below
    # for the content-level contract this CSS position serves).
    assert ".home-table th:nth-child(1),.home-table td:nth-child(1){width:12rem;text-align:left" in css
    assert "font-variant-numeric:tabular-nums" in css


def test_home_table_never_shows_a_blocked_neo_ranking_column(built):
    """PRODUCT PRESENTATION RECOVERY (HOME METRIC AVAILABILITY AUDIT):
    the composite NEO Ranking is a validation-only model score
    (publication_class VALIDATION_MODEL_NOT_PRODUCTION) and must never
    become a public table column -- not even one filled entirely with
    dashes. Both the header cell and the never-populated data-neo-rank
    sort attribute this used to carry are gone outright."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "<th>NEO Ranking</th>" not in html
    assert "data-neo-rank" not in html
    assert '<option value="neo-rank">' not in html


def test_home_table_visual_hierarchy_matches_owner_priority(built):
    """OWNER VISUAL REVIEW FAIL, item 4: 선수(Player) leads the column
    order, then K-Ranking, then the two primary recent-form columns in
    priority order (최근 10R SG before 최근 5R SG -- NOT the reverse,
    and never phrased as "10개 대회"/10 tournaments, which is a
    distinct, not-yet-built future metric -- see item 6/COVERAGE
    AUDIT). 장기 SG/변동성 stay real data but carry the metric-secondary
    class (de-emphasized in CSS, never dropped, never a wider table)."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    header = html[html.index("<thead>"):html.index("</thead>")]
    assert header.index("<th>선수</th>") < header.index("<th>K-Ranking</th>") < header.index("<th>최근 10R SG</th>") < header.index("<th>최근 5R SG</th>")
    assert '<th class="metric-secondary">장기 SG</th>' in header
    assert '<th class="metric-secondary">변동성</th>' in header
    assert "최근 10개 대회" not in html, "10R (rounds) must never be phrased as 10 tournaments"
    row = html[html.index("data-player-row"):]
    row = row[:row.index("</tr>")]
    # MOBILE COLOR/READABILITY PASS (20260910): the first metric <td>
    # (K-Ranking) now carries a k-rank-cell class + data-label attribute
    # for the mobile color system/card layout -- '<td>' bare is no
    # longer literally present, but the underlying invariant (선수 th
    # still precedes every metric td) is unchanged, so match any '<td'
    # tag, not only a bare unattributed one.
    assert row.index('scope="row"') < row.index('<td')
    # 장기 SG/변동성 now also carry a sign-color class alongside
    # metric-secondary (positive/negative SG average) -- the class
    # list must still CONTAIN metric-secondary, even though it is no
    # longer the cell's only class.
    assert re.search(r'<td class="[^"]*\bmetric-secondary\b[^"]*"', row)


def test_home_table_renders_real_recent_sg_values_not_blanket_dashes(built):
    """PRODUCT PRESENTATION RECOVERY (HOME METRIC AVAILABILITY AUDIT,
    Class A): recent_5_sg/recent_10_sg/long_term_sg/volatility are
    plain averages/stdevs off the corrected SG warehouse
    (home_ranking.build_features's own "PASS_CORRECTED_SG_WAREHOUSE"
    validation_state) -- a different thing from the blocked composite
    NEO Ranking, and KB PRE already publishes this exact class of
    metric under the same non-official "최근 5R SG" label. They must
    render as real numbers for players with a connected SG feature set,
    not the blanket "—" the previous renderer hardcoded regardless of
    what evaluate() actually computed."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    dataset = json.loads((CONTENT / "historical_sg_warehouse_corrected.json").read_text(encoding="utf-8"))
    cohort = json.loads((CONTENT / "HOME_PLAYER_MASTER_TOP120.json").read_text(encoding="utf-8"))
    config = json.loads((CONTENT / "NEO_RANKING_VALIDATION_MODEL_V1.json").read_text(encoding="utf-8"))
    rows, summary = evaluate(cohort, dataset, config)
    connected = [r for r in rows if r["features"] is not None]
    assert connected, "fixture must have at least one SG-connected player to make this test meaningful"
    assert summary["sg_connected"] > 0
    sample = connected[0]
    from html import escape as _esc
    expected = f'{sample["features"]["recent_5_sg"]:.2f}'
    assert expected in html, "a real recent_5_sg value for an SG-connected player must appear in the rendered table"
    assert f'{sample["features"]["long_term_sg"]:.2f}' in html
    assert _esc(sample["player_name"]) in html
    # the summary strip's two former dash placeholders ("NEO Ranking" /
    # "NEO 지표" stats) are replaced by real connected-population counts
    # -- recent10_ready, matching the owner's 10R-before-5R priority.
    assert str(summary["sg_connected"]) in html
    assert str(summary["recent10_ready"]) in html


def test_http_routes_are_real_index_pages_not_directory_listings(built):
    routes = {
        "/": "<title>",
        "/ranking/": "<title>",
        "/tournaments/": "대회 분석 허브",
        "/deep-dive/": "<title>",
        "/about/": "<title>",
        "/tournaments/2026/kg-ladies-open/r1/": "<title>",
        "/tournaments/2026/kg-ladies-open/r2/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/pre/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/r1/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/r2/": "<title>",
        "/tournaments/2026/ok-savings-bank-open/final/": "<title>",
    }
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUTPUT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for route, marker in routes.items():
            index = OUTPUT / route.strip("/") / "index.html" if route != "/" else OUTPUT / "index.html"
            assert index.is_file(), route
            response = urllib.request.urlopen(base + route, timeout=10)
            body = response.read().decode("utf-8")
            assert response.status == 200
            assert "Directory listing for" not in body
            assert marker in body
    finally:
        server.shutdown()
        thread.join(timeout=10)


def test_tournament_state_never_infers_a_stage_from_todays_date(_pinned_ok_open_window):
    # The single source of truth: extend by hand (script 96, after a
    # real validated collection), never derive from a calendar. PRE
    # always qualifies; R1 now also qualifies because a real R1 cycle
    # has actually run and validated it (see OK_OPEN_STAGE_STATE.json)
    # -- ok_open_latest_available_stage() correctly reports the most
    # advanced REAL stage, r1, not a hardcoded pre.
    available = ok_open_available_stages()
    assert available["pre"] == "/tournaments/2026/ok-savings-bank-open/pre/"
    assert available.get("r1") == "/tournaments/2026/ok-savings-bank-open/r1/"
    stage, url = ok_open_latest_available_stage()
    stage_order = ("pre", "r1", "r2", "r3", "final")
    validated = [key for key in stage_order if key in available]
    assert validated
    assert stage == validated[-1]
    assert url == available[stage]
    assert home_mode() == "TOURNAMENT_ACTIVE"


# ======================================================================
# HOME TOURNAMENT OWNERSHIP FIX
# ======================================================================
# The prior "tournament hero glued above the ranking table" approach was
# explicitly rejected: during TOURNAMENT_ACTIVE, / must literally BE the
# current validated tournament stage's own canonical page (the identical
# content as its dedicated /tournaments/.../<stage>/ URL) -- never a
# banner sitting on top of the ranking-first page-head. These tests
# distinguish that CORRECT shape from the WRONG one directly, rather
# than merely checking that some tournament-related string exists
# somewhere on the page (the weak assertion that produced a false PASS
# for the rejected hero approach).

# PRODUCTION HOME REGRESSION ROOT-CAUSE + REPAIR (20260911): the
# kicker/H1 pair these markers used to check for ("KLPGA 공식 K-Ranking
# 1~120위" / class="ranking-compare-heading") was the intro/coverage
# block removed ahead of the player table -- the page's one real H1 is
# now "TOP120 선수표" on the player-list section itself
# (class="product-section home-primary"), so these markers check that
# instead.
_RANKING_PAGE_HEAD_MARKERS = ("TOP120 선수표", "home-primary")


def test_home_is_always_player_ranking_first_even_while_a_tournament_is_active(built):
    # PRODUCT RECOVERY V1 (HOME/PRE ROLE AUDIT), further tightened by
    # PRODUCTION HOME REGRESSION ROOT-CAUSE + REPAIR: HOME must NEVER
    # compose a tournament stage's own page body, active tournament or
    # not, and must NEVER lead with tournament content either -- it is
    # always the same player-first ranking content as /ranking/, with
    # no tournament cards attached at all (see
    # test_home_player_first_regression.py for that dedicated coverage).
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker in html, f"player-first heading must be /'s primary body: {marker!r} missing"
    assert "data-player-row" in html, "the K-Ranking table must be /'s primary body"


def test_home_does_not_contain_pre_stage_body_composition(built):
    """HOME/PRE ROLE AUDIT gate: HOME containing PRE page body/template
    composition => FAIL. The current tournament's own PRE page markup
    (its player/sponsor row template, its .panel/.hero PRE-only shell)
    must never appear inside /."""
    home_html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "class='player-name'" not in home_html and "class='player'" not in home_html
    assert "class='sponsor'" not in home_html
    assert "PRE 참가 선수" not in home_html
    assert "id=\"pre\"" not in home_html and "id='pre'" not in home_html


# test_home_tournament_cards_strip_still_names_the_current_tournament
# (formerly here) is SUPERSEDED by PRODUCTION HOME REGRESSION ROOT-
# CAUSE + REPAIR (20260911): the tournament-cards strip it required is
# exactly what put tournament content ahead of the player table on
# every real HOME load -- it is now deliberately removed, not relocated.
# Tournament access is the "대회" nav item's job. See
# test_home_player_first_regression.py::test_home_has_no_tournament_card_block
# for the inverse invariant this now locks in.


def test_home_has_exactly_one_h1(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert html.count("<h1") == 1, "HOME must carry exactly one H1"


def test_protected_top120_dataset_is_exactly_120_players_unchanged_by_this_fix(built):
    # TEST 6.
    dataset = json.loads((OUTPUT / "data" / "neo-top120-evaluation.json").read_text(encoding="utf-8"))
    records = dataset["players"]
    assert len(records) == 120
    assert sorted(r["official_k_rank"] for r in records) == list(range(1, 121))
    assert len({r["player_id"] for r in records}) == 120


def test_dedicated_r1_url_still_works_independently_of_home(built):
    # TEST 7.
    r1_page = OUTPUT / "tournaments" / "2026" / "ok-savings-bank-open" / "r1" / "index.html"
    assert r1_page.is_file()
    html = r1_page.read_text(encoding="utf-8")
    assert html.count("<h1") >= 1
    assert 'href="/">홈</a>' in html  # still carries the full global nav


def test_global_home_nav_points_to_root_and_root_resolves_to_the_ranking_experience(built):
    # PRODUCT RECOVERY V1, updated by PRODUCTION HOME REGRESSION
    # ROOT-CAUSE + REPAIR: root always resolves to the player-first
    # ranking experience, with no tournament content attached at all
    # (the "compact cards strip" this comment used to describe is
    # exactly the regression that fix removed).
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert 'href="/">홈</a>' in html or 'href="/" class="is-active"' in html
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker in html
    assert "R2 &middot; LIVE" not in html


def test_stale_home_mode_cannot_override_official_current_tournament(tmp_path, monkeypatch):
    """PRODUCT RECOVERY V1: HOME is always the ranking experience now,
    so this legacy stage selector has nothing left to override there.
    PRODUCTION HOME REGRESSION ROOT-CAUSE + REPAIR: HOME no longer
    carries a tournament-cards strip at all, so what this test now
    locks in is that a stale/mismatched home_mode() cannot make HOME's
    structure (still player-first, still 120 rows, no LIVE-stage
    leakage) waver either."""
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_stale_mode", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = tmp_path / "candidate"
    monkeypatch.setattr(module, "home_mode", lambda: "RANKING_DEFAULT")
    module.build()
    html = (module.OUTPUT / "index.html").read_text(encoding="utf-8")
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker in html
    assert "R2 &middot; LIVE" not in html
    assert html.count("data-player-row") == 120
    assert (module.OUTPUT / "ranking/index.html").read_text(encoding="utf-8").count("data-player-row") == 120


def test_stale_active_ok_context_cannot_override_calendar_chronology(tmp_path, monkeypatch):
    """Changing the legacy OK end-date signal cannot change HOME
    identity or leak LIVE-stage content into it."""
    from klpga.website_v2 import tournament_state
    monkeypatch.setattr(tournament_state, "OK_END_DATE", "2020-01-01")
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_calendar_current", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = tmp_path / "candidate"
    module.build()
    html = (module.OUTPUT / "index.html").read_text(encoding="utf-8")
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker in html
    for marker in ("R2 &middot; LIVE", "2라운드 공식 리더보드", "1라운드 공식 리더보드"):
        assert marker not in html


# test_kg_ladies_open_is_never_shown_as_the_current_active_tournament
# (formerly here) is SUPERSEDED by PRODUCTION HOME REGRESSION ROOT-
# CAUSE + REPAIR (20260911): it asserted structure (a "current"
# tournament-card article) inside HOME's own HTML, which no longer
# exists -- HOME carries no tournament cards of any kind now. The real
# underlying invariant this test protected (KG Ladies Open, a
# completed tournament, must never be resolved as the CURRENT active
# one) lives in build_home_tournament_chronology()'s own date-driven
# resolver logic, not in HOME's rendering, and is independently covered
# by test_phase8_public_ui.py's test_chronology_* boundary tests and
# test_real_official_schedule_drives_home_never_pipeline_stage_state.
    for route in ("tournaments/2026/kg-ladies-open/pre/index.html", "tournaments/2026/kg-ladies-open/r1/index.html",
                  "tournaments/2026/kg-ladies-open/r2/index.html", "tournaments/2026/kg-ladies-open/r3/index.html",
                  "tournaments/2026/kg-ladies-open/final/index.html"):
        assert (OUTPUT / route).is_file(), route


def test_ranking_h1_fits_one_line_and_never_font_shrunk_below_the_page_default(built):
    css = (OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert ".home-head .ranking-compare-heading{max-width:48rem" in css
    # the fix is the width constraint, not a smaller font stacked on top
    # of the existing clamp() -- .home-head h1's own font-size rule
    # (shared regardless of h1/h2 tag) is untouched by this fix.
    assert ".home-head h1{margin:.3rem 0 .55rem;font-size:clamp(1.7rem,3.5vw,2.35rem)}" in css
