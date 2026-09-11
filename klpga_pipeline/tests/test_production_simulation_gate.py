"""NEO MONTE CARLO PRODUCTION CONTRACT (fix/kb-r2-official-cut-gate-
20260911, explicit user directive): the shared production simulation-
count gate and the single source-of-truth constant every engine reads."""
from __future__ import annotations

import pytest

from klpga.neo_win.production_simulation_gate import (
    PRODUCTION_N_SIMULATIONS, ProductionSimulationContractError, assert_production_simulation_count,
)
from klpga.neo_win.r1_live_probability import DEFAULT_N_SIMULATIONS as r1_default
from klpga.neo_win.round_update import DEFAULT_N_SIMULATIONS as engine_default
from klpga.neo_win.round_update_r2 import DEFAULT_N_SIMULATIONS as r2_default
from klpga.neo_win.round_update_r3 import DEFAULT_N_SIMULATIONS as r3_default


def test_production_contract_is_10000():
    assert PRODUCTION_N_SIMULATIONS == 10000


def test_every_engine_shares_the_same_production_default():
    """R1/R2/R3 (and the gate's own constant) must never silently
    diverge from one another -- a single source of truth."""
    assert engine_default == r2_default == r3_default == r1_default == PRODUCTION_N_SIMULATIONS == 10000


def test_assert_passes_at_the_production_count():
    assert_production_simulation_count(10000)  # must not raise


def test_assert_hard_stops_on_the_old_5000_default():
    with pytest.raises(ProductionSimulationContractError, match="!= 10000"):
        assert_production_simulation_count(5000)


def test_assert_hard_stops_on_the_pre_stage_100000_default():
    """100,000 is a different model's (pre_v2.py) own default -- never
    an acceptable substitute for a round_update-family production
    forecast's simulation count."""
    with pytest.raises(ProductionSimulationContractError):
        assert_production_simulation_count(100000)


def test_assert_hard_stops_on_a_small_synthetic_test_value():
    with pytest.raises(ProductionSimulationContractError):
        assert_production_simulation_count(500)


def test_error_message_names_the_context():
    with pytest.raises(ProductionSimulationContractError, match=r"\[post_r2_final_forecast\]"):
        assert_production_simulation_count(5000, context="post_r2_final_forecast")
