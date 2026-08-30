"""Canonical CODE/DATA path resolution for NEO AUTO OPS.

CODE ROOT is always the current Git worktree's klpga_pipeline/
directory -- wherever it happens to be checked out (any clone, any
worktree). DATA ROOT is the ONE canonical location that holds mutable
operational data required for a live FINAL CLOSE run:
    - klpga.sqlite            (db_path)
    - raw_cache/http/         (cache_dir)
    - roster/                 (roster_dir)

By default DATA ROOT is CODE ROOT/data -- today's existing,
repository-local behavior, fully backward compatible. When the
NEO_DATA_ROOT environment variable is set, every path above resolves
from THAT directory instead, so the exact same code and the exact
same worktree checkout can run against one canonical, gitignored data
directory regardless of where the code itself was cloned.

This module never copies, creates, or modifies anything -- it is pure
path arithmetic. It also never decides where AUTO OPS's own outputs
(outputs/neo_ops/...) go: those intentionally stay tied to the
worktree that produced them (see scripts/neo_ops.py), never to
DATA ROOT, so a run's console log/JSON summary always lives next to
the code that produced it, not inside the shared production data
directory.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ENV_VAR = "NEO_DATA_ROOT"


def code_root() -> Path:
    """The klpga_pipeline/ directory of the current Git worktree."""
    return Path(__file__).resolve().parents[3]


def data_root(env: Optional[dict] = None) -> Path:
    """NEO_DATA_ROOT if set (non-empty) -- otherwise CODE_ROOT/data,
    which is the pre-existing, backward-compatible default."""
    source = env if env is not None else os.environ
    override = (source.get(ENV_VAR) or "").strip()
    if override:
        return Path(override)
    return code_root() / "data"


def db_path(env: Optional[dict] = None) -> Path:
    return data_root(env) / "klpga.sqlite"


def cache_dir(env: Optional[dict] = None) -> Path:
    return data_root(env) / "raw_cache" / "http"


def roster_dir(env: Optional[dict] = None) -> Path:
    return data_root(env) / "roster"
