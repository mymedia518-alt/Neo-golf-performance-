"""Placeholder interface for an automated Claude Code exception-agent
invocation on a WARN/HARD_STOP NEO ops result.

PREPARED, NOT ENABLED — per explicit instruction, this module
intentionally implements no real invocation mechanism yet. Calling
`trigger_exception_agent` only reports whether the interface is
enabled; it never spawns a process, opens a session, or contacts
anything, even when "enabled". This exists so the CALL SITE
(scripts/neo_ops.py) and the on/off switch (an environment variable)
are already wired up, and a real implementation can be dropped in
later without touching neo_ops.py again.

Gated behind NEO_ENABLE_EXCEPTION_AGENT so this module's mere
existence in the codebase can never accidentally activate anything —
the environment variable must be explicitly set truthy, and even then
the result is NOT_IMPLEMENTED, not a real invocation.
"""
from __future__ import annotations

import os

ENV_VAR = "NEO_ENABLE_EXCEPTION_AGENT"

STATUS_DISABLED = "DISABLED"
STATUS_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


def exception_agent_enabled(env: dict | None = None) -> bool:
    source = env if env is not None else os.environ
    return source.get(ENV_VAR, "").strip().lower() in ("1", "true", "yes")


def trigger_exception_agent(verdict: str, summary: dict) -> str:
    """Never raises. Returns STATUS_DISABLED when
    NEO_ENABLE_EXCEPTION_AGENT is not set truthy (the default) —
    otherwise STATUS_NOT_IMPLEMENTED, since no real agent invocation
    exists yet. `verdict`/`summary` are accepted now so the eventual
    real implementation's signature is already the call site's
    contract, but neither is used by this stub."""
    if not exception_agent_enabled():
        return STATUS_DISABLED
    return STATUS_NOT_IMPLEMENTED
