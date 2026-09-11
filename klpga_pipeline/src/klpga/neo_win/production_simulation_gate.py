"""NEO MONTE CARLO PRODUCTION CONTRACT: the shared production
simulation-count gate (explicit user directive, fix/kb-r2-official-
cut-gate-20260911).

The standard NEO Tournament Model production simulation count is
klpga.neo_win.round_update.DEFAULT_N_SIMULATIONS (10,000) -- shared by
every round_update-family Monte Carlo engine (R1 live probability,
POST-R2, POST-R3). A real, PUBLISHED production forecast whose
`n_simulations` differs from that shared constant is a contract
violation and must HARD_STOP before publication.

Deliberately separate from klpga.neo_win.r2_probability_gate /
r3_probability_gate (which validate a forecast's own internal
mathematical integrity -- bounds, monotonicity, population -- and are
also exercised by fast synthetic tests that legitimately use a small
n_simulations for speed). This gate checks ONE additional thing those
generic gates never assume: that a forecast an operator is about to
PUBLISH used the real, current production simulation count. Callers
invoke this only at the real publish boundary (scripts/112, the R3
operator), never from a synthetic unit test's own direct engine call.
"""
from __future__ import annotations

from klpga.neo_win.round_update import DEFAULT_N_SIMULATIONS

PRODUCTION_N_SIMULATIONS = DEFAULT_N_SIMULATIONS


class ProductionSimulationContractError(RuntimeError):
    """A real production forecast's n_simulations diverges from the
    shared NEO Monte Carlo production contract. The caller must treat
    this as HARD_STOP and never publish the forecast."""


def assert_production_simulation_count(n_simulations: int, *, context: str = "") -> None:
    if int(n_simulations) != PRODUCTION_N_SIMULATIONS:
        raise ProductionSimulationContractError(
            f"production tournament forecast n_simulations={n_simulations!r} != "
            f"{PRODUCTION_N_SIMULATIONS} (the current NEO Monte Carlo production contract)"
            f"{f' [{context}]' if context else ''}"
        )
