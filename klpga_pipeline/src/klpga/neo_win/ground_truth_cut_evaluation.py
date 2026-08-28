"""Bridges klpga.neo_win.ground_truth_diagnostic's real R2 x R3
double-verified ground truth into the SAME `PlayerR2Reconciled` shape
klpga.neo_win.r1_to_r2_reconciliation.reconcile_r1_to_r2 produces, so
the already-built, already-tested evaluation pipeline
(klpga.neo_win.r1_r2_evaluation_report.build_player_cut_evaluation_rows,
klpga.neo_win.cut_evaluation's metrics, klpga.neo_win.
r2_pipeline_validation's hard gates) can consume it completely
unchanged. This module does not reimplement any evaluation math — it
only converts a richer, already-resolved status vocabulary into the
narrower one the existing pipeline expects.

======================================================================
EXPLICIT STATUS OVERRIDES — real, human-verified evidence only
======================================================================
`explicit_status_overrides` is a plain {player_code: "WD"|"DQ"} map a
caller supplies from evidence a human directly verified on the real
official site (e.g. explicit "WD" status text visible on the official
leaderboard for a player whose Round 2 row was otherwise ambiguous —
the real 999/INCOMPLETE sentinel). This is never inferred or guessed
here; the same trust level as klpga.neo_win.ground_truth_diagnostic's
own r3_grouping_rows parameter. An overridden player is classified
CUT_OUTCOME_WD_AFTER_R1_START (for "WD") or CUT_OUTCOME_DQ (for "DQ")
— NEVER folded into a generic CUT_OUTCOME_WD, and NEVER conflated with
the separate population of players who were already unavailable /
excluded before Round 1 even started (those never have a frozen R1
prediction at all, so klpga.neo_win.r1_r2_evaluation_report.
build_player_cut_evaluation_rows already excludes them mechanically —
this module does not need to, and does not, special-case them).

If an override conflicts with real Round 3 grouping evidence (the
ground truth row was MADE_CUT_CONFIRMED — i.e. the player was actually
found in the real Round 3 grouping/tee-time list), this is a genuine
R2/R3-vs-human-evidence conflict: the override is NOT silently trusted
over real grouping evidence, the player is kept CUT_OUTCOME_UNRESOLVED
(excluded from scoring either way), and the conflict is reported in
`override_conflicts` for a human to resolve — the same hard-gate
discipline klpga.neo_win.ground_truth_diagnostic already applies to
its own R2/R3 conflicts.
"""
from __future__ import annotations

from typing import Optional

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD,
    CUT_OUTCOME_WD_AFTER_R1_START,
)
from klpga.neo_win.ground_truth_diagnostic import (
    STATUS_DQ,
    STATUS_MADE_CUT,
    STATUS_MISSED_CUT_CANDIDATE,
    STATUS_REVIEW_REQUIRED,
    STATUS_WD,
    GroundTruthRow,
)
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r1_to_r2_reconciliation import PlayerR2Reconciled
from klpga.neo_win.round_reconciliation import NormalizedPlayer

_GROUND_TRUTH_STATUS_TO_CUT_OUTCOME = {
    STATUS_MADE_CUT: CUT_OUTCOME_MADE,
    STATUS_MISSED_CUT_CANDIDATE: CUT_OUTCOME_MISSED,
    STATUS_WD: CUT_OUTCOME_WD,
    STATUS_DQ: CUT_OUTCOME_DQ,
    STATUS_REVIEW_REQUIRED: CUT_OUTCOME_UNRESOLVED,
}

_VALID_OVERRIDE_VALUES = {"WD": CUT_OUTCOME_WD_AFTER_R1_START, "DQ": CUT_OUTCOME_DQ}


