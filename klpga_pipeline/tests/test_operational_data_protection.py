"""Regression for the 운영 데이터 보호 규칙 (2026-10-02 mission): the
global production-write guard installed in tests/conftest.py's
pytest_configure. Exercises the guard itself, not any one pipeline --
these tests would catch a regression in the guard mechanism even if
every other test file in this suite were deleted.

Background: three tests in test_hitejinro_round_pipeline.py used to
call parse_leaderboard(1) against the real, shared, production
LEADERBOARD_PATH with no isolation. Harmless while R1 was the only real
round ever written there, but running pytest -m round_pipeline for
verification during real R2 work silently reverted the live file back
to stale R1-only data. That incident is fixed at its one call site; this
file guards against the SAME class of mistake anywhere, present or
future, in any test.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.conftest import OperationalDataWriteBlocked, _PROTECTED_ROOT

pytestmark = pytest.mark.round_pipeline

# A path under the real protected root that is never a real tracked
# file -- used only to prove the guard fires before any bytes would
# have been written, never to actually touch real content.
_CANARY_JSON = _PROTECTED_ROOT / "__operational_data_protection_canary__.json"
_CANARY_SQLITE = _PROTECTED_ROOT / "__operational_data_protection_canary__.sqlite"


def test_protected_root_is_the_real_content_directory():
    """Sanity check on the guard's own scope: covers 운영 JSON/SQLite/
    Warehouse/Knowledge Engine/incoming_evidence, which all really do
    live under this one root."""
    assert _PROTECTED_ROOT.name == "website_v2"
    assert _PROTECTED_ROOT.is_dir()
    for subdir in ("knowledge_engine", "incoming_evidence"):
        assert (_PROTECTED_ROOT / subdir).exists(), (
            f"{subdir} not found under {_PROTECTED_ROOT} -- protected-root assumption is stale"
        )


def test_path_write_text_to_protected_root_is_blocked():
    assert not _CANARY_JSON.exists(), "canary file should never actually exist -- test setup is wrong if it does"
    with pytest.raises(OperationalDataWriteBlocked, match="운영 데이터 보호 규칙"):
        _CANARY_JSON.write_text("{}", encoding="utf-8")
    assert not _CANARY_JSON.exists(), "the guard must block the write BEFORE any byte reaches disk"


def test_path_open_write_mode_to_protected_root_is_blocked():
    with pytest.raises(OperationalDataWriteBlocked):
        _CANARY_JSON.open("w", encoding="utf-8")
    assert not _CANARY_JSON.exists()


def test_builtin_open_write_mode_to_protected_root_is_blocked():
    with pytest.raises(OperationalDataWriteBlocked):
        open(str(_CANARY_JSON), "w", encoding="utf-8")
    assert not _CANARY_JSON.exists()


def test_sqlite_connect_to_protected_root_without_read_only_is_blocked():
    assert not _CANARY_SQLITE.exists()
    with pytest.raises(OperationalDataWriteBlocked):
        sqlite3.connect(str(_CANARY_SQLITE))
    assert not _CANARY_SQLITE.exists()


def test_a_real_existing_production_file_cannot_be_overwritten():
    """The exact shape of the real incident this rule exists for: a
    test trying to overwrite an already-real, already-committed
    production JSON file."""
    real_leaderboard = _PROTECTED_ROOT / "2026100005_LEADERBOARD.json"
    if not real_leaderboard.is_file():
        pytest.skip("2026100005_LEADERBOARD.json not present in this checkout")
    before = real_leaderboard.read_bytes()
    with pytest.raises(OperationalDataWriteBlocked):
        real_leaderboard.write_text('{"final_round": 1}', encoding="utf-8")
    assert real_leaderboard.read_bytes() == before, "file must be byte-identical after the blocked attempt"


def test_reads_under_the_protected_root_are_unaffected():
    """Read-only access (the rule's own explicit exception) must keep
    working normally -- the guard only ever blocks a write."""
    real_leaderboard = _PROTECTED_ROOT / "2026100005_LEADERBOARD.json"
    if not real_leaderboard.is_file():
        pytest.skip("2026100005_LEADERBOARD.json not present in this checkout")
    text = real_leaderboard.read_text(encoding="utf-8")
    assert len(text) > 0
    with real_leaderboard.open("r", encoding="utf-8") as f:
        assert f.read() == text


def test_tmp_path_writes_are_never_blocked(tmp_path: Path):
    """The rule's other explicit exception: tmp_path (or any other
    Temporary Workspace outside content/website_v2/) is always allowed,
    with no special configuration -- it's simply never under the
    protected root."""
    target = tmp_path / "scratch.json"
    target.write_text("{}", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "{}"

    db_path = tmp_path / "scratch.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()
    assert db_path.is_file()


def test_sqlite_readonly_uri_to_protected_root_is_allowed_if_file_exists():
    """The rule's SQLite read-only exception: a real operational
    .sqlite file can still be opened read-only (uri=True, mode=ro)."""
    candidates = list(_PROTECTED_ROOT.glob("**/*.sqlite"))
    if not candidates:
        pytest.skip("no real .sqlite file present in this checkout to verify against")
    real_db = candidates[0]
    uri = f"file:{real_db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
    conn.close()
