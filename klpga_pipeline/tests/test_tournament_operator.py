from klpga.tournament_engine import Stage
from klpga.tournament_operator import (
    OperatorAction,
    decide_operator_action,
)


def test_54_hole_cut_goes_directly_to_final():
    d = decide_operator_action(
        Stage.CUT_CONFIRMED,
        final_round_number=3,
        current_round_number=2,
        model_ready=True,
    )

    assert d.action == OperatorAction.RUN_FINAL
    assert d.publish_model is True


def test_72_hole_cut_goes_to_intermediate_round():
    d = decide_operator_action(
        Stage.CUT_CONFIRMED,
        final_round_number=4,
        current_round_number=2,
        model_ready=True,
    )

    assert d.action == OperatorAction.RUN_NEXT_ROUND


def test_72_hole_completed_r3_goes_to_final():
    d = decide_operator_action(
        Stage.NEXT_ROUND_COMPLETE,
        final_round_number=4,
        current_round_number=3,
        model_ready=True,
    )

    assert d.action == OperatorAction.RUN_FINAL
    assert d.publish_model is True


def test_five_round_event_remains_generic():
    d = decide_operator_action(
        Stage.NEXT_ROUND_COMPLETE,
        final_round_number=5,
        current_round_number=3,
        model_ready=True,
    )

    assert d.action == OperatorAction.RUN_NEXT_ROUND


def test_model_block_does_not_block_factual_publish():
    d = decide_operator_action(
        Stage.CUT_CONFIRMED,
        final_round_number=3,
        current_round_number=2,
        model_ready=False,
    )

    assert d.publish_factual is True
    assert d.publish_model is False


def test_r2_complete_never_infers_cut():
    d = decide_operator_action(
        Stage.R2_COMPLETE,
        final_round_number=4,
        current_round_number=2,
    )

    assert d.action == OperatorAction.CONFIRM_CUT
    assert d.publish_model is False


def test_final_complete_closes_event():
    d = decide_operator_action(
        Stage.FINAL_COMPLETE,
        final_round_number=3,
        current_round_number=3,
    )

    assert d.action == OperatorAction.CLOSE_FINAL
