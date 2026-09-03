"""NEO WEBSITE V3 Phase 3 visual QA: real Chromium rendering + expanded
geometry/consistency checks against the canonical TOP120 candidate tree
-- not HTML-string assertions. Boots a local static server over
candidate/neo-data-home-top120/, screenshots the required routes at
desktop 1440x900, desktop 1280x800 (HOME only -- this is the width a
real user's browser exposed a Korean heading wrap defect the 1440-only
Phase 2 pass never caught), and mobile 390x844, and measures real
rendered geometry via getBoundingClientRect.
"""
from __future__ import annotations

import http.server
import json
import functools
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SITE_ROOT = ROOT / "candidate" / "neo-data-home-top120"
ARTIFACTS = REPO_ROOT / "artifacts" / "website_v3_visual_qa"
CHROMIUM = "/opt/pw-browsers/chromium"

ALL_ROUTES = [
    ("home", "/"),
    ("tournaments-hub", "/tournaments/"),
    ("deep-dive", "/deep-dive/"),
    ("about", "/about/"),
    ("kg-overview", "/tournaments/2026/kg-ladies-open/"),
    ("kg-pre", "/tournaments/2026/kg-ladies-open/pre/"),
    ("kg-r1", "/tournaments/2026/kg-ladies-open/r1/"),
    ("kg-r2", "/tournaments/2026/kg-ladies-open/r2/"),
    ("kg-r3", "/tournaments/2026/kg-ladies-open/r3/"),
    ("kg-final", "/tournaments/2026/kg-ladies-open/final/"),
    ("ok-pre", "/tournaments/2026/ok-savings-bank-open/pre/"),
    ("ok-r1", "/tournaments/2026/ok-savings-bank-open/r1/"),
    ("ok-r2", "/tournaments/2026/ok-savings-bank-open/r2/"),
    ("ok-final", "/tournaments/2026/ok-savings-bank-open/final/"),
]
_by_slug = dict(ALL_ROUTES)

# Which global-nav item must show as active on each route -- UX spec 2:
# "현재 페이지 active state 표시". None routes (there are none currently)
# would mean no nav item should be marked active.
EXPECTED_ACTIVE_SECTION = {
    "home": "홈", "tournaments-hub": "대회", "deep-dive": "딥다이브", "about": "소개",
    "kg-overview": "대회", "kg-pre": "대회", "kg-r1": "대회", "kg-r2": "대회", "kg-r3": "대회", "kg-final": "대회",
    "ok-pre": "대회", "ok-r1": "대회", "ok-r2": "대회", "ok-final": "대회",
}

VIEWPORT_ROUTES = {
    "desktop": [s for s, _ in ALL_ROUTES],
    "1280": ["home"],
    "mobile": [s for s, _ in ALL_ROUTES],
}
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "1280": {"width": 1280, "height": 800},
    "mobile": {"width": 390, "height": 844},
}

CANONICAL_BRAND_MARK = "NEO"
CANONICAL_NAV_LABELS = ["홈", "대회", "딥다이브", "소개"]
LEGACY_BRAND_STRING = "NEO GOLF DATA"

