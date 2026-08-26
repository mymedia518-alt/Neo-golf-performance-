"""Round 11 — the LOCAL COLLECTOR: a single, resumable, idempotent
orchestrator wrapping this project's already-tested Phase B1/B2/
missing-evidence-acquisition components (`canonical_plan`,
`identity_key_audit`, `missing_evidence_acquisition`, `b2_checkpoint`)
behind ONE entry point (`scripts/run_klpga_collector.py`), so a user
running on a machine with real KLPGA network access never has to chain
separate discovery/acquisition/parser/validation/audit/reporting
commands by hand.

**Scope this round, per explicit instruction**: wraps ONLY the current
milestone — the bounded `UNRESOLVED_INSUFFICIENT_EVIDENCE` missing-
evidence acquisition (`missing_evidence_acquisition`'s own scope,
unchanged). It does NOT implement tournament-level enumeration,
player-level metric linking, or a normalized-database storage layer —
see `scripts/run_klpga_collector.py`'s module docstring for exactly
what is and is not built, so this is never mistaken for 100-tournament
readiness it does not have.

Never touches the production DB, `predictions/`, model/inference code,
the archive, or the public website — this is Phase A/B evidence
discovery tooling only, writing plain files (raw HTML, a JSON
checkpoint, a JSON skip queue, a Markdown report) under
`docs/discovery/local_collector/` by default.

Two independent, durable, on-disk persistence layers — both reused or
directly extended from already-tested project components, never
reinvented:

  1. `klpga.discovery.b2_checkpoint` (UNCHANGED — the exact same
     module `scripts/29`'s Phase B2 sweep already uses) — one
     `CheckpointEntry` per identity_key this collector has ever
     attempted, atomic writes, accumulates across every run against
     the same checkpoint path. This is the collector's own HISTORICAL
     LEDGER — it is NOT what decides which identities get requested
     this run. That gate lives entirely in the identity-key collision
     audit's own raw-file-existence check (already re-verified fresh,
     every run, by `missing_evidence_acquisition.build_missing_
     evidence_request_plan`/`acquire_missing_evidence`) — an identity
     is skipped the moment its raw sample file exists on disk,
     regardless of what the checkpoint says. This is deliberate: a
     checkpoint entry claiming SUCCESS is worthless as a skip signal
     if the underlying raw evidence file was ever deleted or moved —
     ground truth (the file) always wins over recorded state (the
     checkpoint), matching this project's standing "never silently
     trust a state file over ground truth" evidence discipline (see
     e.g. `scripts/32`'s own WARNING when `raw_sample_exists` reads
     unexpectedly `True`).

  2. A new persistent SKIP QUEUE (one JSON row per non-systemic
     failure — a `LOCAL FAILURE` under this round's own SKIP + LOG +
     CONTINUE operating rule) — `tournament`/`identity_key`/`metric`/
     `stage`/`reason`/`evidence_path`/`recommended_action`, plus
     `first_seen`/`last_seen` timestamps. Deduplicated by
     `(tournament, identity_key, stage)` across runs: a repeat failure
     for the same identity/stage updates the existing row in place
     rather than appending a duplicate, and a row this run's results
     didn't touch is left completely alone — the skip queue is a
     durable review log, not a per-run transient list.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from klpga.discovery.b2_checkpoint import (
    CheckpointEntry,
    load_checkpoint,
    mark_http_failure,
    mark_success,
    write_checkpoint_atomic,
)
from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.identity_key_audit import audit_identity_key_collisions
from klpga.discovery.missing_evidence_acquisition import (
    EXIT_HARD_STOP,
    _category_counts,
    acquire_missing_evidence,
    build_missing_evidence_request_plan,
)

EXIT_COMPLETE = 0
EXIT_TAXONOMY_LOAD_FAILED = 5

__all__ = [
    "EXIT_COMPLETE",
    "EXIT_HARD_STOP",
    "EXIT_TAXONOMY_LOAD_FAILED",
    "LocalCollectionReport",
    "load_skip_queue",
    "write_skip_queue_atomic",
    "merge_skip_queue_entries",
    "build_skip_queue_entries",
    "build_local_collection_report",
    "render_report_markdown",
    "run_local_collection",
]


# ---------------------------------------------------------------
# Persistent skip queue
# ---------------------------------------------------------------


def _skip_queue_key(entry: dict) -> tuple:
    return (entry.get("tournament"), entry.get("identity_key"), entry.get("stage"))


def load_skip_queue(path: Path) -> list[dict]:
    """Returns [] if the file doesn't exist yet — a missing skip queue
    is the normal first-run state, not an error."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_skip_queue_atomic(path: Path, entries: list[dict]) -> None:
    """Same atomic-write pattern as `b2_checkpoint.write_checkpoint_
    atomic` — a temp file in the SAME directory, then `os.replace`, so
    a crash mid-write never corrupts the previous, still-valid file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def merge_skip_queue_entries(existing: list[dict], new_entries: list[dict], *, timestamp: str) -> list[dict]:
    """Dedup-merges by `(tournament, identity_key, stage)`. A repeat
    failure for the same identity/stage updates `reason`/`evidence_
    path`/`recommended_action`/`last_seen` in place rather than
    appending a duplicate row; a genuinely new failure gets a fresh
    row with both `first_seen` and `last_seen` set to `timestamp`.
    Never drops an existing row this run's results didn't touch —
    resolved items are removed only by the caller re-deriving the
    active skip set fresh (this function never does that itself), so
    the file stays a durable review log across many runs."""
    by_key = {_skip_queue_key(e): dict(e) for e in existing}
    for new in new_entries:
        key = _skip_queue_key(new)
        if key in by_key:
            by_key[key]["reason"] = new["reason"]
            by_key[key]["evidence_path"] = new.get("evidence_path")
            by_key[key]["recommended_action"] = new.get("recommended_action")
            by_key[key]["last_seen"] = timestamp
        else:
            by_key[key] = {**new, "first_seen": timestamp, "last_seen": timestamp}
    return sorted(by_key.values(), key=lambda e: ((e.get("identity_key") or ""), (e.get("stage") or "")))


def _recommended_action_for(stage: str, reason: str) -> str:
    """Generic, evidence-grounded advice derived purely from the stage/
    reason `acquire_missing_evidence` already recorded — never a new
    inference about the underlying data itself."""
    if stage == "acquisition" and "hard safety stop" in reason:
        return "retry once klpga.co.kr access is confirmed unblocked (a 401/403/429 was encountered)"
    if stage == "acquisition" and "not attempted" in reason:
        return "re-run the collector — this identity was queued behind a hard stop and was never attempted"
    if stage == "pre_request_check":
        return "no action needed — evidence already exists; the next run will classify it correctly"
    if stage == "plan_lookup":
        return "investigate: no matching canonical plan entry for this identity_key (possible taxonomy/audit inconsistency)"
    if stage == "http_failure":
        return "re-run the collector — transient HTTP failure; PoliteHttpClient's own retry/backoff was already exhausted this attempt"
    return "review manually — unrecognized skip stage"


def _metric_label_for(plan: list[dict], identity_key: str) -> Optional[str]:
    labels = [e["label"] for e in plan if e.get("identity_key") == identity_key and e.get("label")]
    return " | ".join(labels) if labels else None


def build_skip_queue_entries(acquisition_result: dict, plan: list[dict]) -> list[dict]:
    """Translates one `acquire_missing_evidence` result's `skipped`
    list and any `HTTP_FAILURE` items into the richer, persistent
    skip-queue row shape. `tournament` is always `None` this round —
    this milestone operates at the metric-identity level, not the
    tournament level; a future tournament-scoped collector stage would
    populate it, without needing to change this row shape."""
    entries: list[dict] = []
    for s in acquisition_result["skipped"]:
        entries.append(
            {
                "tournament": None,
                "identity_key": s["identity_key"],
                "metric": _metric_label_for(plan, s["identity_key"]),
                "stage": s["stage"],
                "reason": s["reason"],
                "evidence_path": None,
                "recommended_action": _recommended_action_for(s["stage"], s["reason"]),
            }
        )
    for it in acquisition_result["items"]:
        if it["http_outcome"] != "HTTP_FAILURE":
            continue
        reason = it.get("error") or "HTTP request failed"
        entries.append(
            {
                "tournament": None,
                "identity_key": it["identity_key"],
                "metric": _metric_label_for(plan, it["identity_key"]),
                "stage": "http_failure",
                "reason": reason,
                "evidence_path": None,
                "recommended_action": _recommended_action_for("http_failure", reason),
            }
        )
    return entries


# ---------------------------------------------------------------
# Checkpoint integration
# ---------------------------------------------------------------


def _update_checkpoint_from_items(checkpoint: dict[str, CheckpointEntry], items: list[dict], season: str) -> None:
    """Records every attempted identity this run into the checkpoint —
    SUCCESS entries carry the full per-identity result record (this
    collector's own shape, not byte-identical to Phase B1's `build_
    sample_record`) so a later run's report can show cumulative
    HTTP_SUCCESS/parse/validation counts without re-reading every raw
    file; HTTP_FAILURE entries stay visible and remain re-attempted on
    the next run (see `b2_checkpoint.COMPLETION_HTTP_FAILURE`'s own
    docstring — unchanged behavior, reused as-is)."""
    for item in items:
        request_params = {"season": item["season"], "menu1": item["menu1"], "menu2": item["menu2"]}
        if item.get("menu3"):
            request_params["menu3"] = item["menu3"]
        if item["http_outcome"] == "HTTP_SUCCESS":
            mark_success(
                checkpoint,
                identity_key=item["identity_key"],
                request_params=request_params,
                season=season,
                parse_status=item["parse_status"],
                schema_fingerprint=item["schema_fingerprint"],
                player_row_count=item["player_row_count"],
                timestamp=item["timestamp"],
                sample_record=item,
                log_entry=None,
            )
        else:
            mark_http_failure(
                checkpoint,
                identity_key=item["identity_key"],
                request_params=request_params,
                season=season,
                timestamp=item["timestamp"],
            )


# ---------------------------------------------------------------
# Report
# ---------------------------------------------------------------


@dataclass
class LocalCollectionReport:
    generated_at: str
    runtime_seconds: float
    live: bool
    season: str
    # Tournament-level fields are always None this round — this
    # milestone operates at the metric-identity level only. Kept as
    # explicit fields (rather than omitted) so a reader can see the
    # scope limitation instead of silently missing a expected field.
    tournaments_expected: Optional[int]
    tournaments_completed: Optional[int]
    metrics_expected: int
    metrics_completed_this_run: int
    metrics_completed_cumulative: int
    http_requests_attempted: int
    http_success: int
    http_failure: int
    cache_hits_observable: bool
    cache_hits: int
    raw_responses_saved: int
    parse_success: int
    parse_empty: int
    parse_ambiguous_or_failed: int
    validation_clean: int
    validation_flagged: int
    skipped_items_this_run: int
    skip_queue_total: int
    remaining_missing_evidence: int
    completion_percent: float
    unresolved_before: int
    unresolved_after: int
    hard_stop: Optional[dict]
    checkpoint_path: str
    skip_queue_path: str


def build_local_collection_report(
    *,
    acquisition_result: Optional[dict],
    preview_rows: list[dict],
    checkpoint: dict[str, CheckpointEntry],
    before_counts: dict,
    after_counts: dict,
    skip_queue: list[dict],
    live: bool,
    season: str,
    runtime_seconds: float,
    checkpoint_path: Path,
    skip_queue_path: Path,
    generated_at: str,
) -> LocalCollectionReport:
    """Pure function over already-computed pieces — no new HTTP or
    audit calls happen here. `acquisition_result` is `None` in preview
    (`live=False`) mode, in which case every acquisition-derived count
    is simply 0/empty and `metrics_expected` comes from `preview_rows`
    alone."""
    metrics_expected = len(preview_rows) if acquisition_result is None else acquisition_result[
        "expected_missing_evidence_identities"
    ]
    items = acquisition_result["items"] if acquisition_result else []
    http_success = sum(1 for it in items if it["http_outcome"] == "HTTP_SUCCESS")
    http_failure = sum(1 for it in items if it["http_outcome"] == "HTTP_FAILURE")
    cache_observed = [it for it in items if it.get("cache_live_distinction") not in (None, "NOT_AVAILABLE")]
    cache_hits = sum(1 for it in items if it.get("cache_live_distinction") == "CACHE_HIT")
    parse_success = sum(1 for it in items if it.get("parse_status") in ("CONFIRMED", "DISCOVERED_NOT_VALIDATED"))
    parse_empty = sum(1 for it in items if it.get("parse_status") == "EMPTY")
    parse_ambiguous_or_failed = sum(1 for it in items if it.get("parse_status") in ("AMBIGUOUS", "FAILED"))
    validation_ran = [it for it in items if it["http_outcome"] == "HTTP_SUCCESS"]
    validation_flagged = sum(1 for it in validation_ran if it.get("data_quality_any_flagged"))
    validation_clean = len(validation_ran) - validation_flagged

    metrics_completed_cumulative = sum(1 for e in checkpoint.values() if e.is_complete)
    remaining_missing_evidence = max(0, metrics_expected - http_success)
    completion_percent = round(100.0 * http_success / metrics_expected, 1) if metrics_expected else 100.0

    return LocalCollectionReport(
        generated_at=generated_at,
        runtime_seconds=round(runtime_seconds, 3),
        live=live,
        season=season,
        tournaments_expected=None,
        tournaments_completed=None,
        metrics_expected=metrics_expected,
        metrics_completed_this_run=http_success,
        metrics_completed_cumulative=metrics_completed_cumulative,
        http_requests_attempted=len(items),
        http_success=http_success,
        http_failure=http_failure,
        cache_hits_observable=bool(cache_observed),
        cache_hits=cache_hits,
        raw_responses_saved=http_success,
        parse_success=parse_success,
        parse_empty=parse_empty,
        parse_ambiguous_or_failed=parse_ambiguous_or_failed,
        validation_clean=validation_clean,
        validation_flagged=validation_flagged,
        skipped_items_this_run=len(acquisition_result["skipped"]) if acquisition_result else 0,
        skip_queue_total=len(skip_queue),
        remaining_missing_evidence=remaining_missing_evidence,
        completion_percent=completion_percent,
        unresolved_before=before_counts["total_unresolved"],
        unresolved_after=after_counts["total_unresolved"],
        hard_stop=acquisition_result["hard_stop"] if acquisition_result else None,
        checkpoint_path=str(checkpoint_path),
        skip_queue_path=str(skip_queue_path),
    )


def render_report_markdown(report: LocalCollectionReport, *, skip_queue: list[dict]) -> str:
    lines = [
        "# KLPGA Local Collector — Run Report",
        "",
        f"Generated: {report.generated_at}  ·  Runtime: {report.runtime_seconds}s  ·  "
        f"Mode: {'LIVE' if report.live else 'PREVIEW (--dry-run, zero HTTP requests)'}  ·  Season: {report.season}",
        "",
        "## Scope",
        "",
        "This milestone collects ONLY the identity_key groups currently classified "
        "`UNRESOLVED_INSUFFICIENT_EVIDENCE` by the identity-key collision audit — never "
        "the full canonical sweep, never an already-resolved or PARTIAL/D_UNRESOLVED group. "
        "Tournament-level fields below are `N/A` — this collector does not yet operate at "
        "the tournament level (see the script's own docstring for what remains to build).",
        "",
        "## Counts",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Tournaments expected / completed | N/A / N/A |",
        f"| Metrics expected | {report.metrics_expected} |",
        f"| Metrics completed this run | {report.metrics_completed_this_run} |",
        f"| Metrics completed cumulative (checkpoint) | {report.metrics_completed_cumulative} |",
        f"| HTTP requests attempted | {report.http_requests_attempted} |",
        f"| HTTP success | {report.http_success} |",
        f"| HTTP failure | {report.http_failure} |",
        f"| Cache hits observable | {report.cache_hits_observable} |",
        f"| Cache hits | {report.cache_hits} |",
        f"| Raw responses saved | {report.raw_responses_saved} |",
        f"| Parse success | {report.parse_success} |",
        f"| Parse empty | {report.parse_empty} |",
        f"| Parse ambiguous/failed | {report.parse_ambiguous_or_failed} |",
        f"| Validation clean (no data-quality flags) | {report.validation_clean} |",
        f"| Validation flagged | {report.validation_flagged} |",
        f"| Skipped items this run | {report.skipped_items_this_run} |",
        f"| Skip queue total (cumulative) | {report.skip_queue_total} |",
        f"| Remaining missing evidence | {report.remaining_missing_evidence} |",
        f"| Completion percent | {report.completion_percent}% |",
        f"| Unresolved BEFORE (collision audit) | {report.unresolved_before} |",
        f"| Unresolved AFTER (collision audit) | {report.unresolved_after} |",
        f"| Hard stop | {report.hard_stop if report.hard_stop else 'None'} |",
        "",
        f"Checkpoint: `{report.checkpoint_path}`",
        f"Skip queue: `{report.skip_queue_path}`",
        "",
        "## Skip queue (all rows currently open, cumulative across runs)",
        "",
    ]
    if not skip_queue:
        lines.append("(empty)")
    else:
        lines.append("| identity_key | metric | stage | reason | recommended_action | last_seen |")
        lines.append("|---|---|---|---|---|---|")
        for e in skip_queue:
            lines.append(
                f"| {e.get('identity_key')} | {e.get('metric') or '—'} | {e.get('stage')} | "
                f"{e.get('reason')} | {e.get('recommended_action')} | {e.get('last_seen')} |"
            )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------
# Live-run progress observability: elapsed-time-stamped log lines plus
# a background heartbeat, so a `--live` run's console never goes silent
# long enough to look like a hang. Pure observation — this NEVER
# changes request timing, retry counts, or any collection/parsing/
# safety behavior; it only reads shared state that the real log calls
# already produce and prints about it on its own schedule.
# ---------------------------------------------------------------

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
"""How often the background heartbeat checks in during a live run.
Independent of `PoliteHttpClient`'s own throttle/retry timing — this
number can change freely without affecting request rate at all."""


def _fmt_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class _ActivityHeartbeat:
    """Background daemon thread that periodically reports elapsed time
    and time-since-last-activity, so a long quiet gap (a slow request,
    a rate-limit backoff sleep, or a genuine hang) is always visible
    instead of silent. Only ever reads/writes its own small bit of
    state (`note()` records the last log line's timestamp/text) and
    prints — it never touches the HTTP client, never sleeps in the
    request path, and has zero effect on what gets requested or when."""

    def __init__(self, log: Callable[[str], None], *, interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS):
        self._log = log
        self._interval = interval_seconds
        self._start = time.perf_counter()
        self._last_activity_ts = self._start
        self._last_activity_desc = "run started"
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def note(self, description: str) -> None:
        with self._lock:
            self._last_activity_ts = time.perf_counter()
            self._last_activity_desc = description

    def _tick(self) -> None:
        with self._lock:
            since_activity = time.perf_counter() - self._last_activity_ts
            desc = self._last_activity_desc
        elapsed = time.perf_counter() - self._start
        self._log(
            f"[HEARTBEAT +{_fmt_elapsed(elapsed)}] still running — {_fmt_elapsed(since_activity)} since last "
            f"activity ({desc}). This can be normal rate-limit/backoff waiting or one slow request — "
            "not necessarily a hang; PoliteHttpClient's own worst case for a single request is bounded "
            "(see http_client.py's module docstring)."
        )

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            self._tick()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="klpga-collector-heartbeat")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self._interval))


def _make_elapsed_log(base_log: Callable[[str], None], heartbeat: _ActivityHeartbeat, start: float) -> Callable[[str], None]:
    """Wraps `base_log` so every line — including every line `acquire_
    missing_evidence`/`fetch_and_analyze`/`PoliteHttpClient.on_retry`
    already produce, unmodified — gets an `[+MM:SS]` elapsed-time
    prefix and marks the heartbeat's last-activity clock, all without
    changing what any of those components actually do."""

    def _log(msg: str) -> None:
        heartbeat.note(msg)
        elapsed = time.perf_counter() - start
        base_log(f"[+{_fmt_elapsed(elapsed)}] {msg}")

    return _log


# ---------------------------------------------------------------
# Orchestration entry point
# ---------------------------------------------------------------


def run_local_collection(
    client,
    taxonomy: dict,
    season: str,
    *,
    raw_samples_dir: Path,
    checkpoint_path: Path,
    skip_queue_path: Path,
    report_path: Path,
    live: bool,
    log: Callable[[str], None] = print,
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
) -> tuple[int, LocalCollectionReport]:
    """The ONE orchestration function `scripts/run_klpga_collector.py`
    calls. Reuses, unmodified: `build_canonical_plan`,
    `audit_identity_key_collisions`, `missing_evidence_acquisition.
    build_missing_evidence_request_plan`/`acquire_missing_evidence`
    (which itself reuses `PoliteHttpClient` and `record_fetch.fetch_
    and_analyze`), and `b2_checkpoint`'s atomic load/write/mark_*
    functions. The only NEW logic here is: loading/updating the
    checkpoint from this run's results, merging this run's failures
    into the persistent skip queue, and assembling the final report —
    everything else is a direct call into an already-tested component.

    `client` is ignored entirely when `live=False` (preview mode) —
    no HTTP-capable object is ever touched in that path, matching
    every other dry-run in this project's history. Returns
    `(exit_code, report)`; `exit_code` is `EXIT_HARD_STOP` if a
    401/403/429 halted live acquisition partway through this run,
    `EXIT_COMPLETE` otherwise (including a preview run, and a live run
    that found zero remaining missing-evidence identities).

    During a `live=True` run, every log line is stamped with elapsed
    time (`[+MM:SS] ...`) and a background heartbeat (every `heartbeat_
    interval_seconds`, default 15s) prints how long it has been since
    the last activity — so a normal rate-limit/backoff wait and a
    genuine hang both stay visibly distinguishable instead of the
    console going silent. `missing_evidence_acquisition.acquire_
    missing_evidence` also emits one `PROGRESS [i/N] | identity_key |
    CACHE/LIVE | HTTP status | PARSE status | SAVED/SKIPPED` line per
    identity as it completes. None of this changes request timing,
    retry counts, or what gets collected — it only observes and prints."""
    start = time.perf_counter()
    generated_at = datetime.now(timezone.utc).isoformat()

    _counts, plan = build_canonical_plan(taxonomy)
    checkpoint = load_checkpoint(checkpoint_path)
    skip_queue = load_skip_queue(skip_queue_path)
    preview_rows = build_missing_evidence_request_plan(taxonomy, season=season, raw_samples_dir=raw_samples_dir)

    if live:
        heartbeat = _ActivityHeartbeat(log, interval_seconds=heartbeat_interval_seconds)
        wrapped_log = _make_elapsed_log(log, heartbeat, start)
        # PoliteHttpClient's own retry/backoff diagnostic messages
        # (`on_retry`) are routed through the SAME wrapped log — same
        # timing, same content, just where the string is printed to —
        # so a retry wait shows up on the heartbeat's activity clock
        # too, instead of appearing to go silent. Never touched for a
        # client double (tests) that has no `on_retry` attribute at all.
        if hasattr(client, "on_retry"):
            client.on_retry = wrapped_log

        wrapped_log("=== LOCAL COLLECTOR: live acquisition (bounded missing-evidence milestone) ===")
        heartbeat.start()
        try:
            acquisition = acquire_missing_evidence(client, taxonomy, season, raw_samples_dir, log=wrapped_log)
        finally:
            heartbeat.stop()
        _update_checkpoint_from_items(checkpoint, acquisition["items"], season)
        write_checkpoint_atomic(checkpoint_path, checkpoint)

        new_skip_entries = build_skip_queue_entries(acquisition, plan)
        skip_queue = merge_skip_queue_entries(skip_queue, new_skip_entries, timestamp=generated_at)
        write_skip_queue_atomic(skip_queue_path, skip_queue)

        before_counts = acquisition["before_counts"]
        after_counts = acquisition["after_counts"]
    else:
        log("=== LOCAL COLLECTOR: preview (--dry-run, zero HTTP requests) ===")
        acquisition = None
        audits_now = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
        before_counts = after_counts = _category_counts(audits_now)

    runtime_seconds = time.perf_counter() - start
    report = build_local_collection_report(
        acquisition_result=acquisition,
        preview_rows=preview_rows,
        checkpoint=checkpoint,
        before_counts=before_counts,
        after_counts=after_counts,
        skip_queue=skip_queue,
        live=live,
        season=season,
        runtime_seconds=runtime_seconds,
        checkpoint_path=checkpoint_path,
        skip_queue_path=skip_queue_path,
        generated_at=generated_at,
    )

    report_markdown = render_report_markdown(report, skip_queue=skip_queue)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_markdown, encoding="utf-8")
    log("")
    log(report_markdown)

    exit_code = EXIT_HARD_STOP if (acquisition and acquisition["hard_stop"]) else EXIT_COMPLETE
    return exit_code, report
