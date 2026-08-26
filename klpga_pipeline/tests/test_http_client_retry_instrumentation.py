"""Tests for klpga.http_client's Phase B1.1 diagnostic addition: the
optional `on_retry` callback fired before each retry's backoff sleep.
No real network access — the session's `request` method is monkeypatched.
"""
from __future__ import annotations

import time

import pytest
import requests

from klpga.http_client import PoliteHttpClient, _before_sleep_log


class _FakeResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        pass


def test_on_retry_defaults_to_none_and_stays_silent(tmp_path):
    """Every existing caller of PoliteHttpClient never set on_retry —
    confirm the default is None so their behavior is completely
    unchanged by this addition."""
    client = PoliteHttpClient(cache_dir=tmp_path)
    assert client.on_retry is None


def test_before_sleep_log_calls_on_retry_with_a_useful_message():
    """Unit-level check of the message-building logic against a
    hand-built stub retry_state, independent of real retry timing."""
    calls = []

    class _FakeSelf:
        on_retry = staticmethod(lambda msg: calls.append(msg))

    class _FakeOutcome:
        def exception(self):
            return requests.exceptions.ConnectionError("boom")

    class _FakeNextAction:
        sleep = 4.2

    class _FakeRetryState:
        args = (_FakeSelf(),)
        outcome = _FakeOutcome()
        next_action = _FakeNextAction()
        attempt_number = 2

    _before_sleep_log(_FakeRetryState())
    assert len(calls) == 1
    assert "attempt 2 failed" in calls[0]
    assert "sleeping 4.2s" in calls[0]
    assert "ConnectionError" in calls[0]


def test_before_sleep_log_is_a_noop_when_on_retry_is_none():
    class _FakeSelf:
        on_retry = None

    class _FakeOutcome:
        def exception(self):
            return None

    class _FakeNextAction:
        sleep = 1.0

    class _FakeRetryState:
        args = (_FakeSelf(),)
        outcome = _FakeOutcome()
        next_action = _FakeNextAction()
        attempt_number = 1

    _before_sleep_log(_FakeRetryState())  # must not raise


def test_on_retry_fires_during_a_real_retry_cycle(tmp_path, monkeypatch):
    """Integration check: a client with on_retry set actually receives
    a callback when a request fails once (retryable) then succeeds —
    proves the callback is genuinely wired into the tenacity decorator,
    not just unit-testable in isolation. Sleep is patched away so this
    test runs instantly rather than waiting out the real ~2s backoff."""
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    calls = []
    client = PoliteHttpClient(cache_dir=tmp_path, on_retry=calls.append)

    attempts = {"count": 0}

    def fake_request(method, url, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise requests.exceptions.ConnectionError("simulated transient failure")
        return _FakeResponse()

    monkeypatch.setattr(client.session, "request", fake_request)

    resp = client._do_request("GET", "https://example.test/x")
    assert resp.status_code == 200
    assert attempts["count"] == 2
    assert len(calls) == 1
    assert "attempt 1 failed" in calls[0]


def test_on_retry_never_fires_for_a_blocked_401_403_429_response(tmp_path, monkeypatch):
    """RateLimitBlockedError is never retried — on_retry must not fire
    for it, since there is no retry/backoff sleep to report."""
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    calls = []
    client = PoliteHttpClient(cache_dir=tmp_path, on_retry=calls.append)
    monkeypatch.setattr(client.session, "request", lambda *a, **k: _FakeResponse(status_code=403))

    from klpga.http_client import RateLimitBlockedError

    with pytest.raises(RateLimitBlockedError):
        client._do_request("GET", "https://example.test/x")
    assert calls == []
