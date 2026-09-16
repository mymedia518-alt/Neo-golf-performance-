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


def test_home_shows_hana_pre_despite_kb_final_being_kbs_own_current_stage():
    """HANA PRE FULL REPLACEMENT (2026-09-16), superseding FINAL PAGE
    GO's HOME=FINAL contract: root HOME's represented tournament is now
    an explicit product-policy choice, not automatically whichever
    tournament's own stage router resolves furthest. KB's own
    kb_current_stage() still correctly resolves to "final" for KB's own
    context (test_real_kb_current_stage_resolves_to_final, above) --
    that internal state is untouched. What changed is that root HOME no
    longer mirrors it: HOME's own status badge and stage-nav now show
    Hana Financial Group Championship's PRE page instead."""
    html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '"status">PRE<' in html
    assert '"status">FINAL<' not in html
    assert extract_owner(html) == CURRENT_TOURNAMENT_OWNER
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/" aria-current="page">사전 분석 PRE</a>' in html
    # KB's own FINAL stage-nav wiring must not leak onto HOME
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/final/" aria-current="page">FINAL</a>' not in html


def _strip_section(html: str, section_id: str) -> str:
    start = html.find(f'<section class="product-section" id="{section_id}">')
    if start == -1:
        return html
    end = html.index("</section>", start) + len("</section>")
    return html[:start] + html[end:]


HANA_PRE_PAGE = DOCS / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"


def test_home_body_mirrors_the_real_published_hana_pre_page_exactly():
    """HANA PRE FULL REPLACEMENT (2026-09-16): HOME's <main>...</main>
    body must now be byte-identical to Hana Financial Group
    Championship's own real, already-built PRE page body -- proves HOME
    is a mirror of that page, never an independent rebuild that could
    silently diverge or fabricate. Unlike the previous KB-FINAL mirror
    contract, there are zero permitted divergent sections here: HOME's
    body is a straight, unmodified copy of the Hana PRE page's own
    hero + single PRE-table structure (no HOME-only additions)."""
    assert HANA_PRE_PAGE.is_file(), "test precondition: the Hana PRE page must exist for this to be a real check"
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    hana_html = HANA_PRE_PAGE.read_text(encoding="utf-8")
    home_body = home_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    hana_body = hana_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]

    assert home_body == hana_body


KB_ONLY_HOME_SECTION_IDS = (
    "r3-forecast-visual", "final-leaderboard", "forecast-vs-result",
    "neo-validation", "biggest-movers", "why-the-winner-won",
)


def test_home_has_no_leftover_kb_only_sections_or_explanations():
    """HANA PRE FULL REPLACEMENT (2026-09-16): every KB-only product
    section previously mirrored onto HOME from KB's own FINAL page (the
    R3-forecast-visual figure, the full FINAL leaderboard, forecast-vs-
    result, NEO validation, biggest-movers, and the winner-analysis
    write-up) must be completely absent from HOME now -- Hana's own PRE
    page has none of that data (it hasn't happened yet), and nothing
    KB-specific may linger as stale/unnecessary content on the new
    HOME body."""
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    for section_id in KB_ONLY_HOME_SECTION_IDS:
        assert f'<section class="product-section" id="{section_id}">' not in home_html, (
            f"KB-only section {section_id!r} must not remain on HOME after the Hana PRE swap"
        )
    assert "우승 포인트" not in home_html
    assert "골든라이프" not in home_html


