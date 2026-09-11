"""R2 HOUSE: SG (strokes gained) precondition gate.

VERIFIED FROZEN R2 -> SG calculation -> OTT/APP/ARG/PUTT/TOTAL.

HONEST STATE (confirmed by repository archaeology, 2026-09-11): this
codebase has no live, per-round OTT/APP/ARG/PUTT/TOTAL SG calculator
anywhere. The only SG data that exists is a prior-season, cross-
tournament warehouse (`historical_sg_warehouse*.json`, built by
scripts/62-64/80) used exclusively for PRE-stage prior form -- never a
live/current-round source. KB's own real R1 model
(scripts/108_apply_r1_model_to_kb.py) does not use SG at all; it scores
players via a field-relative z-score of round-to-par instead. This gate
module is therefore the enforceable PRECONDITION for whatever future
live per-round SG source is eventually built, not a wrapper around one
that already exists -- calling `require_verified_frozen_r2_for_sg`
before any real SG number is computed/published is what stays
permanently true regardless of when/whether a live SG collector is
added. It must never be bypassed to publish a real SG number computed
from incomplete/unfrozen R2 evidence.
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
