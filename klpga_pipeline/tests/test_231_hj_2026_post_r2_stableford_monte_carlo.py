"""Tests for scripts/231_hj_2026_post_r2_stableford_monte_carlo.py --
the POST-R2 R3 forecast for HJ 2026100004. R1+R2 are real, official
KLPGA results (collected via the real network, this sandbox cannot
reach klpga.co.kr directly -- see HJ_2026100004_R2_OFFICIAL_RESULTS_
AND_CUT_V1.json for the full evidence trail); only rounds 3+4 are
simulated, for the 61 players KLPGA's own official cut already let
through."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "231_hj_2026_post_r2_stableford_monte_carlo.py"
CONTENT = Path(__file__).parent.parent / "content" / "website_v2"


def _load_module():
    spec = importlib.util.spec_from_file_location("post_r2_mc_231", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["post_r2_mc_231"] = module
    spec.loader.exec_module(module)
    return module


def _run_main_into_tmp(tmp_path):
    """Load the script fresh and redirect its output paths into tmp_path
    before calling main() -- content/website_v2 is read-only in pytest
    (운영 데이터 보호 규칙), so main() must never write its real production
    output files during a test run."""
    mod = _load_module()
    mod.RESULTS_PATH = tmp_path / "RESULTS.json"
    mod.METHODOLOGY_PATH = tmp_path / "METHODOLOGY.md"
    mod.REPRODUCIBILITY_PATH = tmp_path / "REPRODUCIBILITY.json"
    mod.main()
    return mod


def test_r2_official_results_file_exists_and_sums_to_full_field():
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    assert r2["field_size"] == 108
    total = r2["advanced_count"] + r2["missed_cut_count"] + r2["wd_count"] + r2["other_status_count"]
    assert total == 108
    assert len(r2["advanced_to_r3"]) == r2["advanced_count"]
    assert len(r2["missed_cut"]) == r2["missed_cut_count"]
    assert len(r2["withdrawn"]) == r2["wd_count"]


def test_advanced_and_missed_cut_are_disjoint_and_cover_the_canonical_field():
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    identity = json.loads((CONTENT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json").read_text(encoding="utf-8"))
    canon_names = {r["player_name"] for r in identity["records"]}

    advanced_names = {p["player_name"] for p in r2["advanced_to_r3"]}
    missed_names = {p["player_name"] for p in r2["missed_cut"]}
    wd_names = {p["player_name"] for p in r2["withdrawn"]}

    assert not (advanced_names & missed_names)
    assert not (advanced_names & wd_names)
    assert not (missed_names & wd_names)
    assert advanced_names | missed_names | wd_names == canon_names


def test_cutline_is_clean_no_score_overlap():
    """The real observed cutline must cleanly separate advancing from
    missed-cut players -- no advancing player's real score should be
    lower than any missed-cut player's."""
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    lowest_advancing = min(p["cum36_points"] for p in r2["advanced_to_r3"])
    highest_missed = max((p["r1_points"] or 0) + (p["r2_points"] or 0) for p in r2["missed_cut"])
    assert lowest_advancing > highest_missed, (
        f"cutline overlap: lowest advancing {lowest_advancing} <= highest missed-cut {highest_missed}"
    )


def test_post_r2_forecast_covers_exactly_the_61_advancing_players(tmp_path):
    mod = _run_main_into_tmp(tmp_path)
    results = json.loads(mod.RESULTS_PATH.read_text(encoding="utf-8"))
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    assert results["advanced_to_r3_count"] == 61 == r2["advanced_count"]
    assert len(results["players"]) == 61
    forecast_names = {p["player_name"] for p in results["players"]}
    advanced_names = {p["player_name"] for p in r2["advanced_to_r3"]}
    assert forecast_names == advanced_names


def test_monte_carlo_config_matches_the_fixed_pre_event_baseline(tmp_path):
    mod = _run_main_into_tmp(tmp_path)
    results = json.loads(mod.RESULTS_PATH.read_text(encoding="utf-8"))
    cfg = results["monte_carlo_config"]
    assert cfg["primary_seed"] == 20261007
    assert cfg["n_sims"] == 60_000
    assert cfg["remaining_rounds_simulated"] == 2


def test_reproducibility_same_seed_bit_identical_and_cross_seed_stable(tmp_path):
    mod = _run_main_into_tmp(tmp_path)
    results = json.loads(mod.RESULTS_PATH.read_text(encoding="utf-8"))
    repro = results["reproducibility"]
    assert repro["same_seed_rerun_bit_identical"] is True
    assert {c["seed"] for c in repro["cross_seed_checks"]} == {20261008, 777}
    for check in repro["cross_seed_checks"]:
        assert check["max_abs_win_pct_delta_pct_points"] < 2.0
        assert check["top10_win_overlap_with_primary"] >= 8


def test_win_probabilities_sum_to_one_and_cut_is_trivially_true(tmp_path):
    mod = _run_main_into_tmp(tmp_path)
    results = json.loads(mod.RESULTS_PATH.read_text(encoding="utf-8"))
    win_sum = sum(p["win_pct"] for p in results["players"])
    assert abs(win_sum - 1.0) < 1e-6
    assert all(p["make_cut_pct"] == 1.0 for p in results["players"])


def test_leader_after_r2_has_highest_win_probability(tmp_path):
    """Sanity: the player who led after the real R1+R2 (유현조, +34,
    a 1-point real lead) should not have a LOWER win probability than
    every other player -- the forecast must not contradict the current
    real standing in an obviously wrong direction."""
    mod = _run_main_into_tmp(tmp_path)
    results = json.loads(mod.RESULTS_PATH.read_text(encoding="utf-8"))
    leader_row = next(p for p in results["players"] if p["player_name"] == "유현조")
    assert leader_row["real_cum36_points"] == 34
    max_win = max(p["win_pct"] for p in results["players"])
    assert leader_row["win_pct"] == max_win


def test_results_file_never_exposes_sg_terminology(tmp_path):
    mod = _run_main_into_tmp(tmp_path)
    raw = mod.RESULTS_PATH.read_text(encoding="utf-8")
    for forbidden in ("strokes_gained", "sg_total", "SG_RAW"):
        assert forbidden not in raw
