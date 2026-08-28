"""Tests for klpga.collectors.group_page — fetch-only against the real,
confirmed /web/tourInfo/group endpoint. No parsing logic exists yet
(the page's DOM structure has not been confirmed against real markup),
so this only verifies the fetch call itself: correct URL, correct
(and ONLY) gameCode parameter, raw text returned unmodified."""
from __future__ import annotations

from klpga import config
from klpga.collectors.group_page import fetch_group_page_html


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient.get_text — mirrors the
    FakeClient pattern used across the other collector tests."""

    def __init__(self, html_by_key: dict[tuple, str]):
        self.html_by_key = html_by_key
        self.calls: list[tuple] = []

    def get_text(self, url, params=None, **kwargs):
        key = (url, tuple(sorted((params or {}).items())))
        self.calls.append(key)
        return self.html_by_key[key]


def test_fetch_group_page_html_calls_confirmed_endpoint_with_only_game_code():
    key = (config.GROUP_PAGE_ENDPOINT, (("gameCode", "2026080001"),))
    client = FakeClient({key: "<html>raw group page</html>"})

    html = fetch_group_page_html(client, "2026080001")

    assert html == "<html>raw group page</html>"
    assert client.calls == [key]


def test_fetch_group_page_html_returns_raw_text_unparsed():
    """No fields are extracted — the raw HTML comes back exactly as
    the site returned it, byte for byte."""
    raw = "<html><body>whatever real markup the site sends</body></html>"
    key = (config.GROUP_PAGE_ENDPOINT, (("gameCode", "9999999999"),))
    client = FakeClient({key: raw})

    html = fetch_group_page_html(client, "9999999999")

    assert html == raw