def test_home_omits_biggest_movers_but_kb_final_page_still_has_it_structured_and_bullet_free():
    """HANA PRE FULL REPLACEMENT (2026-09-16): HOME no longer carries a
    biggest-movers section at all (Hana's PRE stage has no results to
    move between -- covered by test_home_has_no_leftover_kb_only_
    sections_or_explanations too; re-asserted here for this specific
    section as this test's own direct precondition).

    What this test still protects, unchanged from before the Hana
    swap: KB's own dedicated FINAL page file was never touched by that
    swap, so its biggest-movers section must still exist with exactly
    the same shape and exactly the same data it had before on this
    branch -- 10 mover rows, each carrying a player-name span and its
    own rank-change text (this branch's own KB FINAL page file predates
    the separate movers-row bullet-alignment fix, which -- per that
    fix's own original test coverage -- was only ever hand-patched onto
    HOME, deliberately never propagated to /final/'s own copy; that
    historical fact is what is being preserved here, not re-asserted as
    if it were new)."""
    import re

    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '<section class="product-section" id="biggest-movers">' not in home_html

    final_html = FINAL_PAGE.read_text(encoding="utf-8")
    start = final_html.find('<section class="product-section" id="biggest-movers">')
    assert start != -1, "KB's own FINAL page must still have its biggest-movers section"
    end = final_html.index("</section>", start) + len("</section>")
    movers_html = final_html[start:end]

    all_li = re.findall(r"<li[^>]*>", movers_html)
    assert len(all_li) == 10, "expected exactly 10 mover rows (5 up, 5 down)"
    assert movers_html.count("class='player-name'") == 10
    assert movers_html.count("NEO 예상") == 10

    def _pairs(html: str, section_id: str) -> set[tuple[str, str]]:
        s = html.find(f'<section class="product-section" id="{section_id}">')
        e = html.index("</section>", s) + len("</section>")
        block = html[s:e]
        names = re.findall(r"<span class='player-name'>([^<]*)</span>", block)
        changes = re.findall(r"(?:NEO 예상[^<]*)", block)
        return set(zip(names, changes))

    final_pairs = _pairs(final_html, "biggest-movers")
    assert len(final_pairs) == 10


def test_home_tournaments_nav_override_points_at_hana_pre_not_kb():
    """HANA PRE FULL REPLACEMENT (2026-09-16): the global-nav '대회'
    override now points at Hana's PRE page, not at any KB stage."""
    html = DOCS_INDEX.read_text(encoding="utf-8")
    assert 'href="/tournaments/2026/2026090002/pre/">대회<' in html
    assert 'href="/tournaments/2026/2026090003/final/">대회<' not in html
    assert 'href="/tournaments/2026/2026090003/r3/">대회<' not in html


EXPECTED_PUBLIC_COLUMNS = [
    "선수", "KLPGA K-RANKING", "NEO 경기력",
    "컷 통과확률", "TOP20", "TOP10", "TOP5", "우승확률",
]


def _check_home_style_table_contract(html: str, *, label: str) -> None:
    """Shared assertions for both HOME and Hana's own PRE page, since
    HOME's body is a byte-identical mirror of it: exactly 8 public
    columns (최근 5R SG removed, 2026-09-16 -- that internal-only metric
    is never rendered on this public page, though the underlying SG
    evidence file and its analysis remain on disk untouched), exactly
    108 rows, K-Ranking ascending sort, and the 5 DATA_INSUFFICIENT
    foreign entrants each showing 데이터 부족 in all 5 probability
    columns."""
    import re

    assert "최근 5R SG" not in html, f"{label}: 최근 5R SG must not appear anywhere in the public page"

    thead = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    headers = re.findall(r"<th[^>]*>(.*?)(?:<button|</th>)", thead, re.DOTALL)
    headers = [re.sub(r"<[^>]+>", "", h).strip() for h in headers]
    assert headers == EXPECTED_PUBLIC_COLUMNS, f"{label}: expected exactly the 8 public columns, got {headers}"

    tbody = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL).group(1)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)
    assert len(rows) == 108, f"{label}: expected exactly 108 player rows"

    k_ranks = []
    insufficient_rows = []
    for row in rows:
        cell = re.search(r"data-label='KLPGA K-RANKING'>([^<]*)<", row).group(1)
        k_ranks.append(int(cell) if cell != "—" else None)
        prob_cells = re.findall(
            r"data-label='(?:컷 통과확률|TOP20|TOP10|TOP5|우승확률)'>(.*?)</td>", row, re.DOTALL
        )
        assert len(prob_cells) == 5, f"{label}: expected exactly 5 probability columns per row"
        if all("데이터 부족" in c for c in prob_cells):
            insufficient_rows.append(row)

    present = [k for k in k_ranks if k is not None]
    assert present == sorted(present), f"{label}: K-Ranking must be ascending among players who have one"
    first_missing = k_ranks.index(None) if None in k_ranks else len(k_ranks)
    assert all(k is not None for k in k_ranks[:first_missing])
    assert all(k is None for k in k_ranks[first_missing:]), f"{label}: players without a K-Ranking must sort last"

    assert len(insufficient_rows) == 5, (
        f"{label}: expected exactly 5 DATA_INSUFFICIENT players with all 5 probability cells showing 데이터 부족"
    )


