"""PRODUCTION HOME REGRESSION ROOT-CAUSE + REPAIR (20260911), retargeted
by PRODUCTION HOME PRODUCT POLICY CORRECTION (20260911).

Original fix locked in here: root cause was
scripts/88_build_neo_top120_candidate.py itself -- render_clean() always
put an intro/coverage-stat block ahead of the player table, and build()
always attached the three tournament cards (지난/이번/다음 대회) right
after the shared header on root HOME.

CORRECTION: "root HOME is always the player-first ranking table, never
a tournament's own content" was itself a misinterpretation -- the
correct policy is state-dependent (RULE A/B/C, see scripts/88's HOME
STATE ROUTER comment and tests/test_home_state_router.py's 12-case
coverage): root legitimately BECOMES the active tournament's own stage
page while one is active. The invariants this file locks in (no
tournament-card block, player-first structure, no internal-debug/
tournament-phase leakage, correct player order) are still real -- they
now hold PERMANENTLY at /ranking/, the one route whose content never
depends on tournament state, rather than unconditionally at / (which
the sponsor-invariant and idempotent-build checks below still also
cover, since those two remain true regardless of HOME's state).

Every test here reads the real production-bound candidate output
(scripts/88's own build(), through the standard candidate_dir()
test-isolation override -- see conftest.py), not a hand-written fixture.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from klpga.tournament_context import candidate_dir

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = candidate_dir("neo-data-home-top120")
CSS = ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css"


def _run_build():
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_playerfirst", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build()
    return module


@pytest.fixture(scope="module")
def built_module():
    return _run_build()


@pytest.fixture(scope="module")
def home_html(built_module) -> str:
    # RETARGETED by PRODUCTION HOME PRODUCT POLICY CORRECTION: these
    # invariants (no tournament cards, player-first structure, no
    # debug/tournament-phase leakage, correct player order) are
    # permanent facts about /ranking/, not / -- / is now state-
    # dependent (see tests/test_home_state_router.py and
    # tests/test_neo_top120_validation.py::
    # test_home_becomes_the_active_tournament_stage_when_one_is_active
    # for /'s own, state-aware coverage).
    return (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")


TOURNAMENT_CARD_MARKERS = ("지난 대회", "이번 대회", "다음 대회", "t-tournament-card", "t-tournament-cards")
INTERNAL_DEBUG_MARKERS = (
    "BLOCKED_FORMULA_NOT_APPROVED", "VALIDATION_MODEL_NOT_PRODUCTION", "HEURISTIC_FOR_EVALUATION",
    "sg_connected", "recent10_ready", "recent5_ready", "publication_class", "neo-build-source-commit",
    "PASS_CORRECTED_SG_WAREHOUSE", "DATA_INSUFFICIENT",
)
TOURNAMENT_PHASE_MARKERS = ("1R 결과", "PRE → R1", "컷 통과", "Top20", "Top10", "Top5", "우승", "합계", "KB금융 골든라이프")


# ---------------------------------------------------------------------
# TEST 1: no tournament-card block on HOME
# ---------------------------------------------------------------------

def test_home_has_no_tournament_card_block(home_html):
    for marker in TOURNAMENT_CARD_MARKERS:
        assert marker not in home_html, f"tournament-card marker leaked into HOME: {marker!r}"


# ---------------------------------------------------------------------
# TEST 2: HOME's primary content is the player list
# ---------------------------------------------------------------------

def test_home_primary_content_is_the_player_list(home_html):
    body = re.search(r"<body[^>]*>(.*)</body>", home_html, re.S).group(1)
    header_end = body.index("</header>") + len("</header>")
    after_header = body[header_end:]
    first_section = re.search(r"<section[^>]*class=\"([^\"]*)\"", after_header)
    assert first_section is not None, "no <section> found immediately after the header"
    assert "home-primary" in first_section.group(1), (
        f"first section after header is {first_section.group(1)!r}, expected the player-list "
        "product-section to be first"
    )
    # the table itself must appear before the glossary/help section
    table_idx = after_header.index('class="data-table home-table"')
    help_idx = after_header.index('class="ranking-help"')
    assert table_idx < help_idx


# ---------------------------------------------------------------------
# TEST 3: real player data present
# ---------------------------------------------------------------------

def test_home_has_real_player_data(home_html):
    assert home_html.count("data-player-row") == 120
    names = re.findall(r'data-player-name="([^"]*)"', home_html)
    assert len(names) == 120
    assert all(n.strip() for n in names)


# ---------------------------------------------------------------------
# TEST 4: player order is the current, non-blocked public ranking
# ---------------------------------------------------------------------

def test_home_player_order_matches_the_current_public_ranking(home_html):
    """The literal product ask is "NEO Ranking 순" -- but the composite
    NEO Ranking score/rank is a publication-blocked validation-only
    model (NEO_RANKING_VALIDATION_MODEL_V1.json's own publication_class
    is VALIDATION_MODEL_NOT_PRODUCTION; render_clean()'s own docstring
    documents why the column was removed rather than published). This
    test locks in the safe interpretation instead: the table's actual
    row order is exactly the one real, currently-published ranking
    (official K-Ranking, ascending) -- consistent, not arbitrary, and
    never the blocked composite. See the final report's [REMAINING
    RISKS] for this explicit, flagged deviation from the literal
    instruction."""
    ranks = [int(r) for r in re.findall(r'data-k-rank="(\d+)"', home_html)]
    assert ranks == sorted(ranks)
    assert ranks == list(range(1, 121))


# ---------------------------------------------------------------------
# TEST 5 + 6: sponsor invariant across every player-bearing public page
# ---------------------------------------------------------------------

def test_sponsor_slot_invariant_holds(built_module):
    """render_player_identity() always emits the sponsor <span> --
    empty (no text) for an unverified player, never omitted -- so the
    structural slot count matches the name count exactly, 1:1. Checked
    against /ranking/ (a fixed, always-120-player population regardless
    of HOME state) -- / itself is state-dependent (TOP120's 120 players
    at "/", or an active tournament's own field size and quote-style
    when one is active) and gets its own sponsor-invariant coverage in
    tests/test_home_state_router.py::
    test_case_10_active_tournament_home_preserves_sponsor_invariant."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    name_count = html.count('class="player-name"')
    sponsor_spans = re.findall(r'<span class="player-sponsor">([^<]*)</span>', html)
    assert name_count == 120
    assert len(sponsor_spans) == 120
    assert sum(1 for s in sponsor_spans if s.strip()) > 0


