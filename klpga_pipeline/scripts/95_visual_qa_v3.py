"""P16/P17 Phase 2 visual QA: real Chromium rendering + geometry checks
against the canonical TOP120 candidate tree, not just HTML-string
assertions. Boots a local static server over
candidate/neo-data-home-top120/, screenshots the required routes at
desktop (1440x900) and mobile (390x844), and measures real rendered
geometry via getBoundingClientRect -- not CSS source values.
"""
from __future__ import annotations

import http.server
import json
import functools
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SITE_ROOT = ROOT / "candidate" / "neo-data-home-top120"
ARTIFACTS = REPO_ROOT / "artifacts" / "website_v3_visual_qa"
CHROMIUM = "/opt/pw-browsers/chromium"

ROUTES = [
    ("home", "/"),
    ("tournaments-hub", "/tournaments/"),
    ("deep-dive", "/deep-dive/"),
    ("about", "/about/"),
    ("kg-pre", "/tournaments/2026/kg-ladies-open/pre/"),
    ("kg-r1", "/tournaments/2026/kg-ladies-open/r1/"),
    ("kg-r2", "/tournaments/2026/kg-ladies-open/r2/"),
    ("kg-r3", "/tournaments/2026/kg-ladies-open/r3/"),
    ("kg-final", "/tournaments/2026/kg-ladies-open/final/"),
    ("ok-pre", "/tournaments/2026/ok-savings-bank-open/pre/"),
    ("ok-final", "/tournaments/2026/ok-savings-bank-open/final/"),
]

VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}

GEOMETRY_JS = """() => {
    const header = document.querySelector('header');
    const h1 = document.querySelector('h1');
    const body = document.body;
    const docEl = document.documentElement;
    const headerRect = header ? header.getBoundingClientRect() : null;
    const h1Rect = h1 ? h1.getBoundingClientRect() : null;
    const h1Style = h1 ? getComputedStyle(h1) : null;
    let firstDataTop = null;
    const dataEl = document.querySelector('table, .tournament-row, .data-table, .home-summary, .comparison-table, .result-card, main section');
    if (dataEl) firstDataTop = dataEl.getBoundingClientRect().top;
    const navEl = document.querySelector('nav');
    const navRect = navEl ? navEl.getBoundingClientRect() : null;
    return {
        viewport_width: window.innerWidth,
        header_height: headerRect ? headerRect.height : null,
        h1_font_size_px: h1Style ? parseFloat(h1Style.fontSize) : null,
        h1_text: h1 ? h1.textContent.trim() : null,
        first_data_top: firstDataTop,
        nav_right_edge: navRect ? navRect.right : null,
        page_scroll_width: docEl.scrollWidth,
        page_client_width: docEl.clientWidth,
        horizontal_overflow: docEl.scrollWidth > docEl.clientWidth + 1,
    };
}"""


def run() -> dict:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "desktop").mkdir(exist_ok=True)
    (ARTIFACTS / "mobile").mkdir(exist_ok=True)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    results = []
    findings = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            for viewport_name, viewport in VIEWPORTS.items():
                page = browser.new_page(viewport=viewport)
                for slug, route in ROUTES:
                    url = base + route
                    response = page.goto(url, wait_until="networkidle", timeout=15000)
                    status = response.status if response else None
                    body_text = page.content()
                    screenshot_path = ARTIFACTS / viewport_name / f"{slug}.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    geometry = page.evaluate(GEOMETRY_JS)
                    record = {
                        "route": route, "slug": slug, "viewport": viewport_name,
                        "status": status, "screenshot": str(screenshot_path.relative_to(REPO_ROOT)),
                        **geometry,
                    }
                    results.append(record)

                    if status != 200:
                        findings.append(f"{viewport_name}/{slug}: HTTP {status}")
                    if "Directory listing for" in body_text:
                        findings.append(f"{viewport_name}/{slug}: directory listing, not a real page")
                    if "�" in body_text:
                        findings.append(f"{viewport_name}/{slug}: U+FFFD present")
                    if record["horizontal_overflow"]:
                        findings.append(f"{viewport_name}/{slug}: horizontal page overflow (scrollWidth={record['page_scroll_width']} > clientWidth={record['page_client_width']})")
                    if record["header_height"] is not None and record["header_height"] > 140:
                        findings.append(f"{viewport_name}/{slug}: header excessively tall ({record['header_height']:.0f}px)")
                    if record["h1_font_size_px"] is not None:
                        lo, hi = (32, 40) if viewport_name == "desktop" else (24, 34)
                        if not (lo <= record["h1_font_size_px"] <= hi):
                            findings.append(f"{viewport_name}/{slug}: H1 font-size {record['h1_font_size_px']:.1f}px outside {lo}-{hi}px band")
                page.close()
            browser.close()
    finally:
        server.shutdown()

    report = {"results": results, "findings": findings}
    (ARTIFACTS / "geometry_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"routes_checked": len(ROUTES), "viewports": list(VIEWPORTS), "findings_count": len(findings)}, ensure_ascii=False))
    for f in findings:
        print("FINDING:", f)
    return report


if __name__ == "__main__":
    run()
