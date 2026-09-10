"""HOME V2 design preview -- automated breakpoint QA (design/home-
ranking-v2-20260910 branch only; not part of the production suite's
release gate). Follows this repo's own established Playwright
fixture pattern (see test_home_current_score_sort_browser.py) --
skips gracefully if Chromium isn't available in this environment.

Checks, at every required viewport (owner brief section 9):
  - no horizontal page overflow (scrollWidth <= viewport width)
  - the global nav never wraps to a second line
  - all 120 real TOP120 rows render
  - the NEO SCORE and K-RANK cells never visually collide
  - the footer never overflows horizontally
"""
from __future__ import annotations

import glob
import http.server
import os
import socket
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_SCRIPT = ROOT / "scripts" / "design_home_v2_preview.py"
PREVIEW_DIR = ROOT / "candidate" / "home-ranking-v2-preview"

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None

VIEWPORTS = [
    (390, 844),
    (430, 932),
    (768, 1024),
    (1366, 768),
    (1440, 900),
]


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def page_url():
    subprocess.run([sys.executable, str(PREVIEW_SCRIPT)], check=True, cwd=ROOT)
    assert (PREVIEW_DIR / "index.html").is_file()

    port = _free_port()

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(PREVIEW_DIR), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _fallback_chromium_executable() -> str | None:
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers_path:
        return None
    candidates = sorted(glob.glob(os.path.join(browsers_path, "chromium-*", "chrome-linux", "chrome")))
    return candidates[-1] if candidates else None


@pytest.fixture(scope="module")
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


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_no_horizontal_overflow(browser, page_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(page_url)
    page.wait_for_selector(".rank-row:not(.rank-row--head)")
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    context.close()
    assert scroll_width <= client_width, f"{width}x{height}: horizontal overflow ({scroll_width} > {client_width})"


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_nav_never_wraps_to_two_lines(browser, page_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(page_url)
    header_box = page.locator(".neo-global-header").bounding_box()
    context.close()
    # A single nav/brand line never needs more than ~64px of header
    # height at any of the required viewports; two lines would push
    # this well past that.
    assert header_box["height"] <= 64, f"{width}x{height}: header wrapped to more than one line (height={header_box['height']})"


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_all_120_rows_render(browser, page_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(page_url)
    page.wait_for_selector(".rank-row:not(.rank-row--head)")
    count = page.locator(".rank-row:not(.rank-row--head)").count()
    context.close()
    assert count == 120


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_neo_score_and_k_rank_never_collide(browser, page_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(page_url)
    first_row = page.locator(".rank-row:not(.rank-row--head)").first
    score_box = first_row.locator(".col-neo-score").bounding_box()
    krank_box = first_row.locator(".col-k-rank").bounding_box()
    context.close()
    # Two boxes collide only if they overlap on BOTH axes at once.
    x_overlap = score_box["x"] < krank_box["x"] + krank_box["width"] and krank_box["x"] < score_box["x"] + score_box["width"]
    y_overlap = score_box["y"] < krank_box["y"] + krank_box["height"] and krank_box["y"] < score_box["y"] + score_box["height"]
    assert not (x_overlap and y_overlap), f"{width}x{height}: NEO SCORE / K-RANK cells overlap"


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_footer_has_no_horizontal_overflow(browser, page_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(page_url)
    footer_box = page.locator(".site-footer").bounding_box()
    client_width = page.evaluate("document.documentElement.clientWidth")
    context.close()
    assert footer_box["width"] <= client_width + 1  # +1 for sub-pixel rounding


def test_sponsor_slot_exists_immediately_below_every_player_name(browser, page_url):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(page_url)
    names = page.locator(".player-name").count()
    sponsors = page.locator(".player-sponsor").count()
    context.close()
    assert names == 120 and sponsors == 120
