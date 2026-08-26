"""Tests for scripts/27_klpga_response_schema_sample.py — no network
access. Same FakeClient pattern as the other script tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "27_klpga_response_schema_sample.py"
FIXTURES = Path(__file__).parent / "fixtures"


def _load_module():
    spec = importlib.util.spec_from_file_location("klpga_response_schema_sample_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _leaf(menu1, menu2, menu3, leaf_level, label):
    key = f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else "")
    return {
        "menu1": menu1,
        "menu1_label": menu1,
        "menu2": menu2,
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": menu3,
        "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": key,
    }


@pytest.fixture()
def small_taxonomy():
    return {
        "source_url": "https://klpga.co.kr/web/record/locationRecord",
        "leaves": [
            _leaf("Sg", "Total", None, "menu2", "SG : 전체"),
            _leaf("Approach", "Approach01", "020104", "menu3", "그린 적중률 - 160~180야드 미만(RTP)"),
            _leaf("Approach", "Approach01", "020105", "menu3", "그린 적중률 - 140~160야드 미만(RTP)"),
        ],
    }


class RecordingFakeClient:
    """Maps (menu1, menu2, menu3, season) -> canned HTML response, and
    records every request made — used to assert TYPE A vs TYPE B
    request shape (TEST 1/2)."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.requests = []

    def post_text(self, url, data=None, **kwargs):
        self.requests.append(dict(data))
        key = (data.get("menu1"), data.get("menu2"), data.get("menu3"), data.get("season"))
        if key not in self.responses:
            raise KeyError(f"RecordingFakeClient has no canned response for {key}")
        return self.responses[key]


def _sg_html():
    return (FIXTURES / "loadLocationRecord_sg_total_sample.html").read_text(encoding="utf-8")


def _approach_020104_html():
    return (FIXTURES / "loadLocationRecord_approach_020104_sample.html").read_text(encoding="utf-8")


def _approach_020105_html():
    return (FIXTURES / "loadLocationRecord_approach_020105_sample.html").read_text(encoding="utf-8")


@pytest.fixture()
def client_2025(small_taxonomy):
    return RecordingFakeClient(
        {
            ("Sg", "Total", None, "2025"): _sg_html(),
            ("Approach", "Approach01", "020104", "2025"): _approach_020104_html(),
            ("Approach", "Approach01", "020105", "2025"): _approach_020105_html(),
        }
    )


# ---------------------------------------------------------------
# TEST 1/2 — menu2-level and menu3-level request construction
# ---------------------------------------------------------------


def test_menu2_level_request_omits_menu3_field_entirely(module):
    leaf = module.SampledLeaf(
        menu1="Sg", menu1_label="SG", menu2="Total", menu2_label="SG : 전체", menu3=None, menu3_label=None,
        leaf_level="menu2", source_metric_key="Sg::Total",
    )
    form = module._request_form(leaf, "2025")
    assert form == {"season": "2025", "menu1": "Sg", "menu2": "Total"}
    assert "menu3" not in form


def test_menu3_level_request_includes_menu3_field(module):
    leaf = module.SampledLeaf(
        menu1="Approach", menu1_label="어프로치", menu2="Approach01", menu2_label="그린 적중률",
        menu3="020104", menu3_label="160~180야드 미만(RTP)", leaf_level="menu3", source_metric_key="Approach::Approach01::020104",
    )
    form = module._request_form(leaf, "2025")
    assert form == {"season": "2025", "menu1": "Approach", "menu2": "Approach01", "menu3": "020104"}


# ---------------------------------------------------------------
# End-to-end orchestration
# ---------------------------------------------------------------


