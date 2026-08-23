"""Optional Playwright-based fetch for pages that need JS rendering.

Playwright is an optional dependency: importing this module never fails
by itself, only calling fetch_rendered_html() without playwright
installed (and its browser binaries) does.
"""
from __future__ import annotations

import logging

from . import config

logger = logging.getLogger("klpga.playwright")


class RenderError(Exception):
    pass


def fetch_rendered_html(url: str, wait_selector: str | None = None) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderError(
            "playwright is not installed; run 'pip install playwright' and "
            "'playwright install chromium' to enable the JS-rendering fallback"
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=config.USER_AGENT)
                page.goto(url, timeout=config.PLAYWRIGHT_NAV_TIMEOUT_MS)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=config.PLAYWRIGHT_NAV_TIMEOUT_MS)
                html = page.content()
                logger.info("rendered %s via playwright (%d bytes)", url, len(html))
                return html
            finally:
                browser.close()
    except RenderError:
        raise
    except Exception as exc:  # pragma: no cover - depends on live browser/network
        raise RenderError(f"failed to render {url} via playwright: {exc}") from exc
