"""Tests for scripts/31_audit_identity_key_collisions.py — fully
offline, no network access, no live requests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "31_audit_identity_key_collisions.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_identity_key_collisions_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _leaf(menu1, menu2, menu3, leaf_level, label):
    return {
        "menu1": menu1,
        "menu1_label": menu1,
        "menu2": menu2,
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": menu3,
        "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else ""),
    }


def _table_response_html(column_labels: list[str]) -> str:
    ths = "".join(f"<th>{label}</th>" for label in column_labels)
    record_attrs = " ".join(
        f'data-record{"" if i == 0 else i}="{i + 1}"' for i in range(len(column_labels) - 2)
    )
    tds = "".join(f"<td>{i}</td>" for i in range(len(column_labels)))
    return f"<table><thead><tr>{ths}</tr></thead><tbody><tr data-rank=\"1\" data-name=\"테스트\" {record_attrs}>{tds}</tr></tbody></table>"


def test_gate_clean_when_every_group_resolves(module, tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Around", "Around04", "030306", "menu3", "평균 남은 거리"),
            _leaf("Around", "Around04", "030306", "menu3", "스크램블링수"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 남은 거리", "스크램블링수"])
    (tmp_path / "Around__Around04__030306__2025.html").write_text(html, encoding="utf-8")

    rc = module.run(taxonomy, "2025", tmp_path)
    assert rc == module.EXIT_GATE_CLEAN


def test_gate_not_clean_when_a_group_has_insufficient_evidence(module, tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Tee", "Tee01", "010101", "menu3", "Par4,5 티샷 비율"),
        ]
    }
    rc = module.run(taxonomy, "2025", tmp_path)  # no raw sample saved
    assert rc == module.EXIT_GATE_NOT_CLEAN


def test_gate_reports_b2_request_count_from_unique_identity_key_count(module, tmp_path, capsys):
    taxonomy = {
        "leaves": [
            _leaf("Sg", "Total", None, "menu2", "SG : 전체"),
            _leaf("Around", "Around04", "030306", "menu3", "평균 남은 거리"),
            _leaf("Around", "Around04", "030306", "menu3", "스크램블링수"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 남은 거리", "스크램블링수"])
    (tmp_path / "Around__Around04__030306__2025.html").write_text(html, encoding="utf-8")

    rc = module.run(taxonomy, "2025", tmp_path)
    out = capsys.readouterr().out
    assert rc == module.EXIT_GATE_CLEAN
    assert "B2_REQUEST_COUNT = 2" in out  # Sg::Total + Around::Around04::030306


# ---------------------------------------------------------------
# Round 10 diagnostic follow-up — dedicated printed sections for
# unresolved groups, built entirely from evidence the audit already
# loaded (no PowerShell text-extraction needed against the free-form
# per-group log lines above).
# ---------------------------------------------------------------


def test_unresolved_collision_diagnostic_section_prints_required_fields(module, tmp_path, capsys):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "Par4,5 티샷 비율"),
            _leaf("Tee", "Tee01", "010101", "menu3", "티샷"),
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 티샷 거리(yds)", "티샷 거리 총 합(yds)", "Par4,5 티샷 횟수"])
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(html, encoding="utf-8")

    module.run(taxonomy, "2025", tmp_path)
    out = capsys.readouterr().out

    assert "=== UNRESOLVED_COLLISION_DIAGNOSTIC ===" in out
    assert "identity_key: Tee::Tee01::010101" in out
    assert "taxonomy_labels:" in out
    assert "  - Par4,5 티샷 비율" in out
    assert "response_columns:" in out
    assert "  - 평균 티샷 거리(yds)" in out
    assert "confirmed_matches:" in out
    # After paren-stripping, "평균 티샷 거리" and "평균 티샷 거리(yds)"
    # normalize to the identical string -- an "exact" match, not a
    # weaker "substring" one.
    assert "  - 평균 티샷 거리 -> 평균 티샷 거리(yds) [exact]" in out
    assert "container_candidates:" in out
    assert "  - 티샷" in out
    assert "unmatched_taxonomy_labels:" in out
    assert "  - Par4,5 티샷 비율" in out
    assert f"raw_sample_path: {tmp_path / 'Tee__Tee01__010101__2025.html'}" in out


def test_missing_evidence_identities_section_lists_expected_paths(module, tmp_path, capsys):
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt02", "040201", "menu3", "성공률"),
            _leaf("Putt", "Putt02", "040201", "menu3", "퍼팅"),
        ]
    }
    module.run(taxonomy, "2025", tmp_path)  # no raw sample saved at all
    out = capsys.readouterr().out

    assert "=== MISSING_EVIDENCE_IDENTITIES ===" in out
    assert "identity_key: Putt::Putt02::040201" in out
    assert f"expected_raw_sample_path: {tmp_path / 'Putt__Putt02__040201__2025.html'}" in out


def test_summary_counts_match_actual_category_counts(module, tmp_path, capsys):
    taxonomy = {
        "leaves": [
            # PARTIAL: one matched, one genuinely unmatched
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Tee", "Tee01", "010101", "menu3", "완전 무관한 라벨"),
            # D_UNRESOLVED: nothing relates at all
            _leaf("Putt", "Putt02", "040201", "menu3", "라벨A"),
            _leaf("Putt", "Putt02", "040201", "menu3", "라벨B"),
            # INSUFFICIENT_EVIDENCE: no raw sample saved
            _leaf("Around", "Around05", "030401", "menu3", "라벨C"),
            _leaf("Around", "Around05", "030401", "menu3", "라벨D"),
        ]
    }
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(
        _table_response_html(["순위", "선수명", "평균 티샷 거리(yds)"]), encoding="utf-8"
    )
    (tmp_path / "Putt__Putt02__040201__2025.html").write_text(
        _table_response_html(["순위", "선수명", "무관한 컬럼"]), encoding="utf-8"
    )

    module.run(taxonomy, "2025", tmp_path)
    out = capsys.readouterr().out

    assert "EXISTING_EVIDENCE_PARTIAL = 1" in out
    assert "EXISTING_EVIDENCE_D_UNRESOLVED = 1" in out
    assert "MISSING_EVIDENCE_REQUESTS = 1" in out
    assert "TOTAL_UNRESOLVED = 3" in out


def test_missing_taxonomy_file_fails_cleanly(module, tmp_path):
    import sys

    argv_backup = sys.argv
    sys.argv = [
        "31_audit_identity_key_collisions.py",
        "--taxonomy",
        str(tmp_path / "does_not_exist.json"),
        "--season",
        "2025",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_TAXONOMY_LOAD_FAILED


def test_main_reads_real_taxonomy_file_end_to_end(module, tmp_path):
    import sys

    taxonomy = {
        "leaves": [
            _leaf("Sg", "Total", None, "menu2", "SG : 전체"),
        ]
    }
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy), encoding="utf-8")

    argv_backup = sys.argv
    sys.argv = [
        "31_audit_identity_key_collisions.py",
        "--taxonomy",
        str(taxonomy_path),
        "--season",
        "2025",
        "--raw-samples-dir",
        str(tmp_path / "raw_samples"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_GATE_CLEAN  # no collisions at all -> trivially clean
