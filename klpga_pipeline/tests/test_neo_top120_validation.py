from __future__ import annotations

import importlib.util
import functools
import http.server
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from klpga.tournament_context import candidate_dir
from klpga.website_v2.top120_validation import evaluate, validate_cohort
from klpga.website_v2.tournament_state import OK_DISPLAY_NAME, home_mode, ok_open_available_stages, ok_open_latest_available_stage

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
# OWNER TEST-ISOLATION FIX: this used to be a hardcoded
# `ROOT / "candidate" / "neo-data-home-top120"` -- the real, tracked
# directory -- while the `built` fixture below runs the real script's
# build(), whose own OUTPUT is resolved through candidate_dir() and
# therefore writes to the pytest-isolated KLPGA_CANDIDATE_ROOT_OVERRIDE
# temp directory (see tests/conftest.py). The two never pointed at the
# same place: every test below was silently reading whatever stale
# content happened to already be sitting in the real tracked directory
# from an earlier manual (non-pytest) build, never what `built` had
# just produced. Resolving OUTPUT the exact same way script 88 does
# fixes that for good, not just for this task's own new assertions.
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
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert html.count("data-player-row") == 120
    assert "KLPGA 공식 K-Ranking 1~120위" in html
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
    priority order (최근 10개 대회 SG before 최근 5개 대회 SG -- NOT the
    reverse). 장기 SG/변동성 stay real data but carry the
    metric-secondary class (de-emphasized in CSS, never dropped, never
    a wider table)."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    header = html[html.index("<thead>"):html.index("</thead>")]
    assert header.index("<th>선수</th>") < header.index("<th>K-Ranking</th>") < header.index("<th>최근 10개 대회 SG</th>") < header.index("<th>최근 5개 대회 SG</th>")
    assert '<th class="metric-secondary">장기 SG</th>' in header
    assert '<th class="metric-secondary">변동성</th>' in header
    row = html[html.index("data-player-row"):]
    row = row[:row.index("</tr>")]
    assert row.index('scope="row"') < row.index('<td>')
    assert '<td class="metric-secondary">' in row


def test_home_never_uses_the_false_rounds_wording_for_sg(built):
    """NEO PRODUCT CONTRACT RECOVERY item 2 (SG LABEL SEMANTICS): SG
    LABEL DECISION forensic audit conclusively proved recent_5_sg/
    recent_10_sg (home_ranking.build_features) are the mean of the
    last 5/10 TOURNAMENT-level observations (one retained snapshot per
    (player_id, game_code)), never actual rounds -- "최근 5R SG"/"최근
    10R SG"/"...라운드..." are therefore false public labels and must
    never reappear anywhere in the built HOME page (this exact
    assertion is what makes the old wording impossible to silently
    reintroduce)."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "5R SG" not in html
    assert "10R SG" not in html
    assert "라운드" not in html, "SG copy must never claim these are rounds"
    assert "최근 5개 대회 SG" in html
    assert "최근 10개 대회 SG" in html


def test_home_has_no_current_score_column_or_sort(built):
    """NEO PRODUCT CONTRACT RECOVERY item 1 (HOME CONTRACT): HOME is
    the persistent player-performance/ranking product, not a live
    tournament board -- 현재 스코어 (current score) belongs only to the
    tournament's own R1/R2/R3/FINAL round pages. Column, sort option,
    and the JS sort branch that drove it must all be gone; a player row
    must never carry a data-current-* sort attribute either."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "현재 스코어" not in html
    assert '<option value="current-score">' not in html
    assert "data-current-score" not in html
    assert "data-current-hole" not in html
    assert "data-current-status" not in html
    js = (OUTPUT / "assets" / "top120.js").read_text(encoding="utf-8")
    assert "current-score" not in js
    assert "currentScoreHasData" not in js


