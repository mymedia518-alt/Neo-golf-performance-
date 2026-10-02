"""2026-10-02 'RELEASE GATE' mission: Playwright half of the checklist
-- every rendering bug a human found by hand this session on the real
R2 page, re-checked automatically against a real Chromium render
before any future build/commit/push for this tournament is allowed to
proceed. Exits non-zero (refuses) the instant any one check fails,
printing exactly which one and the real measured value.

Checks:
1. No real console errors (favicon 404 excluded -- unrelated, present
   on every page this session, never a real regression).
2. R1 score cell renders on ONE line, not wrapped (the real CSS
   specificity bug this session found and fixed: "70" rendering as
   "7"/"0" stacked -- single line is ~20-40px, two lines ~55-60px+).
3. The real section headers ("R2 미출전 — ...", "WD · ...") appear,
   in that order, and the explicitly-rejected "R2 컷 통과"/"본선 진출"
   labels never appear (2026-10-02 EVIDENCE INSUFFICIENT finding).
Runs each check at both desktop (1440x900) and mobile (390x900)
viewports -- a bug fixed at one width and not the other is still a
real regression.
"""
from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
CHROMIUM = "/opt/pw-browsers/chromium"
GAME_CODE = "2026100005"
FORBIDDEN_LABELS = ("R2 컷 통과", "본선 진출")
REQUIRED_SECTION_ORDER = ("R2 미출전", "WD · ")


def _check_viewport(browser, name: str, viewport: dict) -> list[str]:
    failures: list[str] = []
    console_errors: list[str] = []
    page = browser.new_page(viewport=viewport)
    page.on(
        "console",
        lambda msg: console_errors.append(f"{msg.text} ({msg.location.get('url', '')})") if msg.type == "error" else None,
    )
    page.goto(f"http://127.0.0.1:{PORT}/tournaments/2026/{GAME_CODE}/r2/", wait_until="networkidle")

    real_errors = [e for e in console_errors if "favicon" not in e]
    if real_errors:
        failures.append(f"[{name}] real console errors: {real_errors}")

    cell = page.locator("td[data-label='R1']").first
    if cell.count() > 0:
        box = cell.bounding_box()
        if box is not None and box["height"] > 45:
            failures.append(
                f"[{name}] R1 score cell height {box['height']:.1f}px > 45px -- "
                f"likely wrapped onto 2 lines (the real CSS specificity bug)."
            )

    html = page.content()
    for label in FORBIDDEN_LABELS:
        if label in html:
            failures.append(f"[{name}] forbidden unsubstantiated label {label!r} found on the real rendered page")

    positions = [html.find(s) for s in REQUIRED_SECTION_ORDER]
    if any(p == -1 for p in positions):
        failures.append(f"[{name}] missing expected section header(s): {REQUIRED_SECTION_ORDER} -> positions {positions}")
    elif positions != sorted(positions):
        failures.append(f"[{name}] section headers out of order: {REQUIRED_SECTION_ORDER} -> positions {positions}")

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
            all_failures += _check_viewport(browser, "desktop", {"width": 1440, "height": 900})
            all_failures += _check_viewport(browser, "mobile", {"width": 390, "height": 900})
            browser.close()
    finally:
        server.shutdown()

    if all_failures:
        print("PLAYWRIGHT GATE: FAILED")
        for f in all_failures:
            print(f" - {f}")
        return 1

    print("PLAYWRIGHT GATE: PASSED (desktop + mobile, all checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
