"""FINAL PHASE 8 BLOCKER CLOSURE, part B: docs/protected/beta001 must
never be published; the frozen evidence lives only at
klpga_pipeline/evidence/beta001/artifacts/ (git-tracked, outside
docs/), and its public presentation is a sanitized copy at
docs/archive/beta001/<stage>/ -- built by scripts/86 from the same
sha256-verified bytes, never mutating the frozen source."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"

_FORBIDDEN_STRINGS = (
    "R1 DATA UNAVAILABLE", "데이터 수집 지연 중", "reconstructed", "MODEL_A",
    "published_original", "SHA-256", "체크섬", "검증 대기", "검증 상태",
    "BLOCKED_FORMULA_NOT_APPROVED", "NOT_FOUND_IN_AVAILABLE_OFFICIAL_SNAPSHOT",
    "스냅샷", "raw COMPLETE", "ACTIVE",
)


def test_docs_protected_does_not_exist():
    assert not (DOCS / "protected").exists(), "docs/protected/beta001 must never be published"


@pytest.mark.parametrize("stage", ("r1", "r2", "r3"))
def test_public_archive_page_exists_with_global_header(stage):
    page = DOCS / "archive" / "beta001" / stage / "index.html"
    assert page.is_file(), f"missing public archive route: {page}"
    html = page.read_text(encoding="utf-8")
    assert "neo-global-header" in html
    for word in ("NEO GOLF DATA", "NUMBER", "EVIDENCE", "ORACLE"):
        assert word in html


@pytest.mark.parametrize("stage", ("r1", "r2", "r3"))
def test_public_archive_page_has_no_forbidden_internal_language(stage):
    html = (DOCS / "archive" / "beta001" / stage / "index.html").read_text(encoding="utf-8")
    offenders = [phrase for phrase in _FORBIDDEN_STRINGS if phrase in html]
    assert offenders == [], f"{stage}: forbidden internal-language string(s) found: {offenders}"


@pytest.mark.parametrize("stage", ("r1", "r2", "r3"))
def test_public_archive_page_every_identity_has_a_sponsor_slot(stage):
    html = (DOCS / "archive" / "beta001" / stage / "index.html").read_text(encoding="utf-8")
    orphan_re = re.compile(
        r"<span class=(['\"])(?:player-name|player)\1>[^<>]*</span>"
        r"(?!<span class=(?:\"player-sponsor\"|'player-sponsor'|\"sponsor\"|'sponsor'))"
        r"|<button[^>]*player-name-btn[^>]*>[^<>]*</button>"
        r"(?!<span class=\"player-sponsor\")"
    )
    match = orphan_re.search(html)
    assert not match, f"{stage}: identity mention with no sponsor slot: {match.group(0) if match else None}"


def test_public_archive_page_is_a_sanitized_derivative_not_the_raw_evidence():
    """The public copy is EXPECTED to differ from the frozen evidence
    bytes (header injected, sponsor slots completed) -- the invariant
    this correction establishes is exactly that historical integrity
    means source-evidence hash identity, never public-copy byte
    identity. See test_phase0_evidence_source_bytes_are_immutable in
    test_website_v2_beta001_migration.py for the source-side check."""
    manifest_records = {
        "r1": "be9b5fb56090667aea7924abdd7f481d079579687dc1eb1a561134f353b3400c",
        "r2": "531cac52a7c122e0a0a161f18704570f4972eb744b928128c1317fd06a49eeae",
        "r3": "30797700f3e2e6530c1de02575723d94dbb67da860ade493068d891294ffde15",
    }
    import hashlib
    for stage, expected_sha in manifest_records.items():
        public_bytes = (DOCS / "archive" / "beta001" / stage / "index.html").read_bytes()
        assert hashlib.sha256(public_bytes).hexdigest() != expected_sha
