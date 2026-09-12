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
docs/ directly (must show R2 is the current stage now). Section 2 tests
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
DOCS_INDEX = DOCS / "index.html"


# ---------------------------------------------------------------------
# Section 1: the REAL, currently-committed generated site.
# ---------------------------------------------------------------------

def test_real_kb_current_stage_resolves_to_r3():
    """ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-
    v1-20260912): a real, hash-verified R3 freeze now exists for
    2026090003 (official evidence proved this tournament's true
    final_round_number is 4 and R3 has genuinely concluded) --
    kb_current_stage() correctly advances past r2."""
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context(GAME_CODE)
    assert kb_current_stage(context) == "r3"


def test_home_home_kb_equals_r3_while_r3_is_current():
    """ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-
    v1-20260912), pre-deploy R3 candidate sync: HOME -> KB = R3. Root
    HOME's own status badge and stage-nav must show R3 -- via an
    explicit sync_root_home_to_current_stage() call, never a stale R2
    snapshot."""
    html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '"status">R3<' in html
    assert extract_owner(html) == CURRENT_TOURNAMENT_OWNER
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r3/" aria-current="page">R3</a>' in html
    # never a stale disabled R3 placeholder (the exact reported bug class)
    assert '<span class="stage-nav__disabled" aria-disabled="true">R3</span>' not in html


def test_home_body_mirrors_the_real_published_r3_page_exactly():
    """HOME's <main>...</main> body must be byte-identical to R3's own
    real, already-gated page body -- proves HOME is a mirror, never an
    independent rebuild that could silently diverge or fabricate."""
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    r3_html = R3_WAIT_PAGE.read_text(encoding="utf-8")
    home_body = home_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    r3_body = r3_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    assert home_body == r3_body


def test_home_tournaments_nav_override_points_at_r3_not_r2():
    html = DOCS_INDEX.read_text(encoding="utf-8")
    assert 'href="/tournaments/2026/2026090003/r3/">대회<' in html
    assert 'href="/tournaments/2026/2026090003/r2/">대회<' not in html


def test_pre_to_r2_and_r1_to_r2_reachable_on_the_real_site():
    for page in (PRE_PAGE, R1_PAGE):
        html = page.read_text(encoding="utf-8")
        assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r2/">R2</a>' in html


def test_r2_to_pre_and_r2_to_r1_reachable_on_the_real_site():
    html = R2_PAGE.read_text(encoding="utf-8")
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/pre/"' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in html


def test_r3_freeze_is_real_and_home_was_explicitly_resynced_to_it():
    """ROUND-CONTEXT CORRECTION UPDATE, pre-deploy R3 candidate: the R3
    page at this path is the real, published R3 result page (not merely
    a WAIT page), backed by a real, hash-verified R3 freeze --
    kb_current_stage() correctly reflects that. What this test guards:
    HOME now mirrors it, because sync_root_home_to_current_stage() was
    explicitly called for this candidate (Section 1, HOME->R3 sync) --
    a real freeze existing is necessary but was never, by itself,
    sufficient; the explicit sync call is what actually produced this
    HOME body."""
    assert R3_WAIT_PAGE.is_file(), "test precondition: the R3 page must exist for this to be a real check"
    from klpga.neo_win.r3_freeze import r3_freeze_exists
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context(GAME_CODE)
    assert r3_freeze_exists(context) is True
    assert kb_current_stage(context) == "r3"
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '"status">R3<' in home_html  # HOME was explicitly resynced to R3 this session


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