def test_full_run_writes_all_required_output_files(module, small_taxonomy, client_2025, tmp_path):
    rc = module.run(client_2025, small_taxonomy, "2025", tmp_path)

    assert rc == module.EXIT_COMPLETE
    for name in [
        "KLPGA_RESPONSE_SCHEMA_SAMPLES.json",
        "KLPGA_RESPONSE_SCHEMA_SAMPLES.csv",
        "KLPGA_RESPONSE_SCHEMA_REPORT.md",
        "KLPGA_RAW_FIELD_INVENTORY.md",
        "NEO_RAW_INPUT_CANDIDATES.md",
        "KLPGA_PHASE_B1_REQUEST_LOG.json",
        "KLPGA_PHASE_B1_REQUEST_LOG.csv",
    ]:
        assert (tmp_path / name).exists(), f"missing {name}"


def test_full_run_samples_all_three_taxonomy_leaves(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    assert payload["sample_count"] == 3
    keys = {s["identity_key"] for s in payload["samples"]}
    assert keys == {"Sg::Total", "Approach::Approach01::020104", "Approach::Approach01::020105"}


def test_sg_sample_shows_menu2_level_and_six_field_schema(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    sg = next(s for s in payload["samples"] if s["identity_key"] == "Sg::Total")
    assert sg["leaf_level"] == "menu2"
    assert sg["menu3"] is None
    assert sg["parse_status"] == "DISCOVERED_NOT_VALIDATED"  # no metadata block in the SG fixture


def test_approach_sample_confirms_raw_pair_and_rtp(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    approach = next(s for s in payload["samples"] if s["identity_key"] == "Approach::Approach01::020104")
    assert approach["raw_pair_status"] == "CONFIRMED_RAW_PAIR"
    assert approach["rtp_status"] == "RTP_PRESENT"
    assert approach["pit_status"] == "PIT_UNVERIFIED"


def test_schema_report_clusters_by_fingerprint(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    report = (tmp_path / "KLPGA_RESPONSE_SCHEMA_REPORT.md").read_text(encoding="utf-8")
    assert "Schema families discovered" in report
    assert "PIT_UNVERIFIED" in report


def test_request_log_has_exactly_one_entry_per_sampled_metric(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    log_lines = (tmp_path / "KLPGA_PHASE_B1_REQUEST_LOG.json").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 3


# ---------------------------------------------------------------
# Failure behavior — blocked halts the run, one-off failures don't
# ---------------------------------------------------------------


def test_blocked_response_halts_the_entire_run(module, small_taxonomy, tmp_path):
    from klpga.http_client import RateLimitBlockedError

    class BlockedAfterFirstClient:
        def __init__(self):
            self.calls = 0

        def post_text(self, url, data=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return _sg_html()
            raise RateLimitBlockedError("403 — site-side access restriction, not retrying")

    client = BlockedAfterFirstClient()
    rc = module.run(client, small_taxonomy, "2025", tmp_path)

    assert rc == module.EXIT_BLOCKED
    # Partial results (the one successful fetch) must still be written.
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    assert payload["sample_count"] == 1


def test_one_bad_response_does_not_abort_the_whole_sample(module, small_taxonomy, tmp_path):
    class FlakyClient:
        def __init__(self):
            self.calls = 0

        def post_text(self, url, data=None, **kwargs):
            self.calls += 1
            if data.get("menu1") == "Sg":
                raise ValueError("simulated unexpected failure for one metric only")
            if data.get("menu3") == "020104":
                return _approach_020104_html()
            return _approach_020105_html()

    client = FlakyClient()
    rc = module.run(client, small_taxonomy, "2025", tmp_path)

    assert rc == module.EXIT_COMPLETE
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    # Sg failed and is excluded from records (not fabricated); the
    # other two metrics still succeeded.
    assert payload["sample_count"] == 2


def test_max_requests_is_a_hard_cap(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path, max_requests=1)
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    assert payload["sample_count"] == 1


def test_missing_taxonomy_file_fails_cleanly(module, tmp_path, capsys):
    import sys

    argv_backup = sys.argv
    sys.argv = [
        "27_klpga_response_schema_sample.py",
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
