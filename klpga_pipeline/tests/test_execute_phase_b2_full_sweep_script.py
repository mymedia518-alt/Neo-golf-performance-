"""Tests for scripts/29_execute_phase_b2_full_sweep.py — fully
offline, FakeClient pattern matching scripts/27's own test file. No
network access, no live requests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "29_execute_phase_b2_full_sweep.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("execute_phase_b2_full_sweep_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _entry(menu1, menu2, menu3, leaf_level, label):
    identity_key = f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else "")
    return {
        "menu1": menu1,
        "menu2": menu2,
        "menu3": menu3,
        "leaf_level": leaf_level,
        "identity_key": identity_key,
        "label": label,
        "node_type": "REQUESTABLE_METRIC_LEAF",
        "evidence_source": identity_key,
    }


_EMPTY_HTML = "<html><body><table><thead><tr><th>없음</th></tr></thead><tbody></tbody></table></body></html>"


def _sg_family_plan(n: int) -> list[dict]:
    """n entries, all menu1="Sg" — deliberately exceeds Phase B1's
    select_representative_sample_from_canonical_plan per_family_cap
    (4), to prove the B2 full sweep is not subject to it."""
    entries = [_entry("Sg", "Total", None, "menu2", "SG : 전체")]
    for i in range(n - 1):
        entries.append(_entry("Sg", f"Sub{i}", f"00000{i}", "menu3", f"라벨{i}"))
    return entries


class GenericSuccessClient:
    """Returns the same generic, always-parses-EMPTY response for
    every request, and records the request order — used for tests
    that only care about count/order/plan behavior, not parsed
    content."""

    def __init__(self):
        self.requests = []

    def post_text(self, url, data=None, **kwargs):
        self.requests.append(dict(data))
        return _EMPTY_HTML


class NeverCalledClient:
    """Fails the test immediately if post_text is ever invoked —
    used to prove a dry run (or a resume-skip) makes ZERO HTTP
    requests."""

    def post_text(self, url, data=None, **kwargs):
        raise AssertionError(f"post_text must never be called, but was called with {data}")


class AlwaysBlockedClient:
    def __init__(self, block_after: int = 0):
        self.calls = 0
        self.block_after = block_after

    def post_text(self, url, data=None, **kwargs):
        self.calls += 1
        if self.calls > self.block_after:
            from klpga.http_client import RateLimitBlockedError

            raise RateLimitBlockedError("403 — site-side access restriction, not retrying")
        return _EMPTY_HTML


class AlwaysFailsClient:
    def __init__(self):
        self.calls = 0

    def post_text(self, url, data=None, **kwargs):
        self.calls += 1
        raise ValueError("simulated HTTP-layer failure")


class ScriptedClient:
    """Returns EMPTY html on "success" calls and raises ValueError on
    "fail" calls, per a scripted list of outcomes consumed in order —
    used to test the consecutive-failure circuit breaker's reset
    behavior precisely."""

    def __init__(self, outcomes: list[str]):
        self.outcomes = list(outcomes)
        self.calls = 0

    def post_text(self, url, data=None, **kwargs):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if outcome == "fail":
            raise ValueError("simulated HTTP-layer failure")
        return _EMPTY_HTML


class KeyedClient:
    """Maps identity_key -> outcome ("success" or "fail"). Used for
    resume-skip / resume-rerunnable tests where different runs need
    different per-identity behavior."""

    def __init__(self, outcomes: dict[str, str]):
        self.outcomes = outcomes
        self.calls = []

    def post_text(self, url, data=None, **kwargs):
        menu1, menu2, menu3 = data.get("menu1"), data.get("menu2"), data.get("menu3")
        key = f"{menu1}::{menu2}" + (f"::{menu3}" if menu3 else "")
        self.calls.append(key)
        outcome = self.outcomes.get(key, "success")
        if outcome == "fail":
            raise ValueError(f"simulated HTTP-layer failure for {key}")
        return _EMPTY_HTML


# ---------------------------------------------------------------
# 1. Dry run makes zero HTTP requests
# ---------------------------------------------------------------


def test_dry_run_makes_zero_http_requests_and_writes_nothing(module, tmp_path, capsys):
    plan = _sg_family_plan(6)
    client = NeverCalledClient()
    rc = module.run(client, plan, "2025", tmp_path / "phase_b2", dry_run=True)
    assert rc == module.EXIT_COMPLETE
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "Zero HTTP requests made" in out
    assert not (tmp_path / "phase_b2").exists()


# ---------------------------------------------------------------
# 2. Full canonical iteration is not subject to the B1 family cap
# ---------------------------------------------------------------


def test_full_sweep_not_subject_to_family_cap(module, tmp_path):
    plan = _sg_family_plan(6)  # 1 more than B1's per_family_cap of 4
    client = GenericSuccessClient()
    rc = module.run(client, plan, "2025", tmp_path / "phase_b2")
    assert rc == module.EXIT_COMPLETE
    assert len(client.requests) == 6

    checkpoint = json.loads((tmp_path / "phase_b2" / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    assert len(checkpoint) == 6
    assert all(entry["completion_status"] == "SUCCESS" for entry in checkpoint.values())


# ---------------------------------------------------------------
# 3. Deterministic ordering
# ---------------------------------------------------------------


def test_full_sweep_requests_in_deterministic_menu_order(module, tmp_path):
    plan = [
        _entry("Tee", "Tee02", "010102", "menu3", "라벨"),
        _entry("Sg", "Total", None, "menu2", "SG : 전체"),
        _entry("Tee", "Tee01", "010101", "menu3", "라벨"),
        _entry("Approach", "Approach01", "020101", "menu3", "라벨"),
    ]
    client = GenericSuccessClient()
    module.run(client, plan, "2025", tmp_path / "phase_b2")
    order = [(r.get("menu1"), r.get("menu2"), r.get("menu3")) for r in client.requests]
    assert order == [
        ("Approach", "Approach01", "020101"),
        ("Sg", "Total", None),
        ("Tee", "Tee01", "010101"),
        ("Tee", "Tee02", "010102"),
    ]


# ---------------------------------------------------------------
# 4. --max-requests works
# ---------------------------------------------------------------


def test_max_requests_caps_live_requests_this_invocation(module, tmp_path):
    plan = _sg_family_plan(6)
    client = GenericSuccessClient()
    rc = module.run(client, plan, "2025", tmp_path / "phase_b2", max_requests=2)
    assert rc == module.EXIT_COMPLETE
    assert len(client.requests) == 2
    checkpoint = json.loads((tmp_path / "phase_b2" / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    assert len(checkpoint) == 2


# ---------------------------------------------------------------
# 5. Completed identities are skipped on resume
# ---------------------------------------------------------------


def test_completed_identities_are_skipped_on_resume(module, tmp_path):
    plan = _sg_family_plan(3)
    out_dir = tmp_path / "phase_b2"

    first_client = GenericSuccessClient()
    rc1 = module.run(first_client, plan, "2025", out_dir)
    assert rc1 == module.EXIT_COMPLETE
    assert len(first_client.requests) == 3

    # A second run against the SAME out_dir/checkpoint must not call
    # post_text at all — every identity is already SUCCESS.
    second_client = NeverCalledClient()
    rc2 = module.run(second_client, plan, "2025", out_dir)
    assert rc2 == module.EXIT_COMPLETE


# ---------------------------------------------------------------
# 6. Incomplete/failed identities remain rerunnable
# ---------------------------------------------------------------


def test_failed_identity_remains_visible_and_is_retried_on_resume(module, tmp_path):
    plan = _sg_family_plan(3)  # Sg::Total, Sg::Sub0::000000, Sg::Sub1::000001
    out_dir = tmp_path / "phase_b2"

    first_client = KeyedClient({"Sg::Sub0::000000": "fail"})
    rc1 = module.run(first_client, plan, "2025", out_dir)
    assert rc1 == module.EXIT_COMPLETE  # HTTP failures don't halt the sweep

    checkpoint = json.loads((out_dir / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    assert checkpoint["Sg::Sub0::000000"]["completion_status"] == "HTTP_FAILURE"
    assert checkpoint["Sg::Total"]["completion_status"] == "SUCCESS"
    assert checkpoint["Sg::Sub1::000001"]["completion_status"] == "SUCCESS"

    second_client = KeyedClient({})  # everything succeeds this time
    rc2 = module.run(second_client, plan, "2025", out_dir)
    assert rc2 == module.EXIT_COMPLETE
    # Only the previously-failed identity should have been retried.
    assert second_client.calls == ["Sg::Sub0::000000"]

    checkpoint2 = json.loads((out_dir / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    assert checkpoint2["Sg::Sub0::000000"]["completion_status"] == "SUCCESS"


# ---------------------------------------------------------------
# 7. 401/403/429 immediately abort
# ---------------------------------------------------------------


def test_rate_limit_block_immediately_halts_the_entire_sweep(module, tmp_path):
    plan = _sg_family_plan(6)
    client = AlwaysBlockedClient(block_after=2)  # first 2 succeed, 3rd blocks
    rc = module.run(client, plan, "2025", tmp_path / "phase_b2")
    assert rc == module.EXIT_BLOCKED
    assert client.calls == 3  # never retried, never bypassed, no more attempts after the block

    checkpoint = json.loads((tmp_path / "phase_b2" / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    assert len(checkpoint) == 2  # only the 2 successful-before-block identities recorded


# ---------------------------------------------------------------
# 8. Five consecutive HTTP failures trip the circuit breaker
# ---------------------------------------------------------------


def test_five_consecutive_http_failures_trips_circuit_breaker(module, tmp_path):
    plan = _sg_family_plan(8)
    client = AlwaysFailsClient()
    rc = module.run(client, plan, "2025", tmp_path / "phase_b2", consecutive_failure_limit=5)
    assert rc == module.EXIT_CIRCUIT_BREAKER_TRIPPED
    assert client.calls == 5  # stops immediately at the 5th consecutive failure, not all 8

    checkpoint = json.loads((tmp_path / "phase_b2" / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    assert len(checkpoint) == 5
    assert all(entry["completion_status"] == "HTTP_FAILURE" for entry in checkpoint.values())


# ---------------------------------------------------------------
# 9. Successful response resets the consecutive-failure counter
# ---------------------------------------------------------------


def test_successful_response_resets_consecutive_failure_counter(module, tmp_path):
    """fail, fail, SUCCESS, fail, fail — max consecutive run is 2,
    never reaching --consecutive-failure-limit=3. A buggy
    non-resetting (cumulative total) implementation would incorrectly
    trip after the 3rd total failure and never attempt the 5th leaf."""
    plan = _sg_family_plan(5)
    client = ScriptedClient(["fail", "fail", "success", "fail", "fail"])
    rc = module.run(client, plan, "2025", tmp_path / "phase_b2", consecutive_failure_limit=3)
    assert rc == module.EXIT_COMPLETE
    assert client.calls == 5  # every leaf was attempted — breaker never tripped

    checkpoint = json.loads((tmp_path / "phase_b2" / "KLPGA_PHASE_B2_CHECKPOINT.json").read_text(encoding="utf-8"))
    statuses = [entry["completion_status"] for entry in checkpoint.values()]
    assert statuses.count("SUCCESS") == 1
    assert statuses.count("HTTP_FAILURE") == 4


# ---------------------------------------------------------------
# 10. B1 artifacts are never modified
# ---------------------------------------------------------------


def test_b1_artifacts_are_never_modified(module, tmp_path):
    b1_dir = tmp_path / "docs" / "discovery"
    b1_dir.mkdir(parents=True)
    b1_samples_path = b1_dir / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json"
    original_content = '{"sample_count": 999, "note": "B1 artifact, must never be touched by B2"}'
    b1_samples_path.write_text(original_content, encoding="utf-8")
    original_mtime = b1_samples_path.stat().st_mtime_ns

    b2_out_dir = b1_dir / "phase_b2"
    plan = [_entry("Sg", "Total", None, "menu2", "SG : 전체")]
    client = GenericSuccessClient()
    rc = module.run(client, plan, "2025", b2_out_dir)

    assert rc == module.EXIT_COMPLETE
    assert b1_samples_path.read_text(encoding="utf-8") == original_content
    assert b1_samples_path.stat().st_mtime_ns == original_mtime
    assert (b2_out_dir / "KLPGA_PHASE_B2_RESPONSE_SAMPLES.json").exists()
    # And the B2 output is a genuinely separate file, not the B1 one.
    assert b2_out_dir != b1_dir


# ---------------------------------------------------------------
# Output artifacts reflect the full checkpoint, not just this run
# ---------------------------------------------------------------


def test_output_samples_json_reflects_cumulative_checkpoint_across_runs(module, tmp_path):
    plan = _sg_family_plan(3)
    out_dir = tmp_path / "phase_b2"

    module.run(GenericSuccessClient(), plan, "2025", out_dir, max_requests=1)
    payload1 = json.loads((out_dir / "KLPGA_PHASE_B2_RESPONSE_SAMPLES.json").read_text(encoding="utf-8"))
    assert payload1["sample_count"] == 1

    module.run(GenericSuccessClient(), plan, "2025", out_dir)
    payload2 = json.loads((out_dir / "KLPGA_PHASE_B2_RESPONSE_SAMPLES.json").read_text(encoding="utf-8"))
    assert payload2["sample_count"] == 3
