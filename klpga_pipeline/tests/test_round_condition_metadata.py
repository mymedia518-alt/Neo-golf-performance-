"""Tests for klpga.neo_win.round_condition_metadata — Section F of the
R1->R2 evaluation pipeline: R2 weather/round-condition metadata, kept
structurally separate from official CUT/WD/DQ status."""
from __future__ import annotations

from klpga.neo_win.round_condition_metadata import (
    SOURCE_TYPE_FIELD_OBSERVATION,
    build_r2_round_condition_metadata,
    read_round_condition_metadata_json,
    round_condition_metadata_to_dict,
    write_round_condition_metadata_json,
)

GAME_CODE = "2026080001"


def test_build_r2_metadata_has_the_real_reported_field_values():
    m = build_r2_round_condition_metadata(GAME_CODE)
    assert m.game_code == GAME_CODE
    assert m.round_number == 2
    assert m.date == "2026-08-28"
    assert m.weather == "rain"
    assert m.green_condition == "standing water beginning to appear"
    assert m.play_status_at_observation == "play continued"
    assert m.source_type == SOURCE_TYPE_FIELD_OBSERVATION


def test_official_fields_default_to_none_never_guessed():
    m = build_r2_round_condition_metadata(GAME_CODE)
    assert m.official_delay is None
    assert m.official_suspension is None
    assert m.suspension_time is None
    assert m.restart_time is None
    assert m.round_completed_time is None


def test_write_and_read_round_trip(tmp_path):
    m = build_r2_round_condition_metadata(GAME_CODE)
    out_path = tmp_path / "r2" / "round_condition.json"
    write_round_condition_metadata_json(m, out_path)
    assert out_path.exists()
    loaded = read_round_condition_metadata_json(out_path)
    assert loaded == m


def test_to_dict_has_all_expected_keys():
    m = build_r2_round_condition_metadata(GAME_CODE)
    d = round_condition_metadata_to_dict(m)
    assert set(d) == {
        "game_code", "round_number", "date", "weather", "green_condition",
        "play_status_at_observation", "source_type", "official_delay",
        "official_suspension", "suspension_time", "restart_time", "round_completed_time",
    }
