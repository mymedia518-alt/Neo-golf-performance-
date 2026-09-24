"""Terminology dictionary for the playerCode=9431 (박보겸) Player
Intelligence report.

Every label here is identical to the ones 10097's report already uses
-- the labels themselves (FACT/EVIDENCE/analysis/..., chip labels,
status/durability labels, DNA labels, section titles) are player-
agnostic UI vocabulary, not content about any one player. Re-exporting
the single existing dictionary (player_intelligence_10097_terms.py)
rather than redefining it keeps the wording identical across both
Gold Standard reports without touching that module at all -- zero risk
to 10097's own output.
"""
from __future__ import annotations

from klpga.website_v2.player_intelligence_10097_terms import *  # noqa: F401,F403
from klpga.website_v2.player_intelligence_10097_terms import (  # noqa: F401
    CHECKLIST_DESCRIPTION,
    CHECKLIST_TITLE,
    CHIP_LABEL,
    CONFIDENCE_LABEL,
    CONTRIBUTION_LABEL,
    CONTRIBUTION_UNAVAILABLE,
    CURRENT_READING_LABEL,
    CURRENT_STATUS_LABEL,
    DURABILITY_LABEL,
    EVIDENCE_TOGGLE_LABEL,
    EXCLUDED_DESCRIPTION,
    EXCLUDED_TITLE,
    HERO_TITLE,
    LOSS_DNA,
    NEXT_REVIEW_LABEL,
    PROTOCOL_ROW_LABEL,
    SECTION_LABEL,
    SG_COMPONENT,
    SG_TOTAL,
    STATUS_LABEL,
    TOP_CONTRIBUTOR_LABEL,
    TREND_DNA,
    UNIT,
    WIN_DNA,
)
