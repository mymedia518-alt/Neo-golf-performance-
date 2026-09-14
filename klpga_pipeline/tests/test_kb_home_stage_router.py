"""HOTFIX (fix/kb-r2-official-cut-gate-20260911) -- PRODUCTION HOME ->
KB CURRENT STAGE ROUTING FAILURE.

REAL BUG: docs/index.html (root HOME) was written exactly once, by
scripts/109_build_kb_r1_page.py's write_root_home(), as a frozen
snapshot of KB's R1 page. Neither scripts/112 (R2) nor scripts/114 (R3)
ever re-synced it -- HOME -> "current tournament" always returned R1,
and R1's OWN copy in HOME (predating the separate PRE/R1 stage-nav
fix) still showed R2 as a disabled placeholder, stranding the user.

FIX: klpga.website_v2.kb_home_stage_router.kb_current_stage() decides
KB's real current stage from real publication evidence (freeze/forecast
artifacts, never raw HTML file existence); sync_root_home_to_current_
stage() mirrors that stage's own already-published real page body into
root HOME. Both scripts/112 and scripts/114 now call the sync on every
real PUBLISH_AND_CLOSE.

Section 1 tests the REAL, currently-committed generated site under
docs/ directly (must show FINAL is the current stage now). Section 2 tests
the router's genericity/evidence-only decision with fully isolated,
synthetic tournament_context fixtures -- proving it would ALSO block
promotion to a stage whose WAIT page merely exists (never real freeze
evidence), and WOULD advance once real evidence appears, all without
ever touching KB's real repository content."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.neo_win.post_r2_forecast import run_post_r2_forecast
from klpga.neo_win.r2_freeze import build_r2_frozen_evidence, write_r2_freeze_immutable
from klpga.neo_win.r3_freeze import build_r3_frozen_evidence, write_r3_freeze_immutable
from klpga.tournament_context import TournamentContext
from klpga.website_v2.home_ownership_guard import CURRENT_TOURNAMENT_OWNER, extract_owner
from klpga.website_v2.kb_home_stage_router import (
    KbHomeStageRouterError, kb_current_stage, sync_root_home_to_current_stage,
)

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"
GAME_CODE = "2026090003"
TOURNAMENT_DIR = DOCS / "tournaments" / "2026" / GAME_CODE

PRE_PAGE = TOURNAMENT_DIR / "pre" / "index.html"
R1_PAGE = TOURNAMENT_DIR / "r1" / "index.html"
R2_PAGE = TOURNAMENT_DIR / "r2" / "index.html"
R3_WAIT_PAGE = TOURNAMENT_DIR / "r3" / "index.html"
FINAL_PAGE = TOURNAMENT_DIR / "final" / "index.html"
DOCS_INDEX = DOCS / "index.html"


# ---------------------------------------------------------------------
# Section 1: the REAL, currently-committed generated site.
# ---------------------------------------------------------------------

def test_real_kb_current_stage_resolves_to_final():
    """FINAL PAGE GO (2026-09-13): a real, fully-identity-resolved
    (zero review_required/unmatched) FINAL evidence file now exists for
    2026090003 (V3, positions 1-39) and its `final_confirmed_evidence`
    registry pointer is wired -- kb_current_stage() correctly advances
    past r3 to "final"."""
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context(GAME_CODE)
    assert kb_current_stage(context) == "final"


def test_home_home_kb_equals_final_while_final_is_current():
    """FINAL PAGE GO (2026-09-13): HOME -> KB = FINAL. Root HOME's own
    status badge and stage-nav must show FINAL -- via an explicit
    sync_root_home_to_current_stage() call, never a stale R3 snapshot."""
    html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '"status">FINAL<' in html
    assert extract_owner(html) == CURRENT_TOURNAMENT_OWNER
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/final/" aria-current="page">FINAL</a>' in html
    # never a stale disabled FINAL placeholder
    assert '<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>' not in html


def _strip_section(html: str, section_id: str) -> str:
    start = html.find(f'<section class="product-section" id="{section_id}">')
    if start == -1:
        return html
    end = html.index("</section>", start) + len("</section>")
    return html[:start] + html[end:]


def test_home_body_mirrors_the_real_published_final_page_exactly():
    """HOME's <main>...</main> body must be byte-identical to FINAL's own
    real, already-gated page body -- proves HOME is a mirror, never an
    independent rebuild that could silently diverge or fabricate --
    except for exactly two deliberate, explicitly-requested divergences:
    (1) a static <figure id="r3-forecast-visual"> visual (operator-
    supplied image + a fixed caption, no ranking/leaderboard data of its
    own) that exists on HOME only, never on FINAL; (2) the
    id="biggest-movers" section, whose markup was restructured on HOME
    only (row-per-player containers instead of a bare <ul><li> list, to
    fix a reported alignment/bullet bug -- see
    test_home_biggest_movers_rows_are_structured_and_bullet_free) while
    /final/ was explicitly left untouched, so its own copy keeps the old
    markup. Stripping exactly those two sections out of HOME's body must
    restore byte-identity with FINAL -- anything else diverging is still
    a real failure."""
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    final_html = FINAL_PAGE.read_text(encoding="utf-8")
    home_body = home_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    final_body = final_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]

    home_body = _strip_section(home_body, "r3-forecast-visual")
    home_body = _strip_section(home_body, "biggest-movers")
    final_body = _strip_section(final_body, "biggest-movers")

    assert home_body == final_body


def test_home_forecast_visual_figure_has_no_ranking_or_leaderboard_markup():
    """The one permitted HOME-only addition must be a static image +
    fixed caption only -- no data-player-id rows, no rank/score table
    markup of its own that could diverge from or duplicate FINAL's real
    leaderboard data."""
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    start = home_html.find('<section class="product-section" id="r3-forecast-visual">')
    assert start != -1, "expected HOME forecast-visual figure section not found"
    end = home_html.index("</section>", start) + len("</section>")
    figure_html = home_html[start:end]
    assert "data-player-id" not in figure_html
    assert "<table" not in figure_html
    assert 'src="/assets/kb-2026090003-r3-forecast-vs-final.png"' in figure_html
    assert "<figcaption>NEO R3 예측 → 실제 결과</figcaption>" in figure_html


def test_home_biggest_movers_rows_are_structured_and_bullet_free():
    """The reported bug: player name/sponsor and the rank-change text
    were not aligned on one row, a bare bullet rendered on its own line,
    and left/right columns didn't line up -- root-caused to a plain
    <ul><li> whose only children were block-level .player-name/
    .player-sponsor followed by a bare inline change span, giving the
    browser no single row container to align. Fix: every mover is now
    one <li class='movers-row'> containing exactly one
    'movers-row__player' block (name+sponsor) and one
    'movers-row__change' element (the arrow/rank text) -- verified here
    structurally (no bare <li> without the row class) and verified to
    still carry the exact same 5-up/5-down player<->number pairs FINAL's
    own (untouched) copy has, proving the restructure changed markup
    only, never the data."""
    import re

    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    final_html = FINAL_PAGE.read_text(encoding="utf-8")

    start = home_html.find('<section class="product-section" id="biggest-movers">')
    assert start != -1
    end = home_html.index("</section>", start) + len("</section>")
    movers_html = home_html[start:end]

    all_li = re.findall(r"<li[^>]*>", movers_html)
    assert all_li, "expected at least one mover row"
    assert all(li == "<li class='movers-row'>" for li in all_li)
    assert "<ul>" not in movers_html  # every list here must opt out of default bullets
    assert movers_html.count("movers-row__player") == len(all_li)
    assert movers_html.count("movers-row__change") == len(all_li)

    def _pairs(html: str, section_id: str) -> set[tuple[str, str]]:
        s = html.find(f'<section class="product-section" id="{section_id}">')
        e = html.index("</section>", s) + len("</section>")
        block = html[s:e]
        names = re.findall(r"<span class='player-name'>([^<]*)</span>", block)
        changes = re.findall(r"(?:NEO 예상[^<]*)", block)
        return set(zip(names, changes))

    home_pairs = _pairs(home_html, "biggest-movers")
    final_pairs = _pairs(final_html, "biggest-movers")
    assert len(home_pairs) == 10
    assert home_pairs == final_pairs


def test_home_tournaments_nav_override_points_at_final_not_r3():
    html = DOCS_INDEX.read_text(encoding="utf-8")
    assert 'href="/tournaments/2026/2026090003/final/">대회<' in html
    assert 'href="/tournaments/2026/2026090003/r3/">대회<' not in html


def test_pre_to_r2_and_r1_to_r2_reachable_on_the_real_site():
    for page in (PRE_PAGE, R1_PAGE):
        html = page.read_text(encoding="utf-8")
        assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r2/">R2</a>' in html


def test_r2_to_pre_and_r2_to_r1_reachable_on_the_real_site():
    html = R2_PAGE.read_text(encoding="utf-8")
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/pre/"' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in html


def test_final_evidence_is_real_and_home_was_explicitly_resynced_to_it():
    """FINAL PAGE GO update: the FINAL page at this path is the real,
    published FINAL result page (39/39 positions, zero review_required/
    unmatched V3 evidence) -- kb_current_stage() correctly reflects
    that. What this test guards: HOME now mirrors it, because
    sync_root_home_to_current_stage() was explicitly called for this
    build -- real evidence existing is necessary but was never, by
    itself, sufficient; the explicit sync call is what actually
    produced this HOME body."""
    assert FINAL_PAGE.is_file(), "test precondition: the FINAL page must exist for this to be a real check"
    from klpga.website_v2.kb_home_stage_router import _final_evidence_confirmed
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context(GAME_CODE)
    assert _final_evidence_confirmed(context) is True
    assert kb_current_stage(context) == "final"
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '"status">FINAL<' in home_html  # HOME was explicitly resynced to FINAL this session


def test_r3_freeze_still_real_but_no_longer_the_current_stage():
    """The R3 freeze that used to be the current-stage evidence remains
    real and untouched -- FINAL simply outranks it now that FINAL's own
    evidence is confirmed complete, exactly mirroring how r3 previously
    outranked r2 once ITS evidence appeared, with no code change to the
    r3 check itself."""
    from klpga.neo_win.r3_freeze import r3_freeze_exists
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context(GAME_CODE)
    assert r3_freeze_exists(context) is True
    assert R3_WAIT_PAGE.is_file()


def test_pre_and_r1_historical_content_untouched_by_the_sync():
    """PRE/R1's own leaderboard/prediction/sponsor content is governed
    entirely by scripts/109 and scripts/112's stage-nav-activation
    patch -- this hotfix's sync only ever reads those files, never
    writes them. Spot-check their real player counts are unchanged."""
    pre_html = PRE_PAGE.read_text(encoding="utf-8")
    r1_html = R1_PAGE.read_text(encoding="utf-8")
    assert pre_html.count("class='player-name'") == 120
    assert r1_html.count("class='player-name'") == 121


# ---------------------------------------------------------------------
# Section 2: isolated, synthetic evidence -- proves genericity.
# ---------------------------------------------------------------------

@pytest.fixture
def synth(tmp_path, monkeypatch):
    import klpga.tournament_context as tc

    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)

    context = TournamentContext(
        game_code="SYN0001", tournament_name="SYNTHETIC ROUTER TEST OPEN", season=2026,
        start_date="2026-02-01", end_date="2026-02-04", final_round_number=4,
        current_round_number=2, url_base="/tournaments/2026/SYN0001/",
        stage_state_filename="SYN0001_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )

    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs" / "tournaments" / "2026" / "SYN0001"

    def _write_stage_page(stage: str, status_label: str, marker: str) -> None:
        page = docs_dir / stage / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "<html><head><title>t</title></head><body><main>"
            f'<strong class="status">{status_label}</strong><p>{marker}</p>'
            "</main></body></html>",
            encoding="utf-8",
        )

    _write_stage_page("pre", "PRE", "pre-body-marker")
    _write_stage_page("r1", "R1", "r1-body-marker")
    (content_dir / f"{context.game_code}_R1_5PROB_FROZEN_V1.json").write_text("{}", encoding="utf-8")

    return context, repo_root, _write_stage_page


def test_synthetic_current_stage_is_pre_before_r1_frozen_evidence_exists(tmp_path, monkeypatch):
    import klpga.tournament_context as tc

    content_dir = tmp_path / "content"
    content_dir.mkdir()
    monkeypatch.setattr(tc, "CONTENT_DIR", content_dir)
    context = TournamentContext(
        game_code="SYN0002", tournament_name="SYNTHETIC PRE-ONLY OPEN", season=2026,
        start_date="2026-02-01", end_date="2026-02-04", final_round_number=4,
        current_round_number=1, url_base="/tournaments/2026/SYN0002/",
        stage_state_filename="SYN0002_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )
    assert kb_current_stage(context) == "pre"


def test_synthetic_current_stage_advances_to_r1_once_its_frozen_evidence_exists(synth):
    context, _repo_root, _write = synth
    assert kb_current_stage(context) == "r1"


def test_synthetic_sync_mirrors_the_current_stage_body_into_root_home(synth):
    context, repo_root, _write = synth
    result = sync_root_home_to_current_stage(context, repo_root=repo_root)
    assert result["current_stage"] == "r1"
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert "r1-body-marker" in home_html
    assert "pre-body-marker" not in home_html


def test_synthetic_sync_is_idempotent(synth):
    context, repo_root, _write = synth
    sync_root_home_to_current_stage(context, repo_root=repo_root)
    first = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    sync_root_home_to_current_stage(context, repo_root=repo_root)
    second = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert first == second


def test_synthetic_r3_wait_page_existing_alone_never_promotes_current_stage(synth):
    """The exact defect class this hotfix targets: a stage's WAIT page
    can exist on disk with zero real freeze evidence behind it. The
    router must never be fooled by that -- it must keep resolving to
    the last stage with REAL evidence."""
    context, repo_root, write_page = synth
    # R3's WAIT page exists on disk, but no r3 freeze evidence at all.
    write_page("r3", "R3", "r3-wait-marker (no real freeze exists)")
    assert kb_current_stage(context) == "r1"
    result = sync_root_home_to_current_stage(context, repo_root=repo_root)
    assert result["current_stage"] == "r1"
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert "r3-wait-marker" not in home_html


def test_synthetic_current_stage_advances_to_r2_once_real_r2_forecast_exists(synth):
    """Mirrors the real KB fix end-to-end on synthetic data: once R2's
    real, gated forecast artifact exists (not merely its freeze), the
    router advances -- no code change needed, exactly the "generic
    router, not a hardcode" requirement."""
    context, repo_root, write_page = synth
    pre_freeze_path = repo_root / "pre_freeze.json"
    r1_freeze_path = repo_root / "r1_freeze.json"
    repo_root.mkdir(parents=True, exist_ok=True)
    pre_freeze_path.write_text("{}", encoding="utf-8")
    r1_freeze_path.write_text("{}", encoding="utf-8")

    raw = json.dumps([{"player_id": "1", "player_name": "P", "status": "ACTIVE",
                        "r1_score_to_par": -1, "r2_score_to_par": -1}]).encode("utf-8")
    evidence = build_r2_frozen_evidence(
        context=context, official_source_identity="test", official_source_url=None,
        collection_timestamp="2026-02-02T00:00:00Z", raw_official_response=raw,
        records=[{"player_id": "1", "player_name": "P", "status": "ACTIVE",
                  "r1_score_to_par": -1, "r2_score_to_par": -1}],
        expected_field_count=1, status_counts={"ACTIVE": 1}, cut_wd_dq_evidence=[],
        pre_freeze_path=pre_freeze_path, r1_freeze_path=r1_freeze_path, repo_root=repo_root, build_id="B1",
    )
    write_r2_freeze_immutable(context, evidence)
    write_page("r2", "R2", "r2-real-marker")
    # Still r1: freeze exists but the forecast artifact does not yet.
    assert kb_current_stage(context) == "r1"

    run_post_r2_forecast(
        context, pre_performance_snapshot={"profiles": [{"player_id": "1", "player_name": "P", "windows": {}}]},
        repo_root=repo_root, build_id="B1", seed=1, n_simulations=10,
    )
    assert kb_current_stage(context) == "r2"
    result = sync_root_home_to_current_stage(context, repo_root=repo_root)
    assert result["current_stage"] == "r2"
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert "r2-real-marker" in home_html


