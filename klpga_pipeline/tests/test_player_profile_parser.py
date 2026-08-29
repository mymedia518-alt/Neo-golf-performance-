"""Tests for klpga.parsers.player_profile_parser.

test_parse_team_or_sponsor_from_real_capture is the load-bearing test:
it runs against tests/fixtures/player_profile_sample_11134.html, the
REAL markup fragment for playerCode=11134 (서교림) pasted verbatim by
the project owner from a live Windows execution against
klpga.co.kr — not a synthetic/guessed fixture.

The remaining tests are synthetic edge-case coverage for the parser's
own control flow (missing label vs. present-but-empty value). They do
NOT claim to represent real KLPGA markup for those cases — this
project has not observed a real "no sponsor" profile page yet — they
only verify this parser's documented, deliberate distinction between
"structure not found" (raises) and "structure found, value blank"
(returns "")."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.parsers.player_profile_parser import (
    PlayerProfileParseError,
    parse_team_or_sponsor,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "player_profile_sample_11134.html"


@pytest.fixture()
def real_sample_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parse_team_or_sponsor_from_real_capture(real_sample_html):
    assert parse_team_or_sponsor(real_sample_html) == "삼천리"


def test_raises_when_label_missing_entirely():
    """A page with no 소속 label at all does not match the one
    confirmed template — this must be a loud failure, never silently
    treated as 'no sponsor'."""
    html = "<html><body><div class='col-3'><label>다른 필드</label><h5>값</h5></div></body></html>"
    with pytest.raises(PlayerProfileParseError):
        parse_team_or_sponsor(html)


def test_returns_empty_string_when_label_present_but_value_blank():
    html = "<html><body><div class='col-3'><label>소속</label><h5 class='text-white'></h5></div></body></html>"
    assert parse_team_or_sponsor(html) == ""


def test_returns_empty_string_when_label_present_with_no_following_h5():
    html = "<html><body><div class='col-3'><label>소속</label></div></body></html>"
    assert parse_team_or_sponsor(html) == ""


def test_does_not_depend_on_the_single_sample_css_classes():
    """The real sample happened to use class='text-neongreen'/'text-white',
    but the extraction rule only relies on the <label>소속</label> ->
    next <h5> relationship, not on those specific classes (generalizing
    from one sample's styling would itself be an unconfirmed
    assumption)."""
    html = "<html><body><div><label>소속</label><h5>두산건설 We&#8217;ve</h5></div></body></html>"
    assert parse_team_or_sponsor(html) == "두산건설 We’ve"
