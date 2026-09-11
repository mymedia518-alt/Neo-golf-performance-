"""R3 HOUSE: the one explicit R3 publication gate.

R3_PUBLICATION_READY = TRUE only when ALL of the following PASS:
  official_source_verified, completeness, duplicate, status, freeze,
  r2_binding, future_leakage, forecast, probability, production_simulation,
  website_build.

Until real R3 data arrives this legitimately, correctly evaluates to
FALSE (most sub-checks report WAIT/NOT_APPLICABLE rather than PASS) --
that WAIT state is success, not a bug. Mirrors
klpga.neo_win.r2_publication_gate exactly, one round later (no SG gate
-- R3 carries no SG column at all, see r3_real_page.py's own contract).
"""
from __future__ import annotations

from dataclasses import dataclass

PASS = "PASS"
FAIL = "FAIL"
WAIT = "WAIT"
NOT_APPLICABLE = "NOT_APPLICABLE"

GATE_NAMES = (
    "official_source_verified",
    "completeness",
    "duplicate",
    "status",
    "freeze",
    "r2_binding",
    "future_leakage",
    "forecast",
    "probability",
    "production_simulation",
    "website_build",
)


@dataclass(frozen=True)
class GateResult:
    name: str
    state: str  # PASS / FAIL / WAIT / NOT_APPLICABLE
    reason: str


@dataclass(frozen=True)
class R3PublicationGateReport:
    game_code: str
    gates: tuple  # tuple[GateResult, ...]
    overall_state: str  # PASS / FAIL / WAIT
    publication_allowed: bool
    real_r3: str  # "WAIT" | "CONFIRMED"


def evaluate_r3_publication_gate(game_code: str, gates: dict) -> R3PublicationGateReport:
    """`gates`: {gate_name: (state, reason)} for every name in
    GATE_NAMES -- raises KeyError if any gate is missing (never
    silently treats an un-evaluated gate as passing). publication_allowed
    is True only when every gate's state is exactly PASS -- WAIT,
    NOT_APPLICABLE, and FAIL are all non-publishing states (fail
    closed)."""
    missing = [name for name in GATE_NAMES if name not in gates]
    if missing:
        raise KeyError(f"R3 publication gate: missing evaluation for {missing}")

    results = tuple(GateResult(name, gates[name][0], gates[name][1]) for name in GATE_NAMES)
    states = {r.state for r in results}

    if states == {PASS}:
        overall = PASS
    elif FAIL in states:
        overall = FAIL
    else:
        overall = WAIT

    return R3PublicationGateReport(
        game_code=game_code,
        gates=results,
        overall_state=overall,
        publication_allowed=(overall == PASS),
        real_r3=("CONFIRMED" if overall == PASS else "WAIT"),
    )


def empty_house_gate_report(game_code: str, *, reason: str = "official R3 leaderboard unavailable") -> R3PublicationGateReport:
    """The correct, expected gate report while real R3 data is absent
    -- every gate reports WAIT (nothing has failed; there is simply
    nothing to evaluate yet) except the ones that are structurally
    NOT_APPLICABLE until a freeze exists."""
    gates = {
        "official_source_verified": (WAIT, reason),
        "completeness": (WAIT, "no R3 collection attempted yet"),
        "duplicate": (WAIT, "no R3 collection attempted yet"),
        "status": (WAIT, "no R3 collection attempted yet"),
        "freeze": (WAIT, "no R3 freeze exists yet"),
        "r2_binding": (NOT_APPLICABLE, "no R3 freeze exists yet"),
        "future_leakage": (NOT_APPLICABLE, "no R3 freeze exists yet"),
        "forecast": (NOT_APPLICABLE, "no R3 freeze exists yet"),
        "probability": (NOT_APPLICABLE, "no forecast artifact exists yet"),
        "production_simulation": (NOT_APPLICABLE, "no forecast artifact exists yet"),
        "website_build": (WAIT, "R3 route serves the truthful WAIT-state page"),
    }
    return evaluate_r3_publication_gate(game_code, gates)
