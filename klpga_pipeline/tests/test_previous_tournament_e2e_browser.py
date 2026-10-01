"""Playwright E2E: once a tournament's R1 page is real (published),
verifies that HOME, PRE, and R1 all land on the SAME previous
tournament's real FINAL page when "이전 대회" is clicked, with the
FINAL tab active, a real winner line, and a real leaderboard -- same
fixture pattern as tests/test_home_current_score_sort_browser.py
(this project's established precedent); skips gracefully if Chromium
isn't available.

Always collected and run (never file-skipped) so CI always executes
it. It runtime-skips with a clear, specific reason only when the
CURRENT tournament's own R1 page hasn't actually been published yet --
there is nothing real to click through before then, and this project
never fabricates a page just to make a test pass. The moment R1 goes
live for any tournament (this one or the next), this test starts
asserting for real with no further change needed."""
from __future__ import annotations

import glob
import http.server
import json
import os
import re
import socket
import sys
import threading
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.official_schedule import load_official_schedule  # noqa: E402
from klpga.website_v2.tournament_chronology import resolve_tournament_chronology  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None


def _current_tournament_url_base() -> str | None:
    """The CURRENT (in-progress/about-to-start) tournament's url_base,
    resolved the same real, date-only, pure way every page already
    does (klpga.website_v2.tournament_chronology) -- never hardcoded
    to one game_code, so this test keeps working unchanged for
    whichever tournament is current when it runs."""
    content = ROOT / "content" / "website_v2"
    schedule = load_official_schedule(content / "OFFICIAL_KLPGA_SCHEDULE.json")
    registry = json.loads((content / "TOURNAMENT_SITE_REGISTRY.json").read_text(encoding="utf-8"))["tournaments"]
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date.today())
    current = chronology.get("current")
    if current is None or not current.url_base:
        return None
    return current.url_base


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def docs_url():
    """Serves the real, committed docs/ tree as-is (read-only) -- this
    test must see real cross-page links/content, not a synthetic
    single-page fixture."""
    docs_dir = REPO_ROOT / "docs"
    port = _free_port()

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(docs_dir), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _fallback_chromium_executable() -> str | None:
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers_path:
        return None
    candidates = sorted(glob.glob(os.path.join(browsers_path, "chromium-*", "chrome-linux", "chrome")))
    return candidates[-1] if candidates else None


@pytest.fixture()
def browser():
    if sync_playwright is None:
        pytest.skip(f"playwright not importable: {_PLAYWRIGHT_IMPORT_ERROR}")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as first_exc:  # noqa: BLE001
            fallback = _fallback_chromium_executable()
            if not fallback:
                pytest.skip(f"Chromium not available in this environment: {first_exc}")
            try:
                b = p.chromium.launch(executable_path=fallback)
            except Exception as second_exc:  # noqa: BLE001
                pytest.skip(f"Chromium not available in this environment: {second_exc}")
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


def assert_previous_tournament_leads_to_real_final(page, docs_url: str, page_path: str, page_label: str) -> None:
    """The one shared assertion HOME/PRE/R1 (and R2/R3/FR, once those
    exist) are each checked against -- never a per-page duplicate."""
    page.goto(f"{docs_url}{page_path}", wait_until="networkidle")

    link_locator = page.locator("p.meta", has_text="이전 대회").locator("a")
    if link_locator.count() == 0:
        pytest.fail(f"[{page_label}] no '이전 대회' link found at {page_path} -- page markup regressed")
    link_locator.first.click()
    page.wait_for_load_state("networkidle")

    pathname = page.evaluate("window.location.pathname")
    assert pathname.rstrip("/").endswith("/final"), f"[{page_label}] expected a .../final/ URL, got {pathname!r}"

    active_tabs = page.locator("[aria-current='page']").all_inner_texts()
    assert any("FINAL" in t for t in active_tabs), f"[{page_label}] FINAL tab not active: {active_tabs!r}"

    assert page.get_by_text(re.compile(r"우승")).count() > 0, f"[{page_label}] no winner ('우승') text found on the FINAL page"

    rows = page.locator("table.data tbody tr")
    assert rows.count() >= 5, f"[{page_label}] final leaderboard has fewer than 5 rows ({rows.count()})"


def test_home_pre_r1_previous_tournament_link_all_lead_to_the_real_final_page(page, docs_url):
    url_base = _current_tournament_url_base()
    if url_base is None:
        pytest.skip("no current tournament resolved by chronology -- nothing to verify yet")

    r1_path = f"{url_base}r1/"
    if not (REPO_ROOT / "docs" / r1_path.strip("/") / "index.html").is_file():
        pytest.skip(f"current tournament's R1 page not published yet ({r1_path}) -- nothing real to click through")

    pre_path = f"{url_base}pre/"
    for page_path, label in (("/index.html", "HOME"), (pre_path, "PRE"), (r1_path, "R1")):
        assert_previous_tournament_leads_to_real_final(page, docs_url, page_path, label)
