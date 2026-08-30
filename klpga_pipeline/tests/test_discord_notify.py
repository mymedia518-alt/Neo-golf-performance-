"""Tests for klpga.ops.discord_notify -- the optional Discord webhook
notification helper. It must never raise and never affect a caller's
exit code: a missing webhook is a silent no-op, and a network/HTTP
failure is caught and reported back as False.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from klpga.ops.discord_notify import ENV_VAR, send_discord_notification


def test_missing_webhook_is_noop(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with patch("klpga.ops.discord_notify.requests.post") as mock_post:
        result = send_discord_notification("hello", webhook_url=None)
    assert result is False
    mock_post.assert_not_called()


def test_empty_webhook_arg_is_noop(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://discord.example/should-not-be-used")
    with patch("klpga.ops.discord_notify.requests.post") as mock_post:
        result = send_discord_notification("hello", webhook_url="")
    assert result is False
    mock_post.assert_not_called()


def test_present_webhook_posts_expected_payload_and_returns_true(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    fake_response = MagicMock(status_code=204)
    with patch("klpga.ops.discord_notify.requests.post", return_value=fake_response) as mock_post:
        result = send_discord_notification("VERDICT: GO", webhook_url="https://discord.example/webhook", timeout=5.0)
    assert result is True
    mock_post.assert_called_once_with(
        "https://discord.example/webhook", json={"content": "VERDICT: GO"}, timeout=5.0
    )


def test_non_2xx_response_returns_false(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    fake_response = MagicMock(status_code=500)
    with patch("klpga.ops.discord_notify.requests.post", return_value=fake_response):
        result = send_discord_notification("hello", webhook_url="https://discord.example/webhook")
    assert result is False


def test_request_exception_is_caught_and_returns_false(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with patch(
        "klpga.ops.discord_notify.requests.post",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ):
        result = send_discord_notification("hello", webhook_url="https://discord.example/webhook")
    assert result is False


def test_env_var_used_when_arg_omitted(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://discord.example/from-env")
    fake_response = MagicMock(status_code=200)
    with patch("klpga.ops.discord_notify.requests.post", return_value=fake_response) as mock_post:
        result = send_discord_notification("hello")
    assert result is True
    args, kwargs = mock_post.call_args
    assert args[0] == "https://discord.example/from-env"
