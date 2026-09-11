"""R2 HOUSE: the one explicit R2 publication gate.

R2_PUBLICATION_READY = TRUE only when ALL of the following PASS:
  official_source_verified, completeness, duplicate, status, freeze,
  pre_binding, future_leakage, sg, forecast, probability, website_build.

Until real R2 data arrives this legitimately, correctly evaluates to
FALSE (most sub-checks report NOT_APPLICABLE/WAIT rather than PASS) --
that WAIT state is success, not a bug, per the user's own "empty house"
requirement. Follows the same per-domain dict + overall_state +
publication_allowed idiom already used by
klpga.neo_win.tier2_publication_gate (see that module for the
established pattern this mirrors)."""
from __future__ import annotations

from dataclasses import dataclass, field

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
    "pre_binding",
    "future_leakage",
    "sg",
    "forecast",
    "probability",
    "website_build",
)


@dataclass(frozen=True)
class GateResult:
    name: str
    state: str  # PASS / FAIL / WAIT / NOT_APPLICABLE
    reason: str


@dataclass(frozen=True)
class R2PublicationGateReport:
    game_code: str
    gates: tuple  # tuple[GateResult, ...]
    overall_state: str  # PASS / FAIL / WAIT
    publication_allowed: bool
    real_r2: str  # "WAIT" | "CONFIRMED"


def evaluate_r2_publication_gate(game_code: str, gates: dict) -> R2PublicationGateReport:
    """`gates`: {gate_name: (state, reason)} for every name in
    GATE_NAMES -- raises KeyError if any gate is missing (never
    silently treats an un-evaluated gate as passing). publication_allowed
    is True only when every gate's state is exactly PASS -- WAIT,
    NOT_APPLICABLE, and FAIL are all non-publishing states (fail
    closed, matching klpga.neo_win.tier2_publication_gate's own
    fail_closed_unknown convention)."""
    missing = [name for name in GATE_NAMES if name not in gates]
    if missing:
        raise KeyError(f"R2 publication gate: missing evaluation for {missing}")

    results = tuple(GateResult(name, gates[name][0], gates[name][1]) for name in GATE_NAMES)
    states = {r.state for r in results}

    if states == {PASS}:
        overall = PASS
    elif FAIL in states:
        overall = FAIL
    else:
        overall = WAIT

    return R2PublicationGateReport(
        game_code=game_code,
        gates=results,
        overall_state=overall,
        publication_allowed=(overall == PASS),
        real_r2=("CONFIRMED" if overall == PASS else "WAIT"),
    )


def empty_house_gate_report(game_code: str, *, reason: str = "official R2 leaderboard unavailable") -> R2PublicationGateReport:
    """The correct, expected gate report while real R2 data is absent
    -- every gate reports WAIT (nothing has failed; there is simply
    nothing to evaluate yet) except the ones that are structurally
    NOT_APPLICABLE until a freeze exists (sg/forecast/probability/
    website_build all depend on a freeze that doesn't exist yet)."""
    gates = {
        "official_source_verified": (WAIT, reason),
        "completeness": (WAIT, "no R2 collection attempted yet"),
        "duplicate": (WAIT, "no R2 collection attempted yet"),
        "status": (WAIT, "no R2 collection attempted yet"),
        "freeze": (WAIT, "no R2 freeze exists yet"),
        "pre_binding": (NOT_APPLICABLE, "no R2 freeze exists yet"),
        "future_leakage": (NOT_APPLICABLE, "no R2 freeze exists yet"),
        "sg": (NOT_APPLICABLE, "no R2 freeze exists yet -- SG requires a verified frozen R2"),
        "forecast": (NOT_APPLICABLE, "no R2 freeze exists yet"),
        "probability": (NOT_APPLICABLE, "no forecast artifact exists yet"),
        "website_build": (WAIT, "R2 route serves the truthful WAIT-state page"),
    }
    return evaluate_r2_publication_gate(game_code, gates)
