"""Playwright browser test for the R2 PRODUCTION DEPLOYMENT page —
production integrity gate #11 ("mobile layout has no horizontal page
overflow"), verified as a real rendered-DOM measurement rather than
just a CSS assumption. Same fixture pattern as
tests/test_predictions_site_browser.py (this project's established
precedent); skips gracefully if Chromium isn't available."""
from __future__ import annotations

import glob
import http.server
import os
import socket
import threading
from contextlib import closing

import pytest

from klpga.neo_win.r2_production_page import (
    render_calibration_section,
    render_production_hero_section,
    render_production_page,
    render_r2_forecast_section,
    render_r2_forecast_table_rows,
)

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None


def _forecast_row(code, name, rank, score, top20, top10, top5, win):
    return {"player_code": code, "player_name": name, "r2_rank": str(rank), "r2_total_score": score,
            "top20_pct": top20, "top10_pct": top10, "top5_pct": top5, "win_pct": win}


def _sample_forecast_rows(n: int = 30) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        base = max(0.5, 30.0 - i)
        rows.append(_forecast_row(f"P{i:03d}", f"선수이름{i:03d}", i, 140 + i, min(99.0, base * 3), min(99.0, base * 2), base * 1.2, base * 0.5))
    return rows


def _sample_page_html() -> str:
    cut_summary = {
        "n_evaluated": 110, "n_r1_players": 115, "actual_made_cut_count": 62, "actual_missed_cut_count": 48,
        "threshold_accuracy_pct": 68.1818, "brier_score": 0.207404, "log_loss": 0.892103,
        "mean_predicted_cut_pct": 30.3664, "actual_cut_rate_pct": 56.3636,
    }
    threshold_survival = {"threshold_pct": 40.0, "n_at_or_above": 35, "n_made_cut": 35}
    calibration = [
        {"bucket": "0-20%", "n": 48, "made_cut_count": 9, "avg_predicted_pct": 10.0, "actual_made_cut_rate_pct": 18.75, "calibration_gap_pct": 8.75},
        {"bucket": "20-40%", "n": 27, "made_cut_count": 18, "avg_predicted_pct": 30.0, "actual_made_cut_rate_pct": 66.67, "calibration_gap_pct": 36.67},
        {"bucket": "40-60%", "n": 16, "made_cut_count": 16, "avg_predicted_pct": 50.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 50.0},
        {"bucket": "60-80%", "n": 12, "made_cut_count": 12, "avg_predicted_pct": 70.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 30.0},
        {"bucket": "80-100%", "n": 7, "made_cut_count": 7, "avg_predicted_pct": 90.0, "actual_made_cut_rate_pct": 100.0, "calibration_gap_pct": 10.0},
    ]
    rows = _sample_forecast_rows()

    hero = render_production_hero_section(cut_summary, threshold_survival, calibration)
    cal = render_calibration_section(calibration)
    table_html = render_r2_forecast_table_rows(rows, clickable=False)
    forecast_section = render_r2_forecast_section(table_html)
    return render_production_page(
        tournament_name="제15회 KG 레이디스 오픈", status_pill_text="Round 2 Complete",
        hero_html=hero, calibration_html=cal, forecast_section_html=forecast_section,
        player_cards_html="", include_player_card_assets=False,
    )


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_sample_page_html(), encoding="utf-8")

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


def test_mobile_viewport_has_no_horizontal_overflow(page, page_url):
    page.set_viewport_size({"width": 360, "height": 800})
    page.goto(page_url)

    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, (
        f"R2 production page requires horizontal scroll on a 360px viewport: "
        f"scrollWidth={scroll_width}, clientWidth={client_width}"
    )


def test_hero_and_forecast_sections_visible_on_mobile(page, page_url):
    page.set_viewport_size({"width": 360, "height": 800})
    page.goto(page_url)
    assert page.locator("section.hero h1").is_visible()
    assert page.locator("section.forecast h2").is_visible()


def test_desktop_viewport_also_has_no_horizontal_overflow(page, page_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(page_url)
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1