def test_synthetic_sync_refuses_to_promote_to_a_stage_with_no_real_page_file(synth):
    """Real evidence (freeze) exists but the stage's own real page was
    never actually written to docs/ -- must HARD_STOP, never guess/
    fabricate a HOME body."""
    context, repo_root, _write = synth
    repo_root.mkdir(parents=True, exist_ok=True)
    r2_freeze_path = repo_root / "r2_freeze.json"
    r2_freeze_path.write_text("{}", encoding="utf-8")
    raw = json.dumps([]).encode("utf-8")
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="test", official_source_url=None,
        collection_timestamp="2026-02-03T00:00:00Z", raw_official_response=raw,
        records=[], expected_field_count=0, status_counts={}, wd_dq_dns_evidence=[],
        r2_freeze_path=r2_freeze_path, repo_root=repo_root, build_id="B1",
    )
    write_r3_freeze_immutable(context, evidence)
    assert kb_current_stage(context) == "r3"
    with pytest.raises(KbHomeStageRouterError):
        sync_root_home_to_current_stage(context, repo_root=repo_root)


# ---------------------------------------------------------------------
# Section 3: the "final" tier (FINAL PAGE GO, 2026-09-13) -- isolated,
# synthetic evidence proving the completeness gate is a real
# conditional (review_required/unmatched rows block it, zero of them
# unblock it), and that it outranks r3 exactly as r3 outranks r2/r1.
# ---------------------------------------------------------------------

