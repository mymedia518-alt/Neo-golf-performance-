"""Tests for STABLEFORD_OFFICIAL_SEASON_STAT_ACQUISITION_MANIFEST_V1
.json -- the manifest built entirely from already-held real data
(playerCode resolved from mainRecord?playerCode= links already
embedded in the committed scoreRecord captures; last pre-cutoff
gameCode and expected round count from the already-verified
hole-level extraction) for the official-stat acquisition
(scripts/210_acquire_official_season_stats.py)."""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST_PATH = (
    Path(__file__).parent.parent / "content" / "website_v2"
    / "STABLEFORD_OFFICIAL_SEASON_STAT_ACQUISITION_MANIFEST_V1.json"
)

WINNERS = {"2023": ("방신실", "10095"), "2024": ("김민별", "10002"), "2025": ("김민솔", "10725")}
EXPECTED_ENTRY_COUNTS = {"2023": 102, "2024": 103, "2025": 103}


def _load():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_the_three_years_with_expected_entry_counts():
    manifests = _load()
    assert set(manifests.keys()) == {"2023", "2024", "2025"}
    for year, expected in EXPECTED_ENTRY_COUNTS.items():
        assert len(manifests[year]["entries"]) == expected


def test_each_winner_resolved_to_the_correct_real_player_code():
    manifests = _load()
    for year, (winner_name, winner_code) in WINNERS.items():
        by_name = {e["player_name"]: e for e in manifests[year]["entries"]}
        assert winner_name in by_name
        assert by_name[winner_name]["player_code"] == winner_code


def test_every_entry_has_a_last_pre_cutoff_game_code_and_positive_expected_rounds():
    manifests = _load()
    for year, m in manifests.items():
        for e in m["entries"]:
            assert e["last_pre_cutoff_game_code"]
            assert e["expected_pre_cutoff_rounds_total"] > 0
            assert e["player_code"].isdigit()


def test_target_cutoffs_match_the_already_frozen_blind_backtest_cutoffs():
    manifests = _load()
    assert manifests["2023"]["target_cutoff"] == "2023-10-12"
    assert manifests["2024"]["target_cutoff"] == "2024-10-10"
    assert manifests["2025"]["target_cutoff"] == "2025-10-01"
