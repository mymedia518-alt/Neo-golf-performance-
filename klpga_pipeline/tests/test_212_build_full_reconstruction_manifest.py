"""Tests for scripts/212_build_full_reconstruction_manifest.py --
verifies the already-written STABLEFORD_OFFICIAL_SEASON_STAT_
RECONSTRUCTION_MANIFEST_V1.json (built from already-held data, no new
network access) has the right shape and that winners resolve to the
correct per-tournament breakdown summing to their already-known real
pre-cutoff round totals."""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST_PATH = (
    Path(__file__).parent.parent / "content" / "website_v2"
    / "STABLEFORD_OFFICIAL_SEASON_STAT_RECONSTRUCTION_MANIFEST_V1.json"
)

WINNERS = {
    "2023": ("방신실", "10095", 52, 17),
    "2024": ("김민별", "10002", 62, 19),
    "2025": ("김민솔", "10725", 32, 9),
}


def _load():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_three_years_with_expected_cutoffs():
    m = _load()
    assert m["2023"]["target_cutoff"] == "2023-10-12"
    assert m["2024"]["target_cutoff"] == "2024-10-10"
    assert m["2025"]["target_cutoff"] == "2025-10-01"


def test_winner_pre_cutoff_tournament_breakdown_sums_to_known_real_totals():
    m = _load()
    for year, (name, code, expected_rounds, expected_tournaments) in WINNERS.items():
        entries = {e["player_name"]: e for e in m[year]["entries"]}
        assert name in entries
        e = entries[name]
        assert e["player_code"] == code
        assert e["expected_pre_cutoff_rounds_total"] == expected_rounds
        assert len(e["pre_cutoff_tournaments"]) == expected_tournaments
        assert sum(t["real_rounds_this_tournament"] for t in e["pre_cutoff_tournaments"]) == expected_rounds


def test_every_tournament_entry_has_a_real_positive_round_count():
    m = _load()
    for year, data in m.items():
        for e in data["entries"]:
            for t in e["pre_cutoff_tournaments"]:
                assert t["real_rounds_this_tournament"] > 0
                assert t["game_code"]
                assert t["start_date"] < data["target_cutoff"]
