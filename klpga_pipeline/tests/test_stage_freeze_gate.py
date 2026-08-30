import pytest

from klpga.neo_win.stage_freeze_gate import StageFreezeGateError, expected_rounds, validate_stage_transition


def test_stage_freeze_requires_artifact_and_supports_54_72_hole_formats():
    assert expected_rounds(54) == 3
    assert expected_rounds(72) == 4
    assert validate_stage_transition("R3", artifact_frozen=True, total_holes=54, official_complete=True).required_prediction_id == "004"
    with pytest.raises(StageFreezeGateError):
        expected_rounds(55)


def test_final_is_review_only_and_blocks_unresolved_playoff_or_weather():
    blocked = validate_stage_transition("FINAL", artifact_frozen=True, total_holes=72, official_complete=True, playoff_resolved=False)
    assert not blocked.allowed and blocked.required_prediction_id is None
    blocked = validate_stage_transition("R2", artifact_frozen=True, total_holes=72, official_complete=True, weather_complete=False)
    assert not blocked.allowed
    passed = validate_stage_transition("FINAL", artifact_frozen=True, total_holes=72, official_complete=True)
    assert passed.allowed and passed.required_prediction_id is None

