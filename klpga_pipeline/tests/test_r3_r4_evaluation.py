"""Tests for klpga.neo_win.r3_r4_evaluation — BETA #001 FINAL
validation's pure R3->R4 evaluation logic. `sim_inputs` are always
constructed directly as PlayerR3SimInput objects here (never via
build_r3_sim_inputs_from_frozen_snapshot) since this module's whole
point is to be usable with whatever that unmodified production
function already produced."""
from __future__ import annotations

from klpga.neo_win.r3_r4_evaluation import (
    aggregate_r3_r4_evaluation,
    build_r3_r4_evaluation_rows,
    compute_input_fingerprint,
    write_r3_r4_evaluation_csv,
)
from klpga.neo_win.round_update_r3 import PlayerR3SimInput


def _sim(code, name, expected, spread, r1, r2, r3, made_cut):
    return PlayerR3SimInput(
        player_code=code, player_name=name, expected_round_score_to_par=expected, spread=spread,
        r1_score_to_par=r1, r2_score_to_par=r2, r3_score_to_par=r3, made_cut=made_cut,
    )


# ---------------------------------------------------------------
# build_r3_r4_evaluation_rows
# ---------------------------------------------------------------


def test_matched_cutmaker_computes_error_abs_error_zscore():
    sim_inputs = [_sim("p1", "A", -1.0, 2.0, -3, -2, -1, True)]
    rows, missing = build_r3_r4_evaluation_rows(sim_inputs, {"p1": -2.0})
    assert missing == []
    r = rows[0]
    assert r.r3_total_score_to_par == -6
    assert r.expected_r4_score_to_par == -1.0
    assert r.r4_spread == 2.0
    assert r.actual_r4_score_to_par == -2.0
    assert r.prediction_error == -1.0
    assert r.absolute_error == 1.0
    assert r.z_score == -0.5


def test_confirmed_cut_player_excluded_entirely():
    """made_cut=False players never had a real R4 attempt -- they must
    not appear in the evaluation at all (not even as a missing row)."""
    sim_inputs = [_sim("p1", "A", -1.0, 2.0, 2, 3, None, False)]
    rows, missing = build_r3_r4_evaluation_rows(sim_inputs, {})
    assert rows == []
    assert missing == []


def test_cutmaker_missing_r1_r2_r3_excluded_entirely():
    """A player build_r3_sim_inputs_from_frozen_snapshot already
    couldn't fully populate (e.g. missing r3) must not be silently
    evaluated with a fabricated total."""
    sim_inputs = [_sim("p1", "A", -1.0, 2.0, -3, -2, None, True)]
    rows, missing = build_r3_r4_evaluation_rows(sim_inputs, {"p1": -2.0})
    assert rows == []
    assert missing == []


def test_eligible_cutmaker_missing_real_r4_reported_never_fabricated():
    """A real, eligible cutmaker (WD/DQ between R3 and R4, a real
    outcome) with no round_number=4 row must be reported in `missing`,
    never assigned a fabricated actual/error/z_score."""
    sim_inputs = [_sim("p1", "A", -1.0, 2.0, -3, -2, -1, True)]
    rows, missing = build_r3_r4_evaluation_rows(sim_inputs, {})
    assert missing == ["p1"]
    assert len(rows) == 1
    r = rows[0]
    assert r.actual_r4_score_to_par is None
    assert r.prediction_error is None
    assert r.absolute_error is None
    assert r.z_score is None
    # mu/sigma/r3_total are still reported -- those ARE known, real values.
    assert r.expected_r4_score_to_par == -1.0
    assert r.r3_total_score_to_par == -6


def test_only_real_cutmakers_with_r4_populate_evaluated_rows():
    sim_inputs = [
        _sim("p1", "A", -1.0, 2.0, -3, -2, -1, True),
        _sim("p2", "B", 0.5, 1.0, 2, 3, None, False),  # confirmed CUT
    ]
    rows, missing = build_r3_r4_evaluation_rows(sim_inputs, {"p1": -2.0, "p2": 5.0})
    assert {r.player_code for r in rows} == {"p1"}


# ---------------------------------------------------------------
# aggregate_r3_r4_evaluation
# ---------------------------------------------------------------


def test_aggregate_matches_hand_computed_values():
    sim_inputs = [
        _sim("p1", "A", -1.0, 2.0, -3, -2, -1, True),
        _sim("p2", "B", 0.0, 1.5, -1, -1, 0, True),
    ]
    rows, _missing = build_r3_r4_evaluation_rows(sim_inputs, {"p1": -2.0, "p2": 1.0})
    agg = aggregate_r3_r4_evaluation(rows)
    assert agg["evaluated_players"] == 2
    assert agg["mae"] == 1.0
    assert agg["me"] == 0.0
    assert agg["rmse"] == 1.0
    assert agg["within_1_stroke_pct"] == 100.0
    assert agg["within_sigma_pct"] == 100.0


