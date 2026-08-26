"""Tests for scripts/run_klpga_collector.py — the single Windows
entry point wrapping the local collector. Fully offline; the one
`--live` path exercised here uses a taxonomy with zero missing-
evidence identities so the REAL `PoliteHttpClient` can be constructed
safely without ever making an HTTP call (same pattern already proven
in tests/test_bounded_missing_evidence_request_plan_script.py's own
`test_main_live_end_to_end_with_zero_missing_evidence...` test)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_klpga_collector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_klpga_collector_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


_ZERO_MISSING_EVIDENCE_TAXONOMY = {
    "leaves": [
        {
            "menu1": "Tee",
            "menu1_label": "Tee",
            "menu2": "Tee01",
            "menu2_label": "",
            "menu3": "010101",
            "menu3_label": "평균 티샷 거리",
            "leaf_level": "menu3",
            "source_metric_key": "Tee::Tee01::010101",
        }
    ]
}


def test_main_taxonomy_missing_fails_cleanly(module, tmp_path):
    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_collector.py",
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


def test_main_default_preview_makes_zero_http_calls_and_writes_report(module, tmp_path):
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(_ZERO_MISSING_EVIDENCE_TAXONOMY), encoding="utf-8")
    report_path = tmp_path / "out" / "REPORT.md"

    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_collector.py",
        "--taxonomy",
        str(taxonomy_path),
        "--season",
        "2025",
        "--raw-samples-dir",
        str(tmp_path / "raw_samples"),
        "--checkpoint-path",
        str(tmp_path / "out" / "CHECKPOINT.json"),
        "--skip-queue-path",
        str(tmp_path / "out" / "SKIP_QUEUE.json"),
        "--report-path",
        str(report_path),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup

    assert rc == module.EXIT_COMPLETE
    assert report_path.exists()
    assert "PREVIEW" in report_path.read_text(encoding="utf-8")


def test_main_live_with_zero_missing_evidence_uses_real_client_safely(module, tmp_path):
    """Real `PoliteHttpClient` construction+wiring, safe offline only
    because zero identities are missing evidence here — no HTTP call
    is ever made."""
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(_ZERO_MISSING_EVIDENCE_TAXONOMY), encoding="utf-8")

    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_collector.py",
        "--taxonomy",
        str(taxonomy_path),
        "--season",
        "2025",
        "--raw-samples-dir",
        str(tmp_path / "raw_samples"),
        "--cache-dir",
        str(tmp_path / "http_cache"),
        "--checkpoint-path",
        str(tmp_path / "out" / "CHECKPOINT.json"),
        "--skip-queue-path",
        str(tmp_path / "out" / "SKIP_QUEUE.json"),
        "--report-path",
        str(tmp_path / "out" / "REPORT.md"),
        "--live",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE


def test_default_paths_live_under_docs_discovery_local_collector(module):
    assert module.DEFAULT_OUT_DIR.name == "local_collector"
    assert module.DEFAULT_OUT_DIR.parent.name == "discovery"


def test_main_accepts_heartbeat_interval_flag(module, tmp_path):
    """--heartbeat-interval-seconds is optional CLI wiring for the new
    live-progress observability — must not break the safe, real-
    PoliteHttpClient zero-missing-evidence path."""
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(_ZERO_MISSING_EVIDENCE_TAXONOMY), encoding="utf-8")

    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_collector.py",
        "--taxonomy",
        str(taxonomy_path),
        "--season",
        "2025",
        "--raw-samples-dir",
        str(tmp_path / "raw_samples"),
        "--cache-dir",
        str(tmp_path / "http_cache"),
        "--checkpoint-path",
        str(tmp_path / "out" / "CHECKPOINT.json"),
        "--skip-queue-path",
        str(tmp_path / "out" / "SKIP_QUEUE.json"),
        "--report-path",
        str(tmp_path / "out" / "REPORT.md"),
        "--live",
        "--heartbeat-interval-seconds",
        "5",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE
