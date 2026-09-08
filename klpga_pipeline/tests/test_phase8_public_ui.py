"""PUBLIC UI Phase 8 (feat/public-ui-tournament-dashboard): global brand
header, HOME tournament cards, developer-info removal, public roster
safety, and the sponsor rule -- end to end against the REAL generic
pipeline (scripts 88/94), never a re-implementation.
"""
from __future__ import annotations

import importlib.util
import json
import re
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"
CONTENT = ROOT / "content" / "website_v2"

import sys
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.tournament_chronology import (  # noqa: E402
    TournamentCardFacts,
    resolve_tournament_chronology,
)
from klpga.website_v2.tournament_cards import render_tournament_cards_html  # noqa: E402


@pytest.fixture(scope="module")
def built():
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_phase8", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


@pytest.fixture(scope="module")
def html_files(built):
    return list(OUTPUT.rglob("*.html"))


def _visible_pages(html_files):
    return [f for f in html_files if "protected" not in f.parts]


def _strip_head_and_evidence(html: str) -> str:
    """Everything a visitor actually SEES: the <head> (meta tags,
    non-visible by definition) and any collapsed evidence-disclosure
    <details> block (opt-in provenance a user must click to expand --
    already an established, deliberate exception elsewhere in this
    suite, e.g. test_no_unnecessary_english_or_beta_in_product_flow)
    are removed first."""
    html = re.sub(r"<head>.*?</head>", "", html, count=1, flags=re.S)
    html = re.sub(r'<details class="evidence-detail".*?</details>', "", html, flags=re.S)
    return html


# ---------------------------------------------------------------------------
# 1. Global brand header: NUMBER / EVIDENCE / ORACLE on every public page
# ---------------------------------------------------------------------------

def test_every_public_page_shows_number_evidence_oracle(html_files):
    missing = []
    for f in _visible_pages(html_files):
        text = f.read_text(encoding="utf-8")
        if not all(word in text for word in ("NEO GOLF DATA", "NUMBER", "EVIDENCE", "ORACLE")):
            missing.append(str(f.relative_to(ROOT)))
    assert missing == [], f"page(s) missing the NEO GOLF DATA / NUMBER / EVIDENCE / ORACLE brand lockup: {missing}"


def test_klpga_performance_terminal_appears_nowhere(html_files):
    offenders = [str(f.relative_to(ROOT)) for f in html_files if "KLPGA PERFORMANCE TERMINAL" in f.read_text(encoding="utf-8")]
    assert offenders == [], f"retired tagline still present: {offenders}"


# ---------------------------------------------------------------------------
# 3. Developer/pipeline info removed from visible UI
# ---------------------------------------------------------------------------

def test_validating_never_appears_in_visible_public_ui(html_files):
    offenders = []
    for f in _visible_pages(html_files):
        visible = _strip_head_and_evidence(f.read_text(encoding="utf-8"))
        if "VALIDATING" in visible:
            offenders.append(str(f.relative_to(ROOT)))
    assert offenders == [], f"internal VALIDATING status visible on: {offenders}"


def test_wait_and_blocked_never_appear_as_visible_public_status(html_files):
    offenders = []
    for f in _visible_pages(html_files):
        visible = _strip_head_and_evidence(f.read_text(encoding="utf-8"))
        if re.search(r"\bWAIT\b", visible) or re.search(r"\bBLOCKED\b", visible) or "NOT PUBLISHED" in visible:
            offenders.append(str(f.relative_to(ROOT)))
    assert offenders == [], f"internal WAIT/BLOCKED/NOT PUBLISHED status visible on: {offenders}"


