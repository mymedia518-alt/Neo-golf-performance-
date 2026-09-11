"""R2 HOUSE: SG (strokes gained) precondition gate.

VERIFIED FROZEN R2 -> SG ingestion (klpga.neo_win.r2_sg_pipeline,
CLASSIFICATION B -- see that module's own docstring for the full
archaeology) -> OTT/APP/ARG/PUTT/TOTAL.

CORRECTION (2026-09-11, second pass): an earlier version of this
module's docstring said no official per-round SG source exists at all.
That was wrong -- re-archaeology (scripts/63_collect_historical_sg_
warehouse.py) found the real, already-implemented, already-production-
proven parser: klpga.website_v2.official_data.parse_sg_html/
validate_sg_record, reading KLPGA's own strokesGained_detail endpoint
per round. r2_sg_pipeline.py wires it for R2 specifically. What remains
correctly unverified (sandbox has no live network access, confirmed
blocked all session) is whether that endpoint actually populates
round=2 data WHILE the tournament is still in progress -- r2_sg_
pipeline fails safe (WAIT, never fabricated) if it doesn't.

This gate module remains the enforceable PRECONDITION regardless of
that outcome: calling `require_verified_frozen_r2_for_sg` before any
real SG number is computed/published is what stays permanently true --
it must never be bypassed to publish a real SG number computed from
incomplete/unfrozen R2 evidence, whichever of AVAILABLE/NOT_AVAILABLE
the live ingestion turns out to report.
"""
from __future__ import annotations

from klpga.neo_win.r2_freeze import load_r2_freeze, verify_r2_freeze_hash
from klpga.tournament_context import TournamentContext


class SgPreconditionError(RuntimeError):
    """Raised when SG computation/publication is attempted before a
    verified, hash-intact R2 freeze exists."""


def require_verified_frozen_r2_for_sg(context: TournamentContext) -> dict:
    """Hard stop unless a real R2 freeze exists AND its own recorded
    hash still matches its content. Returns the freeze dict on success
    so a real (future) SG calculator can read `records`/`status_counts`
    from the SAME verified source, never a separate live read."""
    freeze = load_r2_freeze(context)
    if freeze is None:
        raise SgPreconditionError(
            f"SG PRECONDITION FAILED: no R2 freeze exists for game_code={context.game_code!r} -- "
            "SG must never be calculated/published from unfrozen R2 evidence"
        )
    if not verify_r2_freeze_hash(context):
        raise SgPreconditionError(
            f"SG PRECONDITION FAILED: R2 freeze for game_code={context.game_code!r} failed hash "
            "verification -- refusing to compute SG from a possibly-tampered/corrupted freeze"
        )
    return freeze


SG_COMPONENTS = ("sg_ott", "sg_app", "sg_arg", "sg_putt", "sg_total")
