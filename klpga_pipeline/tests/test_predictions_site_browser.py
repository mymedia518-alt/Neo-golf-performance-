"""Playwright browser tests for the generated static site — the
DOM-level behaviors a Python-only test can't verify: that search/
filter interactions never reorder rows in the live DOM (only hide/show
them), that expand/collapse actually toggles, and that the mobile
layout (360px viewport) shows Rank/Player/Win% without horizontal
scrolling. `playwright>=1.40` is already a declared project dependency
(requirements.txt) — this is not a new dependency.

Skips gracefully (never fails the suite) if Chromium isn't available
in the environment running pytest, so the rest of the suite's
reliability is unaffected."""
from __future__ import annotations

import glob
import http.server
import os
import socket
import threading
from contextlib import closing

import pytest

from klpga.archive.prediction_archive import (
    EntrantSnapshot,
    PredictionSnapshot,
    build_live_atomic_provenance,
    write_prediction_snapshot_atomic,
)
from klpga.site.build import build_site

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None


def _entrant(rank: int, code: str, name: str, prob: float) -> EntrantSnapshot:
    return EntrantSnapshot(
        rank=rank,
        player_code=code,
        player_name_display=name,
        win_probability=prob,
        prior_events_n=10,
        prior_avg_round_score_to_par=-2.0,
        prior_recent_form_10=-3.0,
        prior_recent_form_10_n=8,
        history_slice="moderate_10_19",
        player_master_matched=True,
    )


def _sample_snapshot(n_players: int = 25) -> PredictionSnapshot:
    entrants = [
        _entrant(i, f"P{i:03d}", f"선수{i:03d}", max(0.001, 0.30 - (i - 1) * 0.01)) for i in range(1, n_players + 1)
    ]
    probs = [e.win_probability for e in entrants]
    return PredictionSnapshot(
        prediction_id="001",
        created_at_utc="2026-08-26T00:00:00Z",
        record_kind="neo_prediction_archive_v1",
        game_code="2026080001",
        tournament_name="제15회 KG 레이디스 오픈",
        cutoff_date="2026-08-27",
        cutoff_source="explicit_arg",
        model_id="M4",
        model_version="v1",
        model_features=("prior_avg_round_score_to_par", "prior_recent_form_10"),
        training_tournament_count=100,
        field_size=n_players,
        entrants_predicted=n_players,
        dropped_entrants=0,
        probability_sum=sum(probs),
        minimum_probability=min(probs),
        maximum_probability=max(probs),
        zero_history_count=0,
        unmatched_count=0,
        required_final_checks={
            "entrants_parsed_eq_field_size": True,
            "entrants_predicted_eq_field_size": True,
            "dropped_entrants_eq_zero": True,
            "duplicate_player_codes_eq_zero": True,
            "probability_sum_within_tolerance": True,
        },
        known_limitations=(),
        provenance=build_live_atomic_provenance(),
        predictions=tuple(entrants),
    )


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture()
def site_url(tmp_path):
    predictions_root = tmp_path / "predictions"
    write_prediction_snapshot_atomic(_sample_snapshot(), predictions_root)
    result = build_site(predictions_root, tmp_path / "dist")

    port = _free_port()

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(result.output_root), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _fallback_chromium_executable() -> str | None:
    """Playwright's default `launch()` resolves a "headless shell"
    binary matched to the installed `playwright` pip package's exact
    build number, which can mismatch a pre-provisioned/cached browser
    directory (a different, but fully functional, full Chromium
    build). If that happens, fall back to whatever full `chromium-*`
    build is actually present under `PLAYWRIGHT_BROWSERS_PATH`, rather
    than skipping a working environment."""
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


def _ranks(page, selector: str) -> list[str]:
    return page.eval_on_selector_all(selector, "els => els.map(e => e.getAttribute('data-rank'))")


def test_search_never_reorders_rows_only_hides_them(page, site_url):
    page.goto(site_url)
    before = _ranks(page, ".pred-row")

    page.fill("#player-search", "선수015")
    page.wait_for_timeout(100)

    after = _ranks(page, ".pred-row")
    assert before == after, "DOM row order must never change on search"

    visible = _ranks(page, ".pred-row:not(.row-hidden)")
    assert visible == ["15"]


def test_top10_filter_hides_rows_without_reordering(page, site_url):
    page.goto(site_url)
    before = _ranks(page, ".pred-row")

    page.click('.filter-pill[data-filter="top10"]')
    page.wait_for_timeout(100)

    after = _ranks(page, ".pred-row")
    assert before == after, "DOM row order must never change on filter"

    visible = sorted(int(r) for r in _ranks(page, ".pred-row:not(.row-hidden)"))
    assert visible == list(range(1, 11))


def test_all_filter_restores_every_row(page, site_url):
    page.goto(site_url)
    page.click('.filter-pill[data-filter="top10"]')
    page.wait_for_timeout(50)
    page.click('.filter-pill[data-filter="all"]')
    page.wait_for_timeout(50)
    visible = _ranks(page, ".pred-row:not(.row-hidden)")
    assert len(visible) == 25


def test_expand_collapse_toggles_detail_row(page, site_url):
    page.goto(site_url)
    first_row = page.locator('.pred-row[data-rank="1"]')
    first_detail = page.locator(".pred-detail").first

    assert first_detail.is_hidden()
    first_row.click()
    assert first_detail.is_visible()
    first_row.click()
    assert first_detail.is_hidden()


def test_mobile_viewport_shows_rank_player_win_without_horizontal_scroll(page, site_url):
    page.set_viewport_size({"width": 360, "height": 800})
    page.goto(site_url)

    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, (
        f"page requires horizontal scroll on a 360px viewport: scrollWidth={scroll_width}, "
        f"clientWidth={client_width}"
    )

    assert page.locator("th.col-rank").is_visible()
    assert page.locator("th.col-player").is_visible()
    assert page.locator("th.col-prob").is_visible()


def test_home_page_title_and_status_badge(page, site_url):
    page.goto(site_url)
    assert "NEO GOLF PREDICTIONS" in page.title()
    # PRE-TOURNAMENT legitimately appears twice as of v1.1 (the
    # tournament header badge, and again in the simplified public
    # Prediction Record panel) — assert the header's badge specifically.
    assert page.locator(".tournament-header .badge-status").inner_text() == "PRE-TOURNAMENT"
