"""Playwright browser test for HOME's "현재 스코어" sort option --
verifies the REAL top120.js sort logic against the spec's own example
(never a re-implementation assumption): rows [-5·5H, -5·15H, -4·F, —]
must resort to [-5·15H, -5·5H, -4·F, —] when "현재 스코어" is selected.
Same fixture pattern as tests/test_r2_production_page_browser.py
(this project's established precedent); skips gracefully if Chromium
isn't available."""
from __future__ import annotations

import glob
import http.server
import os
import shutil
import socket
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from klpga.website_v2.current_score_display import format_current_score  # noqa: E402
from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402

import importlib.util

_spec = importlib.util.spec_from_file_location("script88_under_test", ROOT / "scripts" / "88_build_neo_top120_candidate.py")
script88 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script88)

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None


def _row(player_id, name, k_rank):
    return {"player_id": player_id, "player_name": name, "official_k_rank": k_rank, "neo_validation_rank": k_rank, "features": {}}


def _sample_page_html() -> str:
    rows = [_row("1", "선수A", 10), _row("2", "선수B", 20), _row("3", "선수C", 30), _row("4", "선수D", 40)]
    cells = {
        "1": format_current_score(-5, "5", "ACTIVE"),
        "2": format_current_score(-5, "15", "ACTIVE"),
        "3": format_current_score(-4, "18", "ACTIVE"),
        "4": format_current_score(None, None, None),
    }
    summary = {"neo_ranked": 4, "validation_pending": 0}
    html = script88.render_clean(rows, summary, None, current_score_cells_by_id=cells)
    return inject_global_navigation(html, active_section="home")


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(_sample_page_html(), encoding="utf-8")
    shutil.copyfile(ROOT / "src" / "klpga" / "website_v2" / "static" / "top120.js", dist / "assets" / "top120.js")
    (dist / "assets" / "neo-site.css").write_text("", encoding="utf-8")

    port = _free_port()

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(dist), **kwargs)

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


def test_current_score_sort_matches_the_spec_example(page, page_url):
    page.goto(page_url)
    page.wait_for_selector("[data-player-row]")
    page.select_option("#home-sort", "current-score")
    names = page.eval_on_selector_all("[data-player-row]", "els => els.map(e => e.dataset.playerName)")
    assert names == ["선수b", "선수a", "선수c", "선수d"]


def test_current_score_cell_renders_on_one_line(page, page_url):
    page.goto(page_url)
    cell = page.locator("[data-player-row]").first.locator("td").last
    box = cell.bounding_box()
    assert box["height"] < 40  # single text line, not wrapped