GEOMETRY_JS = """() => {
    // Only the canonical site-nav header carries this class; a page may
    // legitimately use <header> again as a semantic sectioning element
    // inside a card/article (e.g. a chart-card's own <header> with its
    // title) -- that is correct HTML5, not a duplicate nav header, so
    // counting every <header> on the page produces false positives.
    const headers = document.querySelectorAll('header.neo-global-header');
    const header = headers[0] || null;
    const h1 = document.querySelector('h1');
    const docEl = document.documentElement;
    const headerRect = header ? header.getBoundingClientRect() : null;
    const h1Rect = h1 ? h1.getBoundingClientRect() : null;
    const h1Style = h1 ? getComputedStyle(h1) : null;
    let firstDataTop = null;
    const dataEl = document.querySelector('table, .tournament-row, .data-table, .home-summary, .comparison-table, .result-card, main section');
    if (dataEl) firstDataTop = dataEl.getBoundingClientRect().top;
    const mainEl = document.querySelector('main');
    const mainStyle = mainEl ? getComputedStyle(mainEl) : null;
    const brandMarkEl = document.querySelector('.neo-brand-mark');
    const brandLinkEl = document.querySelector('.neo-global-brand');
    const activeLink = header ? header.querySelector('.neo-global-nav a[aria-current="page"]') : null;
    const navLinks = header ? Array.from(header.querySelectorAll('nav a')).map(a => a.textContent.trim()) : [];

    // GLOBAL TABLE SYSTEM (spec 5): every real data table's th/td must
    // compute to text-align:center. Exclude screen-reader-only tables
    // (.sr-data, used for chart-series a11y fallbacks -- never visible).
    const tableOffenders = [];
    document.querySelectorAll('table').forEach((table, ti) => {
        if (table.closest('.sr-data')) return;
        table.querySelectorAll('th, td').forEach((cell, ci) => {
            const align = getComputedStyle(cell).textAlign;
            if (align !== 'center') tableOffenders.push(`table${ti}:cell${ci}:"${cell.textContent.trim().slice(0,20)}"=${align}`);
        });
    });

    // GLOBAL CHART SYSTEM (spec 6/7): every chart-value/x-label/y-label
    // must sit fully inside its own <svg>'s rendered box (no clipping)
    // and must not overlap a sibling label within the same chart (no
    // collision). Anti-aliasing/rounding makes exact-touch common, so a
    // small tolerance avoids flagging harmless 1px adjacency.
    const chartOffenders = [];
    document.querySelectorAll('svg.line-chart, svg.bar-chart').forEach((svg, si) => {
        const svgRect = svg.getBoundingClientRect();
        const labels = Array.from(svg.querySelectorAll('text.chart-value, text.chart-x-label, text.chart-y-label, text.bar-number, text.bar-label'));
        const rects = labels.map(el => el.getBoundingClientRect());
        const TOL = 1;
        rects.forEach((r, i) => {
            if (r.width === 0) return;
            if (r.left < svgRect.left - TOL || r.right > svgRect.right + TOL || r.top < svgRect.top - TOL || r.bottom > svgRect.bottom + TOL) {
                chartOffenders.push(`svg${si}:label${i}:"${labels[i].textContent.trim()}" clips chart edge`);
            }
        });
        for (let i = 0; i < rects.length; i++) {
            for (let j = i + 1; j < rects.length; j++) {
                const a = rects[i], b = rects[j];
                if (a.width === 0 || b.width === 0) continue;
                const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left);
                const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
                if (overlapX > TOL && overlapY > TOL) {
                    chartOffenders.push(`svg${si}:label${i}"${labels[i].textContent.trim()}" overlaps label${j}"${labels[j].textContent.trim()}"`);
                }
            }
        }
    });

    return {
        viewport_width: window.innerWidth,
        header_count: headers.length,
        header_height: headerRect ? headerRect.height : null,
        header_text: header ? header.textContent.replace(/\\s+/g, ' ').trim().slice(0, 200) : null,
        brand_mark_text: brandMarkEl ? brandMarkEl.textContent.trim() : null,
        brand_full_text: brandLinkEl ? brandLinkEl.textContent.replace(/\\s+/g, ' ').trim() : null,
        active_nav_text: activeLink ? activeLink.textContent.trim() : null,
        nav_link_texts: navLinks,
        h1_font_size_px: h1Style ? parseFloat(h1Style.fontSize) : null,
        h1_font_family: h1Style ? h1Style.fontFamily : null,
        h1_text: h1 ? h1.textContent.trim() : null,
        h1_line_count: h1Rect && h1Style ? Math.round(h1Rect.height / parseFloat(h1Style.lineHeight || h1Style.fontSize)) : null,
        first_data_top: firstDataTop,
        main_max_width_px: mainStyle ? mainStyle.maxWidth : null,
        body_background: getComputedStyle(document.body).backgroundColor,
        page_scroll_width: docEl.scrollWidth,
        page_client_width: docEl.clientWidth,
        horizontal_overflow: docEl.scrollWidth > docEl.clientWidth + 1,
        table_alignment_offenders: tableOffenders,
        chart_offenders: chartOffenders,
    };
}"""


