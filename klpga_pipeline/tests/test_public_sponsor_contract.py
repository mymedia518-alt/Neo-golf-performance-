"""Red Team FAIL A regression coverage: the global sponsor-slot rule
(src/klpga/website_v2/player_identity.py) must hold for every public
player-identity display -- name slot + sponsor slot, both ALWAYS
present, never a guessed placeholder. Covers the shared unit contract
directly, then the full route family produced by scripts/88 (the
generator every public page family -- HOME, RANKING, deep-dive, KG
PRE/R1/R2/R3/FINAL, OK PRE/R1/R2/R3, including the orphaned/legacy OK
Open R3 copy that predates the sponsor-slot convention -- ultimately
traces back to)."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from klpga.website_v2.player_identity import normalize_player_sponsor_mentions, render_player_identity, verified_sponsor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"

_NAME_SPONSOR_PAIR = re.compile(
    r"<span class=(['\"])(?:player-name|player)\1>[^<>]*</span>"
    r"<span class=(['\"])(?:player-sponsor|sponsor)\2>[^<>]*</span>"
)


def test_render_player_identity_always_emits_both_slots():
    assert render_player_identity("홍길동", None) == '<span class="player-name">홍길동</span><span class="player-sponsor"></span>'
    assert render_player_identity("홍길동", "삼성") == '<span class="player-name">홍길동</span><span class="player-sponsor">삼성</span>'


def test_render_player_identity_never_guesses_placeholder_text():
    html = render_player_identity("홍길동", None)
    for forbidden in ("미확인", "확인 중", "—"):
        assert forbidden not in html.split("player-sponsor")[1]


def test_verified_sponsor_gates_on_identity_validation_pass():
    assert verified_sponsor({"identity_validation": "PASS", "current_official_sponsor": "삼성"}) == "삼성"
    assert verified_sponsor({"identity_validation": "PENDING", "current_official_sponsor": "삼성"}) is None
    assert verified_sponsor({"identity_validation": "PASS", "current_official_sponsor": ""}) is None


def test_normalizer_repairs_incomplete_legacy_name_span():
    """The exact bug this test guards against: an orphaned/no-longer-
    regenerated page (OK Open's markup convention) with a bare name
    span and NO sponsor sibling at all must still get the sponsor slot
    appended -- a name span merely carrying the right CSS class is not
    by itself "already compliant"."""
    html = "<li><span class='player'>최예림</span></li>"
    out = normalize_player_sponsor_mentions(html, {"최예림": "휴온스"}, known_names={"최예림"})
    assert out == "<li><span class='player'>최예림</span><span class='sponsor'>휴온스</span></li>"


def test_normalizer_never_double_wraps_already_complete_markup():
    html = '<span class="player-name">서교림</span><span class="player-sponsor"></span>'
    out = normalize_player_sponsor_mentions(html, {}, known_names={"서교림"})
    assert out == html
    assert out.count("player-sponsor") == 1


def test_normalizer_adds_adjacent_slot_outside_button_without_corrupting_it():
    html = '<button type="button" class="player-name-btn" data-player-code="1">노승희</button>'
    out = normalize_player_sponsor_mentions(html, {"노승희": "리쥬란"}, known_names={"노승희"})
    assert out == '<button type="button" class="player-name-btn" data-player-code="1">노승희</button><span class="player-sponsor">리쥬란</span>'
    # idempotent: re-running never double-appends a second sponsor span
    assert normalize_player_sponsor_mentions(out, {"노승희": "리쥬란"}, known_names={"노승희"}) == out


@pytest.fixture(scope="module")
def built():
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("sponsor_contract_top120_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


_ROUTE_FAMILIES = (
    "index.html",
    "ranking/index.html",
    "deep-dive/index.html",
    "tournaments/2026/kg-ladies-open/pre/index.html",
    "tournaments/2026/kg-ladies-open/r1/index.html",
    "tournaments/2026/kg-ladies-open/r2/index.html",
    "tournaments/2026/kg-ladies-open/r3/index.html",
    "tournaments/2026/kg-ladies-open/final/index.html",
    "tournaments/2026/ok-savings-bank-open/pre/index.html",
    "tournaments/2026/ok-savings-bank-open/r1/index.html",
    "tournaments/2026/ok-savings-bank-open/r2/index.html",
    "tournaments/2026/ok-savings-bank-open/r3/index.html",
    "archive/beta001/r1/index.html",
    "archive/beta001/r2/index.html",
    "archive/beta001/r3/index.html",
)


@pytest.mark.parametrize("route", _ROUTE_FAMILIES)
def test_every_public_page_family_has_at_least_one_two_slot_identity(built, route):
    page = OUTPUT / route
    assert page.is_file(), f"missing route: {route}"
    html = page.read_text(encoding="utf-8")
    assert _NAME_SPONSOR_PAIR.search(html), f"{route}: no complete name+sponsor slot pair found"


def test_every_public_page_family_has_no_orphaned_name_only_span(built):
    """Guards the specific regression this suite was written for: a
    name span (player or player-name convention) NOT immediately
    followed by its sponsor sibling must never survive into a
    generated public route."""
    orphan_re = re.compile(
        r"<span class=(['\"])(?:player-name|player)\1>[^<>]*</span>"
        r"(?!<span class=(?:\"player-sponsor\"|'player-sponsor'|\"sponsor\"|'sponsor'))"
    )
    for route in _ROUTE_FAMILIES:
        html = (OUTPUT / route).read_text(encoding="utf-8")
        match = orphan_re.search(html)
        assert not match, f"{route}: orphaned name-only span with no sponsor slot: {match.group(0) if match else None}"
