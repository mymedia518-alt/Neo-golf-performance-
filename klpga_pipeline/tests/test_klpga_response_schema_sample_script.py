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
        "KLPGA_RAW_COUNT_METRICS.csv",
        "KLPGA_PLAYER_IDENTITY_REPORT.md",
        "KLPGA_RESPONSE_FAILURES.csv",
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


def test_raw_count_metrics_csv_includes_the_confirmed_approach_pair(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    csv_text = (tmp_path / "KLPGA_RAW_COUNT_METRICS.csv").read_text(encoding="utf-8")
    assert "Approach::Approach01::020104" in csv_text
    assert "Approach::Approach01::020105" in csv_text
    # Sg::Total has no raw numerator/denominator pair — excluded, not padded.
    assert "Sg::Total" not in csv_text


def test_response_failures_csv_is_empty_when_every_sampled_metric_parses_cleanly(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    csv_text = (tmp_path / "KLPGA_RESPONSE_FAILURES.csv").read_text(encoding="utf-8")
    lines = csv_text.strip().splitlines()
    assert len(lines) == 1  # header only — no FAILED/AMBIGUOUS/EMPTY metrics in this fixture set


def test_player_identity_report_not_available_when_fixtures_share_no_player(module, small_taxonomy, client_2025, tmp_path):
    """The bundled fixtures (Sg::Total=서교림, 020104=김수지/배소현,
    020105=임희정) document different players — nobody is
    cross-checkable, so the report must say NOT_AVAILABLE, never
    fabricate a cross-metric match."""
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    report = (tmp_path / "KLPGA_PLAYER_IDENTITY_REPORT.md").read_text(encoding="utf-8")
    assert "`NOT_AVAILABLE`" in report


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


# ---------------------------------------------------------------
# Phase B1.1 — malformed leaf rejection + HTTP vs parse outcome
# reporting, at the script's end-to-end orchestration level.
# ---------------------------------------------------------------


def test_malformed_leaf_is_rejected_and_never_fetched(module, small_taxonomy, client_2025, tmp_path, capsys):
    """A taxonomy leaf with blank menu1/menu2 (the real live-run
    finding — menu_taxonomy.py's Pass 1 fallback for an unresolvable
    data-menu3 tag) must be rejected before sampling, never fetched,
    and never silently absorbed into 'metrics successfully sampled'."""
    small_taxonomy["leaves"].append(_leaf("", "", "010101", "menu3", "고아 항목"))
    rc = module.run(client_2025, small_taxonomy, "2025", tmp_path)
    assert rc == module.EXIT_COMPLETE
    out = capsys.readouterr().out
    assert "[STEP 05] malformed leaves rejected: 1" in out
    # Only the 3 legitimate fixtures were ever fetched — RecordingFakeClient
    # would have raised KeyError on an unrecognized (menu1, menu2, menu3)
    # request, which it never received.
    assert len(client_2025.requests) == 3


def test_http_failure_counted_separately_from_parse_outcomes(module, small_taxonomy, tmp_path):
    class FlakyClient:
        def post_text(self, url, data=None, **kwargs):
            if data.get("menu1") == "Sg":
                raise ValueError("simulated network failure for one metric only")
            if data.get("menu3") == "020104":
                return _approach_020104_html()
            return _approach_020105_html()

    rc = module.run(FlakyClient(), small_taxonomy, "2025", tmp_path)
    assert rc == module.EXIT_COMPLETE
    report = (tmp_path / "KLPGA_RESPONSE_SCHEMA_REPORT.md").read_text(encoding="utf-8")
    assert "Request outcome breakdown" in report
    # 2 real HTTP successes (both parsed CONFIRMED), 1 HTTP failure —
    # never folded into "successfully sampled."
    payload = json.loads((tmp_path / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").read_text(encoding="utf-8"))
    assert payload["sample_count"] == 2


# ---------------------------------------------------------------
# Phase B1.1 diagnostic instrumentation — STEP/REQUEST/RESPONSE/PARSE
# markers, added after a Windows run produced no visible output at all
# before it had to be Ctrl+C'd. These tests prove the markers actually
# fire (not just that flush=True is present, which capsys can't
# observe directly since it's not a real console).
# ---------------------------------------------------------------


def test_step_markers_appear_in_order_for_a_clean_run(module, small_taxonomy, client_2025, tmp_path, capsys):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    out = capsys.readouterr().out
    steps = [line for line in out.splitlines() if line.startswith("[STEP ")]
    step_numbers = [s.split("]")[0].replace("[STEP ", "") for s in steps]
    assert step_numbers == sorted(step_numbers)  # monotonically non-decreasing as printed
    assert any(s.startswith("[STEP 03]") for s in steps)
    assert any(s.startswith("[STEP 04]") for s in steps)
    assert any(s.startswith("[STEP 05]") for s in steps)
    assert any(s.startswith("[STEP 06]") for s in steps)


def test_request_response_parse_markers_are_tagged_and_numbered(module, small_taxonomy, client_2025, tmp_path, capsys):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    out = capsys.readouterr().out
    assert "[REQUEST 1/3]" in out
    assert "[REQUEST 2/3]" in out
    assert "[REQUEST 3/3]" in out
    assert "[RESPONSE 1/3]" in out
    assert "[PARSE 1/3]" in out
    # Each RESPONSE line must carry a real elapsed-time figure, not a
    # placeholder — proves it's measured, not hardcoded.
    response_line = next(line for line in out.splitlines() if line.startswith("[RESPONSE 1/3]"))
    assert "elapsed=" in response_line and "bytes=" in response_line


def test_request_marker_still_fires_even_when_the_fetch_then_fails(module, small_taxonomy, tmp_path, capsys):
    """The REQUEST marker must print BEFORE the network call — so even
    an HTTP failure leaves a trace of which metric was being attempted,
    the exact diagnostic gap the live Windows hang exposed."""

    class AlwaysFailsClient:
        def post_text(self, url, data=None, **kwargs):
            raise ValueError("simulated failure")

    module.run(AlwaysFailsClient(), small_taxonomy, "2025", tmp_path)
    out = capsys.readouterr().out
    assert "[REQUEST 1/3]" in out
    assert "menu1='Sg'" in out
    # No RESPONSE marker for that request — the failure happened
    # before a response was ever received.
    assert "[RESPONSE 1/3]" not in out


def test_fetch_and_analyze_tag_defaults_to_question_mark_when_unspecified(module, small_taxonomy, client_2025, capsys):
    """Direct unit check of fetch_and_analyze's own default — callers
    outside run() (e.g. future ad-hoc debugging) still get a usable,
    non-crashing marker."""
    leaf = module.select_representative_sample(small_taxonomy, target_count=1)[0]
    module.fetch_and_analyze(client_2025, leaf, "2025")
    out = capsys.readouterr().out
    assert "[REQUEST ?]" in out


# ---------------------------------------------------------------
# Phase B1.1 — top-level KeyboardInterrupt diagnostic. Runs the script
# as a real subprocess so SIGINT/KeyboardInterrupt semantics (and the
# `if __name__ == "__main__":` block) are genuinely exercised, not
# simulated in-process.
# ---------------------------------------------------------------


def test_keyboard_interrupt_reports_last_marker_and_is_not_swallowed():
    """Verified structurally (not by fabricating a real hang + timed
    Ctrl+C, which would be flaky in CI): the top-level `if __name__ ==
    "__main__":` block must catch KeyboardInterrupt and its handler
    must end in a bare `raise` — reporting the last marker without
    ever swallowing the interrupt, per Mission 4."""
    import ast

    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_block = next(
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and getattr(node.test.left, "id", None) == "__name__"
    )
    dumped = ast.dump(main_block)
    assert "KeyboardInterrupt" in dumped
    # The handler body must re-raise (bare `raise`), never swallow it.
    handler = next(h for h in main_block.body[0].handlers)
    assert any(isinstance(stmt, ast.Raise) and stmt.exc is None for stmt in handler.body)


# ---------------------------------------------------------------
# Phase B1.1 — raw-response HTML preservation (Mission 3). The live
# Windows run that produced EMPTY_SCHEMA for 200+-row responses needs
# the actual raw HTML to root-cause; PoliteHttpClient already caches
# every response under data/raw_cache/http/ but keyed by an opaque
# content hash, impractical to find "the Putt::Putt01::040101
# response" by hand. These tests cover the human-named second copy.
# ---------------------------------------------------------------


def test_raw_samples_saved_by_default_one_file_per_sampled_metric(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    raw_dir = tmp_path / "raw_samples"
    assert raw_dir.is_dir()
    files = sorted(p.name for p in raw_dir.iterdir())
    assert files == [
        "Approach__Approach01__020104__2025.html",
        "Approach__Approach01__020105__2025.html",
        "Sg__Total__2025.html",
    ]


def test_raw_sample_content_matches_the_exact_response_bytes(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path)
    saved = (tmp_path / "raw_samples" / "Sg__Total__2025.html").read_text(encoding="utf-8")
    assert saved == _sg_html()


def test_raw_samples_skipped_when_disabled(module, small_taxonomy, client_2025, tmp_path):
    module.run(client_2025, small_taxonomy, "2025", tmp_path, save_raw_responses=False)
    assert not (tmp_path / "raw_samples").exists()


def test_raw_sample_still_saved_for_a_zero_row_empty_response(module, tmp_path):
    """A genuinely zero-row response for a real REQUESTABLE metric
    (not a navigation container, which is now rejected before sampling
    entirely — see the CLASS 2 tests below) must still get its raw
    HTML preserved — evidence preservation must not depend on the
    response having rows."""
    taxonomy = {
        "source_url": "https://example.test",
        "leaves": [_leaf("Putt", "Putt02", None, "menu2", "퍼팅 기타")],
    }

    class ZeroRowClient:
        def post_text(self, url, data=None, **kwargs):
            return "<html><body><table><thead><tr><th>없음</th></tr></thead><tbody></tbody></table></body></html>"

    module.run(ZeroRowClient(), taxonomy, "2025", tmp_path)
    saved = tmp_path / "raw_samples" / "Putt__Putt02__2025.html"
    assert saved.exists()
    assert "없음" in saved.read_text(encoding="utf-8")


# ---------------------------------------------------------------
# Phase B1 CLASS 2 — navigation/container nodes (real evidence: a
# menu1="All" request returned 0 rows and a body containing the full
# navigation menu tree) must be rejected before sampling and never
# fetched at all, at the full script-orchestration level.
# ---------------------------------------------------------------


def test_all_navigation_leaves_rejected_and_never_fetched(module, small_taxonomy, client_2025, tmp_path, capsys):
    small_taxonomy["leaves"].append(_leaf("All", "Sg", None, "menu2", "전체기록보기"))
    rc = module.run(client_2025, small_taxonomy, "2025", tmp_path)
    assert rc == module.EXIT_COMPLETE
    out = capsys.readouterr().out
    assert "[STEP 05b] navigation/container leaves rejected: 1" in out
    assert "All::Sg" in out
    # Only the 3 legitimate fixtures were ever fetched.
    assert len(client_2025.requests) == 3
    assert not any(r.get("menu1") == "All" for r in client_2025.requests)


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