def test_home_title_never_claims_a_neo_ranking_that_is_not_published(built):
    """NEO PRODUCT CONTRACT RECOVERY item 3 (NEO RANKING AUDIT): the
    NEO Ranking V1 validation pipeline is explicitly self-labeled
    weight_status=HEURISTIC_FOR_EVALUATION_NOT_FITTED_OR_APPROVED and
    publication_class=VALIDATION_MODEL_NOT_PRODUCTION -- not safe to
    publish. The page must not claim a "NEO Ranking" the visible table
    does not actually provide (the prior H1 "K-Ranking과 NEO Ranking"
    was a product contradiction the Project Owner explicitly flagged);
    the ranking-help panel's own "검증 중 · 공개 전" disclosure for NEO
    Ranking is honest and stays."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "<h1" in html
    h1 = html[html.index("<h1"):html.index("</h1>") + len("</h1>")]
    assert "NEO Ranking" not in h1
    assert "<th>NEO Ranking</th>" not in html


def test_home_table_renders_real_recent_sg_values_not_blanket_dashes(built):
    """PRODUCT PRESENTATION RECOVERY (HOME METRIC AVAILABILITY AUDIT,
    Class A): recent_5_sg/recent_10_sg/long_term_sg/volatility are
    plain averages/stdevs off the corrected SG warehouse
    (home_ranking.build_features's own "PASS_CORRECTED_SG_WAREHOUSE"
    validation_state) -- a different thing from the blocked composite
    NEO Ranking, and KB PRE already publishes this exact class of
    metric under the same non-official "최근 5개 대회 SG" label. They must
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
# KB TOURNAMENT-ONLY PUBLIC HOME -- PRIORITY MODE
# ======================================================================
# Project Owner redesign decision: explicitly SUPERSEDES the
# "PRODUCT RECOVERY V1 (HOME/PRE ROLE AUDIT)" rule that used to govern
# this section (HOME must never compose a tournament stage's own page
# body; / always shows the ranking-page-head with a compact
# three-tournament-cards strip attached). That prior rule is retired
# here, deliberately, along with the tests that enforced it -- while a
# current tournament has a validated, publication-gate-approved stage
# page, / must literally BE that page (the identical content as its own
# dedicated /tournaments/.../<stage>/ URL), never the ranking table and
# never a banner glued on top of it. The player-centric K-Ranking x NEO
# 경기력 table keeps its own permanent, stable home at /ranking/,
# completely unaffected by this change (see
# test_home_is_korean_first_and_table_alignment_is_explicit and its
# neighbors above, which already read from /ranking/, not /).

_TOURNAMENT_HERO_MARKERS = ('class="hero"', "leaderboard-panel")

# PRODUCT RECOVERY V1: corrected to strings render_clean() actually
# emits today -- the previous second marker ("공식 순위와 NEO 검증 순위
# 비교") never matched any real output (confirmed via direct search),
# so the old TOURNAMENT_ACTIVE test asserting its ABSENCE was a
# vacuous pass, never a real check.
_RANKING_PAGE_HEAD_MARKERS = ("KLPGA 공식 K-Ranking 1~120위", "ranking-compare-heading")


def test_home_becomes_the_current_tournament_stage_page_while_one_is_active(built):
    """KB TOURNAMENT-ONLY PUBLIC HOME: while a current tournament has a
    validated, publication-gate-approved stage page, / must BE that
    page's own body -- the ranking-page-head content's permanent home
    is /ranking/ (see test_home_is_korean_first_and_table_alignment_is_
    explicit above, already reading from there), never /."""
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    for marker in _TOURNAMENT_HERO_MARKERS:
        assert marker in html, f"tournament stage hero must be /'s primary body: {marker!r} missing"
    assert "PRE 참가 선수" in html
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker not in html, f"ranking page-head must not leak onto /: {marker!r} present"
    assert "data-player-row" not in html, "/ must not carry the K-Ranking table's own row markup"