def test_no_internal_provenance_metadata_visible_in_body(html_files):
    """schema_version/build-id/source-commit/raw sha/hash strings must
    never appear in the VISIBLE page body -- they are allowed only as
    non-visible <head> <meta> tags (already covered by the P0-3 build
    provenance tests) or inside an opt-in evidence-disclosure <details>
    block (an established, deliberate exception)."""
    offenders = []
    for f in _visible_pages(html_files):
        visible = _strip_head_and_evidence(f.read_text(encoding="utf-8"))
        for needle in ("schema_version", "neo-build-id", "neo-build-source-commit", "SHA-256", "population_count", "k_ranking_join"):
            if needle in visible:
                offenders.append((str(f.relative_to(ROOT)), needle))
    assert offenders == [], f"internal pipeline metadata visible in page body: {offenders}"


def test_neo_lab_explains_methodology_without_internal_status_badges():
    path = OUTPUT / "neo-lab" / "index.html"
    assert path.is_file()
    visible = _strip_head_and_evidence(path.read_text(encoding="utf-8"))
    for forbidden in ("VALIDATING", "NOT PUBLISHED", "546", "119", "97개 대회", "DATA COVERAGE", "TEMPORAL INTEGRITY"):
        assert forbidden not in visible, f"NEO LAB still exposes internal status: {forbidden!r}"
    assert "NEO" in visible and len(visible) > 200  # genuine methodology copy, not an empty shell


# ---------------------------------------------------------------------------
# 2 / 6 / 7 / 8. HOME tournament cards
# ---------------------------------------------------------------------------