def to_player_r2_reconciled_rows(
    ground_truth_rows: list[GroundTruthRow],
    official_r2_normalized: dict[str, NormalizedPlayer],
    explicit_status_overrides: Optional[dict[str, str]] = None,
) -> tuple[list[PlayerR2Reconciled], list[dict]]:
    """Returns (reconciled_rows, override_conflicts). `official_r2_normalized`
    (klpga.neo_win.round_reconciliation.normalize_official_round's own
    output for round_number=2) supplies the real r2_position/
    r2_score_to_par fields — GroundTruthRow does not carry those, only
    the raw rank/score text needed for its own comparison table."""
    overrides = explicit_status_overrides or {}
    unknown = set(overrides.values()) - set(_VALID_OVERRIDE_VALUES)
    if unknown:
        raise ValueError(f"explicit_status_overrides values must be 'WD' or 'DQ', got {sorted(unknown)}")

    rows: list[PlayerR2Reconciled] = []
    override_conflicts: list[dict] = []
    for g in ground_truth_rows:
        outcome = _GROUND_TRUTH_STATUS_TO_CUT_OUTCOME[g.final_ground_truth_status]
        override = overrides.get(g.player_code)
        if override is not None:
            if g.final_ground_truth_status == STATUS_MADE_CUT:
                override_conflicts.append(
                    {
                        "player_code": g.player_code,
                        "player_name": g.official_name,
                        "ground_truth_status": g.final_ground_truth_status,
                        "override": override,
                        "reason": (
                            "explicit status override conflicts with real Round 3 grouping presence — "
                            "kept UNRESOLVED, never silently trusted over real R3 evidence"
                        ),
                    }
                )
                outcome = CUT_OUTCOME_UNRESOLVED
            else:
                outcome = _VALID_OVERRIDE_VALUES[override]

        o = official_r2_normalized.get(g.player_code)
        rows.append(
            PlayerR2Reconciled(
                player_code=g.player_code,
                player_name=g.official_name,
                r2_position=o.position if o else None,
                r2_score_to_par=o.score_to_par if o else None,
                r2_outcome=outcome,
                in_frozen_r1=False,  # not consumed downstream; real membership comes from the frozen_r1 join itself
                in_official_r2=g.r2_present,
            )
        )
    return rows, override_conflicts


def summarize_ground_truth_reconciliation(
    frozen_r1: list[PlayerR1Frozen],
    reconciled_rows: list[PlayerR2Reconciled],
    official_r2_normalized: dict[str, NormalizedPlayer],
) -> dict:
    """Same summary shape klpga.neo_win.r1_to_r2_reconciliation.
    reconcile_r1_to_r2 produces (required keys: new_wd, new_dq, cut,
    made_cut, missing) so klpga.neo_win.r2_pipeline_validation's
    existing check_wd_dq_explicitly_handled /
    check_unavailable_players_explicitly_handled can be reused
    unchanged against ground-truth-derived data."""
    frozen_codes = {f.player_code for f in frozen_r1}
    r2_codes = set(official_r2_normalized)
    reconciled_codes = {r.player_code for r in reconciled_rows}
    missing_rows = [r for r in reconciled_rows if r.r2_outcome == CUT_OUTCOME_UNRESOLVED]

    return {
        "r1_players": len(frozen_codes),
        "r2_players": len(r2_codes),
        "new_wd": sum(1 for r in reconciled_rows if r.r2_outcome in (CUT_OUTCOME_WD, CUT_OUTCOME_WD_AFTER_R1_START)),
        "new_dq": sum(1 for r in reconciled_rows if r.r2_outcome == CUT_OUTCOME_DQ),
        "cut": sum(1 for r in reconciled_rows if r.r2_outcome == CUT_OUTCOME_MISSED),
        "made_cut": sum(1 for r in reconciled_rows if r.r2_outcome == CUT_OUTCOME_MADE),
        "missing": len(missing_rows),
        "missing_player_diagnostics": [
            {"player_code": r.player_code, "player_name": r.player_name} for r in missing_rows
        ],
        "unmatched_player_codes": {
            "only_in_frozen_r1": sorted(frozen_codes - reconciled_codes),
            "only_in_official_r2": sorted(r2_codes - frozen_codes),
        },
    }
