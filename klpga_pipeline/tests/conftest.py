import builtins
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# QA HARD STOP remediation (test/build isolation): many tests deliberately
# call a real scripts/NN_....py build() function -- exercising the
# actual generated HTML rather than a mock -- and those build()
# functions write to their own module-level OUTPUT/OUT constant, which
# used to hardcode the real, git-tracked candidate/ directory. Running
# the suite therefore mutated tracked repository files every time (a
# fresh neo-build-id/neo-build-source-commit provenance stamp on every
# generated page, never real content -- see
# klpga.website_v2.global_navigation.inject_build_provenance -- but a
# real repository-hygiene defect regardless of how harmless the diff
# itself is).
#
# pytest_configure runs once per test session, before any test module
# (and therefore before any scripts/NN_....py the tests import) is
# collected -- setting KLPGA_CANDIDATE_ROOT_OVERRIDE here means every
# build script's own OUTPUT/OUT (resolved through
# klpga.tournament_context.candidate_dir(), not a hardcoded path)
# writes into this disposable temp directory instead, with zero
# per-test-file changes required. A real `python scripts/NN_....py`
# invocation outside pytest never sees this env var and is unaffected.
_CANDIDATE_ROOT_OVERRIDE = tempfile.mkdtemp(prefix="klpga-test-candidate-")


# ---------------------------------------------------------------------------
# Operational data protection rule (2026-10-02 mission): no pytest run may
# ever write to real production data. Added after pytest -m round_pipeline
# silently reverted the live content/website_v2/2026100005_LEADERBOARD.json
# back to stale R1-only data mid-session, because three tests called
# parse_leaderboard(1) against the real, shared LEADERBOARD_PATH with no
# isolation (fixed on its own in test_hitejinro_round_pipeline.py). That fix
# only protected the one function three tests happened to call -- this is
# the general-purpose version: a hard filesystem guard, installed for every
# test in the suite, that makes ANY write under content/website_v2/ (운영
# JSON, 운영 SQLite, Warehouse, Knowledge Engine, incoming_evidence -- every
# one of those already lives under this single real root; see
# klpga.neo_win.hitejinro_round_pipeline.CONTENT /
# klpga.tournament_context.CONTENT_DIR) raise immediately and fail the test,
# rather than relying on each test author remembering to redirect a path by
# hand. Reads are completely unaffected -- only a write (or a SQLite
# connection opened for anything but mode=ro) under that root is blocked.
# tmp_path (or any other Temporary Workspace outside content/website_v2/) is
# always allowed, with zero extra configuration, since it's simply never
# under the protected root to begin with.
# ---------------------------------------------------------------------------
_PROTECTED_ROOT = (Path(__file__).resolve().parents[1] / "content" / "website_v2").resolve()


class OperationalDataWriteBlocked(RuntimeError):
    """Raised instead of letting a test write to real production data."""


def _blocked_message(path, mode: str) -> str:
    return (
        f"BLOCKED (운영 데이터 보호 규칙): test attempted to write to real production "
        f"path {path} (mode={mode!r}). All test writes must go through tmp_path or "
        f"another Temporary Workspace -- 운영 JSON/SQLite/Warehouse/Knowledge Engine/"
        f"incoming_evidence under {_PROTECTED_ROOT} are read-only in pytest."
    )


def _is_protected(path_str: str) -> bool:
    try:
        resolved = Path(path_str).resolve()
    except (OSError, ValueError):
        return False
    return resolved == _PROTECTED_ROOT or _PROTECTED_ROOT in resolved.parents


_WRITE_MODE_CHARS = set("wax+")
_real_path_open = pathlib.Path.open
_real_builtin_open = builtins.open
_real_sqlite_connect = sqlite3.connect


def _guarded_path_open(self, mode="r", *args, **kwargs):
    if any(c in _WRITE_MODE_CHARS for c in mode) and _is_protected(str(self)):
        raise OperationalDataWriteBlocked(_blocked_message(self, mode))
    return _real_path_open(self, mode, *args, **kwargs)


def _guarded_builtin_open(file, mode="r", *args, **kwargs):
    if any(c in _WRITE_MODE_CHARS for c in mode) and isinstance(file, (str, os.PathLike)) and _is_protected(str(file)):
        raise OperationalDataWriteBlocked(_blocked_message(file, mode))
    return _real_builtin_open(file, mode, *args, **kwargs)


def _guarded_sqlite_connect(database, *args, **kwargs):
    db_str = str(database)
    is_read_only_uri = kwargs.get("uri", False) and "mode=ro" in db_str
    check_path = db_str.split("?", 1)[0] if kwargs.get("uri", False) else db_str
    if not is_read_only_uri and _is_protected(check_path):
        raise OperationalDataWriteBlocked(
            f"BLOCKED (운영 데이터 보호 규칙): test attempted to open real production "
            f"SQLite database {database} without mode=ro. All test writes must go "
            f"through tmp_path or another Temporary Workspace -- operational SQLite "
            f"files under {_PROTECTED_ROOT} are read-only in pytest."
        )
    return _real_sqlite_connect(database, *args, **kwargs)


def pytest_configure(config):
    os.environ["KLPGA_CANDIDATE_ROOT_OVERRIDE"] = _CANDIDATE_ROOT_OVERRIDE
    pathlib.Path.open = _guarded_path_open
    builtins.open = _guarded_builtin_open
    sqlite3.connect = _guarded_sqlite_connect


def pytest_unconfigure(config):
    os.environ.pop("KLPGA_CANDIDATE_ROOT_OVERRIDE", None)
    shutil.rmtree(_CANDIDATE_ROOT_OVERRIDE, ignore_errors=True)
    pathlib.Path.open = _real_path_open
    builtins.open = _real_builtin_open
    sqlite3.connect = _real_sqlite_connect