def test_home_has_hana_pre_link_108_players_8_columns_k_ranking_sorted():
    """HANA PRE FULL REPLACEMENT (2026-09-16) + PUBLIC-UI SG REDACTION
    (2026-09-16) contract, verified directly against HOME's own file
    content (independent of the byte-identity-with-Hana's-own-page
    check above, so this still holds even if that mirroring approach
    changes later): a real link to Hana Financial Group Championship's
    PRE page (game_code 2026090002), plus the shared table contract."""
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    assert 'href="/tournaments/2026/2026090002/pre/"' in home_html
    _check_home_style_table_contract(home_html, label="HOME")


def test_hana_pre_page_itself_has_108_players_8_columns_k_ranking_sorted():
    """Same shared table contract, checked directly against Hana's own
    PRE page file (not just inherited via the byte-identity-with-HOME
    check) -- so a regression in Hana's own build output is caught even
    if HOME's mirroring step is ever skipped or broken."""
    assert HANA_PRE_PAGE.is_file(), "test precondition: the Hana PRE page must exist for this to be a real check"
    hana_html = HANA_PRE_PAGE.read_text(encoding="utf-8")
    _check_home_style_table_contract(hana_html, label="Hana PRE page")


def test_pre_to_r2_and_r1_to_r2_reachable_on_the_real_site():
    for page in (PRE_PAGE, R1_PAGE):
        html = page.read_text(encoding="utf-8")
        assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r2/">R2</a>' in html


def test_r2_to_pre_and_r2_to_r1_reachable_on_the_real_site():
    html = R2_PAGE.read_text(encoding="utf-8")
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/pre/"' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in html


def test_kb_final_evidence_still_real_but_home_was_explicitly_repointed_to_hana():
    """FINAL PAGE GO's own evidence-completeness contract for KB
    (39/39 positions, zero review_required/unmatched V3 evidence) is
    still real and still true -- kb_current_stage() still correctly
    resolves KB's own context to "final". What changed, by explicit
    HANA PRE FULL REPLACEMENT (2026-09-16) product-policy decision, is
    that root HOME is no longer produced by mirroring whatever KB's own
    router resolves to: it was deliberately repointed to Hana's PRE
    page instead. This test guards both halves at once -- KB's real
    evidence/router state is untouched, AND HOME correctly does not
    show KB's FINAL status despite that evidence being real."""
    assert FINAL_PAGE.is_file(), "test precondition: the FINAL page must exist for this to be a real check"
    from klpga.website_v2.kb_home_stage_router import _final_evidence_confirmed
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context(GAME_CODE)
    assert _final_evidence_confirmed(context) is True
    assert kb_current_stage(context) == "final"
    home_html = DOCS_INDEX.read_text(encoding="utf-8")
    assert '"status">FINAL<' not in home_html  # explicit override: HOME shows Hana PRE, not KB's real FINAL
    assert '"status">PRE<' in home_html
    final_html = FINAL_PAGE.read_text(encoding="utf-8")
    assert '"status">FINAL<' in final_html  # KB's own dedicated FINAL page file is untouched


def test_kb_final_page_itself_retains_full_original_structure_and_data():
    """HANA PRE FULL REPLACEMENT (2026-09-16): the swap touches only
    docs/index.html (root HOME) -- KB's own dedicated FINAL page file
    must still have every one of its original sections, its original
    title, and its original 39-position result set, completely
    unaffected by root HOME no longer mirroring it."""
    final_html = FINAL_PAGE.read_text(encoding="utf-8")
    # r3-forecast-visual was always a HOME-only addition, never part of
    # KB's own FINAL page file -- not expected here.
    for section_id in (
        "tournament", "final-leaderboard", "forecast-vs-result",
        "neo-validation", "biggest-movers", "why-the-winner-won",
    ):
        assert f'id="{section_id}"' in final_html, f"KB FINAL page must still have its {section_id!r} section"
    assert "KB금융 골든라이프 챔피언십" in final_html
    assert '"status">FINAL<' in final_html
    assert "우승 포인트" in final_html
    assert final_html.count("data-player-id=") == 39


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
