"""KB금융 골든라이프 챔피언십 FR BUILD (2026-09-13): tests for
klpga.neo_win.fr_real_page and scripts/132_build_kb_fr_page.py.

Uses the REAL KB 2026090003 pipeline (real V3 operator-supplied-
official-screenshot evidence, positions 1-39) -- the same inputs
scripts/132 itself uses -- so these are simultaneously unit tests of
the renderer AND a regression guard against the real production
output. Covers exactly what the FR BUILD mission required: winner,
leaderboard, round arithmetic, tie positions, sponsor invariant,
39-row scope, zero internal-state leakage, ZERO model-analysis
language (FR is a pure results page), navigation, mobile structure,
and R3 freeze integrity."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from klpga.neo_win.fr_real_page import is_fr_real_page, render_fr_real_page
from klpga.tournament_context import load_tournament_context

ROOT = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090003"
EXPECTED_R3_FORECAST_SHA256 = "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"


@pytest.fixture(scope="module")
def real_fr_html():
    context = load_tournament_context(GAME_CODE)
    evidence_path = ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert all(not r["review_required"] and r["player_id"] is not None for r in evidence["confirmed_records"])
    html = render_fr_real_page(
        tournament_name=context.tournament_name, game_code=context.game_code,
        date_range=context.display_date_range, evidence=evidence,
    )
    return html, evidence


def test_is_fr_real_page_recognizes_real_output(real_fr_html):
    html, _evidence = real_fr_html
    assert is_fr_real_page(html) is True


def test_is_fr_real_page_rejects_arbitrary_html():
    assert is_fr_real_page("<html><body>not an fr page</body></html>") is False


def test_winner_is_박보겸_with_correct_score(real_fr_html):
    html, evidence = real_fr_html
    winner = next(r for r in evidence["confirmed_records"] if str(r["final_rank"]) == "1")
    assert winner["player_name"] == "박보겸"
    assert winner["final_to_par"] == -5
    assert winner["final_total_strokes"] == 283
    assert winner["r4_strokes"] == 71
    assert "우승 <span class='player-name'>박보겸</span><span class='player-sponsor'>삼천리</span>" in html
    assert "<span class='metric'>-5</span>" in html
    assert "FR 71" in html


def test_leaderboard_has_exactly_39_rows_in_rank_order(real_fr_html):
    html, evidence = real_fr_html
    rows = re.findall(r"<tr data-player-id='(\d+)'>", html)
    assert len(rows) == 39
    assert len(evidence["confirmed_records"]) == 39


def test_round_arithmetic_is_correct_for_every_row(real_fr_html):
    _html, evidence = real_fr_html
    par_per_round = evidence["par_per_round"]
    for r in evidence["confirmed_records"]:
        rounds = [r["r1_strokes"], r["r2_strokes"], r["r3_strokes"], r["r4_strokes"]]
        assert sum(rounds) == r["final_total_strokes"]
        assert r["final_total_strokes"] - par_per_round * 4 == r["final_to_par"]


def test_tie_positions_render_with_t_prefix(real_fr_html):
    html, _evidence = real_fr_html
    for name in ("박예지", "방신실", "유서연2"):
        row = re.search(rf"<tr data-player-id='\d+'>(?:(?!</tr>).)*{name}.*?</tr>", html, re.DOTALL)
        assert row is not None
        assert "data-label='순위'>T2<" in row.group(0)


def test_leaderboard_columns_are_r1_r2_r3_fr_total_in_order(real_fr_html):
    html, evidence = real_fr_html
    winner = next(r for r in evidence["confirmed_records"] if str(r["final_rank"]) == "1")
    row = re.search(rf"<tr data-player-id='{winner['player_id']}'>((?:(?!</tr>).)*)", html).group(1)
    assert "data-label='R1'>70<" in row
    assert "data-label='R2'>69<" in row
    assert "data-label='R3'>73<" in row
    assert "data-label='FR'>71<" in row
    assert "data-label='합계'>-5<" in row


def test_sponsor_invariant_every_name_has_a_sponsor_span(real_fr_html):
    html, _evidence = real_fr_html
    name_count = html.count("class='player-name'")
    sponsor_count = html.count("class='player-sponsor'")
    assert name_count > 0
    assert name_count == sponsor_count


def test_sponsor_left_blank_when_unverified_never_guessed(real_fr_html):
    html, evidence = real_fr_html
    row = next(r for r in evidence["confirmed_records"] if r["player_name"] == "유서연2")
    assert row.get("sponsor") is None
    match = re.search(r"<tr data-player-id='11066'>((?:(?!</tr>).)*)", html)
    assert match is not None
    assert "class='player-sponsor'></span>" in match.group(0)


def test_scope_label_present_and_correct(real_fr_html):
    html, evidence = real_fr_html
    scope_through = evidence["positions_confirmed_gapless_through"]
    assert scope_through == 39
    assert f"FR 상위 {scope_through}명 공식 결과 기준" in html
    assert "70명" not in html


def test_no_internal_state_leak(real_fr_html):
    html, _evidence = real_fr_html
    forbidden = [
        "sha256", "evidence_tier", "OPERATOR_SUPPLIED", "OPERATOR_REPORTED",
        "review_required", "content/website_v2", "build_id", "code_commit",
        "fingerprint", "not_direct_klpga_automated_ingestion",
    ]
    for needle in forbidden:
        assert needle not in html
    for pattern in (r"\.py\b", r"[A-Za-z0-9_\-/]+\.json"):
        assert not re.search(pattern, html)


def test_zero_model_analysis_language(real_fr_html):
    """FR is a RESULT page, not an analysis page -- none of NEO's
    probability/validation/postmortem vocabulary may appear here."""
    html, _evidence = real_fr_html
    forbidden = [
        "우승확률", "win_pct", "NEO 우승", "NEO 예상", "NEO 랭킹", "NEO PICK",
        "Top5", "Top10", "Top20", "top5_pct", "top10_pct", "top20_pct",
        "확률", "Brier", "log_loss", "Monte Carlo", "몬테카를로",
        "SURPRISE", "MISS", "예측", "postmortem", "코스 분석", "모델",
    ]
    for needle in forbidden:
        assert needle not in html, f"forbidden model-analysis term leaked into FR: {needle!r}"


def test_stage_nav_fr_current_no_final_link(real_fr_html):
    """Desired sequence for THIS build: PRE -> R1 -> R2 -> R3 -> FR
    only -- FINAL is explicitly out of scope for FR's own nav."""
    html, _evidence = real_fr_html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/pre/">사전 분석 PRE</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r2/">R2</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r3/">R3</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/fr/" aria-current="page">FR</a>' in html
    assert "FINAL" not in html.split("<nav", 1)[1].split("</nav>", 1)[0]