def _write_final_evidence(context, content_dir: Path, records: list) -> Path:
    path = context.artifact_path("final_confirmed_evidence")
    assert path.parent == content_dir  # sanity: still redirected under the isolated CONTENT_DIR
    path.write_text(json.dumps({"confirmed_records": records}, ensure_ascii=False), encoding="utf-8")
    return path


def test_synthetic_final_tier_blocked_while_review_required_rows_remain(synth):
    """The exact completeness bar scripts/131 itself hard-stops on: one
    unresolved row is enough to keep the router at r3, never "final"."""
    import klpga.tournament_context as tc

    context, repo_root, write_page = synth
    _write_final_evidence(context, tc.CONTENT_DIR, [
        {"player_id": "1", "player_name": "P1", "review_required": False},
        {"player_id": None, "player_name": "P2", "review_required": True},
    ])
    assert kb_current_stage(context) == "r1"  # unchanged: r3 isn't even real evidence here yet


def test_synthetic_final_tier_confirmed_and_outranks_r3(synth):
    """Once every confirmed row is fully identity-resolved (zero
    review_required, zero player_id:null), "final" outranks r3 --
    mirrors the real KB fix end-to-end on synthetic data, no code
    change needed for genericity."""
    import klpga.tournament_context as tc

    context, repo_root, write_page = synth
    repo_root.mkdir(parents=True, exist_ok=True)
    r2_freeze_path = repo_root / "r2_freeze.json"
    r2_freeze_path.write_text("{}", encoding="utf-8")
    raw = json.dumps([]).encode("utf-8")
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="test", official_source_url=None,
        collection_timestamp="2026-02-03T00:00:00Z", raw_official_response=raw,
        records=[], expected_field_count=0, status_counts={}, wd_dq_dns_evidence=[],
        r2_freeze_path=r2_freeze_path, repo_root=repo_root, build_id="B1",
    )
    write_r3_freeze_immutable(context, evidence)
    write_page("r3", "R3", "r3-real-marker")
    assert kb_current_stage(context) == "r3"  # real r3 evidence, but no final evidence yet

    _write_final_evidence(context, tc.CONTENT_DIR, [
        {"player_id": "1", "player_name": "P1", "review_required": False},
        {"player_id": "2", "player_name": "P2", "review_required": False},
    ])
    assert kb_current_stage(context) == "final"

    write_page("final", "FINAL", "final-real-marker")
    result = sync_root_home_to_current_stage(context, repo_root=repo_root)
    assert result["current_stage"] == "final"
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert "final-real-marker" in home_html
    assert "r3-real-marker" not in home_html


def test_synthetic_final_tier_ignored_when_evidence_file_absent(synth):
    """No final_confirmed_evidence artifact at all (the common case for
    every tournament that hasn't reached FINAL yet) must never raise or
    silently promote -- it just falls through to r3/r2/r1/pre as before."""
    context, _repo_root, _write = synth
    assert kb_current_stage(context) == "r1"
