"""KB 2026090003 (current tournament) public-page mobile hotfix --
automated breakpoint QA (branch fix/kb-current-mobile-ui-20260911).

Serves the real docs/ tree (the deployed PRE/R1/root-HOME pages, no
synthetic fixture) and checks, at every required viewport, the FAIL
conditions from the mobile-hotfix brief: horizontal overflow, nav
wrap, leaderboard row rendering/collision, sponsor placement,
probability order, and 1-decimal display.
"""
from __future__ import annotations

import glob
import http.server
import os
import re
import socket
import threading
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent / "docs"

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

ROUTES = {
    "root": "/",
    "pre": "/tournaments/2026/2026090003/pre/",
    "r1": "/tournaments/2026/2026090003/r1/",
}


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    assert (DOCS / "index.html").is_file()
    assert (DOCS / "tournaments" / "2026" / "2026090003" / "pre" / "index.html").is_file()
    assert (DOCS / "tournaments" / "2026" / "2026090003" / "r1" / "index.html").is_file()

    port = _free_port()

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(DOCS), **kwargs)

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


# ROOT HOME RECOVERY (scripts/111_promote_top120_root_home_only.py):
# root ("/") is no longer KB content -- it reverted to the TOP120
# K-Ranking page, which has its own dedicated overflow coverage in
# tests/test_home_mobile_color_readability.py. This file's overflow
# check specifically waits on ".leaderboard-table", KB's own markup,
# so it stays scoped to the two routes KB still actually owns.
@pytest.mark.parametrize("route_key", ["pre", "r1"])
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_no_horizontal_overflow(browser, base_url, width, height, route_key):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES[route_key])
    page.wait_for_selector(".leaderboard-table tbody tr")
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    context.close()
    assert scroll_width <= client_width, (
        f"{route_key} {width}x{height}: horizontal overflow ({scroll_width} > {client_width})"
    )


@pytest.mark.parametrize("route_key", ["root", "pre", "r1"])
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_nav_never_wraps(browser, base_url, width, height, route_key):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES[route_key])
    header_box = page.locator(".neo-global-header").bounding_box()
    context.close()
    assert header_box["height"] <= 72, (
        f"{route_key} {width}x{height}: header wrapped (height={header_box['height']})"
    )


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_pre_all_120_players_render(browser, base_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES["pre"])
    page.wait_for_selector(".leaderboard-table tbody tr")
    count = page.locator(".leaderboard-table tbody tr").count()
    context.close()
    assert count == 120


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_r1_all_118_players_render(browser, base_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES["r1"])
    page.wait_for_selector(".leaderboard-table tbody tr")
    count = page.locator(".leaderboard-table tbody tr").count()
    context.close()
    assert count == 118


@pytest.mark.parametrize("route_key", ["pre", "r1"])
@pytest.mark.parametrize("width,height", [(390, 844), (430, 932)])
def test_sponsor_immediately_below_player_name(browser, base_url, width, height, route_key):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES[route_key])
    page.wait_for_selector(".leaderboard-table tbody tr")
    first_row = page.locator(".leaderboard-table tbody tr").first
    name_box = first_row.locator(".player-name").bounding_box()
    sponsor_locator = first_row.locator(".player-sponsor")
    sponsor_count = sponsor_locator.count()
    sponsor_box = sponsor_locator.bounding_box() if sponsor_count == 1 else None
    context.close()
    assert sponsor_count == 1
    # sponsor must sit directly under the name, never beside it
    assert sponsor_box["y"] >= name_box["y"] + name_box["height"] - 2, (
        f"{route_key} {width}x{height}: sponsor is not below player name"
    )
    assert abs(sponsor_box["x"] - name_box["x"]) <= 4, (
        f"{route_key} {width}x{height}: sponsor horizontally displaced from player name"
    )


@pytest.mark.parametrize("width,height", [(390, 844), (430, 932), (768, 1024)])
def test_r1_probability_cells_never_collide(browser, base_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES["r1"])
    page.wait_for_selector(".leaderboard-table tbody tr")
    first_row = page.locator(".leaderboard-table tbody tr").first
    cells = first_row.locator("td")
    boxes = [cells.nth(i).bounding_box() for i in range(cells.count())]
    context.close()
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            x_overlap = a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
            y_overlap = a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]
            assert not (x_overlap and y_overlap), f"{width}x{height}: R1 cells {i} and {j} collide"


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_r1_probability_order(browser, base_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES["r1"])
    labels = page.eval_on_selector_all(
        ".leaderboard-table thead th", "els => els.map(e => e.textContent.trim())"
    )
    context.close()
    prob_labels = [l for l in labels if l in ("컷 통과", "Top20", "Top10", "Top5", "우승")]
    assert prob_labels == ["컷 통과", "Top20", "Top10", "Top5", "우승"]


@pytest.mark.parametrize("route_key", ["pre", "r1"])
def test_footer_no_horizontal_overflow(browser, base_url, route_key):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(base_url + ROUTES[route_key])
    footer_box = page.locator(".site-footer").bounding_box()
    client_width = page.evaluate("document.documentElement.clientWidth")
    context.close()
    assert footer_box["width"] <= client_width + 1


@pytest.mark.parametrize("route_key", ["pre", "r1"])
def test_decimal_display_one_place(browser, base_url, route_key):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(base_url + ROUTES[route_key])
    html = page.content()
    context.close()
    two_decimal_percents = re.findall(r"\d+\.\d{2}%", html)
    assert two_decimal_percents == [], f"{route_key}: found 2-decimal percentages: {two_decimal_percents[:5]}"


@pytest.mark.parametrize("width,height", [(390, 844), (768, 1024)])
def test_stage_nav_pre_to_r1_no_overflow(browser, base_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base_url + ROUTES["pre"])
    nav_box = page.locator(".stage-nav").bounding_box()
    client_width = page.evaluate("document.documentElement.clientWidth")
    context.close()
    assert nav_box["width"] <= client_width + 1
