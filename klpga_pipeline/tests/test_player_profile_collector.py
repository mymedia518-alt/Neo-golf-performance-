"""Tests for klpga.collectors.player_profile — fetch-only against the
reported (not yet independently confirmed) /web/profile/mainRecord
endpoint. No parsing logic exists yet (the page's DOM structure has
not been confirmed against real markup), so this only verifies the
fetch call itself: correct URL, correct (and ONLY) playerCode
parameter, always-live (never cached) fetch, real HTTP status + raw
text returned unmodified, and that a real fetch failure propagates
rather than being swallowed here."""
from __future__ import annotations

import pytest

from klpga import config
from klpga.collectors.player_profile import fetch_player_profile_html


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


def test_fetch_player_profile_html_calls_reported_endpoint_with_only_player_code():
    key = (config.PLAYER_PROFILE_ENDPOINT, (("playerCode", "9788"),))
    client = FakeClient({key: (200, "<html>raw profile page</html>")})

    status, html = fetch_player_profile_html(client, "9788")

    assert status == 200
    assert html == "<html>raw profile page</html>"
    assert client.calls == [key]


def test_fetch_player_profile_html_returns_raw_text_unparsed():
    """No fields are extracted — the raw HTML comes back exactly as
    the site returned it, byte for byte, alongside its real status."""
    raw = "<html><body>whatever real markup the site sends</body></html>"
    key = (config.PLAYER_PROFILE_ENDPOINT, (("playerCode", "11134"),))
    client = FakeClient({key: (200, raw)})

    status, html = fetch_player_profile_html(client, "11134")

    assert status == 200
    assert html == raw


def test_fetch_player_profile_html_propagates_real_fetch_failures():
    """A real network/HTTP failure must never be swallowed here — the
    caller (the diagnostic script) is responsible for failing loudly
    rather than silently continuing with no evidence."""
    key = (config.PLAYER_PROFILE_ENDPOINT, (("playerCode", "9788"),))
    client = FakeClient({}, error_keys=frozenset({key}))

    with pytest.raises(ConnectionError):
        fetch_player_profile_html(client, "9788")
