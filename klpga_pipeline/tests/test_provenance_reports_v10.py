"""MISSION V10 (2026-09-25): guards the 3 generated governance reports
(data provenance report, missing-data report, derived-value dependency
graph) against silently breaking or going stale. The reports
themselves are generated code, not hand-maintained prose (see
scripts/generate_provenance_reports_v10.py) -- this test exercises the
same generator functions the real files were built from, so a broken
generator fails CI here rather than only being caught the next time
someone happens to re-run it by hand."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("generate_provenance_reports_v10", ROOT / "scripts" / "generate_provenance_reports_v10.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_provenance_report_covers_both_builders_and_all_five_labels():
    report = gen._provenance_report()
    assert "Player History" in report
    assert "Player Intelligence Report" in report
    for label in ("MEASURED", "DERIVED", "IMPUTED", "NOT_COLLECTED", "NOT_AVAILABLE"):
        assert label in report


def test_missing_data_report_lists_at_least_one_real_gap_per_builder():
    report = gen._missing_data_report()
    assert "NOT_AVAILABLE" in report
    assert "NOT_COLLECTED" in report
    assert "coverage_matrix.rows" in report  # the flagged governance-gap section


def test_dependency_graph_report_names_at_least_one_real_edge():
    report = gen._dependency_graph_report()
    assert "depends on" in report


def test_the_three_committed_report_files_exist_and_are_non_trivial():
    docs = ROOT / "docs"
    for name, min_lines in (
        ("NEO_DATA_PROVENANCE_REPORT_10097_V1.md", 500),
        ("NEO_MISSING_DATA_REPORT_10097_V1.md", 30),
        ("NEO_DERIVED_VALUE_DEPENDENCY_GRAPH_10097_V1.md", 20),
    ):
        path = docs / name
        assert path.exists(), f"missing report file: {name}"
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) >= min_lines, f"{name} looks too short to be a real report ({len(text.splitlines())} lines)"


def test_committed_report_files_are_not_stale_relative_to_the_live_provenance_maps():
    """Regenerates the reports in-memory and checks the on-disk files
    still match -- if someone changes a _provenance_map() and forgets
    to re-run the generator, this test catches the drift."""
    docs = ROOT / "docs"
    checks = [
        ("NEO_DATA_PROVENANCE_REPORT_10097_V1.md", gen._provenance_report),
        ("NEO_MISSING_DATA_REPORT_10097_V1.md", gen._missing_data_report),
        ("NEO_DERIVED_VALUE_DEPENDENCY_GRAPH_10097_V1.md", gen._dependency_graph_report),
    ]
    stale = []
    for name, fn in checks:
        on_disk = (docs / name).read_text(encoding="utf-8")
        fresh = fn()
        if on_disk != fresh:
            stale.append(name)
    assert not stale, f"stale report(s), re-run scripts/generate_provenance_reports_v10.py: {stale}"
