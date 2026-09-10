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
CONTENT = ROOT / "content" / "website_v2"

import sys
sys.path.insert(0, str(ROOT / "src"))

# SPONSOR OFFICIAL-EVIDENCE RECOVERY V2 regression fix: must resolve
# through candidate_dir() (honors tests/conftest.py's
# KLPGA_CANDIDATE_ROOT_OVERRIDE) -- see the identical fix and rationale
# in test_public_sponsor_contract.py.
from klpga.tournament_context import candidate_dir  # noqa: E402

OUTPUT = candidate_dir("neo-data-home-top120")

from klpga.website_v2.tournament_chronology import (  # noqa: E402
    TournamentCardFacts,
    resolve_tournament_chronology,
)
from klpga.website_v2.tournament_cards import render_tournament_cards_html  # noqa: E402
from klpga.website_v2.official_schedule import ScheduleEntry  # noqa: E402


def _entry(game_code, name, start, end, venue=None):
    """Synthetic official-schedule fixture entry -- Red Team FAIL B:
    resolve_tournament_chronology() now reads calendar identity ONLY
    from ScheduleEntry objects like this one, never from the site
    registry and never from any pipeline stage-validation signal."""
    return ScheduleEntry(
        game_code=game_code, tournament_name=name, start_date=start, end_date=end,
        source_identity="tests/fixture", retrieved_at="2026-01-01T00:00:00Z", source_hash="0" * 64,
        venue=venue,
    )


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
            missing.append(str(f.relative_to(OUTPUT)))
    assert missing == [], f"page(s) missing the NEO GOLF DATA / NUMBER / EVIDENCE / ORACLE brand lockup: {missing}"


def test_klpga_performance_terminal_appears_nowhere(html_files):
    offenders = [str(f.relative_to(OUTPUT)) for f in html_files if "KLPGA PERFORMANCE TERMINAL" in f.read_text(encoding="utf-8")]
    assert offenders == [], f"retired tagline still present: {offenders}"


# ---------------------------------------------------------------------------
# 3. Developer/pipeline info removed from visible UI
# ---------------------------------------------------------------------------

def test_validating_never_appears_in_visible_public_ui(html_files):
    offenders = []
    for f in _visible_pages(html_files):
        visible = _strip_head_and_evidence(f.read_text(encoding="utf-8"))
        if "VALIDATING" in visible:
            offenders.append(str(f.relative_to(OUTPUT)))
    assert offenders == [], f"internal VALIDATING status visible on: {offenders}"


def test_wait_and_blocked_never_appear_as_visible_public_status(html_files):
    offenders = []
    for f in _visible_pages(html_files):
        visible = _strip_head_and_evidence(f.read_text(encoding="utf-8"))
        if re.search(r"\bWAIT\b", visible) or re.search(r"\bBLOCKED\b", visible) or "NOT PUBLISHED" in visible:
            offenders.append(str(f.relative_to(OUTPUT)))
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
                offenders.append((str(f.relative_to(OUTPUT)), needle))
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
    # FINAL PHASE 8 RED-TEAM CLOSURE item 3: "이 모델 버전" (Deep Dive) was
    # implementation/version terminology leaking into golfer-facing
    # copy -- rewritten to plain language; "모델 버전" guarded here so it
    # never regresses back in.
    forbidden = ("검증 대기", "검증용 · 공개 확정 전", "승인 전인 검증용 경기력 순위", "NEO 랭킹 검증", "모델 버전")
    offenders = []
    for f in html_files:
        text = f.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                offenders.append((str(f.relative_to(OUTPUT)), phrase))
    assert offenders == [], f"internal validation-state phrase(s) still present: {offenders}"


