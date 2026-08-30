"""Tests for klpga.ops.paths -- the CODE ROOT / DATA ROOT resolver
NEO AUTO OPS uses so the exact same worktree checkout can run against
either its own repo-local data/ directory (default, backward
compatible) or one external, canonical NEO_DATA_ROOT directory.
"""
from __future__ import annotations

from pathlib import Path

from klpga.ops import paths


def test_code_root_is_the_klpga_pipeline_checkout():
    assert paths.code_root().name == "klpga_pipeline"
    assert (paths.code_root() / "src" / "klpga").is_dir()


def test_data_root_defaults_to_code_root_data_when_unset():
    assert paths.data_root(env={}) == paths.code_root() / "data"


def test_data_root_defaults_when_env_var_empty_string():
    assert paths.data_root(env={paths.ENV_VAR: ""}) == paths.code_root() / "data"


def test_data_root_defaults_when_env_var_whitespace_only():
    assert paths.data_root(env={paths.ENV_VAR: "   "}) == paths.code_root() / "data"


def test_data_root_honors_external_override():
    external = "/mnt/external/neo_data"
    assert paths.data_root(env={paths.ENV_VAR: external}) == Path(external)


def test_db_path_derived_from_data_root_default():
    assert paths.db_path(env={}) == paths.code_root() / "data" / "klpga.sqlite"


def test_db_path_derived_from_data_root_override():
    assert paths.db_path(env={paths.ENV_VAR: "/mnt/external"}) == Path("/mnt/external/klpga.sqlite")


def test_cache_dir_derived_from_data_root_default():
    assert paths.cache_dir(env={}) == paths.code_root() / "data" / "raw_cache" / "http"


def test_cache_dir_derived_from_data_root_override():
    assert paths.cache_dir(env={paths.ENV_VAR: "/mnt/external"}) == Path("/mnt/external/raw_cache/http")


def test_roster_dir_derived_from_data_root_default():
    assert paths.roster_dir(env={}) == paths.code_root() / "data" / "roster"


def test_roster_dir_derived_from_data_root_override():
    assert paths.roster_dir(env={paths.ENV_VAR: "/mnt/external"}) == Path("/mnt/external/roster")


def test_functions_read_real_os_environ_when_no_env_arg_given(monkeypatch):
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    assert paths.data_root() == paths.code_root() / "data"

    monkeypatch.setenv(paths.ENV_VAR, "/mnt/external/neo_data")
    assert paths.data_root() == Path("/mnt/external/neo_data")
    assert paths.db_path() == Path("/mnt/external/neo_data/klpga.sqlite")
