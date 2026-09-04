from __future__ import annotations

import json

import pytest

from klpga.website_v2 import tournament_state as ts


@pytest.fixture(autouse=True)
def _isolated_state_path(tmp_path, monkeypatch):
    path = tmp_path / "OK_OPEN_STAGE_STATE.json"
    monkeypatch.setattr(ts, "STAGE_STATE_PATH", path)
    yield path


def test_ok_open_r1_status_is_none_before_any_r1_data():
    assert ts.ok_open_r1_status() is None


def test_ok_open_r1_status_is_in_progress_once_r1_validated_but_not_complete(_isolated_state_path):
    _isolated_state_path.write_text(json.dumps({"stages": {"r1": {"validated": True, "retrieved_at": "2026-09-04T04:00:00Z"}}}), encoding="utf-8")
    assert ts.ok_open_r1_status() == "IN_PROGRESS"


def test_ok_open_r1_status_is_complete_once_r1_complete_flag_is_set(_isolated_state_path):
    _isolated_state_path.write_text(
        json.dumps({"stages": {"r1": {"validated": True, "retrieved_at": "2026-09-04T04:00:00Z"}}, "r1_complete": True}), encoding="utf-8"
    )
    assert ts.ok_open_r1_status() == "COMPLETE"


def test_ok_open_r1_status_never_inferred_from_r1_complete_flag_alone(_isolated_state_path):
    # A malformed/partial state with r1_complete=True but no validated r1
    # stage must never report a status -- nothing was actually validated.
    _isolated_state_path.write_text(json.dumps({"r1_complete": True}), encoding="utf-8")
    assert ts.ok_open_r1_status() is None


def test_ok_open_latest_stage_update_formats_hhmm_in_kst(_isolated_state_path):
    _isolated_state_path.write_text(json.dumps({"stages": {"r1": {"validated": True, "retrieved_at": "2026-09-04T04:30:00Z"}}}), encoding="utf-8")
    update = ts.ok_open_latest_stage_update()
    assert update["retrieved_at_hhmm_kst"] == "13:30"  # UTC+9
    assert update["retrieved_at"] == "2026-09-04T04:30:00Z"  # raw ISO preserved, never dropped
