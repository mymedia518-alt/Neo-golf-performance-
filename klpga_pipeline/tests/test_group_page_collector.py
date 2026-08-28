"""Tests for klpga.collectors.group_page — fetch-only against the real,
confirmed /web/tourInfo/group endpoint. No parsing logic exists yet
(the page's DOM structure has not been confirmed against real markup),
so this only verifies the fetch call itself: correct URL, correct
(and ONLY) gameCode parameter, always-live (never cached) fetch,
real HTTP status + raw text returned unmodified, and that a real
fetch failure propagates rather than being swallowed here."""
from __future__ import annotations

import pytest

from klpga import config
from klpga.collectors.group_page import fetch_group_page_html


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


def test_fetch_group_page_html_calls_confirmed_endpoint_with_only_game_code():
    key = (config.GROUP_PAGE_ENDPOINT, (("gameCode", "2026080001"),))
    client = FakeClient({key: (200, "<html>raw group page</html>")})

    status, html = fetch_group_page_html(client, "2026080001")

    assert status == 200
    assert html == "<html>raw group page</html>"
    assert client.calls == [key]


def test_fetch_group_page_html_returns_raw_text_unparsed():
    """No fields are extracted — the raw HTML comes back exactly as
    the site returned it, byte for byte, alongside its real status."""
    raw = "<html><body>whatever real markup the site sends</body></html>"
    key = (config.GROUP_PAGE_ENDPOINT, (("gameCode", "9999999999"),))
    client = FakeClient({key: (200, raw)})

    status, html = fetch_group_page_html(client, "9999999999")

    assert status == 200
    assert html == raw


def test_fetch_group_page_html_propagates_real_fetch_failures():
    """A real network/HTTP failure must never be swallowed here — the
    caller (the diagnostic script) is responsible for failing loudly
    rather than silently continuing with no Round 3 evidence."""
    key = (config.GROUP_PAGE_ENDPOINT, (("gameCode", "2026080001"),))
    client = FakeClient({}, error_keys=frozenset({key}))

    with pytest.raises(ConnectionError):
        fetch_group_page_html(client, "2026080001")
