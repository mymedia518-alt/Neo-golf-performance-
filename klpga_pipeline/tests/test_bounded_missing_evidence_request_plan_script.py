"""Tests for scripts/32_bounded_missing_evidence_request_plan.py —
fully offline, no network access, no live requests. DRY RUN ONLY this
round: the script has no live-fire code path to test."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "32_bounded_missing_evidence_request_plan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("bounded_missing_evidence_request_plan_script", SCRIPT_PATH)
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


def _mixed_taxonomy() -> dict:
    """Three collision groups: one fully resolved (has a matching raw
    sample), one PARTIAL_MATCH_NEEDS_REVIEW (has a raw sample but one
    label doesn't match), one with NO raw sample at all
    (INSUFFICIENT_EVIDENCE) — this last one is the only one that
    should ever appear in the missing-evidence plan."""
    return {
        "leaves": [
            _leaf("Sg", "All", None, "menu2", "Strokes Gained"),
            _leaf("Sg", "All", None, "menu2", "전체"),
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Tee", "Tee01", "010101", "menu3", "완전히 무관한 라벨"),
            _leaf("Putt", "Putt09", "040901", "menu3", "라벨A"),
            _leaf("Putt", "Putt09", "040901", "menu3", "라벨B"),
        ]
    }


def _write_raw_samples(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "Sg__All__2025.html").write_text(
        "<html><body><table><thead><tr><th></th></tr></thead><tbody></tbody></table></body></html>",
        encoding="utf-8",
    )
    (raw_dir / "Tee__Tee01__010101__2025.html").write_text(
        _table_response_html(["순위", "선수명", "평균 티샷 거리(yds)"]), encoding="utf-8"
    )
    # Deliberately NO file for Putt__Putt09__040901__2025.html.


def test_dry_run_flag_required(module, tmp_path):
    taxonomy = _mixed_taxonomy()
    rc = module.run(taxonomy, "2025", tmp_path, dry_run=False)
    assert rc == module.EXIT_DRY_RUN_REQUIRED


def test_dry_run_makes_zero_http_requests(module, tmp_path, capsys):
    """No client/network object exists anywhere in this script — the
    only assertion possible is that it runs to completion and reports
    zero requests, purely from local file reads."""
    _write_raw_samples(tmp_path)
    taxonomy = _mixed_taxonomy()
    rc = module.run(taxonomy, "2025", tmp_path, dry_run=True)
    assert rc == module.EXIT_COMPLETE
    out = capsys.readouterr().out
    assert "Zero HTTP requests made" in out


def test_plan_includes_only_insufficient_evidence_identity(module, tmp_path):
    _write_raw_samples(tmp_path)
    taxonomy = _mixed_taxonomy()
    rows = module.build_missing_evidence_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert len(rows) == 1
    assert rows[0]["identity_key"] == "Putt::Putt09::040901"


def test_plan_excludes_resolved_and_partial_groups(module, tmp_path):
    _write_raw_samples(tmp_path)
    taxonomy = _mixed_taxonomy()
    rows = module.build_missing_evidence_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    identity_keys = {r["identity_key"] for r in rows}
    assert "Sg::All" not in identity_keys  # EMPTY_SHARED_RESPONSE, resolved
    assert "Tee::Tee01::010101" not in identity_keys  # PARTIAL_MATCH_NEEDS_REVIEW


def test_plan_row_fields_match_the_canonical_request_parameters(module, tmp_path):
    _write_raw_samples(tmp_path)
    taxonomy = _mixed_taxonomy()
    rows = module.build_missing_evidence_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    row = rows[0]
    assert row["menu1"] == "Putt"
    assert row["menu2"] == "Putt09"
    assert row["menu3"] == "040901"
    assert row["season"] == "2025"
    assert row["expected_raw_sample_path"] == str(tmp_path / "Putt__Putt09__040901__2025.html")
    assert row["raw_sample_exists"] is False


def test_request_count_matches_number_of_missing_identities(module, tmp_path, capsys):
    _write_raw_samples(tmp_path)
    taxonomy = _mixed_taxonomy()
    module.run(taxonomy, "2025", tmp_path, dry_run=True)
    out = capsys.readouterr().out
    assert "exact request count: 1" in out
    assert "identity_key: Putt::Putt09::040901" in out


def test_authoritative_count_not_hardcoded_scales_with_real_data(module, tmp_path):
    """The plan's size must come from the audit's own classification,
    not a fixed assumption — add a second genuinely-missing-evidence
    identity and confirm the count tracks it."""
    _write_raw_samples(tmp_path)
    taxonomy = _mixed_taxonomy()
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨C"))
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨D"))

    rows = module.build_missing_evidence_request_plan(taxonomy, season="2025", raw_samples_dir=tmp_path)
    assert len(rows) == 2
    assert {r["identity_key"] for r in rows} == {"Putt::Putt09::040901", "Around::Around09::030901"}


def test_missing_taxonomy_file_fails_cleanly(module, tmp_path):
    import sys

    argv_backup = sys.argv
    sys.argv = [
        "32_bounded_missing_evidence_request_plan.py",
        "--taxonomy",
        str(tmp_path / "does_not_exist.json"),
        "--season",
        "2025",
        "--dry-run",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_TAXONOMY_LOAD_FAILED


def test_main_end_to_end_dry_run(module, tmp_path):
    import sys

    _write_raw_samples(tmp_path / "raw_samples")
    taxonomy = _mixed_taxonomy()
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy), encoding="utf-8")

    argv_backup = sys.argv
    sys.argv = [
        "32_bounded_missing_evidence_request_plan.py",
        "--taxonomy",
        str(taxonomy_path),
        "--season",
        "2025",
        "--raw-samples-dir",
        str(tmp_path / "raw_samples"),
        "--dry-run",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE


def test_main_without_dry_run_flag_refuses(module, tmp_path):
    import sys

    taxonomy = _mixed_taxonomy()
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy), encoding="utf-8")

    argv_backup = sys.argv
    sys.argv = [
        "32_bounded_missing_evidence_request_plan.py",
        "--taxonomy",
        str(taxonomy_path),
        "--season",
        "2025",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_DRY_RUN_REQUIRED