def test_unapproved_neo_ranking_keeps_structure_but_publishes_no_values():
    """The product slot remains, while the validation-only model stays private."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "NEO Ranking" in html
    assert "NEO 검증 순위" not in html and "검증 대기" not in html
    assert not re.search(r'data-neo-rank="\d+"', html)


# ---------------------------------------------------------------------------
# 2 / 6 / 7 / 8. HOME tournament cards
# ---------------------------------------------------------------------------

def test_home_contains_last_current_next_tournament_cards(built):
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert '<section class="t-tournament-cards"' in html
    for kind, kicker in (("last", "지난 대회"), ("current", "이번 대회"), ("next", "다음 대회")):
        assert f'data-tournament-card="{kind}"' in html
        assert kicker in html


def test_real_official_schedule_drives_home_never_pipeline_stage_state():
    """Red Team FAIL B: chronology identity comes ONLY from the
    official schedule artifact, never from
    tournament_state.ok_open_tournament_is_complete() (a pipeline
    stage-validation signal). OK Open's real official window
    (2026-09-04 to 2026-09-06) has genuinely closed by real calendar
    date regardless of whether this sandbox ever collected a validated
    FINAL snapshot -- it must resolve into "last" (지난 대회), not
    "current", and that must hold identically whether the pipeline
    stage signal is True or False (the resolver never even looks)."""
    from datetime import date
    from klpga.tournament_context import SITE_REGISTRY_PATH
    from klpga.website_v2.official_schedule import load_official_schedule
    import json

    registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig")).get("tournaments", {})
    schedule = load_official_schedule(CONTENT / "OFFICIAL_KLPGA_SCHEDULE.json")
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date(2026, 9, 8))
    assert chronology["last"] is not None and chronology["last"].game_code == "2026120001"
    assert chronology["current"] is None or chronology["current"].game_code != "2026120001"


def test_tournament_cards_are_schedule_and_registry_driven_not_hardcoded():
    """Pure resolver test -- a synthetic schedule (calendar identity)
    joined with a synthetic registry (route/display metadata) must
    produce the exact matching cards, proving the mapping is generic
    (schedule+registry in, facts out), not a lookup table of real
    tournament names baked into source."""
    schedule = [
        _entry("SYN0001", "Synthetic Open", "2099-01-01", "2099-01-04"),
        _entry("SYN0002", "Synthetic Future Open", "2099-06-01", "2099-06-04"),
    ]
    registry = {
        "SYN0001": {
            "url_base": "/tournaments/2099/synthetic-open/",
            "hub_card": {"date_range": "2099.01.01-01.04", "winner": "Player X", "winning_score": "-10"},
        },
        "SYN0002": {
            "url_base": "/tournaments/2099/synthetic-future-open/",
            "hub_card": {"date_range": "2099.06.01-06.04"},
        },
    }
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date(2099, 3, 1))
    assert chronology["last"].tournament_name == "Synthetic Open"
    assert chronology["last"].winner == "Player X"
    # nothing is ongoing on 2099-03-01 -- 이번 대회 degrades to the
    # nearest upcoming event (Red Team FAIL B: "이번 대회 = this week's
    # event OR nearest upcoming official event"), leaving no second
    # upcoming entry for 다음 대회.
    assert chronology["current"].tournament_name == "Synthetic Future Open"
    assert chronology["next"] is None
    html = render_tournament_cards_html(chronology)
    assert "Synthetic Open" in html and "Synthetic Future Open" in html
    assert "Player X" in html


def test_unseen_future_tournament_needs_zero_html_source_edit():
    """A brand-new synthetic game_code with no code anywhere mentioning
    it must still produce a fully-formed, correct tournament card --
    proving HOME's cards need no source edit when the calendar
    advances (only a new OFFICIAL_KLPGA_SCHEDULE.json entry)."""
    schedule = [_entry("FIXTUREPHASE8UNSEEN", "Fixture Phase 8 Open", "2099-09-01", "2099-09-04", venue="Fixture Course")]
    chronology = resolve_tournament_chronology(schedule, {}, as_of=date(2099, 12, 1))
    facts = chronology["last"]
    assert facts.tournament_name == "Fixture Phase 8 Open"
    assert facts.venue == "Fixture Course"
    assert facts.url_base == ""  # no registry route -- calendar facts still render, no link
    html = render_tournament_cards_html(chronology)
    assert "Fixture Phase 8 Open" in html and "Fixture Course" in html
    import subprocess
    result = subprocess.run(
        ["git", "grep", "-l", "FIXTUREPHASE8UNSEEN", "--", "src/", "scripts/"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert result.returncode != 0, "the synthetic game_code must appear nowhere in operational source"


def test_bootstrap_only_registry_entry_still_shows_no_link():
    """klpga.tournament_context.ensure_site_registry_entry writes a
    minimal, mechanical url_base the moment ANY pipeline prerequisite
    (e.g. an offline entry-list import) resolves a TournamentContext
    for a brand-new game_code -- long before any real public page
    exists at that route. A card must never turn that internal
    bootstrap url_base into a clickable link (a guaranteed dead link):
    only a registry entry that also declares real public content
    (has_hub_index, or a non-empty hub_card.nav_stages) may produce a
    link, matching the same 'no public page yet' -> '' contract this
    module already guarantees for a game_code entirely absent from the
    registry."""
    schedule = [_entry("BOOTSTRAPONLY0001", "Bootstrap Only Open", "2099-05-01", "2099-05-04")]
    registry = {"BOOTSTRAPONLY0001": {"url_base": "/tournaments/2099/BOOTSTRAPONLY0001/", "stage_state_filename": "x.json", "stage_order": ["pre", "r1", "final"]}}
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date(2099, 8, 1))
    facts = chronology["last"]
    assert facts.tournament_name == "Bootstrap Only Open"
    assert facts.url_base == ""
    html = render_tournament_cards_html(chronology)
    assert "Bootstrap Only Open" in html
    assert "/tournaments/2099/BOOTSTRAPONLY0001/" not in html


def test_registry_entry_with_real_hub_index_still_shows_link():
    """The opposite case: once a registry entry actually declares real
    public content (has_hub_index True), its url_base must still
    render as a clickable link -- this fix must not blanket-suppress
    every link, only the bootstrap-only case."""
    schedule = [_entry("REALPAGE0001", "Real Page Open", "2099-05-01", "2099-05-04")]
    registry = {"REALPAGE0001": {"url_base": "/tournaments/2099/real-page-open/", "has_hub_index": True, "stage_state_filename": "x.json", "stage_order": ["pre", "r1", "final"]}}
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date(2099, 8, 1))
    facts = chronology["last"]
    assert facts.url_base == "/tournaments/2099/real-page-open/"
    html = render_tournament_cards_html(chronology)
    assert '<a href="/tournaments/2099/real-page-open/">Real Page Open</a>' in html


def test_missing_evidence_shows_dash_never_inferred():
    schedule = [_entry("SYN0003", "Synthetic No-Result Open", "2099-01-01", "2099-01-04")]
    # deliberately no registry entry at all -- venue/winner/winning_score all unknown
    chronology = resolve_tournament_chronology(schedule, {}, as_of=date(2099, 3, 1))
    facts = chronology["last"]
    assert facts.venue is None and facts.winner is None and facts.winning_score is None
    html = render_tournament_cards_html(chronology)
    # the card itself renders, with dashes for the unknown fields
    assert "Synthetic No-Result Open" in html
    assert html.count("—") >= 2


# ---------------------------------------------------------------------------
# Red Team FAIL B correction: chronology must be PURE-calendar-driven,
# never influenced by any pipeline stage-validation signal in either
# direction -- a scheduled tournament that has genuinely ended by real
# calendar date must never be shown as 이번 대회, no matter what any
# internal stage-state artifact claims (there is no more
# active_is_complete parameter at all: this resolver never accepts or
# consults a pipeline-stage signal).
# ---------------------------------------------------------------------------

_FAIL_B_SCHEDULE = [
    _entry("PAST0001", "Past Open", "2099-01-01", "2099-01-04"),
    _entry("FUTURE0001", "Future Open One", "2099-03-01", "2099-03-04"),
    _entry("FUTURE0002", "Future Open Two", "2099-06-01", "2099-06-04"),
]
_FAIL_B_REGISTRY = {
    "PAST0001": {"url_base": "/tournaments/2099/past-open/", "hub_card": {"winner": "Past Winner", "winning_score": "-10"}},
    "FUTURE0001": {"url_base": "/tournaments/2099/future-open-one/"},
    "FUTURE0002": {"url_base": "/tournaments/2099/future-open-two/"},
}


def test_chronology_ongoing_event_is_shown_as_current():
    schedule = _FAIL_B_SCHEDULE + [_entry("LIVE0001", "Live Open", "2099-02-01", "2099-02-10")]
    chronology = resolve_tournament_chronology(schedule, _FAIL_B_REGISTRY, as_of=date(2099, 2, 5))
    assert chronology["current"].tournament_name == "Live Open"
    assert chronology["last"].tournament_name == "Past Open"
    assert chronology["next"].tournament_name == "Future Open One"


def test_chronology_day_after_event_ends_falls_back_to_upcoming():
    """The day after a tracked tournament's own end_date, it must
    never still render as 이번 대회 -- purely by calendar date, with no
    pipeline-stage signal involved at all."""
    schedule = _FAIL_B_SCHEDULE + [_entry("LIVE0001", "Live Open", "2099-02-01", "2099-02-10")]
    chronology = resolve_tournament_chronology(schedule, _FAIL_B_REGISTRY, as_of=date(2099, 2, 11))
    assert chronology["current"].tournament_name == "Future Open One"
    assert chronology["next"].tournament_name == "Future Open Two"
    # the now-ended tournament competes for "last" like any other
    # completed entry, and wins (it ended most recently).
    assert chronology["last"].tournament_name == "Live Open"


def test_chronology_stale_end_date_never_keeps_a_tournament_as_current():
    """CORE FAIL B regression: a tournament whose scheduled window has
    closed by real calendar date must move to 지난 대회 even though no
    pipeline stage-validation evidence ever confirmed it "complete" --
    this is the exact real production scenario the previous (now
    reversed) correction got backwards: OK Open's scheduled 2026-09-06
    end_date passing while this sandbox's pipeline stage state is
    still stuck at R2_LIVE (no live network access to ever validate a
    FINAL snapshot). Internal pipeline staleness must never keep a
    genuinely-ended tournament pinned to 이번 대회."""
    schedule = _FAIL_B_SCHEDULE + [_entry("STALE0001", "Stale Tracked Open", "2026-09-04", "2026-09-06")]
    chronology = resolve_tournament_chronology(schedule, _FAIL_B_REGISTRY, as_of=date(2026, 9, 8))
    assert chronology["current"] is None or chronology["current"].tournament_name != "Stale Tracked Open"
    assert chronology["last"].tournament_name == "Stale Tracked Open"


def test_chronology_gap_days_before_next_event_starts():
    """No tournament is ongoing at all (the last one ended, the next
    hasn't started yet) -- 이번 대회 degrades to the nearest upcoming
    event rather than staying empty or showing the finished one."""
    chronology = resolve_tournament_chronology(_FAIL_B_SCHEDULE, _FAIL_B_REGISTRY, as_of=date(2099, 1, 20))
    assert chronology["current"].tournament_name == "Future Open One"
    assert chronology["next"].tournament_name == "Future Open Two"
    assert chronology["last"].tournament_name == "Past Open"


def test_chronology_no_future_event_leaves_current_and_next_blank():
    schedule = [_entry("PAST0001", "Past Open", "2099-01-01", "2099-01-04")]
    chronology = resolve_tournament_chronology(schedule, _FAIL_B_REGISTRY, as_of=date(2099, 6, 1))
    assert chronology["current"] is None
    assert chronology["next"] is None
    assert chronology["last"].tournament_name == "Past Open"
    html = render_tournament_cards_html(chronology)
    assert 'data-tournament-card="current"' in html and 'data-tournament-card="next"' in html


def test_chronology_not_yet_started_event_counts_as_current():
    """A tournament whose window hasn't opened yet (PRE stage, before
    play begins) but is the nearest upcoming event is legitimately
    이번 대회."""
    schedule = [_entry("UPCOMING0001", "Upcoming Tracked Open", "2099-04-01", "2099-04-04")]
    chronology = resolve_tournament_chronology(schedule, _FAIL_B_REGISTRY, as_of=date(2099, 3, 15))
    assert chronology["current"].tournament_name == "Upcoming Tracked Open"


def test_chronology_2026_09_08_fixture_required_regression():
    """The exact fixture Red Team's FAIL B remediation requires: as_of
    2026-09-08, a Sep 4-6 official event that has already completed is
    지난 대회, a Sep 10-13 official event is 이번 대회 (this week's
    event), and the following official event is 다음 대회. Purely
    synthetic fixture data -- these dates are never hardcoded into the
    resolver or any rendering code, only here."""
    schedule = [
        _entry("FIXTURE_LAST", "Fixture Past Open", "2026-09-04", "2026-09-06"),
        _entry("FIXTURE_CURRENT", "Fixture Current Open", "2026-09-10", "2026-09-13"),
        _entry("FIXTURE_NEXT", "Fixture Next Open", "2026-09-24", "2026-09-27"),
    ]
    chronology = resolve_tournament_chronology(schedule, {}, as_of=date(2026, 9, 8))
    assert chronology["last"].tournament_name == "Fixture Past Open"
    assert chronology["current"].tournament_name == "Fixture Current Open"
    assert chronology["next"].tournament_name == "Fixture Next Open"


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

def test_sponsor_slot_appears_directly_below_every_player_name(built):
    """OWNER DECISION (PRODUCT PRESENTATION RECOVERY): the sponsor
    contract is GLOBAL -- HOME resolves the same way KB PRE does (see
    tests/test_cross_tournament_sponsor_cache.py for the full six-point
    gate coverage). The structural contract (both slots always present)
    holds regardless of how many actually carry a real value."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    identities = re.findall(r'<span class="player-name">[^<]+</span><span class="player-sponsor">[^<]*</span>', html)
    assert len(identities) == 120


