from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.probability_movers import compute_probability_movers  # noqa: E402


def test_risers_and_fallers_ranked_by_signed_delta():
    before = {"P1": 10.0, "P2": 5.0, "P3": 20.0}
    after = {"P1": 15.0, "P2": 2.0, "P3": 20.0}
    names = {"P1": "Alice", "P2": "Bob", "P3": "Carol"}
    report = compute_probability_movers(before, after, names, before_label="PRE", after_label="FINAL", top_n=2)
    assert report.risers[0].player_id == "P1"
    assert report.risers[0].delta_pct == 5.0
    assert report.fallers[0].player_id == "P2"
    assert report.fallers[0].delta_pct == -3.0


def test_player_missing_from_either_side_is_skipped_never_fabricated():
    before = {"P1": 10.0, "P2": 5.0}
    after = {"P1": 12.0, "P3": 40.0}
    report = compute_probability_movers(before, after, {}, before_label="A", after_label="B")
    ids = {m.player_id for m in report.risers} | {m.player_id for m in report.fallers}
    assert ids == {"P1"}


def test_top_n_limits_result_size():
    before = {f"P{i}": 0.0 for i in range(20)}
    after = {f"P{i}": float(i) for i in range(20)}
    report = compute_probability_movers(before, after, {}, before_label="A", after_label="B", top_n=5)
    assert len(report.risers) == 5
    assert len(report.fallers) == 5


def test_name_lookup_falls_back_to_player_id():
    report = compute_probability_movers({"P1": 1.0}, {"P1": 2.0}, {}, before_label="A", after_label="B")
    assert report.risers[0].player_name == "P1"


def test_stable_tie_break_by_player_id():
    before = {"PB": 0.0, "PA": 0.0}
    after = {"PB": 5.0, "PA": 5.0}
    report = compute_probability_movers(before, after, {}, before_label="A", after_label="B")
    assert [m.player_id for m in report.risers] == ["PA", "PB"]
