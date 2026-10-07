"""Tests for scripts/214_finalize_reconstruction_verdict.py -- the
final winner field rank/percentile computation against the real,
Windows-acquired season-to-date cumulative reconstruction (commit
eadf36f, evidence/stableford_official_stats_reconstructed_<year>/
RECONSTRUCTION_REPORT.json). These are regression anchors: if the
real evidence files are ever regenerated, these exact numbers must be
re-verified, not assumed."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "214_finalize_reconstruction_verdict.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("finalize_214", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["finalize_214"] = module
    spec.loader.exec_module(module)
    return module


def test_2025_missing_player_excluded_from_population_not_fabricated():
    mod = _load_module()
    results = mod.load_results("2025")
    by_code = {r["player_code"]: r for r in results}
    missing = by_code["12010"]
    assert missing["player_name"] == "이시은 0901(A)"
    assert missing["reconstructed"]["driving_distance"]["value"] is None
    report = mod.winner_report("2025")
    # field_n must exclude her: 103 total players - 1 null = 102
    assert report["metrics"]["driving_distance"]["raw_field_n"] == 102


def test_zero_gate_failures_across_full_field_except_the_one_known_missing_player():
    mod = _load_module()
    for year, expected_total_calls in (("2023", 1769), ("2024", 2165), ("2025", 2134)):
        results = mod.load_results(year)
        total_calls = sum(r["n_tournaments_total"] for r in results)
        gate_failed = sum(r["n_tournaments_total"] - r["n_tournaments_gate_passed"] for r in results)
        assert total_calls == expected_total_calls
        assert gate_failed == (1 if year == "2025" else 0)


def test_winner_driving_distance_and_gir_are_core_fairway_is_not():
    """The actual final verdict, anchored to the real numbers: Driving
    Distance and GIR are 3/3 top-25% (CORE) in both the raw and
    sample-qualified (>=10 rounds) populations; Fairway Accuracy shows
    no common direction at all (one winner in the bottom decile)."""
    mod = _load_module()
    reports = {year: mod.winner_report(year) for year in ("2023", "2024", "2025")}

    dd_pct = [reports[y]["metrics"]["driving_distance"]["qualified_percentile"] for y in ("2023", "2024", "2025")]
    gir_pct = [reports[y]["metrics"]["gir"]["qualified_percentile"] for y in ("2023", "2024", "2025")]
    fw_pct = [reports[y]["metrics"]["fairway_accuracy"]["qualified_percentile"] for y in ("2023", "2024", "2025")]

    assert all(p >= 75.0 for p in dd_pct), dd_pct
    assert all(p >= 75.0 for p in gir_pct), gir_pct
    assert not any(p >= 75.0 for p in fw_pct), fw_pct


def test_target_event_game_code_never_among_reconstruction_tournaments():
    """Red Team: target-event leakage must be structurally impossible,
    not merely unobserved -- the winning tournament's own gameCode
    must never appear among any player's pre-cutoff tournaments used
    in the reconstruction, for any of the 3 years."""
    import json
    content_root = Path(__file__).parent.parent / "content" / "website_v2"
    prior_files = {
        "2023": "STABLEFORD_2023_PRIOR_TOURNAMENT_MANIFEST_V1.json",
        "2024": "STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json",
        "2025": "STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json",
    }
    reconstruction_manifest = json.loads(
        (content_root / "STABLEFORD_OFFICIAL_SEASON_STAT_RECONSTRUCTION_MANIFEST_V1.json").read_text(encoding="utf-8")
    )
    for year, fname in prior_files.items():
        target_game_code = json.loads((content_root / fname).read_text(encoding="utf-8"))["target_game_code"]
        used_codes = {t["game_code"] for e in reconstruction_manifest[year]["entries"]
                      for t in e["pre_cutoff_tournaments"]}
        assert target_game_code not in used_codes


def test_raw_and_qualified_percentiles_agree_closely_for_winners():
    """All 3 winners have 32-62 rounds, far above the 10-round
    qualification floor, so excluding the field's handful of thin-
    sample outliers should barely move the winners' own percentile."""
    mod = _load_module()
    for year in ("2023", "2024", "2025"):
        report = mod.winner_report(year)
        for metric in ("driving_distance", "fairway_accuracy", "gir"):
            m = report["metrics"][metric]
            assert abs(m["raw_percentile"] - m["qualified_percentile"]) <= 2.0
