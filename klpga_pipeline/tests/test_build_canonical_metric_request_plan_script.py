"""Tests for scripts/28_build_canonical_metric_request_plan.py — fully
offline, no network access at all (this script never fetches
anything, only reads a local taxonomy JSON)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "28_build_canonical_metric_request_plan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_canonical_metric_request_plan_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _real_evidence_taxonomy() -> dict:
    """Mirrors the real evidence: five All::* navigation entries plus
    the five confirmed stat families."""
    leaves = []
    for menu2 in ("Sg", "Tee", "Approach", "Around", "Putt"):
        leaves.append(
            {
                "menu1": "All", "menu1_label": "All", "menu2": menu2, "menu2_label": "전체기록보기",
                "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": f"All::{menu2}",
            }
        )
    leaves.append(
        {
            "menu1": "Sg", "menu1_label": "SG", "menu2": "Total", "menu2_label": "SG : 전체",
            "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "Sg::Total",
        }
    )
    leaves.append(
        {
            "menu1": "Putt", "menu1_label": "퍼팅", "menu2": "Putt01", "menu2_label": "1퍼트",
            "menu3": "040101", "menu3_label": "1퍼트 성공률", "leaf_level": "menu3", "source_metric_key": "Putt::Putt01::040101",
        }
    )
    return {"source_url": "https://example.test/record", "leaves": leaves}


def test_run_writes_canonical_plan_json_excluding_all_navigation_entries(module, tmp_path, capsys):
    taxonomy = _real_evidence_taxonomy()
    rc = module.run(taxonomy, "test.json", tmp_path)
    assert rc == module.EXIT_COMPLETE

    out_path = tmp_path / "KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json"
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["counts"]["navigation_container_count"] == 5
    assert payload["counts"]["canonical_requestable_metric_count"] == 2
    identity_keys = {m["identity_key"] for m in payload["canonical_requestable_metrics"]}
    assert identity_keys == {"Sg::Total", "Putt::Putt01::040101"}
    assert not any(m["menu1"] == "All" for m in payload["canonical_requestable_metrics"])


def test_run_prints_the_required_count_breakdown(module, tmp_path, capsys):
    taxonomy = _real_evidence_taxonomy()
    module.run(taxonomy, "test.json", tmp_path)
    out = capsys.readouterr().out
    assert "navigation/container nodes:" in out
    assert "CANONICAL requestable metric count:" in out
    assert "Phase B2" in out


def test_missing_taxonomy_file_fails_cleanly(module, tmp_path):
    import sys

    argv_backup = sys.argv
    sys.argv = [
        "28_build_canonical_metric_request_plan.py",
        "--taxonomy",
        str(tmp_path / "does_not_exist.json"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_TAXONOMY_LOAD_FAILED


# ---------------------------------------------------------------
# Follow-up round — real Windows result (283 total, 272 malformed,
# ~96%): malformed-leaf diagnostic report, per-family breakdown, and
# the sanity-invariant safety guard that must fail loudly on exactly
# this shape rather than presenting a misleading canonical plan.
# ---------------------------------------------------------------


def _windows_shaped_taxonomy() -> dict:
    leaves = []
    for i in range(27):
        leaves.append(
            {
                "menu1": "", "menu1_label": "", "menu2": "", "menu2_label": "",
                "menu3": f"{900000 + i}", "menu3_label": "고아 항목",
                "leaf_level": "menu3", "source_metric_key": f"::{900000 + i}",
            }
        )
    for menu2 in ("Sg", "Tee", "Approach", "Around", "Putt", "Other"):
        leaves.append(
            {
                "menu1": "All", "menu1_label": "All", "menu2": menu2, "menu2_label": "전체",
                "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": f"All::{menu2}",
            }
        )
    leaves.append(
        {
            "menu1": "Sg", "menu1_label": "SG", "menu2": "Total", "menu2_label": "SG : 전체",
            "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "Sg::Total",
        }
    )
    for i in range(4):
        leaves.append(
            {
                "menu1": "Tee", "menu1_label": "티샷", "menu2": "Tee01", "menu2_label": "",
                "menu3": f"01010{i}", "menu3_label": f"거리 구간 {i}",
                "leaf_level": "menu3", "source_metric_key": f"Tee::Tee01::01010{i}",
            }
        )
    return {"source_url": "https://example.test", "leaves": leaves}


def test_run_writes_malformed_leaf_report_csv(module, tmp_path):
    taxonomy = _windows_shaped_taxonomy()
    module.run(taxonomy, "test.json", tmp_path)
    report_path = tmp_path / "KLPGA_MALFORMED_LEAF_REPORT.csv"
    assert report_path.exists()
    lines = report_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 + 27  # header + 27 malformed rows
    assert "missing_menu1_and_menu2" in report_path.read_text(encoding="utf-8")


def test_run_prints_per_family_breakdown(module, tmp_path, capsys):
    taxonomy = _windows_shaped_taxonomy()
    module.run(taxonomy, "test.json", tmp_path)
    out = capsys.readouterr().out
    assert "Counts by menu1 family:" in out
    for family in ("Sg", "Tee", "Approach", "Around", "Putt", "other"):
        assert family in out


def test_run_returns_sanity_check_failed_on_the_windows_shaped_result(module, tmp_path, capsys):
    """The exact regression this round demands: a ~96%-malformed
    result must exit non-zero and say so loudly, never presenting
    itself as a clean, trustworthy canonical plan."""
    taxonomy = _windows_shaped_taxonomy()
    rc = module.run(taxonomy, "test.json", tmp_path)
    assert rc == module.EXIT_SANITY_CHECK_FAILED
    out = capsys.readouterr().out
    assert "SANITY CHECK FAILED" in out
    assert "malformed_ratio" in out
    # Output files are still written even on a failed sanity check —
    # the data is real and worth having on disk to investigate.
    assert (tmp_path / "KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json").exists()
    assert (tmp_path / "KLPGA_MALFORMED_LEAF_REPORT.csv").exists()


def test_run_returns_complete_on_a_clean_result(module, tmp_path):
    taxonomy = _real_evidence_taxonomy()
    rc = module.run(taxonomy, "test.json", tmp_path)
    assert rc == module.EXIT_COMPLETE


def test_main_reads_real_taxonomy_file_end_to_end(module, tmp_path):
    import sys

    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(_real_evidence_taxonomy()), encoding="utf-8")
    out_dir = tmp_path / "out"

    argv_backup = sys.argv
    sys.argv = [
        "28_build_canonical_metric_request_plan.py",
        "--taxonomy",
        str(taxonomy_path),
        "--out-dir",
        str(out_dir),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE
    assert (out_dir / "KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json").exists()
