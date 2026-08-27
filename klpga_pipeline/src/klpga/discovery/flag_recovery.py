"""Separates VALUE validity from RANK validity for a response classified
FLAGGED at the response level (`official_metric_value.validation_status`).

Real-evidence finding (docs/NEO_WIN_V0_1_METHODOLOGY.md): across this
project's real committed evidence, FLAGGED is dominated by
`duplicate_ranks` — a rank-COLUMN artifact (ties, or an unranked/
insufficient-attempts sentinel), never proven to affect the VALUE
column. `response_schema.DataQualityFlags` already distinguishes rank-
only flags from value-affecting flags at the FIELD level; this module
just classifies which category(ies) actually fired for one response,
so a FLAGGED response whose ONLY nonzero flag is `duplicate_ranks` can
have its VALUES safely recovered for use — never its ranks.

This is a per-RESPONSE classification (matching how `validation_status`
itself is computed — one flag set per raw response, shared by every
player row within it), not a per-player-row classification: this
project's evidence does not support a finer-grained claim.
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from klpga.discovery.response_parser import parse_record_response
from klpga.discovery.response_schema import DataQualityFlags, analyze_response

RANK_ONLY_FLAGS: frozenset[str] = frozenset({"duplicate_ranks"})
VALUE_FLAGS: frozenset[str] = frozenset(
    {
        "duplicate_player_rows",
        "missing_player_code",
        "missing_player_name",
        "non_numeric_numeric_fields",
        "blank_values",
        "percentage_out_of_range",
        "successes_exceed_attempts",
        "negative_counts",
        "non_positive_measured_rounds",
    }
)

REASON_NONE = "NONE"
REASON_RANK_ONLY = "RANK_ONLY"
REASON_VALUE_ISSUE = "VALUE_ISSUE"


def classify_flag_reasons(dq: DataQualityFlags) -> dict:
    """Pure classification over an already-computed DataQualityFlags —
    no I/O. Returns {"reason", "value_validity", "rank_validity",
    "flags"} where `flags` is every nonzero flag name -> count."""
    nonzero = {f.name: getattr(dq, f.name) for f in fields(dq) if f.name != "notes" and getattr(dq, f.name)}
    if not nonzero:
        return {"reason": REASON_NONE, "value_validity": "VALID", "rank_validity": "VALID", "flags": {}}

    value_flags_present = {k: v for k, v in nonzero.items() if k in VALUE_FLAGS}
    rank_flags_present = {k: v for k, v in nonzero.items() if k in RANK_ONLY_FLAGS}

    if value_flags_present:
        return {
            "reason": REASON_VALUE_ISSUE,
            "value_validity": "SUSPECT",
            "rank_validity": "SUSPECT" if rank_flags_present else "VALID",
            "flags": nonzero,
        }
    return {"reason": REASON_RANK_ONLY, "value_validity": "VALID", "rank_validity": "SUSPECT", "flags": nonzero}


def recover_value_validity(raw_sample_path: "str | Path") -> dict:
    """Re-parses the already-saved raw response (never fires a live
    request) and classifies its flag reason. Returns the same shape as
    classify_flag_reasons, or {"reason": "FILE_MISSING", ...} if the
    raw sample no longer exists on disk — never crashes, never assumes
    RANK_ONLY when it can't actually check."""
    path = Path(raw_sample_path)
    if not path.exists():
        return {"reason": "FILE_MISSING", "value_validity": "UNKNOWN", "rank_validity": "UNKNOWN", "flags": {}}
    html = path.read_text(encoding="utf-8")
    parsed = parse_record_response(html)
    analysis = analyze_response(parsed)
    return classify_flag_reasons(analysis.data_quality)
