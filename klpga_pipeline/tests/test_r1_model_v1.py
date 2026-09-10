"""NEO_R1_MODEL_V1 (src/klpga/neo_win/r1_model_v1.py) -- regression tests.

Locks in: the frozen coefficients match NEO_R1_MODEL_V1_FREEZE.json
exactly, the nested-chain form guarantees probability coherence for
any real-valued input (not just the walk-forward corpus), and the
module never reaches out to KB or any live data source (it is a pure
function of two floats).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r1_model_v1 import (  # noqa: E402
    CHAIN_COEFFICIENTS,
    FEATURE_STANDARDIZATION,
    field_relative_r1_z,
    predict_r1_tiers,
)


def _freeze() -> dict:
    return json.loads((CONTENT / "NEO_R1_MODEL_V1_FREEZE.json").read_text(encoding="utf-8"))


def test_coefficients_match_freeze_artifact_exactly():
    freeze_coefs = _freeze()["chain_coefficients"]
    for label, coef in CHAIN_COEFFICIENTS.items():
        frozen = freeze_coefs[label]
        assert coef["intercept"] == frozen["intercept"]
        assert coef["coef_pre_score"] == frozen["coef_pre_score"]
        assert coef["coef_r1_z"] == frozen["coef_r1_z"]


def test_feature_standardization_matches_freeze_artifact():
    freeze_std = _freeze()["feature_standardization"]
    for feat, params in FEATURE_STANDARDIZATION.items():
        assert params["mean"] == freeze_std[feat]["mean"]
        assert params["std"] == freeze_std[feat]["std"]


def test_coherence_holds_for_wide_random_input_range():
    """Not just the historical corpus's range -- coherence must hold
    structurally, so sweep a wide, deliberately extreme range."""
    rng = random.Random(20260910)
    for _ in range(5000):
        pre = rng.uniform(-10, 10)
        r1 = rng.uniform(-10, 10)
        result = predict_r1_tiers(pre, r1)
        assert result.is_coherent(), (pre, r1, result)


def test_higher_pre_score_never_decreases_any_tier_probability():
    """Monotonicity in the PRE feature -- a stronger PRE prior, all
    else equal, must never make any tier LESS likely (each stage
    coefficient on pre_score is positive by the fit, but this test
    checks the actual composed behavior, not just the sign)."""
    r1 = 0.0
    weak = predict_r1_tiers(-1.0, r1)
    strong = predict_r1_tiers(1.0, r1)
    assert strong.cut >= weak.cut
    assert strong.top20 >= weak.top20
    assert strong.top10 >= weak.top10
    assert strong.top5 >= weak.top5
    assert strong.win >= weak.win


def test_higher_r1_performance_never_decreases_any_tier_probability():
    pre = 0.0
    weak_r1 = predict_r1_tiers(pre, -1.0)
    strong_r1 = predict_r1_tiers(pre, 1.0)
    assert strong_r1.cut >= weak_r1.cut
    assert strong_r1.top20 >= weak_r1.top20
    assert strong_r1.top10 >= weak_r1.top10
    assert strong_r1.top5 >= weak_r1.top5
    assert strong_r1.win >= weak_r1.win


def test_field_relative_r1_z_leakage_safe_formula():
    # a player 2 strokes better than field mean, field stddev 4 -> z=0.5
    assert field_relative_r1_z(r1_to_par=-2, field_mean=0, field_stddev=4) == 0.5
    # zero stddev field (degenerate single-player field) must not divide by zero
    assert field_relative_r1_z(r1_to_par=-2, field_mean=0, field_stddev=0) == 2.0


def test_module_is_a_pure_function_no_network_or_file_access():
    """Guard against a future edit silently reaching out to KB data or
    any live source -- this module's public functions must only ever
    touch their own arguments and the frozen module-level constants."""
    import inspect
    import klpga.neo_win.r1_model_v1 as mod

    source = inspect.getsource(mod)
    for forbidden in ("requests.", "open(", "Path(", "http_client", "2026090003"):
        assert forbidden not in source, f"r1_model_v1.py unexpectedly references {forbidden!r}"


def test_model_selection_finalized_before_kb_inspection():
    freeze = _freeze()
    assert freeze["candidate_selection"]["selection_finalized_before_kb_was_inspected"] is True
    assert freeze["kb_holdout"]["used_for_training_feature_selection_or_calibration"] is False
