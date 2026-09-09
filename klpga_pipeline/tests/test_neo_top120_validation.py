from __future__ import annotations

import importlib.util
import functools
import http.server
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from klpga.website_v2.top120_validation import evaluate, validate_cohort
from klpga.website_v2.tournament_state import OK_DISPLAY_NAME, home_mode, ok_open_available_stages, ok_open_latest_available_stage

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"


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
    assert ".home-table th:nth-child(3),.home-table td:nth-child(3){width:12rem;text-align:left" in css
    assert "font-variant-numeric:tabular-nums" in css


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

_RANKING_PAGE_HEAD_MARKERS = ("KLPGA 공식 K-Ranking 1~120위", "공식 순위와 NEO 검증 순위 비교", "ranking-compare-heading")


def test_home_does_not_contain_the_ranking_page_head_as_primary_body_while_a_tournament_is_active(built):
    # TEST 1 (see NEO GOLF DATA -- HOME TOURNAMENT OWNERSHIP FIX spec).
    assert home_mode() == "TOURNAMENT_ACTIVE"
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker not in html, f"ranking page-head leaked into / while TOURNAMENT_ACTIVE: {marker!r}"
    assert "data-player-row" not in html, "the 120-row ranking table must not be /'s primary body while a tournament is active"
    assert "tournament-day-hero" not in html, "no hero banner either -- / must BE the stage page, not a teaser above one"


def test_home_contains_the_current_validated_tournament_stage_content_while_active(built):
    """Official chronology selects KB PRE even while stale OK R2 exists."""
    stage_html = (OUTPUT / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")
    home_html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "KB금융 골든라이프 챔피언십" in home_html
    assert "R2 &middot; LIVE" not in home_html
    import re as _re
    stage_main = _re.search(r"<main>.*?</main>", stage_html, _re.S)
    assert stage_main is not None
    fingerprints = [value for value in _re.findall(r">([^<]{6,40})<", stage_main.group(0)) if value.strip()][:5]
    assert fingerprints
    assert all(value in home_html for value in fingerprints)


def test_current_validated_stage_produces_matching_tournament_experience_on_home(built):
    """HOME mirrors the current tournament's latest validated PRE page."""
    home_html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    stage_html = (OUTPUT / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")
    import re as _re
    def body_after_header(value):
        return _re.sub(r"^.*?</header>", "", value, count=1, flags=_re.S)
    home_body = body_after_header(home_html)
    stage_body = body_after_header(stage_html)
    home_body = _re.sub(r"<p\s+class=[\"']home-ranking-access[\"'][^>]*>.*?</p>", "", home_body, count=1, flags=_re.S)
    home_body = _re.sub(r'<section class="t-tournament-cards".*?</section>', "", home_body, count=1, flags=_re.S)
    assert home_body == stage_body


def test_home_has_exactly_one_h1_while_a_tournament_is_active(built):
    # TEST 5.
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


def test_global_home_nav_points_to_root_and_root_resolves_to_the_tournament_experience(built):
    # TEST 8.
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert 'href="/">홈</a>' in html or 'href="/" class="is-active"' in html
    for marker in _RANKING_PAGE_HEAD_MARKERS:
        assert marker not in html
    assert "KB금융 골든라이프 챔피언십" in html
    assert "R2 &middot; LIVE" not in html


def test_stale_home_mode_cannot_override_official_current_tournament(tmp_path, monkeypatch):
    """The legacy OK stage selector cannot replace the calendar-selected KB PRE."""
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
    assert html.count("data-player-row") == 0
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
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    # PUBLIC UI Phase 8: KG Ladies Open is now legitimately named in
    # HOME's own "지난 대회" (last completed tournament) card -- that is
    # real, correct, registry-driven content, not a stale-active-
    # tournament bug. The invariant this test actually guards is that
    # KG is never shown INSIDE the "current"-kind card; it must still
    # appear inside the "last"-kind card.
    import re as _re
    current_card = _re.search(r'data-tournament-card="current"[^>]*>.*?</article>', html, flags=_re.S)
    assert current_card, "HOME must carry a 'current' tournament card"
    assert "KG" not in current_card.group(0) and "레이디스" not in current_card.group(0), (
        "KG Ladies Open must never appear inside the CURRENT tournament card"
    )
    # PUBLIC UI Phase 8 correction (FAIL 3): tournament_chronology is
    # now purely date-driven (see test_phase8_public_ui.py's
    # test_chronology_* boundary tests) -- whichever registered
    # tournament ended most recently as of "today" wins the "last"
    # slot. That is sometimes KG, sometimes another completed
    # tournament (e.g. once OK Open's own scheduled window has also
    # passed) -- never hardcode which one; the only real invariant this
    # test guards is a non-empty "last" card.
    last_card = _re.search(r'data-tournament-card="last"[^>]*>.*?</article>', html, flags=_re.S)
    assert last_card and 'data-game-code' in last_card.group(0), (
        "HOME must carry a real, non-empty 'last' tournament card"
    )
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