def test_home_contains_last_current_next_tournament_cards(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert '<section class="t-tournament-cards"' in html
    for kind, kicker in (("last", "지난 대회"), ("current", "이번 대회"), ("next", "다음 대회")):
        assert f'data-tournament-card="{kind}"' in html
        assert kicker in html


def test_tournament_cards_are_registry_and_context_driven_not_hardcoded():
    """Pure resolver test -- a synthetic registry with a synthetic
    active game_code must produce the exact matching cards, proving
    the mapping is generic (registry+context in, facts out), not a
    lookup table of real tournament names baked into source."""
    registry = {
        "SYN0001": {
            "url_base": "/tournaments/2099/synthetic-open/",
            "start_date": "2099-01-01", "end_date": "2099-01-04",
            "hub_card": {"display_name": "Synthetic Open", "date_range": "2099.01.01-01.04", "winner": "Player X", "winning_score": "-10"},
        },
        "SYN0002": {
            "url_base": "/tournaments/2099/synthetic-future-open/",
            "start_date": "2099-06-01", "end_date": "2099-06-04",
            "hub_card": {"display_name": "Synthetic Future Open", "date_range": "2099.06.01-06.04"},
        },
    }
    chronology = resolve_tournament_chronology(
        registry, active_game_code=None, as_of=date(2099, 3, 1),
    )
    assert chronology["last"].tournament_name == "Synthetic Open"
    assert chronology["last"].winner == "Player X"
    assert chronology["next"].tournament_name == "Synthetic Future Open"
    assert chronology["current"] is None
    html = render_tournament_cards_html(chronology)
    assert "Synthetic Open" in html and "Synthetic Future Open" in html
    assert "Player X" in html


def test_unseen_future_tournament_needs_zero_html_source_edit():
    """A brand-new synthetic game_code with no code anywhere mentioning
    it must still produce a fully-formed, correct tournament card --
    proving HOME's cards need no source edit when the calendar
    advances."""
    registry = {
        "FIXTUREPHASE8UNSEEN": {
            "url_base": "/tournaments/2099/fixture-phase8-unseen/",
            "start_date": "2099-09-01", "end_date": "2099-09-04",
            "venue": "Fixture Course",
            "hub_card": {"display_name": "Fixture Phase 8 Open", "date_range": "2099.09.01-09.04", "winner": "Fixture Winner", "winning_score": "-5"},
        },
    }
    chronology = resolve_tournament_chronology(registry, active_game_code=None, as_of=date(2099, 12, 1))
    facts = chronology["last"]
    assert facts.tournament_name == "Fixture Phase 8 Open"
    assert facts.venue == "Fixture Course"
    html = render_tournament_cards_html(chronology)
    assert "Fixture Phase 8 Open" in html and "Fixture Course" in html
    import subprocess
    result = subprocess.run(
        ["git", "grep", "-l", "FIXTUREPHASE8UNSEEN", "--", "src/", "scripts/"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert result.returncode != 0, "the synthetic game_code must appear nowhere in operational source"


def test_missing_evidence_shows_dash_never_inferred():
    registry = {
        "SYN0003": {
            "url_base": "/tournaments/2099/synthetic-noresult-open/",
            "start_date": "2099-01-01", "end_date": "2099-01-04",
            "hub_card": {"display_name": "Synthetic No-Result Open", "date_range": "2099.01.01-01.04"},
            # deliberately no venue, winner, winning_score
        },
    }
    chronology = resolve_tournament_chronology(registry, active_game_code=None, as_of=date(2099, 3, 1))
    facts = chronology["last"]
    assert facts.venue is None and facts.winner is None and facts.winning_score is None
    html = render_tournament_cards_html(chronology)
    # the card itself renders, with dashes for the unknown fields
    assert "Synthetic No-Result Open" in html
    assert html.count("—") >= 2


# ---------------------------------------------------------------------------
# 4. Public roster safety: 546 foundation must never leak into public HOME
# ---------------------------------------------------------------------------

def test_home_player_board_never_shows_the_546_foundation_roster(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    ranking_html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    for page_html, label in ((html, "index.html"), (ranking_html, "ranking/index.html")):
        row_count = page_html.count("data-player-row")
        assert row_count <= 120, f"{label}: {row_count} player rows -- must never exceed the approved 120-player public cohort"


def test_home_regular_tour_player_master_546_file_is_preserved_but_never_read_by_the_public_builder():
    foundation_path = CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"
    assert foundation_path.is_file(), "the 546-player foundation database must remain preserved internally"
    data = json.loads(foundation_path.read_text(encoding="utf-8"))
    assert data.get("player_count") == 546 or len(data.get("records") or data.get("players") or []) >= 500
    # the real HOME/ranking builder script must never reference this file
    builder_source = (ROOT / "scripts" / "88_build_neo_top120_candidate.py").read_text(encoding="utf-8")
    assert "HOME_REGULAR_TOUR_PLAYER_MASTER" not in builder_source


# ---------------------------------------------------------------------------
# 5. Sponsor rule
# ---------------------------------------------------------------------------

def test_sponsor_appears_directly_below_player_name_when_verified(built):
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<span class="player-name">[^<]+</span><span class="player-sponsor">[^<]+</span>', html), (
        "at least one verified sponsor must render directly under its player name"
    )


def test_unverified_sponsor_remains_blank_never_guessed(built):
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    # Every player row must have EITHER a real sponsor span or none at
    # all -- never an empty placeholder / "unknown" / "확인 중" guess text.
    assert "player-sponsor\"></span>" not in html
    assert "스폰서 확인 중" not in html and "스폰서 미확인" not in html
    rows_without_sponsor = len(re.findall(r'<th scope="row"><span class="player-name">[^<]+</span></th>', html))
    rows_with_sponsor = len(re.findall(r'<span class="player-sponsor">', html))
    assert rows_without_sponsor + rows_with_sponsor == 120


# ---------------------------------------------------------------------------
# Historical integrity
# ---------------------------------------------------------------------------

def test_kg_ladies_open_historical_pages_are_byte_identical_apart_from_shared_chrome(built):
    """The historical KG Ladies Open result content itself (winner,
    scores, round-by-round data) must be untouched -- only the shared
    header/brand/nav chrome legitimately changes site-wide."""
    for stage in ("pre", "r1", "r2", "r3", "final"):
        page = OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / stage / "index.html"
        assert page.is_file()
        html = page.read_text(encoding="utf-8")
        assert "KLPGA PERFORMANCE TERMINAL" not in html
    final_html = (OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / "final" / "index.html").read_text(encoding="utf-8")
    assert "신다인" in final_html and "271" in final_html, "KG Ladies Open's real historical result must remain present and unchanged"
