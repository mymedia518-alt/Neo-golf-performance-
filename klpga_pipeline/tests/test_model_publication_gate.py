"""P0 MODEL SAFETY PATCH -- unit tests for
klpga.website_v2.model_publication_gate, the pure decision logic
behind the hard release gate that keeps blocked-model probability
output out of production."""
import pytest

from klpga.website_v2.model_publication_gate import (
    FORBIDDEN_MARKERS_WHEN_BLOCKED,
    ModelPublicationGateError,
    assert_no_blocked_probability_output,
)


def test_clean_page_passes_while_blocked():
    html = "<table><tr><td>순위</td><td>선수</td></tr></table>"
    assert_no_blocked_probability_output(html, model_validated=False, label="t")


def test_each_forbidden_marker_individually_trips_the_gate_while_blocked():
    for marker in FORBIDDEN_MARKERS_WHEN_BLOCKED:
        with pytest.raises(ModelPublicationGateError) as exc:
            assert_no_blocked_probability_output(f"<html>{marker}</html>", model_validated=False, label="t")
        assert marker in str(exc.value)


def test_forbidden_markers_are_allowed_once_the_model_is_validated():
    html = "".join(FORBIDDEN_MARKERS_WHEN_BLOCKED)
    assert_no_blocked_probability_output(html, model_validated=True, label="t")


def test_multiple_forbidden_markers_all_reported():
    html = "<th>Cut%</th><th>Win%</th>"
    with pytest.raises(ModelPublicationGateError) as exc:
        assert_no_blocked_probability_output(html, model_validated=False, label="t")
    assert "<th>Cut%</th>" in str(exc.value)
    assert "<th>Win%</th>" in str(exc.value)