def test_aggregate_excludes_missing_r4_rows():
    sim_inputs = [
        _sim("p1", "A", -1.0, 2.0, -3, -2, -1, True),
        _sim("p2", "B", 0.0, 1.5, -1, -1, 0, True),  # no real R4 -- WD before R4
    ]
    rows, missing = build_r3_r4_evaluation_rows(sim_inputs, {"p1": -2.0})
    assert missing == ["p2"]
    agg = aggregate_r3_r4_evaluation(rows)
    assert agg["evaluated_players"] == 1  # only p1


def test_aggregate_zero_evaluated_players_returns_none_metrics_never_zero():
    agg = aggregate_r3_r4_evaluation([])
    assert agg == {
        "evaluated_players": 0, "mae": None, "me": None, "rmse": None,
        "within_1_stroke_pct": None, "within_sigma_pct": None,
    }


def test_within_1_stroke_and_within_sigma_thresholds_are_inclusive_boundaries():
    # error exactly 1.0 -> within_1_stroke; z exactly 1.0 -> within_sigma.
    sim_inputs = [_sim("p1", "A", 0.0, 1.0, -3, -2, -1, True)]
    rows, _ = build_r3_r4_evaluation_rows(sim_inputs, {"p1": 1.0})
    agg = aggregate_r3_r4_evaluation(rows)
    assert agg["within_1_stroke_pct"] == 100.0
    assert agg["within_sigma_pct"] == 100.0


def test_bias_me_is_signed_not_absolute():
    """A model that is systematically optimistic (predicts too low a
    score, i.e. too good) shows a POSITIVE me, distinct from mae."""
    sim_inputs = [_sim("p1", "A", -2.0, 1.0, -3, -2, -1, True)]
    rows, _ = build_r3_r4_evaluation_rows(sim_inputs, {"p1": 0.0})  # actual much worse than predicted
    agg = aggregate_r3_r4_evaluation(rows)
    assert agg["me"] == 2.0
    assert agg["mae"] == 2.0


# ---------------------------------------------------------------
# write_r3_r4_evaluation_csv
# ---------------------------------------------------------------


def test_write_csv_schema_and_unavailable_for_missing_r4(tmp_path):
    import csv as csv_module

    sim_inputs = [_sim("p1", "A", -1.0, 2.0, -3, -2, -1, True)]
    rows, _missing = build_r3_r4_evaluation_rows(sim_inputs, {})  # p1 missing real R4
    path = write_r3_r4_evaluation_csv(rows, tmp_path / "out.csv")
    with open(path, encoding="utf-8-sig") as f:
        reader = csv_module.DictReader(f)
        assert reader.fieldnames == [
            "player_code", "player_name", "r3_total_score_to_par",
            "expected_r4_score_to_par", "r4_spread", "actual_r4_score_to_par",
            "prediction_error", "absolute_error", "z_score",
        ]
        row = next(reader)
        assert row["actual_r4_score_to_par"] == "unavailable"
        assert row["prediction_error"] == "unavailable"
        assert row["z_score"] == "unavailable"
        assert row["expected_r4_score_to_par"] == "-1.0"  # a known value is never "unavailable"


# ---------------------------------------------------------------
# compute_input_fingerprint — deterministic, order-independent
# ---------------------------------------------------------------


def test_fingerprint_is_deterministic_regardless_of_dict_order():
    r1a = {"p1": -3.0, "p2": -1.0}
    r1b = {"p2": -1.0, "p1": -3.0}
    r2 = {"p1": -2.0, "p2": -1.0}
    r3 = {"p1": -1.0, "p2": 0.0}
    made_cut = {"p1": True, "p2": True}
    fp_a = compute_input_fingerprint(r1a, r2, r3, made_cut)
    fp_b = compute_input_fingerprint(r1b, r2, r3, made_cut)
    assert fp_a == fp_b
    assert len(fp_a) == 64  # sha256 hex digest


def test_fingerprint_changes_when_any_input_value_changes():
    base = compute_input_fingerprint({"p1": -3.0}, {"p1": -2.0}, {"p1": -1.0}, {"p1": True})
    changed_r1 = compute_input_fingerprint({"p1": -2.0}, {"p1": -2.0}, {"p1": -1.0}, {"p1": True})
    changed_made_cut = compute_input_fingerprint({"p1": -3.0}, {"p1": -2.0}, {"p1": -1.0}, {"p1": False})
    assert base != changed_r1
    assert base != changed_made_cut


def test_fingerprint_never_reads_round_4_by_signature():
    """Structural proof: compute_input_fingerprint's signature has no
    round-4 parameter at all -- a round_number=4 value cannot reach it
    even by caller error."""
    import inspect

    sig = inspect.signature(compute_input_fingerprint)
    assert list(sig.parameters) == ["r1_scores", "r2_scores", "r3_scores", "made_cut_by_player"]
