"""Tests for scripts/225_build_hj_2026100004_pre_page.py -- the HJ
PRE page built from the frozen Stableford V1 snapshot, never a new
0-100 score, never a fabricated K-RANKING/win-probability column."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "225_build_hj_2026100004_pre_page.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("pre_225", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pre_225"] = module
    spec.loader.exec_module(module)
    return module


def test_all_108_entrants_present_exactly_once():
    mod = _load_module()
    result = mod.build()
    assert result["field_size"] == 108
    assert result["ranked_count"] + result["no_prior_data_count"] == 108


def test_top_ranks_match_frozen_snapshot_order():
    mod = _load_module()
    result = mod.build()
    html = result["html"]
    expected_top5 = ["서교림", "김민솔", "유현조", "박현경", "김민선7"]
    tbody = html[html.find("<tbody>"):]
    positions = [tbody.find(name) for name in expected_top5]
    assert positions == sorted(positions), "top-5 order must match the frozen V1 rank order"
    assert all(p != -1 for p in positions)


def test_no_fabricated_0_to_100_score_or_kranking_or_win_probability():
    mod = _load_module()
    html = mod.build()["html"]
    for forbidden in ("Stableford Fit", "KLPGA K-RANKING", "우승확률", "컷 통과확률", "NEO 경기력"):
        assert forbidden not in html


def test_no_internal_verification_jargon_exposed():
    mod = _load_module()
    html = mod.build()["html"]
    for forbidden in ("sha256", "CORE", "SUPPORTING", "REJECTED", "parser", "cutoff"):
        assert forbidden not in html


def test_data_limited_players_never_get_a_fabricated_rank():
    mod = _load_module()
    result = mod.build()
    html = result["html"]
    assert "신규 출전" in html
    assert "표본 적음" in html  # the 2 thin-sample players stay ranked but visibly marked
    # "데이터 부족" appears once per no-prior-data player's rank cell, plus once
    # per non-OK-sim-status player's cut/top20/win cells (3 each), plus once in
    # the page's own explanatory footnote -- never a hardcoded magic count, since
    # it depends on how many players the live Monte Carlo results mark non-OK.
    import json
    snapshot = json.loads(mod.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    mc = json.loads((mod.CONTENT / "HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json").read_text(encoding="utf-8"))
    mc_by_pid = {str(p["player_code"]): p for p in mc["players"]}
    non_ok_sim = sum(
        1 for r in snapshot["records"]
        if (sim := mc_by_pid.get(str(r["player_code"]))) and sim.get("data_status") != "OK"
    )
    expected = result["no_prior_data_count"] + non_ok_sim * 3 + 1  # +1 for the footnote
    assert html.count("데이터 부족") == expected


def test_rank_format_is_hash_number_never_a_decimal_score():
    mod = _load_module()
    html = mod.build()["html"]
    assert "#1</td>" in html or "#1 <span" in html
    import re
    assert not re.search(r"#\d+\.\d", html)


def test_no_operational_update_timestamps_shown_to_readers():
    mod = _load_module()
    html = mod.build()["html"]
    assert "페이지 업데이트" not in html
    assert "1R 종료 후 업데이트" not in html


def test_stableford_scoring_shown_high_to_low_including_albatross_and_par():
    mod = _load_module()
    html = mod.build()["html"]
    for term in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3"):
        assert term in html
    positions = [html.find(t) for t in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3")]
    assert positions == sorted(positions), "scores must render +8 -> +5 -> +2 -> 0 -> -1 -> -3"


def test_seogyorim_data_kept_but_player_page_link_removed():
    mod = _load_module()
    html = mod.build()["html"]
    idx = html.find("서교림")
    assert idx != -1
    window = html[max(0, idx - 300):idx]
    assert "/player/11134/" not in window, "서교림 must never link to her own (broken) player page"
    assert "#1" in html[idx:idx + 400] or "삼천리" in html[idx:idx + 200]


def test_other_players_player_page_links_unaffected():
    mod = _load_module()
    html = mod.build()["html"]
    idx = html.find("김민솔")
    window = html[max(0, idx - 250):idx]
    assert "/player/10725/" in window
