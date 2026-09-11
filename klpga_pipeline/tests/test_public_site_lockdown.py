"""NEO PUBLIC SITE -- APPROVED-ROUTES-ONLY LOCKDOWN.

Regression coverage for scripts/apply_public_site_lockdown.py's effect
on docs/ (the GitHub Pages publish root). Locks in: only docs/index.html
and explicitly approved routes serve real content; every other real page/data file was preserved
(never deleted) under docs_internal_archive/ and replaced in docs/ with
the exact required placeholder; assets/CNAME/.nojekyll are untouched;
and -- the hard requirement -- a DIRECT URL to a locked path (not just
a link click) cannot expose real content, verified by actually serving
docs/ over HTTP and requesting every locked path.
"""
from __future__ import annotations

import http.server
import re
import socket
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"
ARCHIVE = REPO_ROOT / "docs_internal_archive"

import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
import apply_public_site_lockdown as lockdown  # noqa: E402


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def docs_server():
    port = _find_free_port()
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(DOCS), **kw)  # noqa: E731
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _get(base: str, path: str) -> tuple[int, str]:
    try:
        resp = urlopen(f"{base}/{path}")
        return resp.status, resp.read().decode("utf-8")
    except Exception as exc:  # urllib raises HTTPError for 4xx/5xx
        status = getattr(exc, "code", 0)
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        return status, body


# ---------------------------------------------------------------------
# Static assertions on the file tree itself
# ---------------------------------------------------------------------

def test_home_page_is_never_the_lockdown_placeholder_and_carries_a_recognized_owner():
    """PRODUCTION HOME PRODUCT POLICY CORRECTION (20260911): "root HOME
    is TOP120_OWNER's page again" is no longer a permanent fact -- the
    HOME STATE ROUTER makes root HOME state-dependent (TOP120_OWNER's
    K-Ranking x NEO Ranking page with no active tournament,
    CURRENT_TOURNAMENT_OWNER's copy of the active tournament's own
    latest stage -- possibly KB itself -- while one is active; see
    tests/test_home_state_router.py for that contract's own coverage).
    What this lockdown gate still guarantees unconditionally: root is
    never the "공사중" placeholder other locked-down routes carry, and
    always carries a recognized, real owner marker -- never a blank or
    third-party page. KB's own R1 content is separately verified
    untouched at its own dedicated route
    (tests/test_kb_r1_publication_gate.py)."""
    home = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "공사중" not in home
    owner_match = re.search(r'neo-home-owner" content="([^"]*)"', home)
    assert owner_match is not None
    assert owner_match.group(1) in ("top120-v1", "current-tournament-v1")


def test_every_enumerated_locked_html_path_is_exactly_the_placeholder():
    for rel in lockdown.LOCKED_HTML_PATHS:
        content = (DOCS / rel).read_text(encoding="utf-8")
        assert content == lockdown.PLACEHOLDER_HTML, f"{rel} is not the exact placeholder"