def test_home_sponsor_slot_is_present_in_the_tournament_stage_body_now_shown_on_home(built):
    """The current tournament's own player/sponsor identity cell (name
    slot + sponsor slot, always both present -- see
    player_identity.render_player_identity) is now HOME's own primary
    content, since / literally is that tournament's own page."""
    home_html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "class='player-name'" in home_html
    assert "class='player-sponsor'" in home_html


def test_home_no_longer_carries_the_retired_tournament_cards_strip(built):
    """The old 지난/이번/다음 대회 three-card strip is dropped from HOME
    entirely (Project Owner: "previous/current/next tournament three
    large horizontal panels" consuming HOME's vertical space was itself
    the problem to solve) -- HOME's tournament identity is now carried
    structurally, by literally being that tournament's own page, not by
    a separate labelled card. render_tournament_cards_html itself is
    untouched (see tests/test_phase8_public_ui.py) -- just no longer
    spliced into HOME's own output."""
    home_html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "t-tournament-cards" not in home_html
    assert "data-tournament-card" not in home_html
    assert "KB금융 골든라이프 챔피언십" in home_html


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


def test_global_home_nav_points_to_root_and_ranking_experience_stays_at_its_own_url(built):
    # KB TOURNAMENT-ONLY PUBLIC HOME: root now resolves to the current
    # tournament's own stage experience (see
    # test_home_becomes_the_current_tournament_stage_page_while_one_is_active
    # above) -- the ranking-page-head content keeps its own permanent
    # home at /ranking/, completely independent of whatever / shows.
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert 'href="/">홈</a>' in html or 'href="/" class="is-active"' in html
    ranking_html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker in ranking_html
    assert "R2 &middot; LIVE" not in html


