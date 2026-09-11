"""R3 HOUSE: klpga.neo_win.r3_leakage_gate."""
from __future__ import annotations

import pytest

from klpga.neo_win.r3_leakage_gate import (
    FutureLeakageError, assert_artifact_type_allowed, assert_no_forbidden_result_fields, assert_stage_allowed,
)


@pytest.mark.parametrize("stage", ["pre", "r1", "r2", "r3"])
def test_allowed_stages_pass(stage):
    assert_stage_allowed(stage)  # must not raise


@pytest.mark.parametrize("stage", ["r4", "final", "postmortem", "post_event", "nonsense"])
def test_forbidden_or_unknown_stages_hard_stop(stage):
    with pytest.raises(FutureLeakageError):
        assert_stage_allowed(stage)


def test_artifact_type_referencing_r4_hard_stops():
    with pytest.raises(FutureLeakageError):
        assert_artifact_type_allowed("post_r4_forecast")


def test_artifact_type_referencing_final_hard_stops():
    with pytest.raises(FutureLeakageError):
        assert_artifact_type_allowed("final_result_snapshot")


def test_artifact_type_referencing_r3_is_allowed():
    assert_artifact_type_allowed("r3_frozen_evidence")  # must not raise


def test_forbidden_result_field_hard_stops():
    from klpga.evidence.manifest import FORBIDDEN_RESULT_FIELDS
    forbidden_field = sorted(FORBIDDEN_RESULT_FIELDS)[0]
    with pytest.raises(FutureLeakageError):
        assert_no_forbidden_result_fields({forbidden_field: "x"})


def test_clean_payload_passes():
    assert_no_forbidden_result_fields({"win_pct": 10.0, "player_id": "p1"})  # must not raise
