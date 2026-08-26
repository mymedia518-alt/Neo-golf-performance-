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
