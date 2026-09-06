"""Regressions for progress semantics observed in live official R3 cards."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("current_round_evidence", Path(__file__).parents[1] / "scripts" / "collect_current_round_evidence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("display,raw,tee,count", [
    ("13H", "13", 1, 12),
    ("18H", "18", 1, 17),
    ("F", "18", 1, 18),
    ("F*", "9", 10, 18),
    ("9H*", "9", 10, 17),
    ("1H*", "1", 10, 9),
    ("10H*", "10", 10, 0),
])
def test_official_current_hole_is_not_completed_count(display, raw, tee, count):
    assert module.expected_completed_holes(display, raw, tee) == count


def test_unknown_official_progress_is_not_guessed():
    with pytest.raises(ValueError):
        module.expected_completed_holes("unavailable", "13", 1)
