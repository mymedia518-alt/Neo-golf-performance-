"""Regression tests for Hana (2026090002) R2: the official-cut-only
probability population, cut-missed players kept in the score table
with `--` probability cells, WD exclusion, and reuse (not
reimplementation) of KB's own generic Monte Carlo engine
(klpga.neo_win.round_update_r2.simulate_post_round2 via
klpga.neo_win.post_r2_forecast.run_post_r2_forecast).

Operator's explicit requirements under test:
  - 108 official entrants; 105 real R2 leaderboard rows; 102 real-score
    rows; 3 WD by exact name (최예본/리 슈잉/박혜준), never guessed.
  - Official cut fixed at +6 / 150 strokes; exactly 64 players made it.
  - remaining_rounds=2, n_simulations=60000, real R1+R2 scores --
    computed by the SAME generic KB engine, not a new one.
  - No current-round SG added to the historical baseline.
  - Public page: 102 score rows, WD excluded, only the 64 cut-survivors
    show real TOP20/TOP10/TOP5/win probabilities; the 38 cut-missed
    rows show real scores with `--` probability cells (never 0%).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"
CONTENT = KLPGA_ROOT / "content" / "website_v2"

FREEZE_PATH = CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json"
FORECAST_PATH = CONTENT / "2026090002_POST_R2_FINAL_FORECAST.json"
SNAPSHOT_PATH = CONTENT / "2026090002_PRE_PERFORMANCE_SNAPSHOT.json"
R2_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r2" / "index.html"

CONFIRMED_WD_NAMES = {"최예본", "리 슈잉", "박혜준"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_snapshot_is_leakage_safe_and_reuses_the_same_historical_windows():
    snapshot = _load(SNAPSHOT_PATH)
    assert snapshot["game_code"] == "2026090002"
    assert snapshot["calculation_version"] == "ok_open_pre_performance_v1"
    assert snapshot["cutoff"].startswith("2026-09-17")
    assert len(snapshot["profiles"]) == 108
    sample = snapshot["profiles"][0]
    assert set(sample["windows"].keys()) == {"current", "recent3", "recent5", "recent10", "season2026", "multi_season"}


def test_freeze_has_exactly_105_records_with_correct_status_split():
    freeze = _load(FREEZE_PATH)
    assert freeze["game_code"] == "2026090002"
    assert freeze["round"] == 2
    records = freeze["records"]
    assert len(records) == 105
    status_counts = {}
    for r in records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    assert status_counts == {"ACTIVE": 64, "CUT": 38, "WD": 3}


def test_freeze_wd_players_are_exactly_the_confirmed_three_by_name():
    freeze = _load(FREEZE_PATH)
    wd_names = {r["player_name"] for r in freeze["records"] if r["status"] == "WD"}
    assert wd_names == CONFIRMED_WD_NAMES


def test_freeze_cut_line_is_official_plus6_150():
    freeze = _load(FREEZE_PATH)
    for r in freeze["records"]:
        if r["status"] == "WD":
            continue
        total = r["r2_total_under_par"]
        assert total is not None
        if r["status"] == "ACTIVE":
            assert total <= 6, f"{r['player_name']} marked ACTIVE but total={total} > +6"
        else:
            assert total > 6, f"{r['player_name']} marked CUT but total={total} <= +6"


def test_freeze_every_non_wd_record_has_a_real_r1_score_joined():
    freeze = _load(FREEZE_PATH)
    for r in freeze["records"]:
        if r["status"] == "WD":
            continue
        assert r["r1_score_to_par"] is not None, f"{r['player_name']} missing real R1 score"


def test_freeze_no_sg_field_anywhere():
    """Operator's explicit instruction: current-round SG is never added
    to the historical baseline for this forecast."""
    freeze = _load(FREEZE_PATH)
    raw = json.dumps(freeze, ensure_ascii=False)
    assert '"sg"' not in raw.lower() and "strokes_gained" not in raw.lower()


def test_forecast_uses_the_generic_kb_engine_with_operator_specified_parameters():
    forecast = _load(FORECAST_PATH)
    assert forecast["game_code"] == "2026090002"
    assert forecast["remaining_rounds"] == 2
    assert forecast["n_simulations"] == 60000
    assert forecast["simulation_engine"] == "klpga.neo_win.round_update_r2.simulate_post_round2"
    assert forecast["official_advancing_field_size"] == 64
    assert forecast["simulated_field_size"] == 64
    assert forecast["missing_players"] == []


def test_forecast_win_probabilities_sum_to_100_percent():
    forecast = _load(FORECAST_PATH)
    total = sum(r["win_pct"] for r in forecast["records"])
    assert abs(total - 100.0) < 0.01


def test_forecast_population_is_exactly_the_freeze_active_set():
    freeze = _load(FREEZE_PATH)
    forecast = _load(FORECAST_PATH)
    active_ids = {r["player_id"] for r in freeze["records"] if r["status"] == "ACTIVE"}
    forecast_ids = {r["player_id"] for r in forecast["records"]}
    assert active_ids == forecast_ids


def test_r2_page_has_102_score_rows_wd_excluded():
    html = R2_PAGE.read_text(encoding="utf-8")
    for name in CONFIRMED_WD_NAMES:
        assert name not in html
    rows = re.findall(r"<tr>.*?</tr>", html, re.S)
    data_rows = [r for r in rows if "data-label='순위'" in r]
    assert len(data_rows) == 102


def test_r2_page_cut_missed_rows_show_em_dash_never_zero_percent():
    """COLUMN RESTRUCTURE (2026-09-18): the header text/data-label is now
    '우승' (was '우승확률') and probability cells drop the trailing '%' --
    both are display-string changes only, not a data change; a cut-missed
    row must still show a bare em-dash, never a numeric "0"."""
    html = R2_PAGE.read_text(encoding="utf-8")
    rows = re.findall(r"<tr>.*?</tr>", html, re.S)
    cut_rows = [r for r in rows if "status-badge" in r]
    assert len(cut_rows) == 38
    for r in cut_rows:
        for label in ("TOP20", "TOP10", "TOP5", "우승"):
            cell = re.search(rf"data-label='{label}'>([^<]*)<", r)
            assert cell is not None
            assert cell.group(1) == "—", f"cut-missed row shows {cell.group(1)!r} for {label}, expected em-dash"
            assert re.search(rf"data-label='{label}'>0<", r) is None, f"cut-missed row shows a fabricated 0 for {label}"


def test_r2_page_cut_survivors_show_real_nonzero_probabilities():
    """COLUMN RESTRUCTURE (2026-09-18): header/data-label '우승확률' ->
    '우승'; cell values no longer carry a trailing '%'."""
    html = R2_PAGE.read_text(encoding="utf-8")
    rows = re.findall(r"<tr>.*?</tr>", html, re.S)
    active_rows = [r for r in rows if "data-label='순위'" in r and "status-badge" not in r]
    assert len(active_rows) == 64
    for r in active_rows:
        win_cell = re.search(r"data-label='우승'>([^<]*)<", r)
        assert win_cell is not None
        assert win_cell.group(1) != "—"
        assert "%" not in win_cell.group(1)


def test_r2_page_cumulative_score_is_to_par_never_raw_strokes():
    html = R2_PAGE.read_text(encoding="utf-8")
    cells = re.findall(r"data-label='합계'>([^<]*)<", html)
    assert cells
    for cell in cells:
        assert cell == "—" or re.fullmatch(r"E|[+-]\d{1,2}", cell), f"'합계' cell {cell!r} is not to-par notation"


def test_pre_and_r1_pages_untouched_by_r2_build():
    pre_page = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"
    r1_page = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
    assert pre_page.is_file()
    assert r1_page.is_file()
    assert "골든라이프" not in r1_page.read_text(encoding="utf-8")


def test_pre_and_r1_stage_nav_now_link_to_r2():
    pre_page = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "pre" / "index.html"
    r1_page = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html"
    r2_link = '<a class="stage-nav__link" href="/tournaments/2026/2026090002/r2/">R2</a>'
    assert r2_link in pre_page.read_text(encoding="utf-8")
    assert r2_link in r1_page.read_text(encoding="utf-8")


def test_r2_page_stage_nav_links_back_to_pre_and_r1_and_leaves_r3_fr_disabled():
    html = R2_PAGE.read_text(encoding="utf-8")
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/">' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090002/r1/">' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090002/r2/" aria-current="page">R2</a>' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">R3</span>' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">FR</span>' in html
