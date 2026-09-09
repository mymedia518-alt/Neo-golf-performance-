"""Playwright browser test for the KB PRE page's NEO 경기력 info tooltip
-- real rendered-DOM measurements rather than CSS assumptions, covering
both the desktop overflow fix (SHA 30ff282) and the mobile
accessibility follow-up (the info trigger living inside a mobile-hidden
<thead> was, until this fix, completely unreachable on a real phone).
Same fixture pattern as tests/test_r2_production_page_browser.py (this
project's established precedent); skips gracefully if Chromium isn't
available.
"""
from __future__ import annotations

import glob
import http.server
import importlib.util
import os
import socket
import threading
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder_tooltip_browser", ROOT / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url():
    out = builder.build()
    port = _free_port()

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(out), **kwargs)

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


def test_mobile_info_trigger_is_actually_visible_and_tappable(page, page_url):
    """OWNER FOLLOW-UP regression guard: the mobile card transformation
    moves <thead> (and everything in it) off-screen at left:-9999px.
    Before this fix, the info trigger lived only inside that <thead>,
    so it was unreachable on a real phone regardless of the desktop
    overflow fix. If a future change removes the th.band-head
    position:fixed override (or re-nests the trigger somewhere else
    thead's rule still hides), this test catches it by measuring the
    real rendered position, not just asserting CSS text exists."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(page_url)
    trigger = page.locator(".info-control")
    assert trigger.is_visible()
    box = trigger.bounding_box()
    assert box is not None
    assert 0 <= box["x"] <= 390 - box["width"], f"trigger x={box['x']} is off the 390px viewport"
    assert 0 <= box["y"] <= 844, f"trigger y={box['y']} is off the 844px viewport"
    trigger.click()  # must not raise/timeout -- proves it is actually clickable, not just "visible"


def test_mobile_popover_opens_fully_inside_viewport_with_no_layout_shift(page, page_url):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(page_url)

    scroll_width_before = page.evaluate("document.documentElement.scrollWidth")
    first_card_box_before = page.locator("tbody tr").first.bounding_box()

    page.click(".info-control")
    page.wait_for_timeout(50)
    popover = page.locator(".info-popover")
    assert popover.is_visible()
    box = popover.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390, f"popover escapes viewport horizontally: {box}"
    assert box["y"] >= 0 and box["y"] + box["height"] <= 844, f"popover escapes viewport vertically: {box}"

    # Korean text must wrap normally inside the box, not overflow it
    text_height = page.evaluate("document.getElementById('neo-info').scrollHeight")
    assert text_height <= box["height"] + 1, "popover content overflows its own box instead of wrapping"

    scroll_width_after = page.evaluate("document.documentElement.scrollWidth")
    assert scroll_width_after == scroll_width_before, "opening the popover must not introduce horizontal scroll"
    first_card_box_after = page.locator("tbody tr").first.bounding_box()
    assert first_card_box_after == first_card_box_before, "opening the popover shifted the card layout"


def test_mobile_popover_closes_on_escape_and_outside_click(page, page_url):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(page_url)
    popover = page.locator(".info-popover")

    page.click(".info-control")
    page.wait_for_timeout(50)
    assert "is-open" in popover.get_attribute("class")
    page.keyboard.press("Escape")
    page.wait_for_timeout(50)
    assert "is-open" not in popover.get_attribute("class"), "ESC must close the popover regardless of what currently has focus"

    page.click(".info-control")
    page.wait_for_timeout(50)
    assert "is-open" in popover.get_attribute("class")
    page.mouse.click(5, 5)
    page.wait_for_timeout(50)
    assert "is-open" not in popover.get_attribute("class")


def test_desktop_tooltip_unaffected_by_the_mobile_fix(page, page_url):
    """Regression guard for requirement 1/10: the mobile-only fix must
    not change desktop's own (already-fixed, SHA 30ff282) behavior."""
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(page_url)
    page.click(".info-control")
    page.wait_for_timeout(50)
    box = page.locator(".info-popover").bounding_box()
    assert box["x"] + box["width"] <= 1440, "desktop popover must still stay inside the viewport"
    assert box["x"] >= 0