def test_mobile_leaderboard_uses_fr_full_modifier(real_fr_html):
    html, _evidence = real_fr_html
    assert 'class="data leaderboard-table leaderboard-table--fr-full"' in html
    assert "data-label='순위'" in html
    assert "data-label='선수'" in html
    assert "data-label='FR'" in html
    assert "data-label='합계'" in html


def test_r3_frozen_forecast_fingerprint_unchanged():
    path = ROOT / "content" / "website_v2" / "2026090003_POST_R3_FINAL_FORECAST.json"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == EXPECTED_R3_FORECAST_SHA256


# ---------------------------------------------------------------------
# LAST-ROW VISIBILITY BUG (2026-09-13): "39 rows exist in the HTML" is
# not the same claim as "all 39 rows are reachable by normal page
# scrolling" -- neo.css's shared .table-wrap class carried an
# unconditional overflow-y:hidden (only ever inert because .table-wrap
# had no explicit height, so clientHeight always equalled scrollHeight
# by coincidence) that could silently clip the leaderboard the moment
# any future rule gave the container a height. These tests render the
# REAL committed docs/ output in an actual browser -- not a string
# assertion on the HTML source -- and physically scroll the page to
# prove the true final player's complete row is visible on both
# desktop and mobile, plus assert the container can never clip
# vertically regardless of what future CSS does to its height.
# ---------------------------------------------------------------------
import http.server
import socket
import threading
from contextlib import closing

try:
    from playwright.sync_api import sync_playwright
except ImportError as _exc:  # pragma: no cover
    sync_playwright = None
    _PLAYWRIGHT_IMPORT_ERROR = _exc
else:
    _PLAYWRIGHT_IMPORT_ERROR = None

DOCS = ROOT.parent / "docs"
FR_ROUTE = "/tournaments/2026/2026090003/fr/"


