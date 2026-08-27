"""Tests for klpga.discovery.flag_recovery — separating VALUE validity
from RANK validity for a FLAGGED response."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.response_schema import DataQualityFlags
from klpga.discovery.flag_recovery import (
    REASON_NONE,
    REASON_RANK_ONLY,
    REASON_VALUE_ISSUE,
    classify_flag_reasons,
    recover_value_validity,
)

REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


def test_classify_none_when_no_flags():
    result = classify_flag_reasons(DataQualityFlags())
    assert result["reason"] == REASON_NONE
    assert result["value_validity"] == "VALID"
    assert result["rank_validity"] == "VALID"


def test_classify_rank_only_when_only_duplicate_ranks():
    result = classify_flag_reasons(DataQualityFlags(duplicate_ranks=3))
    assert result["reason"] == REASON_RANK_ONLY
    assert result["value_validity"] == "VALID"
    assert result["rank_validity"] == "SUSPECT"
    assert result["flags"] == {"duplicate_ranks": 3}


def test_classify_value_issue_when_a_value_flag_is_present():
    result = classify_flag_reasons(DataQualityFlags(blank_values=2))
    assert result["reason"] == REASON_VALUE_ISSUE
    assert result["value_validity"] == "SUSPECT"
    assert result["rank_validity"] == "VALID"


def test_classify_value_issue_dominates_when_both_present():
    result = classify_flag_reasons(DataQualityFlags(duplicate_ranks=3, non_numeric_numeric_fields=1))
    assert result["reason"] == REASON_VALUE_ISSUE
    assert result["value_validity"] == "SUSPECT"
    assert result["rank_validity"] == "SUSPECT"


def test_recover_value_validity_missing_file_returns_unknown(tmp_path):
    result = recover_value_validity(tmp_path / "does_not_exist.html")
    assert result["reason"] == "FILE_MISSING"
    assert result["value_validity"] == "UNKNOWN"


def test_recover_value_validity_real_flagged_evidence_is_rank_only():
    """Real, already-committed evidence: Approach__Approach01__020101__2025.html
    was independently confirmed (docs/NEO_WIN_V0_1_METHODOLOGY.md) to be
    FLAGGED purely due to duplicate_ranks (a real "0" rank sentinel
    shared by many players), never a value-affecting flag."""
    path = REAL_RAW_SAMPLES_DIR / "Approach__Approach01__020101__2025.html"
    result = recover_value_validity(path)
    assert result["reason"] == REASON_RANK_ONLY
    assert result["value_validity"] == "VALID"
