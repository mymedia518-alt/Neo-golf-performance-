"""Batch collector: real KLPGA player-profile fetch + parse for every
player in a roster, producing a validated (player_code, player_name,
team_or_sponsor) result per player.

Built on the already-confirmed pieces:
  - klpga.collectors.player_profile.fetch_player_profile_html — the
    fetch-only adapter for the reported PLAYER_PROFILE_ENDPOINT
  - klpga.parsers.player_profile_parser.parse_team_or_sponsor — the
    소속 extractor, built against the one real captured fragment
    (playerCode=11134, 서교림 → 삼천리) and now cross-confirmed live
    on Windows for playerCode=9788 (박혜준 → 두산건설 We've) too

Every player result is one of exactly three outcomes, never blended:
  - FETCH FAILURE — the HTTP call itself failed (network error, a
    non-2xx status via PoliteHttpClient's normal error propagation)
  - IDENTITY FAILURE — the fetch succeeded but the roster's expected
    player_name does not appear anywhere in the returned page; this
    project has a documented history of a real player_code typo
    (김나영: 11014 vs the correct 10114) reaching this point
    undetected, so this check is never skipped
  - PARSE FAILURE — the fetch and identity check succeeded, but
    parse_team_or_sponsor raised PlayerProfileParseError (the page did
    not carry a `소속` label at all — a structural mismatch from the
    one confirmed template)
  - OK — team_or_sponsor holds the real extracted value, which may
    legitimately be "" (label present, value blank — a genuine "no
    sponsor" result, never to be confused with any of the three
    failure modes above)

A HARD FAIL for even one player (a FETCH/IDENTITY/PARSE failure) means
this module's caller must not silently substitute an empty string for
that player or otherwise disguise the failure — see
scripts/56_collect_player_team_sponsor.py, which refuses to write the
final output CSV unless every roster player reached OK.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from klpga.collectors.player_profile import fetch_player_profile_html
from klpga.http_client import PoliteHttpClient
from klpga.parsers.player_profile_parser import (
    PlayerProfileParseError,
    parse_team_or_sponsor,
)

# See docs/KLPGA_OFFICIAL_DATA_MAP.md and this project's own commit
# history: playerCode=10114 is the confirmed correct code for 김나영;
# 11014 (a digit transposition) was a real, previously-caught typo.
# This is not a general rule about any player — just a specific,
# documented land mine this collector refuses to walk past silently.
_KNOWN_IDENTITY_LANDMINES: dict[str, str] = {
    "김나영": "10114",
}


class RosterIntegrityError(ValueError):
    """Raised for a roster-level problem (duplicates, a known
    identity-landmine mismatch) BEFORE any network call is made."""


@dataclass
class PlayerCollectionResult:
    player_code: str
    player_name: str
    outcome: str
    """One of 'OK', 'FETCH_FAILURE', 'IDENTITY_FAILURE', 'PARSE_FAILURE'."""
    team_or_sponsor: Optional[str] = None
    """Only meaningful when outcome == 'OK'. Never set for a failure
    outcome — a failure must never be represented as an empty string."""
    raw_html: Optional[str] = None
    """The real fetched page text, present whenever the fetch itself
    succeeded (OK, IDENTITY_FAILURE, or PARSE_FAILURE outcomes) so a
    caller can preserve it as evidence even for a failed player."""
    detail: str = ""


def validate_roster(roster: list[tuple[str, str]]) -> None:
    """Raises RosterIntegrityError for duplicate player_code, duplicate
    player_name, or a known identity-landmine mismatch. Call this
    BEFORE making any network request."""
    codes = [code for code, _ in roster]
    names = [name for _, name in roster]

    dup_codes = {c for c in codes if codes.count(c) > 1}
    dup_names = {n for n in names if names.count(n) > 1}
    if dup_codes or dup_names:
        raise RosterIntegrityError(
            f"Duplicate player_code(s) {sorted(dup_codes)} or player_name(s) "
            f"{sorted(dup_names)} in roster — refusing to collect."
        )

    for code, name in roster:
        expected_code = _KNOWN_IDENTITY_LANDMINES.get(name)
        if expected_code is not None and code != expected_code:
            raise RosterIntegrityError(
                f"{name}'s roster player_code is {code!r}, expected {expected_code!r} "
                "(documented identity-landmine player) — refusing to collect."
            )


def collect_one(client: PoliteHttpClient, player_code: str, player_name: str) -> PlayerCollectionResult:
    try:
        _status, html = fetch_player_profile_html(client, player_code)
    except Exception as exc:  # a real fetch failure must propagate as a result, not crash the batch
        return PlayerCollectionResult(
            player_code=player_code,
            player_name=player_name,
            outcome="FETCH_FAILURE",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if player_name not in html:
        return PlayerCollectionResult(
            player_code=player_code,
            player_name=player_name,
            outcome="IDENTITY_FAILURE",
            raw_html=html,
            detail=f"expected name {player_name!r} not found anywhere in the fetched page",
        )

    try:
        sponsor = parse_team_or_sponsor(html)
    except PlayerProfileParseError as exc:
        return PlayerCollectionResult(
            player_code=player_code,
            player_name=player_name,
            outcome="PARSE_FAILURE",
            raw_html=html,
            detail=str(exc),
        )

    return PlayerCollectionResult(
        player_code=player_code,
        player_name=player_name,
        outcome="OK",
        team_or_sponsor=sponsor,
        raw_html=html,
    )


def collect_roster(client: PoliteHttpClient, roster: list[tuple[str, str]]) -> list[PlayerCollectionResult]:
    """Validates the roster (raises RosterIntegrityError on any
    problem, before any network call), then collects every player
    independently — one player's failure never aborts the rest, so a
    single run surfaces the full set of problems at once."""
    validate_roster(roster)
    return [collect_one(client, code, name) for code, name in roster]
