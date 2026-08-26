"""Tests for scripts/32_bounded_missing_evidence_request_plan.py —
fully offline, no network access, no live requests: the `--live` mode
tested below is exercised against fake in-process client doubles that
never touch a socket, exactly like every other HTTP-adjacent test in
this project (see e.g. tests/test_execute_phase_b2_full_sweep_script.py)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from klpga.http_client import RateLimitBlockedError

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


# ---------------------------------------------------------------
# --live mode — fully offline, exercised against fake in-process
# client doubles (no socket ever touched). Reuses `_mixed_taxonomy`/
# `_write_raw_samples`/`_table_response_html` above: the only
# UNRESOLVED_INSUFFICIENT_EVIDENCE identity in that taxonomy is
# Putt::Putt09::040901 (labels "라벨A"/"라벨B", no raw sample written).
# ---------------------------------------------------------------


class _FakeClient:
    """Minimal stand-in for `PoliteHttpClient` — same `post_text`
    surface `record_fetch.fetch_and_analyze` actually calls, plus an
    optional `_cache_path` for exercising `_cache_live_distinction`.
    Never opens a socket; every response is a canned string or a
    raised exception, keyed by the exact identity_key the POST body
    (`data`) encodes."""

    def __init__(self, tmp_path, *, html_by_identity=None, raise_by_identity=None, precached_identities=None):
        self._cache_dir = tmp_path / "fake_client_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_by_identity = html_by_identity or {}
        self.raise_by_identity = raise_by_identity or {}
        self.calls: list[str] = []
        for key in precached_identities or []:
            self._cache_marker_path(key).write_text("{}", encoding="utf-8")

    @staticmethod
    def _identity_key_from_form(data: dict) -> str:
        menu1, menu2, menu3 = data.get("menu1"), data.get("menu2"), data.get("menu3")
        return f"{menu1}::{menu2}::{menu3}" if menu3 else f"{menu1}::{menu2}"

    def _cache_marker_path(self, identity_key: str) -> Path:
        return self._cache_dir / f"{identity_key.replace('::', '_')}.json"

    def _cache_path(self, url, params):
        data = (params or {}).get("data") or {}
        return self._cache_marker_path(self._identity_key_from_form(data))

    def post_text(self, url, data=None, use_cache=True, headers=None):
        key = self._identity_key_from_form(data or {})
        self.calls.append(key)
        if key in self.raise_by_identity:
            raise self.raise_by_identity[key]
        return self.html_by_identity.get(
            key,
            "<html><body><table><thead><tr></tr></thead><tbody></tbody></table></body></html>",
        )


class _FakeClientNoCacheIntrospection:
    """Same `post_text` surface as `_FakeClient` but deliberately has
    NO `_cache_path` — exercises the honest NOT_AVAILABLE fallback."""

    def __init__(self):
        self.calls: list[str] = []

    def post_text(self, url, data=None, use_cache=True, headers=None):
        key = _FakeClient._identity_key_from_form(data or {})
        self.calls.append(key)
        return "<html><body><table><thead><tr></tr></thead><tbody></tbody></table></body></html>"


def test_acquire_only_fires_for_the_insufficient_evidence_identity(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(
        tmp_path,
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert client.calls == ["Putt::Putt09::040901"]
    assert len(result["items"]) == 1
    assert result["items"][0]["identity_key"] == "Putt::Putt09::040901"
    assert result["items"][0]["http_outcome"] == "HTTP_SUCCESS"


def test_acquire_saves_raw_sample_and_records_parser_fields(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(
        tmp_path,
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    item = result["items"][0]
    expected_path = raw_dir / "Putt__Putt09__040901__2025.html"
    assert expected_path.exists()
    assert item["raw_sample_path"] == str(expected_path)
    assert item["response_size"] == expected_path.stat().st_size
    assert item["parse_status"] in ("CONFIRMED", "DISCOVERED_NOT_VALIDATED")
    assert item["player_row_count"] == 1
    assert item["missing_player_code"] == 1  # the fixture row carries no player_code source at all
    assert item["missing_player_name"] == 0
    assert item["cache_live_distinction"] == "LIVE_FETCH"


def test_acquire_never_touches_partial_or_resolved_groups(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(tmp_path)

    module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert "Sg::All" not in client.calls
    assert "Tee::Tee01::010101" not in client.calls


def test_acquire_hard_stops_on_rate_limit_and_skips_remaining(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    raw_dir.mkdir(parents=True)
    taxonomy = _mixed_taxonomy()
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨C"))
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨D"))

    client = _FakeClient(
        tmp_path,
        raise_by_identity={"Around::Around09::030901": RateLimitBlockedError("403 from example — blocked")},
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    # The plan is sorted alphabetically by identity_key, so
    # "Around::Around09::030901" is requested (and blocked) before
    # "Putt::Putt09::040901" is ever attempted at all.
    assert result["hard_stop"] is not None
    assert result["hard_stop"]["identity_key"] == "Around::Around09::030901"
    assert result["items"] == []
    assert client.calls == ["Around::Around09::030901"]
    skipped_reasons = {s["identity_key"]: s["reason"] for s in result["skipped"]}
    assert "hard safety stop" in skipped_reasons["Around::Around09::030901"]
    assert "not attempted" in skipped_reasons["Putt::Putt09::040901"]


def test_acquire_records_http_failure_and_continues_to_next_identity(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨C"))
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨D"))

    client = _FakeClient(
        tmp_path,
        raise_by_identity={"Around::Around09::030901": ConnectionError("simulated transient failure")},
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert result["hard_stop"] is None
    outcomes = {it["identity_key"]: it["http_outcome"] for it in result["items"]}
    assert outcomes["Around::Around09::030901"] == "HTTP_FAILURE"
    assert outcomes["Putt::Putt09::040901"] == "HTTP_SUCCESS"
    assert set(client.calls) == {"Around::Around09::030901", "Putt::Putt09::040901"}


def test_acquire_never_overwrites_evidence_that_already_exists_at_call_time(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    # Simulate the exact evidence file appearing right before this run —
    # the plan itself is built fresh inside acquire_missing_evidence, so
    # writing it here (before the call) is equivalent to "already there".
    existing_path = raw_dir / "Putt__Putt09__040901__2025.html"
    existing_path.write_text("<html><body>already here</body></html>", encoding="utf-8")

    client = _FakeClient(tmp_path)
    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert client.calls == []
    assert result["items"] == []
    assert existing_path.read_text(encoding="utf-8") == "<html><body>already here</body></html>"


def test_acquire_before_after_audit_counts_reflect_new_evidence(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(
        tmp_path,
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert result["before_counts"]["UNRESOLVED_INSUFFICIENT_EVIDENCE"] == 1
    assert result["after_counts"].get("UNRESOLVED_INSUFFICIENT_EVIDENCE", 0) == 0
    assert result["after_counts"]["total_unresolved"] < result["before_counts"]["total_unresolved"]


def test_cache_live_distinction_reports_not_available_without_cache_path_support(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClientNoCacheIntrospection()

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert result["items"][0]["cache_live_distinction"] == "NOT_AVAILABLE"


def test_cache_live_distinction_reports_cache_hit_when_precached(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(tmp_path, precached_identities=["Putt::Putt09::040901"])

    result = module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lambda msg: None)

    assert result["items"][0]["cache_live_distinction"] == "CACHE_HIT"


def test_run_live_prints_consolidated_report_sections_and_returns_complete(module, tmp_path, capsys):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(
        tmp_path,
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )

    rc = module.run_live(client, taxonomy, "2025", raw_dir)

    out = capsys.readouterr().out
    assert rc == module.EXIT_COMPLETE
    for section in (
        "=== EXECUTION SUMMARY ===",
        "=== HTTP / CACHE ===",
        "=== PARSER ===",
        "=== COLLISION AUDIT ===",
        "=== SKIPPED_ITEMS_REVIEW ===",
        "=== HARD_STOPS ===",
    ):
        assert section in out
    assert "EXPECTED_MISSING_EVIDENCE_IDENTITIES = 1" in out
    assert "HTTP_SUCCESS = 1" in out
    assert "UNRESOLVED_BEFORE = " in out
    assert "UNRESOLVED_AFTER = " in out


def test_run_live_returns_hard_stop_exit_code_on_block(module, tmp_path, capsys):
    raw_dir = tmp_path / "raw_samples"
    raw_dir.mkdir(parents=True)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(
        tmp_path,
        raise_by_identity={"Putt::Putt09::040901": RateLimitBlockedError("429 from example — blocked")},
    )

    rc = module.run_live(client, taxonomy, "2025", raw_dir)

    assert rc == module.EXIT_HARD_STOP


def test_main_live_and_dry_run_together_refused(module, tmp_path):
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
        "--dry-run",
        "--live",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_DRY_RUN_REQUIRED


def test_main_live_end_to_end_with_zero_missing_evidence_makes_no_real_client_error(module, tmp_path):
    """Uses the REAL `PoliteHttpClient` wiring (not a fake) — safe
    offline only because this taxonomy has no colliding identity_key
    groups at all, so the missing-evidence plan is empty and zero HTTP
    calls are ever made. Proves --live's argument wiring and client
    construction work without needing a fake for this one path."""
    import sys

    taxonomy = {
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
        "--cache-dir",
        str(tmp_path / "http_cache"),
        "--live",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE


# ---------------------------------------------------------------
# PROGRESS lines — `acquire_missing_evidence` (now in `klpga.discovery.
# missing_evidence_acquisition`, re-exported here) emits one
# `PROGRESS [i/N] | identity_key | CACHE/LIVE | HTTP status | PARSE
# status | SAVED/SKIPPED` line per identity as it completes, purely as
# an observability addition — no collection/request/parser behavior
# changes. Reuses `_mixed_taxonomy`/`_write_raw_samples`/`_table_
# response_html`/`_FakeClient`/`_leaf` from above.
# ---------------------------------------------------------------


def test_progress_line_emitted_on_http_success(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(
        tmp_path,
        html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])},
    )
    lines = []
    module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lines.append)

    progress_lines = [l for l in lines if l.startswith("PROGRESS ")]
    assert len(progress_lines) == 1
    assert progress_lines[0] == "PROGRESS [1/1] | Putt::Putt09::040901 | LIVE | SUCCESS | DISCOVERED_NOT_VALIDATED | SAVED"


def test_progress_line_shows_cache_short_label_on_cache_hit(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(tmp_path, precached_identities=["Putt::Putt09::040901"])
    lines = []
    module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lines.append)

    progress_line = next(l for l in lines if l.startswith("PROGRESS "))
    assert " | CACHE | " in progress_line


def test_progress_line_emitted_on_http_failure(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(tmp_path, raise_by_identity={"Putt::Putt09::040901": ConnectionError("boom")})
    lines = []
    module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lines.append)

    progress_line = next(l for l in lines if l.startswith("PROGRESS "))
    assert progress_line == "PROGRESS [1/1] | Putt::Putt09::040901 | LIVE | FAILURE | N/A | SKIPPED"


def test_progress_line_emitted_on_hard_stop_and_queued_skip(module, tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨C"))
    taxonomy["leaves"].append(_leaf("Around", "Around09", "030901", "menu3", "라벨D"))
    client = _FakeClient(
        tmp_path, raise_by_identity={"Around::Around09::030901": RateLimitBlockedError("429 blocked")}
    )
    lines = []
    module.acquire_missing_evidence(client, taxonomy, "2025", raw_dir, log=lines.append)

    progress_lines = [l for l in lines if l.startswith("PROGRESS ")]
    assert progress_lines == [
        "PROGRESS [1/2] | Around::Around09::030901 | LIVE | BLOCKED | N/A | SKIPPED",
        "PROGRESS [2/2] | Putt::Putt09::040901 | N/A | NOT_ATTEMPTED | N/A | SKIPPED",
    ]
