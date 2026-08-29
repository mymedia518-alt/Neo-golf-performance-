"""Parser for the KLPGA player-profile page's team/sponsor ("소속") field.

Endpoint (reported, see klpga.collectors.player_profile and config.py's
PLAYER_PROFILE_ENDPOINT for the full provenance note):
  GET https://klpga.co.kr/web/profile/mainRecord?playerCode=<code>

CONFIRMED real markup (playerCode=11134, 서교림, pasted verbatim by the
user from a live Windows capture via scripts/53_fetch_player_profile_sample.py
— see tests/fixtures/player_profile_sample_11134.html):

    <div class="col-3">
        <label class="text-neongreen">소속</label>
        <h5 class="text-white">삼천리</h5>
    </div>

This is the ONLY structure this project has actually observed. The
extraction rule below only relies on the confirmed part of it — a
`<label>` tag whose text is exactly "소속", followed by the nearest
`<h5>` tag carrying the value — and deliberately does NOT depend on the
`col-3` / `text-neongreen` / `text-white` CSS classes, since those were
only seen once and generalizing from a single sample's styling classes
would itself be an unconfirmed assumption.

NOT yet confirmed by this project: the real markup for a player with NO
recorded team/sponsor (the "소속 없음" case) — i.e. whether the `<h5>`
is present-but-empty, absent entirely, or something else. Per this
project's provenance discipline, `parse_team_or_sponsor` returns an
empty string only when a `<label>` matching "소속" is found (so the page
matches the confirmed template) and the value it carries is blank —
never as a fallback for "couldn't find the expected structure at all",
which raises `PlayerProfileParseError` instead. A caller must not treat
those two outcomes as interchangeable.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

_TEAM_SPONSOR_LABEL = "소속"


class PlayerProfileParseError(ValueError):
    """Raised when the page does not match the confirmed structure at
    all (no `<label>소속</label>` found anywhere) — this is a parse
    failure, never to be confused with a real "no sponsor" result."""


def parse_team_or_sponsor(html: str) -> str:
    """Extract the 소속 (team/sponsor) value from a real player-profile
    page. Returns "" if the 소속 label is present but its value is
    blank (a real "no sponsor" result). Raises
    `PlayerProfileParseError` if no 소속 label is found anywhere on the
    page — this means the page did not match the one confirmed
    template and must not be silently treated as "no sponsor"."""
    soup = BeautifulSoup(html, "lxml")
    label = soup.find("label", string=lambda s: s is not None and s.strip() == _TEAM_SPONSOR_LABEL)
    if label is None:
        raise PlayerProfileParseError(
            f"Could not find a <label>{_TEAM_SPONSOR_LABEL}</label> anywhere in the page — "
            "player-profile page structure may not match the one confirmed sample "
            "(see tests/fixtures/player_profile_sample_11134.html)"
        )
    value_tag = label.find_next("h5")
    if value_tag is None:
        return ""
    return value_tag.get_text(strip=True)