def _real_current_production_evidence() -> dict:
    """MISSION J (2026-09-13): production now builds FR from the
    validated, complete 70-player official dataset via
    scripts/138_build_kb_fr_page_full70.py, not the 39-row V3 evidence
    scripts/132 used before the 70/70 DATA GATE passed. Load the same
    evidence the live docs/ page was actually built from, so this test
    file never re-drifts from whatever is really on disk."""
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location(
        "kb_fr_build_full70", ROOT / "scripts" / "138_build_kb_fr_page_full70.py"
    )
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["kb_fr_build_full70"] = mod
    spec.loader.exec_module(mod)
    return mod.build_evidence()


def _real_last_confirmed_record() -> dict:
    evidence = _real_current_production_evidence()
    records = sorted(evidence["confirmed_records"], key=lambda r: r["position_from"])
    assert len(records) == 70
    return records[-1]


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def fr_base_url():
    assert (DOCS / "tournaments" / "2026" / "2026090003" / "fr" / "index.html").is_file()
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


@pytest.fixture(scope="module")
def fr_browser():
    if sync_playwright is None:
        pytest.skip(f"playwright not importable: {_PLAYWRIGHT_IMPORT_ERROR}")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium not available in this environment: {exc}")
        yield b
        b.close()


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_final_player_row_reachable_by_real_page_scroll(fr_browser, fr_base_url, width, height):
    """The exact required proof: after a REAL window.scrollTo to the
    bottom of the page (not a full-page screenshot trick), the true
    final confirmed player's row/card must be entirely inside the
    viewport -- not merely present somewhere in the DOM."""
    last = _real_last_confirmed_record()
    context = fr_browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(f"{fr_base_url}{FR_ROUTE}", wait_until="networkidle")

    rows = page.locator("tr[data-player-id]")
    assert rows.count() == 70

    first_row = rows.first
    first_box = first_row.bounding_box()
    assert first_box is not None
    assert first_box["y"] < height, "first player row must be visible near the top without scrolling"

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(150)

    last_row = page.locator(f"tr[data-player-id='{last['player_id']}']")
    assert last_row.count() == 1
    box = last_row.bounding_box()
    assert box is not None, f"final player row ({last['player_name']}) not found in rendered page"
    assert box["y"] >= 0 and box["y"] + box["height"] <= height, (
        f"final player row ({last['player_name']}) not fully visible after scrolling to the bottom "
        f"of the page at {width}x{height}: box={box}"
    )
    context.close()


def test_leaderboard_container_chain_cannot_clip_vertically(fr_browser, fr_base_url):
    """No ancestor of the leaderboard table -- table-wrap included --
    may have overflow-y:hidden combined with a clientHeight smaller
    than its scrollHeight. This is the generic, future-proof version of
    the check above: it fails even if a later change gives one of
    these containers an explicit height, long before it would ever
    visibly clip a row."""
    context = fr_browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(f"{fr_base_url}{FR_ROUTE}", wait_until="networkidle")

    chain = page.evaluate("""
        () => {
          const results = [];
          let el = document.querySelector('#fr-leaderboard table');
          while (el) {
            const cs = getComputedStyle(el);
            results.push({
              tag: el.tagName, cls: el.className,
              overflowY: cs.overflowY,
              clientHeight: el.clientHeight, scrollHeight: el.scrollHeight,
            });
            el = el.parentElement;
          }
          return results;
        }
    """)
    assert chain, "could not walk ancestor chain of the FR leaderboard table"
    for node in chain:
        clipped = node["overflowY"] == "hidden" and node["scrollHeight"] > node["clientHeight"]
        assert not clipped, f"leaderboard ancestor clips vertical content: {node}"
    context.close()


def test_no_fixed_or_max_height_on_leaderboard_containers(fr_browser, fr_base_url):
    context = fr_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(f"{fr_base_url}{FR_ROUTE}", wait_until="networkidle")

    panel_height_info = page.evaluate("""
        () => {
          const panel = document.querySelector('#fr-leaderboard');
          const wrap = panel.querySelector('.table-wrap');
          const cs_panel = getComputedStyle(panel);
          const cs_wrap = getComputedStyle(wrap);
          return {
            panelMaxHeight: cs_panel.maxHeight, wrapMaxHeight: cs_wrap.maxHeight,
            wrapClientHeight: wrap.clientHeight, wrapScrollHeight: wrap.scrollHeight,
          };
        }
    """)
    assert panel_height_info["panelMaxHeight"] == "none"
    assert panel_height_info["wrapMaxHeight"] == "none"
    assert panel_height_info["wrapClientHeight"] >= panel_height_info["wrapScrollHeight"]
    context.close()
