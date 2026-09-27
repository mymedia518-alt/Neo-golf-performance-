"""Tests for klpga.collectors.tournament_record -- fetch-only against
the UNCONFIRMED /web/tourRecord/mainRecord?gameCode=<code> endpoint
named in the RED TEAM mission (2026-09-25). No parsing logic exists yet
(the endpoint itself has never been confirmed to exist or return
technical stats), so this only verifies the fetch call's shape: correct
URL, correct (and ONLY) gameCode parameter, always-live fetch, real
status + raw text returned unmodified, a real fetch failure propagating
rather than being swallowed, and the not-yet-implemented parser failing
loudly rather than guessing at markup nobody has seen."""
from __future__ import annotations

import pytest

from klpga import config
from klpga.collectors.tournament_record import fetch_tournament_record_html, parse_tournament_record_html


class FakeClient:
    def __init__(self, responses_by_key: dict, error_keys: frozenset = frozenset()):
        self.responses_by_key = responses_by_key
        self.error_keys = error_keys
        self.calls: list = []

    def get_text_with_status(self, url, params=None, **kwargs):
        key = (url, tuple(sorted((params or {}).items())))
        self.calls.append(key)
        if key in self.error_keys:
            raise ConnectionError(f"simulated real network failure for {key}")
        return self.responses_by_key[key]


def test_fetch_tournament_record_html_calls_the_unconfirmed_endpoint_with_only_game_code():
    key = (config.TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED, (("gameCode", "2026120001"),))
    client = FakeClient({key: (200, "<html>raw tourRecord/mainRecord page</html>")})

    status, html = fetch_tournament_record_html(client, "2026120001")

    assert status == 200
    assert html == "<html>raw tourRecord/mainRecord page</html>"
    assert client.calls == [key]


def test_fetch_tournament_record_html_returns_raw_text_unparsed():
    raw = "<html><body>whatever real markup the site sends, if anything</body></html>"
    key = (config.TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED, (("gameCode", "9999999999"),))
    client = FakeClient({key: (200, raw)})

    status, html = fetch_tournament_record_html(client, "9999999999")

    assert status == 200
    assert html == raw


def test_fetch_tournament_record_html_propagates_real_fetch_failures():
    key = (config.TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED, (("gameCode", "2026120001"),))
    client = FakeClient({}, error_keys=frozenset({key}))

    with pytest.raises(ConnectionError):
        fetch_tournament_record_html(client, "2026120001")


def test_fetch_tournament_record_html_is_generic_over_any_game_code():
    """RED TEAM mission: 'Do not patch player 10097 manually. Design a
    generic collector.' -- proven here by calling the SAME function
    across several distinct real game_codes already known to this
    project, with no per-tournament branching in the collector itself."""
    codes = ["2026080001", "2026090002", "2026090003", "2026120001"]
    responses = {
        (config.TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED, (("gameCode", c),)): (200, f"<html>{c}</html>")
        for c in codes
    }
    client = FakeClient(responses)
    for c in codes:
        status, html = fetch_tournament_record_html(client, c)
        assert status == 200
        assert c in html


def test_parse_tournament_record_html_rejects_unseen_markup():
    # No real sample of this page has ever been captured -- this
    # project never writes a parser against guessed DOM structure.
    with pytest.raises(NotImplementedError):
        parse_tournament_record_html(
            "<html><table><tr><td>박결</td><td>247.5</td></tr></table></html>",
            player_code="10097",
        )