@pytest.mark.parametrize("route", ["index.html", "ranking/index.html"])
def test_no_fabricated_sponsor_for_unverified_players(built_module, route):
    """A sponsor span only ever exists for a player with real evidence
    -- there is no code path that emits a placeholder/guessed sponsor
    value, so this asserts the absence of any known placeholder text
    rather than a count (a genuinely blank slot is simply absent)."""
    html = (OUTPUT / route).read_text(encoding="utf-8")
    for placeholder in ("미확인", "TBD", "N/A", "unknown sponsor", "확인 필요"):
        assert placeholder not in html


# ---------------------------------------------------------------------
# TEST 7: mobile CSS never changes HOME's DOM/content structure
# ---------------------------------------------------------------------

def test_mobile_css_does_not_inject_visible_content(home_html):
    """Structural separation check: the built HTML is pure server-
    rendered markup with no CSS-generated content. Any `content:"..."`
    declaration inside a mobile @media block that contains real player-
    facing text would be exactly the kind of "CSS changes altered
    HOME's content" defect this test forbids."""
    css = CSS.read_text(encoding="utf-8")
    for block in re.findall(r"@media\(max-width:\d+px\)\{(.*?)\}\}", css, re.S):
        for content_decl in re.findall(r'content:"([^"]*)"', block):
            assert content_decl.strip() == "" or not re.search(r"[가-힣]", content_decl), (
                f"mobile CSS injects visible Korean text via content: {content_decl!r}"
            )
    # and the structural facts test 1-3 already proved (row count, no
    # tournament cards, home-primary first) hold regardless of which
    # viewport a real browser renders at -- CSS never adds/removes rows.


# ---------------------------------------------------------------------
# TEST 8: idempotent build
# ---------------------------------------------------------------------

def test_home_build_is_idempotent():
    _run_build()
    first = (OUTPUT / "index.html").read_text(encoding="utf-8")
    _run_build()
    second = (OUTPUT / "index.html").read_text(encoding="utf-8")
    strip_provenance = lambda h: re.sub(r'(neo-build-id|neo-build-source-commit)" content="[^"]*"', r'\1" content="X"', h)
    assert strip_provenance(first) == strip_provenance(second)


# ---------------------------------------------------------------------
# TEST 9: no internal validation/debug status on HOME
# ---------------------------------------------------------------------

def test_home_exposes_no_internal_debug_status(home_html):
    body = re.search(r"<body[^>]*>(.*)</body>", home_html, re.S).group(1)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    for marker in INTERNAL_DEBUG_MARKERS:
        assert marker not in body, f"internal/debug marker leaked into HOME body: {marker!r}"


# ---------------------------------------------------------------------
# TEST 10: tournament phase content never leaks into HOME
# ---------------------------------------------------------------------

def test_home_has_no_tournament_phase_content(home_html):
    body = re.search(r"<body[^>]*>(.*)</body>", home_html, re.S).group(1)
    for marker in TOURNAMENT_PHASE_MARKERS:
        assert marker not in body, f"tournament-phase marker leaked into HOME: {marker!r}"