def test_stale_home_mode_cannot_override_official_current_tournament(tmp_path, monkeypatch):
    """HOME is now the current tournament's own stage page -- what a
    stale legacy stage selector must still never be able to do is make
    HOME disagree with the real, calendar-selected current tournament
    (KB), regardless of what the stale selector itself claims, and
    /ranking/ must independently keep its full 120-player population no
    matter what HOME is currently showing (home_mode() is not actually
    wired into build() at all -- this monkeypatch documents that it
    cannot matter, whichever way build() is later refactored)."""
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_stale_mode", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = tmp_path / "candidate"
    monkeypatch.setattr(module, "home_mode", lambda: "RANKING_DEFAULT")
    module.build()
    html = (module.OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "KB금융 골든라이프 챔피언십" in html
    assert "R2 &middot; LIVE" not in html
    assert (module.OUTPUT / "ranking/index.html").read_text(encoding="utf-8").count("data-player-row") == 120


def test_stale_active_ok_context_cannot_override_calendar_chronology(tmp_path, monkeypatch):
    """Changing the legacy OK end-date signal cannot change HOME identity."""
    from klpga.website_v2 import tournament_state
    monkeypatch.setattr(tournament_state, "OK_END_DATE", "2020-01-01")
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_calendar_current", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = tmp_path / "candidate"
    module.build()
    html = (module.OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "KB금융 골든라이프 챔피언십" in html
    for marker in ("R2 &middot; LIVE", "2라운드 공식 리더보드", "1라운드 공식 리더보드"):
        assert marker not in html


def test_kg_ladies_open_is_never_shown_as_the_current_active_tournament(built):
    """KB TOURNAMENT-ONLY PUBLIC HOME: the retired tournament-cards strip
    (which used to carry a labelled "current"-kind card) is gone from /
    entirely -- see test_home_no_longer_carries_the_retired_tournament_
    cards_strip above. The real invariant this test guards -- KG Ladies
    Open (a completed, historical tournament) must never be presented as
    if it were the current tournament -- now applies to HOME's own hero
    identity directly, since / literally IS whichever tournament is
    current."""
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "<h1" in html
    h1 = html[html.index("<h1"):html.index("</h1>") + len("</h1>")]
    assert "KG" not in h1 and "레이디스" not in h1, "KG Ladies Open must never be HOME's own current-tournament identity"
    assert "KB금융 골든라이프 챔피언십" in h1
    # KG's own archive is preserved untouched elsewhere in the tree
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


# ======================================================================
# KB TOURNAMENT-ONLY PUBLIC HOME -- PRIORITY MODE, remaining coverage
# ======================================================================

def test_primary_public_nav_is_minimized_to_home_and_current_tournament(built):
    """Project Owner decision: 랭킹/딥다이브/NEO LAB stay fully built and
    reachable by direct URL (never deleted -- see the routes asserted
    below), but are hidden from the persistent header nav via a CSS-only
    rule (see global_navigation.py's _SECONDARY_NAV_KEYS / neo-site.css's
    .nav-secondary) so the public nav reads as just 홈 / 이번 대회."""
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert 'href="/ranking/" class="nav-secondary">랭킹</a>' in html
    assert 'href="/deep-dive/" class="nav-secondary">딥다이브</a>' in html
    assert 'href="/neo-lab/" class="nav-secondary">NEO LAB</a>' in html
    assert ">이번 대회</a>" in html
    css = (OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert ".neo-global-nav a.nav-secondary{display:none}" in css
    # never deleted: still real, buildable, reachable routes.
    for route in ("ranking/index.html", "deep-dive/index.html", "neo-lab/index.html"):
        assert (OUTPUT / route).is_file(), route


def test_ranking_page_still_marks_its_own_nav_item_active_when_visited_directly(built):
    """A visitor landing on /ranking/ directly still sees "랭킹"
    highlighted as the current page in its own header -- only OTHER
    pages hide the link, per the nav-secondary CSS rule (see
    _SECONDARY_NAV_KEYS's docstring in global_navigation.py)."""
    ranking_html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert 'href="/ranking/" class="is-active" aria-current="page">랭킹</a>' in ranking_html
    nav_html = ranking_html[ranking_html.index('<nav class="neo-global-nav"'):ranking_html.index("</nav>")]
    assert "nav-secondary" not in nav_html.split(">랭킹<")[0].split("<a")[-1]


def test_home_hero_shows_verified_venue_and_field_size_never_fabricated_holes(built):
    """DATA FILL: venue (블랙스톤 이천) is populated from already-verified
    official schedule evidence (see TOURNAMENT_SITE_REGISTRY.json's
    2026090003 entry, _venue_comment), and field size (120명) from the
    same validated entry_snapshot count every other public figure on
    this page already uses. Hole count / par are deliberately NOT
    asserted here -- no verified source exists for KB yet, so the page
    must never show a fabricated "72홀"/"파72", matching the Owner's own
    "do not guess" rule."""
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "블랙스톤 이천" in html
    assert "120명" in html
    assert "72홀" not in html and "파 72" not in html and "Par 72" not in html


def test_pre_leaderboard_sg_column_is_honestly_labelled_a_rank_not_a_value(built):
    """LIVE FAIL #2 finding (discovered during this redesign): the PRE
    leaderboard's SG column is fed by sg_total_rank (scripts/82's own
    schema: an ordinal RANK derived from the mean of the latest five
    pre-cutoff tournament_cumulative SG Total observations), not the raw
    SG value itself -- an integer like 80 or 114 rendered under a label
    that reads as an SG figure is itself misleading, even though the
    words "5R"/"10R"/rounds were already fixed. Corrected to "...SG 순위"
    (rank), matching what is actually shown; the underlying sg_total_
    rank computation is completely untouched (no SG/model calculation
    was changed -- see scripts/82_build_corrected_sg_total_rank.py)."""
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "최근 5개 대회 SG 순위" in html
    assert ">최근 5개 대회 SG<" not in html
    assert "data-label='최근 5개 대회 SG'>" not in html
