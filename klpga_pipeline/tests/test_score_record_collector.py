"""Tests for klpga.collectors.score_record -- fetch-only against the
real, URL-confirmed /web/tourRecord/scoreRecord endpoint. No parsing
logic exists yet (the page's DOM structure has not been confirmed
against real markup), so this only verifies the fetch call itself:
correct URL, correct (and ONLY) gameCode parameter, always-live (never
cached) fetch, real HTTP status + raw text returned unmodified, that a
real fetch failure propagates rather than being swallowed here, and
that the not-yet-implemented parser fails loudly and specifically
rather than silently guessing at markup it has never seen."""
from __future__ import annotations

import pytest

from klpga import config
from klpga.collectors.score_record import fetch_score_record_html, parse_score_record_html


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient.get_text_with_status."""

    def __init__(self, responses_by_key: dict[tuple, tuple[int, str]], error_keys: frozenset = frozenset()):
        self.responses_by_key = responses_by_key
        self.error_keys = error_keys
        self.calls: list[tuple] = []

    def get_text_with_status(self, url, params=None, **kwargs):
        key = (url, tuple(sorted((params or {}).items())))
        self.calls.append(key)
        if key in self.error_keys:
            raise ConnectionError(f"simulated real network failure for {key}")
        return self.responses_by_key[key]


def test_fetch_score_record_html_calls_confirmed_endpoint_with_only_game_code():
    key = (config.SCORE_RECORD_ENDPOINT, (("gameCode", "2026120001"),))
    client = FakeClient({key: (200, "<html>raw score record page</html>")})

    status, html = fetch_score_record_html(client, "2026120001")

    assert status == 200
    assert html == "<html>raw score record page</html>"
    assert client.calls == [key]


def test_fetch_score_record_html_returns_raw_text_unparsed():
    raw = "<html><body>whatever real markup the site sends</body></html>"
    key = (config.SCORE_RECORD_ENDPOINT, (("gameCode", "9999999999"),))
    client = FakeClient({key: (200, raw)})

    status, html = fetch_score_record_html(client, "9999999999")

    assert status == 200
    assert html == raw


def test_fetch_score_record_html_propagates_real_fetch_failures():
    key = (config.SCORE_RECORD_ENDPOINT, (("gameCode", "2026120001"),))
    client = FakeClient({}, error_keys=frozenset({key}))

    with pytest.raises(ConnectionError):
        fetch_score_record_html(client, "2026120001")


def test_parse_score_record_html_refuses_to_guess_at_unseen_markup():
    # This project never writes a parser against DOM structure it has
    # not actually seen -- see scripts/97_fetch_score_record_sample.py.
    # Any input, including well-formed-looking HTML, must raise the
    # same explicit NotImplementedError rather than silently returning
    # a plausible-looking but fabricated result.
    with pytest.raises(NotImplementedError) as exc:
        parse_score_record_html("<html><table><tr><td>박결</td><td>WD</td></tr></table></html>")
    assert "scripts/97_fetch_score_record_sample.py" in str(exc.value)
