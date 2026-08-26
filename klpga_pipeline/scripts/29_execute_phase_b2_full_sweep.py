"""Phase B2 — the full canonical-metric sweep. Requires explicit,
separate authorization to actually fire (see docs/KLPGA_OFFICIAL_
DATA_MAP.md's B2 gate history) and is never started implicitly by any
other script. This script itself, once invoked for real (not
--dry-run), makes ONE live HTTP request per canonical requestable
metric in `docs/discovery/KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json`
(scripts/28's output) — the full count, not a representative sample,
and NOT subject to Phase B1's `per_family_cap` (see
`klpga.discovery.sampler.select_full_canonical_plan`).

Reuses, unmodified, the exact request/parse/analyze logic already
proven in Phase B1 (`klpga.discovery.record_fetch.fetch_and_analyze`,
extracted from scripts/27 this same round specifically so B1 and B2
never diverge in how a single metric is fetched) and the same
`PoliteHttpClient` rate limiting (1.5s min interval + jitter, 4-attempt
retry with backoff on transient errors, immediate hard stop — never a
retry or bypass — on 401/403/429 via `RateLimitBlockedError`).

Two independent resumability layers:
  1. `PoliteHttpClient`'s own disk cache (`data/raw_cache/http/` by
     default, the SAME directory Phase B1 already uses) — an
     already-fetched URL is never re-requested, even across scripts.
  2. THIS script's own explicit checkpoint/state artifact
     (`klpga.discovery.b2_checkpoint`), keyed by `identity_key`,
     written ATOMICALLY every `--flush-every` completed identities
     (default 10). On restart, already-`SUCCESS` identities are
     skipped entirely (not even re-attempted); `HTTP_FAILURE`
     identities remain visible in the checkpoint and are retried. The
     checkpoint is the AUTHORITATIVE resume/skip decision — layer 1 is
     a lower-level safety net underneath it, not a substitute for it
     (a checkpoint corruption or deletion would fall back to re-doing
     live requests that the HTTP cache would still short-circuit, but
     that is a degraded-safety fallback, never the intended path).

Safety stops:
  - 401/403/429 (`RateLimitBlockedError`): halts the ENTIRE sweep
    immediately, matching Phase B1 exactly — never retried, never
    bypassed.
  - `--consecutive-failure-limit` (default 5) consecutive HTTP-level
    failures (any exception other than RateLimitBlockedError, e.g.
    exhausted retries on a 5xx/timeout): halts the sweep as a circuit
    breaker. Resets to 0 on the next successful request. This counter
    is in-memory only for the current process — a fresh invocation
    (even resuming the same checkpoint) starts it back at 0, since a
    process restart is itself already a strong enough signal to
    re-attempt.
  - An individual metric's malformed/unexpected PARSE result
    (AMBIGUOUS/FAILED) does NOT halt the sweep — recorded and moved
    on, exactly like Phase B1.

Output artifacts, all under `--out-dir` (default
`docs/discovery/phase_b2/`, NEVER Phase B1's `docs/discovery/`
directory, so a B2 run can never overwrite a B1 artifact):
  docs/discovery/phase_b2/KLPGA_PHASE_B2_CHECKPOINT.json
  docs/discovery/phase_b2/KLPGA_PHASE_B2_RESPONSE_SAMPLES.json/.csv
  docs/discovery/phase_b2/KLPGA_PHASE_B2_RESPONSE_FAILURES.csv
  docs/discovery/phase_b2/KLPGA_PHASE_B2_REQUEST_LOG.jsonl/.csv
  docs/discovery/phase_b2/raw_samples/<identity_key>__<season>.html

The samples/failures/request-log artifacts are REGENERATED in full
from the checkpoint on every flush (not appended-to) — the checkpoint
stores each successful identity's full sample record and log entry
(see `b2_checkpoint.CheckpointEntry`), so these artifacts always
reflect every identity completed across ALL runs against this
checkpoint, not only the current invocation's slice. Deliberately
narrower than Phase B1's full report set (no schema-report/raw-field-
inventory/player-identity markdown) — those were not required for this
round's B2 scope and can be added later against the accumulated
checkpoint without any live requests.

Usage — MANDATORY dry run first (zero HTTP requests, zero files
written):
    python scripts\\29_execute_phase_b2_full_sweep.py --dry-run \\
        --canonical-plan docs\\discovery\\KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json \\
        --season 2025

Only after reviewing the dry-run's printed plan, the real run (still
requires this project's separate, explicit "execute B2 now"
authorization per docs/KLPGA_OFFICIAL_DATA_MAP.md):
    python scripts\\29_execute_phase_b2_full_sweep.py \\
        --canonical-plan docs\\discovery\\KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json \\
        --season 2025
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.b2_checkpoint import (  # noqa: E402
    CheckpointEntry,
    COMPLETION_HTTP_FAILURE,
    load_checkpoint,
    mark_http_failure,
    mark_success,
    write_checkpoint_atomic,
)
from klpga.discovery.record_fetch import fetch_and_analyze, request_form  # noqa: E402
from klpga.discovery.request_log import RequestLogEntry, to_log_csv, to_log_jsonl  # noqa: E402
from klpga.discovery.sampler import select_full_canonical_plan  # noqa: E402
from klpga.discovery.schema_report import (  # noqa: E402
    build_request_outcome_counts,
    build_sample_record,
    write_response_failures_csv,
    write_samples_csv,
    write_samples_json,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_BLOCKED = 4
EXIT_PLAN_LOAD_FAILED = 5
EXIT_CIRCUIT_BREAKER_TRIPPED = 7

DEFAULT_FLUSH_EVERY = 10
DEFAULT_CONSECUTIVE_FAILURE_LIMIT = 5

_LAST_MARKER = {"text": "no marker recorded yet"}


def _log(msg: str) -> None:
    _LAST_MARKER["text"] = msg
    print(msg, flush=True)


def _write_outputs(out_dir: Path, entries: dict[str, CheckpointEntry]) -> None:
    """Regenerates every human-facing output artifact from the FULL
    accumulated checkpoint (sorted by identity_key for a deterministic
    file — not necessarily this run's fetch order). Never touches
    anything outside `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)

    success_entries = sorted(
        (e for e in entries.values() if e.is_complete and e.sample_record is not None),
        key=lambda e: e.identity_key,
    )
    records = [e.sample_record for e in success_entries]

    (out_dir / "KLPGA_PHASE_B2_RESPONSE_SAMPLES.json").write_text(
        write_samples_json(
            records,
            discovered_at=datetime.now(timezone.utc).isoformat(),
            source_taxonomy="phase_b2_full_canonical_sweep",
        ),
        encoding="utf-8",
    )
    (out_dir / "KLPGA_PHASE_B2_RESPONSE_SAMPLES.csv").write_text(
        write_samples_csv(records), encoding="utf-8", newline=""
    )

    failures = [r for r in records if r["parse_status"] in ("AMBIGUOUS", "FAILED")]
    (out_dir / "KLPGA_PHASE_B2_RESPONSE_FAILURES.csv").write_text(
        write_response_failures_csv(failures), encoding="utf-8", newline=""
    )

    log_entries = [RequestLogEntry(**e.log_entry) for e in success_entries if e.log_entry]
    (out_dir / "KLPGA_PHASE_B2_REQUEST_LOG.jsonl").write_text(to_log_jsonl(log_entries), encoding="utf-8")
    (out_dir / "KLPGA_PHASE_B2_REQUEST_LOG.csv").write_text(to_log_csv(log_entries), encoding="utf-8", newline="")


def run(
    client: PoliteHttpClient,
    canonical_plan: list[dict],
    season: str,
    out_dir: Path,
    *,
    max_requests: Optional[int] = None,
    save_raw_responses: bool = True,
    flush_every: int = DEFAULT_FLUSH_EVERY,
    consecutive_failure_limit: int = DEFAULT_CONSECUTIVE_FAILURE_LIMIT,
    checkpoint_path: Optional[Path] = None,
    dry_run: bool = False,
) -> int:
    full_leaves = select_full_canonical_plan(canonical_plan)
    full_count = len(full_leaves)
    _log(f"[STEP 01] canonical plan loaded: {len(canonical_plan)} canonical requestable metrics")
    _log(
        f"[STEP 02] full sweep plan built: {full_count} identities, deterministic (menu1, menu2, menu3) "
        "order, NO Phase B1 per_family_cap applied"
    )
    for idx, leaf in enumerate(full_leaves, start=1):
        _log(
            f"  {idx}. {leaf.source_metric_key} (menu1={leaf.menu1!r} menu2={leaf.menu2!r} "
            f"menu3={leaf.menu3!r} leaf_level={leaf.leaf_level!r})"
        )

    if dry_run:
        _log(
            f"[DRY RUN] {full_count} identities would be requested against season={season!r}. "
            "Zero HTTP requests made. Zero files written. Phase B2 NOT executed."
        )
        return EXIT_COMPLETE

    checkpoint_path = checkpoint_path or (out_dir / "KLPGA_PHASE_B2_CHECKPOINT.json")
    entries = load_checkpoint(checkpoint_path)
    already_complete = {key for key, e in entries.items() if e.is_complete}
    _log(
        f"[STEP 03] checkpoint loaded: {checkpoint_path} — {len(entries)} entries on disk, "
        f"{len(already_complete)} already SUCCESS (will be skipped this run)"
    )

    to_attempt = [leaf for leaf in full_leaves if leaf.source_metric_key not in already_complete]
    _log(f"[STEP 04] {len(to_attempt)} identities remaining to attempt this run")

    raw_dir = (out_dir / "raw_samples") if save_raw_responses else None
    request_count = 0
    consecutive_failures = 0
    since_flush = 0
    blocked = False

    def _flush() -> None:
        _write_outputs(out_dir, entries)
        write_checkpoint_atomic(checkpoint_path, entries)

    for i, leaf in enumerate(to_attempt, start=1):
        if max_requests is not None and request_count >= max_requests:
            _log(f"Reached --max-requests={max_requests} — stopping before {leaf.source_metric_key}.")
            break

        attempt_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            parsed, analysis, log_entry = fetch_and_analyze(
                client, leaf, season, tag=f"{i}/{len(to_attempt)}", raw_dir=raw_dir, log=_log
            )
            request_count += 1
            consecutive_failures = 0
        except RateLimitBlockedError as exc:
            _log(f"BLOCKED on {leaf.source_metric_key}: {exc}")
            _log("Not retrying, not bypassing — halting the ENTIRE sweep per instruction.")
            blocked = True
            break
        except Exception as exc:  # noqa: BLE001 — an HTTP-layer failure must not abort the whole sweep.
            _log(f"HTTP_FAILURE fetching {leaf.source_metric_key}: {exc}")
            request_count += 1
            consecutive_failures += 1
            mark_http_failure(
                entries,
                identity_key=leaf.source_metric_key,
                request_params=request_form(leaf, season),
                season=season,
                timestamp=attempt_timestamp,
            )
            since_flush += 1
            if consecutive_failures >= consecutive_failure_limit:
                _log(
                    f"CIRCUIT BREAKER: {consecutive_failures} consecutive HTTP failures >= "
                    f"--consecutive-failure-limit={consecutive_failure_limit} — halting the sweep."
                )
                _flush()
                return EXIT_CIRCUIT_BREAKER_TRIPPED
            if since_flush >= flush_every:
                _flush()
                since_flush = 0
            continue

        record = build_sample_record(leaf, season=season, http_status=200, parsed=parsed, analysis=analysis)
        mark_success(
            entries,
            identity_key=leaf.source_metric_key,
            request_params=request_form(leaf, season),
            season=season,
            parse_status=parsed.parse_status,
            schema_fingerprint=analysis.schema_fingerprint,
            player_row_count=len(parsed.rows),
            timestamp=attempt_timestamp,
            sample_record=record,
            log_entry=asdict(log_entry),
        )
        since_flush += 1
        if since_flush >= flush_every:
            _flush()
            since_flush = 0

    _flush()

    success_count = sum(1 for e in entries.values() if e.is_complete)
    http_failure_count = sum(1 for e in entries.values() if e.completion_status == COMPLETION_HTTP_FAILURE)
    records_now = [e.sample_record for e in entries.values() if e.is_complete and e.sample_record is not None]
    outcome_counts = build_request_outcome_counts(records_now, http_failure_count=http_failure_count)

    _log("")
    _log("Phase B2 sweep summary (cumulative, across all runs against this checkpoint):")
    _log(f"  canonical identities total:      {full_count}")
    _log(f"  checkpoint SUCCESS:              {success_count}")
    _log(f"  checkpoint HTTP_FAILURE:         {http_failure_count}")
    _log(f"  http_success:                    {outcome_counts['http_success']}")
    _log(f"  http_failure:                    {outcome_counts['http_failure']}")
    _log(f"  parse_success:                   {outcome_counts['parse_success']}")
    _log(f"  parse_empty:                     {outcome_counts['parse_empty']}")
    _log(f"  parse_ambiguous_or_failed:       {outcome_counts['parse_ambiguous_or_failed']}")
    _log(f"Output written to: {out_dir}")

    if blocked:
        return EXIT_BLOCKED
    return EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--canonical-plan",
        required=True,
        help="Path to docs/discovery/KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json (scripts/28's output).",
    )
    parser.add_argument("--season", required=True, help="Season value to request (e.g. 2025) — not guessed")
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "discovery" / "phase_b2"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument(
        "--checkpoint-path",
        default=None,
        help="Defaults to <out-dir>/KLPGA_PHASE_B2_CHECKPOINT.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the full request plan and count. Makes ZERO HTTP requests, writes ZERO files.",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="Cap on live requests THIS invocation makes (default: no cap beyond the full canonical count).",
    )
    parser.add_argument("--flush-every", type=int, default=DEFAULT_FLUSH_EVERY)
    parser.add_argument("--consecutive-failure-limit", type=int, default=DEFAULT_CONSECUTIVE_FAILURE_LIMIT)
    parser.add_argument(
        "--no-raw-samples",
        action="store_true",
        help="Skip saving a human-named raw HTML copy per fetched metric under <out-dir>/raw_samples/.",
    )
    args = parser.parse_args()

    plan_path = Path(args.canonical_plan)
    if not plan_path.exists():
        _log(f"Canonical plan file not found: {plan_path}")
        _log("Run scripts/28_build_canonical_metric_request_plan.py first.")
        return EXIT_PLAN_LOAD_FAILED
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    canonical_plan = payload.get("canonical_requestable_metrics", [])

    out_dir = Path(args.out_dir)
    checkpoint_path = Path(args.checkpoint_path) if args.checkpoint_path else None
    client = PoliteHttpClient(cache_dir=Path(args.cache_dir), on_retry=lambda msg: _log(f"[HTTP RETRY] {msg}"))

    return run(
        client,
        canonical_plan,
        args.season,
        out_dir,
        max_requests=args.max_requests,
        save_raw_responses=not args.no_raw_samples,
        flush_every=args.flush_every,
        consecutive_failure_limit=args.consecutive_failure_limit,
        checkpoint_path=checkpoint_path,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
