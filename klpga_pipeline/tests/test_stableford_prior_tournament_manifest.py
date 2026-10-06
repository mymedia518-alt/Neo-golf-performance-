"""Tests for klpga.website_v2.stableford_prior_tournament_manifest --
built against the real historical_sg_warehouse_corrected_v2.json and
TOURNAMENT_MASTER_DATES_V1.json files already committed in this repo."""
from __future__ import annotations

from datetime import date

from klpga.website_v2.stableford_historical_dates import HISTORICAL_EVENT_DATES
from klpga.website_v2.stableford_prior_tournament_manifest import build_manifest


def test_2025_manifest_has_the_23_bounded_prior_tournaments():
    target = HISTORICAL_EVENT_DATES["2025100001"].event_start_date
    manifest = build_manifest("2025100001", target)
    assert len(manifest) == 23
    assert all(e.before_target_event_start for e in manifest)


def test_every_manifest_entry_strictly_precedes_the_target_start_date():
    target = HISTORICAL_EVENT_DATES["2025100001"].event_start_date
    manifest = build_manifest("2025100001", target)
    for e in manifest:
        y, m, d = map(int, e.start_date.split("-"))
        assert date(y, m, d) < target


def test_no_duplicate_game_codes_and_all_start_not_yet_acquired():
    target = HISTORICAL_EVENT_DATES["2025100001"].event_start_date
    manifest = build_manifest("2025100001", target)
    codes = [e.game_code for e in manifest]
    assert len(codes) == len(set(codes))
    assert all(e.acquisition_status == "NOT_YET_ACQUIRED" for e in manifest)
    assert all(e.response_status is None for e in manifest)
    assert all(e.sha256 is None for e in manifest)


def test_known_tournament_matches_expected_real_fields():
    target = HISTORICAL_EVENT_DATES["2025100001"].event_start_date
    manifest = build_manifest("2025100001", target)
    by_code = {e.game_code: e for e in manifest}
    entry = by_code["2025090004"]
    assert entry.tournament_name == "제25회 하이트진로 챔피언십"
    assert entry.start_date == "2025-09-25"
    assert entry.round_count == 4
    assert entry.end_date == "2025-09-28"
    assert entry.end_date_is_derived is True


def test_target_event_code_itself_never_appears_in_its_own_manifest():
    target = HISTORICAL_EVENT_DATES["2025100001"].event_start_date
    manifest = build_manifest("2025100001", target)
    assert "2025100001" not in {e.game_code for e in manifest}
