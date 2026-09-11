"""R3 HOUSE: klpga.neo_win.r3_publication_gate."""
from __future__ import annotations

import pytest

from klpga.neo_win.r3_publication_gate import (
    FAIL, GATE_NAMES, NOT_APPLICABLE, PASS, WAIT, empty_house_gate_report, evaluate_r3_publication_gate,
)


def test_empty_house_never_passes():
    report = empty_house_gate_report("TEST0003")
    assert report.overall_state == WAIT
    assert report.publication_allowed is False
    assert report.real_r3 == "WAIT"


def test_missing_gate_raises_keyerror():
    with pytest.raises(KeyError):
        evaluate_r3_publication_gate("TEST0003", {name: (PASS, "x") for name in GATE_NAMES[:-1]})


def test_all_pass_yields_confirmed():
    gates = {name: (PASS, "x") for name in GATE_NAMES}
    report = evaluate_r3_publication_gate("TEST0003", gates)
    assert report.overall_state == PASS
    assert report.publication_allowed is True
    assert report.real_r3 == "CONFIRMED"


def test_any_fail_yields_fail_never_publishes():
    gates = {name: (PASS, "x") for name in GATE_NAMES}
    gates["probability"] = (FAIL, "monotonicity violated")
    report = evaluate_r3_publication_gate("TEST0003", gates)
    assert report.overall_state == FAIL
    assert report.publication_allowed is False


def test_wait_without_fail_yields_wait_not_fail():
    gates = {name: (PASS, "x") for name in GATE_NAMES}
    gates["freeze"] = (WAIT, "no freeze yet")
    report = evaluate_r3_publication_gate("TEST0003", gates)
    assert report.overall_state == WAIT
    assert report.publication_allowed is False


def test_not_applicable_never_counts_as_pass():
    gates = {name: (PASS, "x") for name in GATE_NAMES}
    gates["r2_binding"] = (NOT_APPLICABLE, "no freeze yet")
    report = evaluate_r3_publication_gate("TEST0003", gates)
    assert report.publication_allowed is False
