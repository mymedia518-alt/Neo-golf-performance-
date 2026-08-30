"""Tests for klpga.ops.exception_agent -- a PREPARED, NOT ENABLED
interface. Even when explicitly enabled via NEO_ENABLE_EXCEPTION_AGENT,
trigger_exception_agent must never do more than report
NOT_IMPLEMENTED -- it must never actually invoke anything.
"""
from __future__ import annotations

from klpga.ops.exception_agent import (
    ENV_VAR,
    STATUS_DISABLED,
    STATUS_NOT_IMPLEMENTED,
    exception_agent_enabled,
    trigger_exception_agent,
)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert exception_agent_enabled() is False
    assert trigger_exception_agent("WARN", {}) == STATUS_DISABLED


def test_enabled_via_env_var_still_not_implemented(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "true")
    assert exception_agent_enabled() is True
    assert trigger_exception_agent("HARD_STOP", {"hard_stop_reasons": ["x"]}) == STATUS_NOT_IMPLEMENTED


def test_enabled_accepts_1_and_yes(monkeypatch):
    for value in ("1", "yes", "YES", "True"):
        monkeypatch.setenv(ENV_VAR, value)
        assert exception_agent_enabled() is True


def test_falsey_values_stay_disabled(monkeypatch):
    for value in ("0", "false", "no", ""):
        monkeypatch.setenv(ENV_VAR, value)
        assert exception_agent_enabled() is False
        assert trigger_exception_agent("WARN", {}) == STATUS_DISABLED


def test_explicit_env_dict_overrides_os_environ(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert exception_agent_enabled(env={ENV_VAR: "true"}) is True
    assert exception_agent_enabled(env={}) is False