def run() -> dict:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for viewport_name in VIEWPORTS:
        (ARTIFACTS / viewport_name).mkdir(exist_ok=True)

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
                for slug in VIEWPORT_ROUTES[viewport_name]:
                    route = _by_slug[slug]
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
                    tag = f"{viewport_name}/{slug}"

                    if status != 200:
                        findings.append(f"{tag}: HTTP {status}")
                    if "Directory listing for" in body_text:
                        findings.append(f"{tag}: directory listing, not a real page")
                    if "�" in body_text:
                        findings.append(f"{tag}: U+FFFD present")
                    if record["horizontal_overflow"]:
                        findings.append(f"{tag}: horizontal page overflow (scrollWidth={record['page_scroll_width']} > clientWidth={record['page_client_width']})")
                    if record["header_height"] is not None and record["header_height"] > 140:
                        findings.append(f"{tag}: header excessively tall ({record['header_height']:.0f}px)")
                    if record["h1_font_size_px"] is not None:
                        lo, hi = (32, 40) if viewport_name in ("desktop", "1280") else (24, 34)
                        if not (lo <= record["h1_font_size_px"] <= hi):
                            findings.append(f"{tag}: H1 font-size {record['h1_font_size_px']:.1f}px outside {lo}-{hi}px band")
                    # P1-8: exactly one header per page -- no page independently
                    # recreates its own on top of (or instead of) the canonical one.
                    if record["header_count"] != 1:
                        findings.append(f"{tag}: header_count={record['header_count']}, expected exactly 1")
                    if record["brand_mark_text"] != CANONICAL_BRAND_MARK:
                        findings.append(f"{tag}: brand mark is {record['brand_mark_text']!r}, expected {CANONICAL_BRAND_MARK!r}")
                    brand_text = record["brand_full_text"] or ""
                    if not all(word in brand_text for word in ("NEO", "Number", "Evidence", "Oracle")):
                        findings.append(f"{tag}: brand lockup text {brand_text!r} missing one of NEO/Number/Evidence/Oracle")
                    if record["nav_link_texts"] != CANONICAL_NAV_LABELS:
                        findings.append(f"{tag}: header nav labels {record['nav_link_texts']} != canonical {CANONICAL_NAV_LABELS}")
                    if record["header_text"] and LEGACY_BRAND_STRING in record["header_text"]:
                        findings.append(f"{tag}: legacy 'NEO GOLF DATA' text found INSIDE the site header (prose mentions elsewhere on the page are fine)")
                    if record["h1_line_count"] is not None and record["h1_line_count"] > 2:
                        findings.append(f"{tag}: H1 wraps to {record['h1_line_count']} lines -- check for a mid-word Korean break")
                    # UX spec 2: the correct nav item must show as "here".
                    expected_active = EXPECTED_ACTIVE_SECTION.get(slug)
                    if expected_active is not None and record["active_nav_text"] != expected_active:
                        findings.append(f"{tag}: active nav is {record['active_nav_text']!r}, expected {expected_active!r}")
                    # UX spec 5: numeric/short data columns center; no
                    # left-aligned data cell should remain anywhere.
                    for offender in record["table_alignment_offenders"][:10]:
                        findings.append(f"{tag}: table cell not centered -- {offender}")
                    # UX spec 6/7: chart labels must neither clip past
                    # their chart nor collide with a neighboring label.
                    for offender in record["chart_offenders"][:10]:
                        findings.append(f"{tag}: chart label issue -- {offender}")
                page.close()

            # P0 FAIL check (UX spec 2): with the stylesheet blocked, the
            # header's brand/nav text must still read as space-separated
            # words, not run together into one unreadable string like
            # "NEONumber · Evidence · Oracle홈대회딥다이브소개" -- the
            # literal example the spec calls a hard failure. Real
            # newline whitespace text nodes (see global_navigation.py)
            # are what make this pass even with zero CSS.
            css_off_page = browser.new_page(viewport=VIEWPORTS["desktop"])
            css_off_page.route("**/*.css", lambda route: route.abort())
            css_off_page.goto(base + "/", wait_until="networkidle", timeout=15000)
            header_text_no_css = css_off_page.evaluate(
                "() => { const h = document.querySelector('header.neo-global-header'); return h ? h.innerText.replace(/\\s+/g,' ').trim() : null; }"
            )
            css_off_page.close()
            bad_runons = ["NEONumber", "Oracle홈", "홈대회", "대회딥다이브", "딥다이브소개"]
            if header_text_no_css is None:
                findings.append("css-off/home: no canonical header found with stylesheets blocked")
            else:
                hits = [b for b in bad_runons if b in header_text_no_css]
                if hits:
                    findings.append(f"css-off/home: header text run together with no CSS ({hits}): {header_text_no_css!r}")

            browser.close()
    finally:
        server.shutdown()

    report = {"results": results, "findings": findings}
    (ARTIFACTS / "geometry_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"routes_checked": sum(len(v) for v in VIEWPORT_ROUTES.values()), "viewports": list(VIEWPORTS), "findings_count": len(findings)}, ensure_ascii=False))
    for f in findings:
        print("FINDING:", f)
    return report


if __name__ == "__main__":
    run()
