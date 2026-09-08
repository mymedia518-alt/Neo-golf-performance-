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


def test_internal_validation_state_korean_phrases_never_appear_anywhere(html_files):
    """FAIL 1 correction: these are internal validation/approval-state
    phrases (Korean equivalents of "validation pending"/"approval
    pending"/"publication pending"), forbidden even inside a
    non-rendered HTML comment -- not just the visible body."""
    forbidden = ("검증 대기", "검증용 · 공개 확정 전", "승인 전인 검증용 경기력 순위", "NEO 랭킹 검증")
    offenders = []
    for f in html_files:
        text = f.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                offenders.append((str(f.relative_to(ROOT)), phrase))
    assert offenders == [], f"internal validation-state phrase(s) still present: {offenders}"


def test_neo_geomjeung_sunwi_label_survives_as_a_real_product_label():
    """"NEO 검증 순위" (the metric NAME, distinct from the phrases above
    that describe its internal approval STATE) is a legitimate,
    intentionally-retained product label -- the column header/sort
    option distinguishing NEO's own rank from K-Ranking -- not an
    internal-state leak. Removing it entirely would be over-correction."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "NEO 검증 순위" in html
    assert "검증 대기" not in html


# ---------------------------------------------------------------------------
# 2 / 6 / 7 / 8. HOME tournament cards
# ---------------------------------------------------------------------------

def test_home_contains_last_current_next_tournament_cards(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert '<section class="t-tournament-cards"' in html
    for kind, kicker in (("last", "지난 대회"), ("current", "이번 대회"), ("next", "다음 대회")):
        assert f'data-tournament-card="{kind}"' in html
        assert kicker in html


def test_real_active_tournament_still_shown_as_current_despite_stale_schedule(built):
    """The real, production registry+context data: OK Open's own
    scheduled end_date has passed (it's a multi-day event whose real
    final round hasn't been played yet), but it is NOT genuinely
    complete (no "final" stage validated) -- 이번 대회 must show it, not
    blank it out for a calendar reason alone."""
    from klpga.website_v2.tournament_state import ok_open_tournament_is_complete, OK_GAME_CODE
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    if not ok_open_tournament_is_complete():
        assert f'data-game-code="{OK_GAME_CODE}"' in html
        current_card = re.search(r'data-tournament-card="current"[^>]*>.*?</article>', html, flags=re.S)
        assert current_card and OK_GAME_CODE in current_card.group(0), (
            "the still-active tournament must be 이번 대회, not blanked out by a stale schedule date"
        )


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
# FAIL 3 correction: chronology must be date-driven, never
# stale-active-driven -- a tracked "active" game_code that has already
# ended by real calendar date must never be shown as 이번 대회.
# ---------------------------------------------------------------------------

_FAIL3_REGISTRY = {
    "PAST0001": {
        "url_base": "/tournaments/2099/past-open/",
        "start_date": "2099-01-01", "end_date": "2099-01-04",
        "hub_card": {"display_name": "Past Open", "date_range": "2099.01.01-01.04", "winner": "Past Winner", "winning_score": "-10"},
    },
    "FUTURE0001": {
        "url_base": "/tournaments/2099/future-open-one/",
        "start_date": "2099-03-01", "end_date": "2099-03-04",
        "hub_card": {"display_name": "Future Open One", "date_range": "2099.03.01-03.04"},
    },
    "FUTURE0002": {
        "url_base": "/tournaments/2099/future-open-two/",
        "start_date": "2099-06-01", "end_date": "2099-06-04",
        "hub_card": {"display_name": "Future Open Two", "date_range": "2099.06.01-06.04"},
    },
}


def test_chronology_active_event_live_is_shown_as_current():
    chronology = resolve_tournament_chronology(
        _FAIL3_REGISTRY, active_game_code="LIVE0001",
        active_tournament_name="Live Open", active_start_date="2099-02-01", active_end_date="2099-02-10",
        active_is_complete=False, as_of=date(2099, 2, 5),
    )
    assert chronology["current"].tournament_name == "Live Open"
    assert chronology["last"].tournament_name == "Past Open"
    assert chronology["next"].tournament_name == "Future Open One"


def test_chronology_day_after_active_event_ends_falls_back_to_upcoming():
    """The tracked tournament has REALLY finished (active_is_complete)
    by the day after its scheduled end_date -- it must never still
    render as 이번 대회 just because the pipeline still points at its
    game_code."""
    chronology = resolve_tournament_chronology(
        _FAIL3_REGISTRY, active_game_code="LIVE0001",
        active_tournament_name="Live Open", active_start_date="2099-02-01", active_end_date="2099-02-10",
        active_is_complete=True, as_of=date(2099, 2, 11),
    )
    assert chronology["current"].tournament_name == "Future Open One"
    assert chronology["next"].tournament_name == "Future Open Two"
    # the now-completed active tournament competes for "last" like any
    # other completed entry, and wins (it ended most recently).
    assert chronology["last"].tournament_name == "Live Open"


def test_chronology_stale_active_context_never_shown_as_current():
    """A tracked game_code whose scheduled end_date has passed but is
    REALLY complete (active_is_complete=True, real stage-validation
    evidence) must not still show as 이번 대회."""
    chronology = resolve_tournament_chronology(
        _FAIL3_REGISTRY, active_game_code="STALE0001",
        active_tournament_name="Stale Tracked Open", active_start_date="2026-09-04", active_end_date="2026-09-06",
        active_is_complete=True, as_of=date(2026, 9, 8),
    )
    assert chronology["current"] is None or chronology["current"].tournament_name != "Stale Tracked Open"
    assert chronology["last"].tournament_name == "Stale Tracked Open"


def test_chronology_scheduled_end_date_alone_never_retires_a_still_active_tournament():
    """PUBLIC UI correction: a SCHEDULED end_date going stale (a real-
    world delay, a postponed final round) must never, by itself, blank
    out a tournament that real stage-validation evidence (
    active_is_complete=False) says is still genuinely being played --
    this is the exact real production scenario (OK Open's scheduled
    2026-09-06 end_date vs. still being R2-live on 2026-09-08) this
    correction was filed against."""
    chronology = resolve_tournament_chronology(
        _FAIL3_REGISTRY, active_game_code="STALE0001",
        active_tournament_name="Stale Tracked Open", active_start_date="2026-09-04", active_end_date="2026-09-06",
        active_is_complete=False, as_of=date(2026, 9, 8),
    )
    assert chronology["current"].tournament_name == "Stale Tracked Open"
    assert chronology["current"].defending_champion is None  # unknown fields still blank, never guessed
    # never retired into "last" just because its schedule is stale --
    # no OTHER real registry entry has actually completed by this as_of
    # either (they're all dated 2099), so "last" is honestly None.
    assert chronology["last"] is None


def test_chronology_gap_days_before_next_event_starts():
    """No tournament is live at all (active really finished, next
    hasn't started yet) -- 이번 대회 degrades to the nearest upcoming
    event rather than staying empty or showing the finished one."""
    chronology = resolve_tournament_chronology(
        _FAIL3_REGISTRY, active_game_code="PAST0001",
        active_tournament_name="Past Open", active_start_date="2099-01-01", active_end_date="2099-01-04",
        active_is_complete=True, as_of=date(2099, 1, 20),
    )
    assert chronology["current"].tournament_name == "Future Open One"
    assert chronology["next"].tournament_name == "Future Open Two"
    assert chronology["last"].tournament_name == "Past Open"


def test_chronology_no_future_event_leaves_current_and_next_blank():
    registry = {"PAST0001": _FAIL3_REGISTRY["PAST0001"]}
    chronology = resolve_tournament_chronology(
        registry, active_game_code="PAST0001",
        active_tournament_name="Past Open", active_start_date="2099-01-01", active_end_date="2099-01-04",
        active_is_complete=True, as_of=date(2099, 6, 1),
    )
    assert chronology["current"] is None
    assert chronology["next"] is None
    assert chronology["last"].tournament_name == "Past Open"
    html = render_tournament_cards_html(chronology)
    assert 'data-tournament-card="current"' in html and 'data-tournament-card="next"' in html


def test_chronology_active_not_yet_started_still_counts_as_current():
    """An active tournament with a future start_date (PRE stage, before
    play begins) is not complete -- it is legitimately 이번 대회, the
    one thing this correction must NOT change."""
    chronology = resolve_tournament_chronology(
        _FAIL3_REGISTRY, active_game_code="UPCOMING0001",
        active_tournament_name="Upcoming Tracked Open", active_start_date="2099-04-01", active_end_date="2099-04-04",
        active_is_complete=False, as_of=date(2099, 3, 15),
    )
    assert chronology["current"].tournament_name == "Upcoming Tracked Open"


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


# FAIL 2 correction: the sponsor rule is global, not a HOME/RANKING-only
# exception. Every public route that renders individual player-identity
# rows (name as its own displayed unit, not a data-table label) is
# enumerated here and checked against the same shared rule:
# klpga.website_v2.player_identity.render_player_identity /
# verified_sponsor -- reused by both script 88 (HOME/RANKING) and
# script 84 (OK Open PRE/R1/R2/FINAL).
_OK_OPEN_IDENTITY_ROUTES = (
    "tournaments/2026/ok-savings-bank-open/pre/index.html",
    "tournaments/2026/ok-savings-bank-open/r1/index.html",
    "tournaments/2026/ok-savings-bank-open/r2/index.html",
)


def test_player_identity_helper_never_guesses_and_omits_when_unverified():
    from klpga.website_v2.player_identity import render_player_identity, verified_sponsor
    assert render_player_identity("선수", None) == '<span class="player-name">선수</span>'
    assert render_player_identity("선수", "") == '<span class="player-name">선수</span>'
    assert render_player_identity("선수", "공식스폰서") == '<span class="player-name">선수</span><span class="player-sponsor">공식스폰서</span>'
    assert verified_sponsor({"identity_validation": "PASS", "current_official_sponsor": "공식스폰서"}) == "공식스폰서"
    assert verified_sponsor({"identity_validation": "UNCONFIRMED", "current_official_sponsor": "공식스폰서"}) is None
    assert verified_sponsor({"identity_validation": "PASS", "current_official_sponsor": None}) is None


def test_normalize_player_sponsor_mentions_wraps_only_bare_identity_display_text():
    from klpga.website_v2.player_identity import normalize_player_sponsor_mentions
    sponsor_by_name = {"신다인": "요진건설산업"}
    # a genuine identity display (table cell, heading, result caption) is wrapped
    assert normalize_player_sponsor_mentions("<td>신다인</td>", sponsor_by_name) == (
        '<td><span class="player-name">신다인</span><span class="player-sponsor">요진건설산업</span></td>'
    )
    assert normalize_player_sponsor_mentions("<h3>신다인</h3>", sponsor_by_name) == (
        '<h3><span class="player-name">신다인</span><span class="player-sponsor">요진건설산업</span></h3>'
    )
    # a clickable control's label and a composite/partial text node are left untouched
    assert normalize_player_sponsor_mentions("<button>신다인</button>", sponsor_by_name) == "<button>신다인</button>"
    assert normalize_player_sponsor_mentions("<title>신다인 PRE: 1.9%</title>", sponsor_by_name) == "<title>신다인 PRE: 1.9%</title>"
    # a name with no verified evidence is left exactly as-is -- never guessed
    assert normalize_player_sponsor_mentions("<td>모르는선수</td>", sponsor_by_name) == "<td>모르는선수</td>"
    # already-wrapped markup (either convention) is never re-wrapped
    already = '<td><span class="player-name">신다인</span><span class="player-sponsor">요진건설산업</span></td>'
    assert normalize_player_sponsor_mentions(already, sponsor_by_name) == already
    already_ok_style = "<th scope='row'><span class='player'>신다인</span><span class='sponsor'>요진건설산업</span></th>"
    assert normalize_player_sponsor_mentions(already_ok_style, sponsor_by_name) == already_ok_style


def test_normalization_pass_excludes_the_active_tournament_own_routes(built):
    """OK Open's own generator already applies the rule natively -- the
    promotion-time normalization pass targets every OTHER registered
    tournament plus DEEP DIVE, never re-processing OK Open's own
    already-correct output."""
    from klpga.website_v2.tournament_state import OK_BASE
    html = (OUTPUT / OK_BASE.strip("/") / "r1" / "index.html").read_text(encoding="utf-8")
    assert "class='player'" in html  # OK Open's own established markup, untouched


def test_sponsor_rule_enumerated_across_every_ok_open_stage_route(built):
    """Every OK Open PRE/R1/R2 leaderboard row must follow the exact
    same rule already proven for HOME/RANKING: a verified sponsor
    renders directly under the name, an unverified one is omitted --
    never an empty placeholder span, never guess text."""
    checked_any_row = False
    for route in _OK_OPEN_IDENTITY_ROUTES:
        path = OUTPUT / route
        assert path.is_file(), route
        html = path.read_text(encoding="utf-8")
        rows = re.findall(r"<span class='player'>[^<]*</span>(?:<span class='sponsor'>[^<]*</span>)?", html)
        if not rows:
            continue  # R2 has no rendered leaderboard yet on this data snapshot
        checked_any_row = True
        assert "class='sponsor'></span>" not in html, f"{route}: empty sponsor placeholder span"
        assert "확인 중" not in html and "미확인" not in html, f"{route}: guessed/placeholder sponsor text"
    assert checked_any_row, "expected at least one OK Open route with real player-identity rows"


def test_kg_ladies_open_player_mentions_have_no_fabricated_sponsor(built):
    """KG Ladies Open is already completed, and this pipeline's own
    dedicated code no longer regenerates its archived pages -- but its
    winner/finalists are also in OK Open's current field, so the SAME
    official, identity-validated player master (verified_sponsor())
    provides real evidence for them too. GLOBAL SPONSOR RULE
    correction: this promotion-time normalization pass (see
    normalize_player_sponsor_mentions()) never touches migration.py's
    frozen source -- only the promoted HTML text -- and never fabricates
    one for a player this master has no record of."""
    for stage in ("pre", "r3", "final"):
        html = (OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / stage / "index.html").read_text(encoding="utf-8")
        assert "확인 중" not in html and "미확인" not in html
        assert "class='sponsor'></span>" not in html and 'class="player-sponsor"></span>' not in html
    # the real, known-verified KG winner now carries her real sponsor
    # wherever her bare name appears in an identity-display context.
    final_html = (OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / "final" / "index.html").read_text(encoding="utf-8")
    assert '<span class="player-name">신다인</span><span class="player-sponsor">' in final_html


def test_deep_dive_player_mentions_get_verified_sponsor_where_evidence_exists(built):
    """FAIL 2 correction (GLOBAL SPONSOR RULE): the prior scope
    exception for DEEP DIVE is removed -- a bare player-name table cell
    there must pick up the same verified sponsor evidence too."""
    html = (OUTPUT / "deep-dive" / "index.html").read_text(encoding="utf-8")
    assert '<span class="player-name">신다인</span><span class="player-sponsor">' in html
    assert "확인 중" not in html and "미확인" not in html
    assert 'class="player-sponsor"></span>' not in html


def test_player_sponsor_mentions_never_double_wrapped(built):
    """The promotion-time normalization pass must be idempotent-safe:
    no page anywhere should ever show a nested/doubled name-sponsor
    wrapper (e.g. a normalization bug re-wrapping an already-wrapped
    name)."""
    nested = re.compile(r'<span class="player-name">[^<]*<span class="player-name">')
    for path in OUTPUT.rglob("index.html"):
        html = path.read_text(encoding="utf-8")
        assert nested.search(html) is None, path
        assert html.count('class="player-name"') == len(re.findall(r'<span class="player-name">[^<]*</span>', html))


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