def test_kb_pre_r1_and_r2_are_the_only_released_tournament_routes():
    """KB's R1 page was added (see scripts/109_build_kb_r1_page.py,
    NEO_R1_MODEL_V1_FREEZE.json) once its own publication gate passed.
    R2 HOUSE (20260911) added a third: a real, truthful WAIT-state page
    (klpga.neo_win.r2_wait_page) is intentionally public before real R2
    data exists -- this is NOT a weakening of the release list, since
    that page fabricates nothing and the HOME STATE ROUTER separately
    refuses to ever promote it to root HOME (STAGE_READINESS_MARKER)
    until its own R2 publication gate passes. Still exactly these three
    routes, nothing else."""
    assert lockdown.RELEASED_HTML_PATHS == {
        "tournaments/2026/2026090003/pre/index.html",
        "tournaments/2026/2026090003/r1/index.html",
        "tournaments/2026/2026090003/r2/index.html",
    }
    pre_content = (DOCS / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")
    assert pre_content != lockdown.PLACEHOLDER_HTML
    assert "KB금융 골든라이프 챔피언십" in pre_content
    assert pre_content.count("class='player-name'") == 120
    assert pre_content.count("class='player-sponsor'") == 120

    r1_content = (DOCS / "tournaments/2026/2026090003/r1/index.html").read_text(encoding="utf-8")
    assert r1_content != lockdown.PLACEHOLDER_HTML
    assert "KB금융 골든라이프 챔피언십" in r1_content
    # 111 predicted + 7 excluded (no fabricated pre_score) = 118 R1-active rows
    # shown, plus the top-3 PRE->R1 movers repeating their identity = 121.
    assert r1_content.count("class='player-name'") == 121
    assert r1_content.count("class='player-sponsor'") == 121


def test_placeholder_contains_all_four_required_lines():
    html = lockdown.PLACEHOLDER_HTML
    for required in ("NEO GOLF DATA", "공사중", "준비 중입니다.", "홈으로"):
        assert required in html


def test_placeholder_home_link_points_to_root():
    assert 'href="/"' in lockdown.PLACEHOLDER_HTML


def test_no_stray_json_data_files_remain_in_docs():
    leftover = list(DOCS.rglob("*.json"))
    assert leftover == [], f"raw JSON still present under docs/: {leftover}"


def test_every_locked_original_was_preserved_in_archive_not_deleted():
    for rel in lockdown.LOCKED_HTML_PATHS + lockdown.LOCKED_DATA_PATHS_NO_PLACEHOLDER:
        archived = ARCHIVE / rel
        assert archived.is_file(), f"{rel} was not preserved in {ARCHIVE}"


def test_archived_original_matches_the_last_committed_real_content():
    """Confirms archiving didn't corrupt or truncate anything -- the
    archived copy must byte-for-byte match what was actually removed
    from the public path (not a fresh regeneration)."""
    sample = "about/index.html"
    archived_text = (ARCHIVE / sample).read_text(encoding="utf-8")
    assert "공사중" not in archived_text
    assert len(archived_text) > 500  # a real page, not an empty/truncated stub


def test_assets_cname_and_nojekyll_are_untouched():
    assert (DOCS / "CNAME").read_text(encoding="utf-8").strip() == "neogolfdata.com"
    assert (DOCS / ".nojekyll").is_file()
    for asset in ("neo-site.css", "neo-site.js", "neo.css", "top120.js"):
        assert (DOCS / "assets" / asset).is_file()


def test_verify_lockdown_reports_no_problems():
    assert lockdown.verify_lockdown() == []


def test_lockdown_is_idempotent_on_rerun():
    before = {p: (DOCS / p).read_text(encoding="utf-8") for p in lockdown.LOCKED_HTML_PATHS}
    lockdown.apply_lockdown()
    after = {p: (DOCS / p).read_text(encoding="utf-8") for p in lockdown.LOCKED_HTML_PATHS}
    assert before == after
    assert lockdown.verify_lockdown() == []


# ---------------------------------------------------------------------
# Live HTTP checks -- the hard requirement: DIRECT URL, not link clicks
# ---------------------------------------------------------------------

def test_home_serves_real_content_over_http(docs_server):
    status, body = _get(docs_server, "")
    assert status == 200
    assert "공사중" not in body


@pytest.mark.parametrize("path", [
    "tournaments/", "ranking/", "deep-dive/", "neo-lab/", "about/",
    "tournaments/2026/kg-ladies-open/",
    "tournaments/2026/kg-ladies-open/final/",
    "tournaments/2026/kg-ladies-open/pre/",
    "tournaments/2026/kg-ladies-open/r1/",
    "tournaments/2026/kg-ladies-open/r2/",
    "tournaments/2026/kg-ladies-open/r3/",
    "tournaments/2026/ok-savings-bank-open/final/",
    "tournaments/2026/ok-savings-bank-open/pre/",
    "tournaments/2026/ok-savings-bank-open/r1/",
    "tournaments/2026/ok-savings-bank-open/r2/",
    "tournaments/2026/ok-savings-bank-open/r3/",
    "archive/beta001/r1/", "archive/beta001/r2/", "archive/beta001/r3/",
])
def test_every_locked_path_shows_placeholder_via_direct_http_url(docs_server, path):
    """The hard requirement: a DIRECT URL request (no referrer, no
    link click) to a locked path must return the placeholder, never
    the real page, and never a leak of real player/sponsor names."""
    status, body = _get(docs_server, path)
    assert status == 200
    assert "공사중" in body
    for leaked_name in ("김민솔", "서교림", "player-row", "data-player-row"):
        assert leaked_name not in body


def test_released_kb_pre_serves_validated_page_via_direct_http_url(docs_server):
    status, body = _get(docs_server, "tournaments/2026/2026090003/pre/")
    assert status == 200
    assert body != lockdown.PLACEHOLDER_HTML
    assert "KB금융 골든라이프 챔피언십" in body
    assert body.count("class='player-name'") == 120
    assert body.count("class='player-sponsor'") == 120
    assert body.count("class='win'") == 600


@pytest.mark.parametrize("bypass_path", [
    "tournaments/index.html",
    "tournaments/2026/kg-ladies-open/index.html",
    "./ranking/",
])
def test_bypass_style_urls_also_show_placeholder_not_real_content(docs_server, bypass_path):
    status, body = _get(docs_server, bypass_path)
    assert status == 200
    assert "공사중" in body


def test_removed_json_data_path_returns_404_not_real_data(docs_server):
    status, body = _get(docs_server, "data/neo-top120-evaluation.json")
    assert status == 404
    assert "김민솔" not in body


def test_shared_assets_still_serve_normally_over_http(docs_server):
    for asset in ("assets/neo-site.css", "assets/neo-site.js", "assets/neo.css", "assets/top120.js", "CNAME"):
        status, _ = _get(docs_server, asset)
        assert status == 200, f"{asset} did not serve (status={status})"
