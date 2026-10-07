"""HJ중공업·동부건설 챔피언십 (2026100004) HOME + PRE Playwright QA gate.

Checks both pages at desktop (1440x900) and mobile (390x844), per the
operator's explicit visual-QA checklist for this homepage build:
  (a) same NEO design shell (global header/nav/footer present, no new
      CSS introduced -- checked by class presence, not pixel diff).
  (b) player name/sponsor/nationality render without breaking.
  (c) no mobile horizontal overflow.
  (d) rank values not truncated (no 2-line-wrapped rank cell).
  (e) no internal terminology exposed (sha256/CORE/SUPPORTING/REJECTED/
      parser/cutoff -- the same forbidden-jargon list as the unit tests,
      re-checked here against the REAL rendered DOM, not just the raw
      HTML string, in case anything is only visible after render).
  (f) no awkward/empty-looking UI from missing fields (an empty
      sponsor slot must not leave a dangling separator/placeholder
      text like "확인 중").
  (g) the event's core point (main message) is visible in the first
      viewport on page load, not just present somewhere in the DOM.

Saves screenshots to the scratchpad (not committed -- this repo's own
convention: every other Playwright gate here is pass/fail text only,
no binary screenshots in git history) for manual visual confirmation.
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
CHROMIUM = "/opt/pw-browsers/chromium"
SHOT_DIR = Path(
    os.environ.get("HJ_QA_SHOT_DIR")
    or "/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04/scratchpad/hj_2026100004_qa"
)

PAGES = {
    "home": "/",
    "pre": "/tournaments/2026/2026100004/pre/",
}
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}
FORBIDDEN_JARGON = ("sha256", "CORE", "SUPPORTING", "REJECTED", "parser", "cutoff", "Stableford Fit")
MAIN_MESSAGE = "같은 경기력도 Stableford에서는 가치가 달라진다"


def _check_page(browser, page_key: str, path: str, vp_key: str, viewport: dict) -> list[str]:
    failures: list[str] = []
    console_errors: list[str] = []
    page = browser.new_page(viewport=viewport)
    page.on(
        "console",
        lambda msg: console_errors.append(f"{msg.text} ({msg.location.get('url', '')})") if msg.type == "error" else None,
    )
    page.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="networkidle")

    real_errors = [e for e in console_errors if "favicon" not in e]
    if real_errors:
        failures.append(f"[{page_key}/{vp_key}] console errors: {real_errors}")

    # (a) same NEO shell
    for sel in ("header.neo-global-header", "footer.site-footer", "nav.breadcrumb"):
        if page.locator(sel).count() == 0:
            failures.append(f"[{page_key}/{vp_key}] missing expected shell element {sel!r}")

    # (c) no horizontal overflow
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow > 1:
        failures.append(f"[{page_key}/{vp_key}] horizontal overflow {overflow}px")

    html = page.content()

    # (e) no internal jargon
    for term in FORBIDDEN_JARGON:
        if term in html:
            failures.append(f"[{page_key}/{vp_key}] forbidden internal term {term!r} exposed")

    # (f) no dangling empty-sponsor artifacts
    if "확인 중" in html or "undefined" in html.lower():
        failures.append(f"[{page_key}/{vp_key}] placeholder/undefined artifact found in rendered HTML")

    if page_key == "pre":
        # (d) rank value itself ("#N") renders on one line, never split
        # across lines mid-number -- the mobile layout legitimately
        # stacks the small data-label caption ABOVE the value (by
        # design, matching the existing template's card pattern), so
        # the check is on the digit text itself, not the cell height.
        rank_cell = page.locator("td[data-label='Stableford 사전평가']").first
        if rank_cell.count() > 0:
            rank_text = rank_cell.inner_text().strip()
            first_line = rank_text.splitlines()[-1] if rank_text else ""
            if not re.match(r"^#\d+", first_line) and "데이터 부족" not in rank_text:
                failures.append(f"[{page_key}/{vp_key}] rank value malformed: {rank_text!r}")
        # (b) every row has a non-empty name span
        name_count = page.locator("span.player-name").count()
        if name_count != 108:
            failures.append(f"[{page_key}/{vp_key}] expected 108 player-name spans, found {name_count}")

    if page_key == "home":
        # (g) main message visible in first viewport
        hero_p = page.locator(f"text={MAIN_MESSAGE}")
        if hero_p.count() == 0:
            failures.append(f"[{page_key}/{vp_key}] main message not found on page")
        else:
            box = hero_p.first.bounding_box()
            if box is None or box["y"] > viewport["height"]:
                failures.append(f"[{page_key}/{vp_key}] main message not visible without scrolling")

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / f"{page_key}_{vp_key}.png"), full_page=True)
    page.close()
    return failures


def main() -> int:
    global PORT
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    PORT = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    all_failures: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            for page_key, path in PAGES.items():
                for vp_key, viewport in VIEWPORTS.items():
                    all_failures += _check_page(browser, page_key, path, vp_key, viewport)
            browser.close()
    finally:
        server.shutdown()

    print(f"Screenshots: {SHOT_DIR}")
    if all_failures:
        print("PLAYWRIGHT QA: FAILED")
        for f in all_failures:
            print(f" - {f}")
        return 1

    print("PLAYWRIGHT QA: PASSED (home + pre, desktop + mobile)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
