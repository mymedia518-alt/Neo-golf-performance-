"""Tests for scripts/217_build_2026_prior_tournament_manifest.py --
the 2026-season prior-tournament manifest, built entirely from two
already-real calendar sources (TOURNAMENT_K_WEEK_MAPPING_V1.json,
OFFICIAL_KLPGA_SCHEDULE.json), no new network access."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "217_build_2026_prior_tournament_manifest.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("manifest_217", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["manifest_217"] = module
    spec.loader.exec_module(module)
    return module


def test_build_entries_covers_all_24_known_real_2026_tournaments():
    mod = _load_module()
    entries = mod.build_entries()
    codes = {e["game_code"] for e in entries}
    assert len(entries) == 24
    # the 4 most-recent-season codes confirmed via OFFICIAL_KLPGA_SCHEDULE.json
    assert {"2026120001", "2026090003", "2026090002", "2026100005"} <= codes
    # a sample from the 20 confirmed via TOURNAMENT_K_WEEK_MAPPING_V1.json
    assert {"2026030001", "2026080001"} <= codes
    # the target event itself must never appear as a prior entry
    assert "2026100004" not in codes


def test_every_entry_strictly_before_target_cutoff():
    mod = _load_module()
    entries = mod.build_entries()
    target = date.fromisoformat(mod.TARGET_START_DATE)
    for e in entries:
        assert date.fromisoformat(e["start_date"]) < target


def test_assert_no_leakage_raises_on_a_same_or_later_date():
    mod = _load_module()
    bad = [{"game_code": "2026100004", "tournament_name": "x", "start_date": "2026-10-08"}]
    try:
        mod.assert_no_leakage(bad)
        assert False, "expected AssertionError"
    except AssertionError:
        pass


def test_entries_sorted_chronologically_with_no_duplicates():
    mod = _load_module()
    entries = mod.build_entries()
    dates = [e["start_date"] for e in entries]
    assert dates == sorted(dates)
    codes = [e["game_code"] for e in entries]
    assert len(codes) == len(set(codes))