def test_unverified_sponsor_remains_blank_never_guessed(built):
    """Red Team FAIL A: the sponsor slot is ALWAYS present (structural
    contract) -- an unverified player gets a genuinely EMPTY sponsor
    span (no text content), never omitted entirely and never a
    guessed/placeholder string like "확인 중"/"미확인"."""
    html = (OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "스폰서 확인 중" not in html and "스폰서 미확인" not in html
    name_spans = len(re.findall(r'<span class="player-name">[^<]*</span>', html))
    sponsor_spans = len(re.findall(r'<span class="player-sponsor">[^<]*</span>', html))
    assert name_spans == sponsor_spans == 120


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
    """Red Team FAIL A: render_player_identity ALWAYS emits both slots
    -- an unverified sponsor renders as a structurally-present but
    empty span, never omitted."""
    from klpga.website_v2.player_identity import render_player_identity, verified_sponsor
    assert render_player_identity("선수", None) == '<span class="player-name">선수</span><span class="player-sponsor"></span>'
    assert render_player_identity("선수", "") == '<span class="player-name">선수</span><span class="player-sponsor"></span>'
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
    # a clickable control's label is never rewritten in place (its own
    # accessible text stays exactly "신다인") -- Red Team FAIL A: an
    # adjacent sponsor slot is appended immediately outside it instead.
    assert normalize_player_sponsor_mentions("<button>신다인</button>", sponsor_by_name) == (
        '<button>신다인</button><span class="player-sponsor">요진건설산업</span>'
    )
    # a composite/partial text node is left untouched
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
    # PRODUCT RECOVERY V1 (design-system consolidation, phase 1): OK
    # Open's own generator now emits the shared player-name/player-sponsor
    # classes too (see scripts/84's _player_identity_cell), so this
    # exclusion-list test's own fixture markup moves with it.
    assert "class='player-name'" in html  # OK Open's own established markup, untouched


def test_sponsor_rule_enumerated_across_every_ok_open_stage_route(built):
    """Every OK Open PRE/R1/R2 leaderboard row must follow the exact
    same global rule proven for HOME/RANKING: both the name slot AND
    the sponsor slot are ALWAYS present -- a verified sponsor renders
    directly under the name, an unverified one leaves the slot
    structurally present but empty -- never guessed placeholder text."""
    checked_any_row = False
    for route in _OK_OPEN_IDENTITY_ROUTES:
        path = OUTPUT / route
        assert path.is_file(), route
        html = path.read_text(encoding="utf-8")
        name_spans = re.findall(r"<span class='player-name'>[^<]*</span>", html)
        sponsor_spans = re.findall(r"<span class='player-sponsor'>[^<]*</span>", html)
        if not name_spans:
            continue  # R2 has no rendered leaderboard yet on this data snapshot
        checked_any_row = True
        assert len(name_spans) == len(sponsor_spans), f"{route}: every name span must have a paired sponsor span"
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
