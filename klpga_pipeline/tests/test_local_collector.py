"""Tests for src/klpga/discovery/local_collector.py — fully offline.
`--live`-equivalent paths are exercised against a fake in-process
client double that never touches a socket, exactly like
tests/test_bounded_missing_evidence_request_plan_script.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.discovery import local_collector as lc
from klpga.discovery.b2_checkpoint import load_checkpoint
from klpga.http_client import RateLimitBlockedError


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
    """One resolved group (Sg::All — has a raw sample, empty shared
    response), one PARTIAL group (Tee::Tee01::010101 — has a raw
    sample, one label doesn't match), one INSUFFICIENT_EVIDENCE group
    (Putt::Putt09::040901 — no raw sample at all). Same shape used
    throughout tests/test_bounded_missing_evidence_request_plan_script.py."""
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


class _FakeClient:
    """Minimal stand-in for `PoliteHttpClient` — same `post_text`
    surface `record_fetch.fetch_and_analyze` calls. Never opens a
    socket; every response is a canned string or a raised exception,
    keyed by the identity_key the POST body (`data`) encodes."""

    def __init__(self, *, html_by_identity=None, raise_by_identity=None):
        self.html_by_identity = html_by_identity or {}
        self.raise_by_identity = raise_by_identity or {}
        self.calls: list[str] = []

    @staticmethod
    def _identity_key_from_form(data: dict) -> str:
        menu1, menu2, menu3 = data.get("menu1"), data.get("menu2"), data.get("menu3")
        return f"{menu1}::{menu2}::{menu3}" if menu3 else f"{menu1}::{menu2}"

    def post_text(self, url, data=None, use_cache=True, headers=None):
        key = self._identity_key_from_form(data or {})
        self.calls.append(key)
        if key in self.raise_by_identity:
            raise self.raise_by_identity[key]
        return self.html_by_identity.get(
            key,
            "<html><body><table><thead><tr></tr></thead><tbody></tbody></table></body></html>",
        )


# ---------------------------------------------------------------
# Skip queue persistence
# ---------------------------------------------------------------


def test_load_skip_queue_missing_file_returns_empty(tmp_path):
    assert lc.load_skip_queue(tmp_path / "does_not_exist.json") == []


def test_skip_queue_write_and_load_roundtrip(tmp_path):
    path = tmp_path / "skip_queue" / "SKIP_QUEUE.json"
    entries = [{"tournament": None, "identity_key": "Putt::Putt09::040901", "stage": "acquisition"}]
    lc.write_skip_queue_atomic(path, entries)
    assert lc.load_skip_queue(path) == entries


def test_merge_skip_queue_entries_dedups_by_identity_and_stage(tmp_path):
    existing = [
        {
            "tournament": None,
            "identity_key": "A::B::C",
            "metric": "라벨",
            "stage": "acquisition",
            "reason": "old reason",
            "evidence_path": None,
            "recommended_action": "old action",
            "first_seen": "2026-01-01T00:00:00+00:00",
            "last_seen": "2026-01-01T00:00:00+00:00",
        }
    ]
    new_entries = [
        {
            "tournament": None,
            "identity_key": "A::B::C",
            "metric": "라벨",
            "stage": "acquisition",
            "reason": "new reason",
            "evidence_path": None,
            "recommended_action": "new action",
        }
    ]
    merged = lc.merge_skip_queue_entries(existing, new_entries, timestamp="2026-02-01T00:00:00+00:00")
    assert len(merged) == 1
    assert merged[0]["reason"] == "new reason"
    assert merged[0]["first_seen"] == "2026-01-01T00:00:00+00:00"  # preserved
    assert merged[0]["last_seen"] == "2026-02-01T00:00:00+00:00"  # updated


def test_merge_skip_queue_entries_preserves_untouched_rows(tmp_path):
    existing = [
        {
            "tournament": None,
            "identity_key": "Untouched::X::Y",
            "metric": None,
            "stage": "acquisition",
            "reason": "still open",
            "evidence_path": None,
            "recommended_action": "review",
            "first_seen": "2026-01-01T00:00:00+00:00",
            "last_seen": "2026-01-01T00:00:00+00:00",
        }
    ]
    merged = lc.merge_skip_queue_entries(existing, [], timestamp="2026-02-01T00:00:00+00:00")
    assert merged == existing


def test_merge_skip_queue_entries_adds_genuinely_new_rows(tmp_path):
    merged = lc.merge_skip_queue_entries(
        [],
        [
            {
                "tournament": None,
                "identity_key": "New::X::Y",
                "metric": None,
                "stage": "http_failure",
                "reason": "boom",
                "evidence_path": None,
                "recommended_action": "retry",
            }
        ],
        timestamp="2026-02-01T00:00:00+00:00",
    )
    assert len(merged) == 1
    assert merged[0]["first_seen"] == merged[0]["last_seen"] == "2026-02-01T00:00:00+00:00"


def test_build_skip_queue_entries_covers_skipped_and_http_failure_items():
    plan = [{"identity_key": "Putt::Putt09::040901", "label": "라벨A"}, {"identity_key": "Putt::Putt09::040901", "label": "라벨B"}]
    acquisition_result = {
        "skipped": [{"identity_key": "Around::X::Y", "stage": "acquisition", "reason": "hard safety stop: 429"}],
        "items": [
            {
                "identity_key": "Putt::Putt09::040901",
                "http_outcome": "HTTP_FAILURE",
                "error": "ConnectionError: boom",
            },
            {"identity_key": "Other::A::B", "http_outcome": "HTTP_SUCCESS"},
        ],
    }
    entries = lc.build_skip_queue_entries(acquisition_result, plan)
    keys = {(e["identity_key"], e["stage"]) for e in entries}
    assert ("Around::X::Y", "acquisition") in keys
    assert ("Putt::Putt09::040901", "http_failure") in keys
    assert ("Other::A::B", "http_failure") not in keys  # HTTP_SUCCESS items never go to the skip queue

    putt_entry = next(e for e in entries if e["identity_key"] == "Putt::Putt09::040901")
    assert putt_entry["metric"] == "라벨A | 라벨B"
    assert "retry" in putt_entry["recommended_action"].lower() or "re-run" in putt_entry["recommended_action"].lower()


# ---------------------------------------------------------------
# run_local_collection — the orchestration entry point
# ---------------------------------------------------------------


def test_preview_makes_zero_http_calls_and_writes_report(tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    report_path = tmp_path / "out" / "REPORT.md"

    exit_code, report = lc.run_local_collection(
        None,
        taxonomy,
        "2025",
        raw_samples_dir=raw_dir,
        checkpoint_path=tmp_path / "out" / "CHECKPOINT.json",
        skip_queue_path=tmp_path / "out" / "SKIP_QUEUE.json",
        report_path=report_path,
        live=False,
        log=lambda msg: None,
    )

    assert exit_code == lc.EXIT_COMPLETE
    assert report.live is False
    assert report.metrics_expected == 1
    assert report.http_requests_attempted == 0
    assert report_path.exists()
    assert "LOCAL FAILURE" not in report_path.read_text(encoding="utf-8")  # no crash-y placeholder text


def test_live_acquires_writes_checkpoint_and_skip_queue(tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])})
    checkpoint_path = tmp_path / "out" / "CHECKPOINT.json"
    skip_queue_path = tmp_path / "out" / "SKIP_QUEUE.json"

    exit_code, report = lc.run_local_collection(
        client,
        taxonomy,
        "2025",
        raw_samples_dir=raw_dir,
        checkpoint_path=checkpoint_path,
        skip_queue_path=skip_queue_path,
        report_path=tmp_path / "out" / "REPORT.md",
        live=True,
        log=lambda msg: None,
    )

    assert exit_code == lc.EXIT_COMPLETE
    assert client.calls == ["Putt::Putt09::040901"]
    assert report.http_success == 1
    assert report.metrics_completed_cumulative == 1

    checkpoint = load_checkpoint(checkpoint_path)
    assert "Putt::Putt09::040901" in checkpoint
    assert checkpoint["Putt::Putt09::040901"].is_complete

    skip_queue = json.loads(skip_queue_path.read_text(encoding="utf-8"))
    assert skip_queue == []  # nothing failed this run


def test_second_run_is_idempotent_and_makes_no_new_requests(tmp_path):
    """Resumability/idempotency: once the raw evidence file exists,
    re-running never re-requests that identity — the audit's own
    fresh existence check is what gates requests, not the checkpoint."""
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    checkpoint_path = tmp_path / "out" / "CHECKPOINT.json"
    skip_queue_path = tmp_path / "out" / "SKIP_QUEUE.json"
    client1 = _FakeClient(html_by_identity={"Putt::Putt09::040901": _table_response_html(["순위", "선수명", "라벨A", "라벨B"])})

    lc.run_local_collection(
        client1, taxonomy, "2025", raw_samples_dir=raw_dir, checkpoint_path=checkpoint_path,
        skip_queue_path=skip_queue_path, report_path=tmp_path / "out" / "REPORT.md", live=True, log=lambda m: None,
    )

    client2 = _FakeClient()  # would raise KeyError-free empty response if called — we just assert zero calls
    exit_code, report = lc.run_local_collection(
        client2, taxonomy, "2025", raw_samples_dir=raw_dir, checkpoint_path=checkpoint_path,
        skip_queue_path=skip_queue_path, report_path=tmp_path / "out" / "REPORT.md", live=True, log=lambda m: None,
    )

    assert client2.calls == []
    assert exit_code == lc.EXIT_COMPLETE
    assert report.metrics_completed_cumulative == 1  # carried over from the checkpoint
    assert report.http_success == 0  # nothing new this run


def test_hard_stop_still_writes_report_and_returns_hard_stop_exit_code(tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(raise_by_identity={"Putt::Putt09::040901": RateLimitBlockedError("429 blocked")})
    report_path = tmp_path / "out" / "REPORT.md"

    exit_code, report = lc.run_local_collection(
        client, taxonomy, "2025", raw_samples_dir=raw_dir,
        checkpoint_path=tmp_path / "out" / "CHECKPOINT.json",
        skip_queue_path=tmp_path / "out" / "SKIP_QUEUE.json",
        report_path=report_path, live=True, log=lambda m: None,
    )

    assert exit_code == lc.EXIT_HARD_STOP
    assert report.hard_stop is not None
    assert report_path.exists()
    assert "hard stop" in report_path.read_text(encoding="utf-8").lower() or "429" in report_path.read_text(encoding="utf-8")


def test_hard_stop_records_the_blocked_identity_in_the_skip_queue(tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    client = _FakeClient(raise_by_identity={"Putt::Putt09::040901": RateLimitBlockedError("429 blocked")})
    skip_queue_path = tmp_path / "out" / "SKIP_QUEUE.json"

    lc.run_local_collection(
        client, taxonomy, "2025", raw_samples_dir=raw_dir,
        checkpoint_path=tmp_path / "out" / "CHECKPOINT.json",
        skip_queue_path=skip_queue_path,
        report_path=tmp_path / "out" / "REPORT.md", live=True, log=lambda m: None,
    )

    skip_queue = json.loads(skip_queue_path.read_text(encoding="utf-8"))
    assert any(e["identity_key"] == "Putt::Putt09::040901" for e in skip_queue)


def test_report_markdown_contains_required_observability_fields(tmp_path):
    raw_dir = tmp_path / "raw_samples"
    _write_raw_samples(raw_dir)
    taxonomy = _mixed_taxonomy()
    report_path = tmp_path / "out" / "REPORT.md"

    lc.run_local_collection(
        None, taxonomy, "2025", raw_samples_dir=raw_dir,
        checkpoint_path=tmp_path / "out" / "CHECKPOINT.json",
        skip_queue_path=tmp_path / "out" / "SKIP_QUEUE.json",
        report_path=report_path, live=False, log=lambda m: None,
    )

    text = report_path.read_text(encoding="utf-8")
    for required in (
        "Tournaments expected",
        "Metrics expected",
        "HTTP requests attempted",
        "Cache hits",
        "Raw responses saved",
        "Parse success",
        "Validation clean",
        "Skipped items",
        "Remaining missing evidence",
        "Completion percent",
        "Runtime",
    ):
        assert required in text, f"missing required report field: {required}"
