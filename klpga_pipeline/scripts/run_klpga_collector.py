"""Round 11 — THE LOCAL COLLECTOR: a single Windows entry point that
runs the entire bounded missing-evidence acquisition workflow — state
inspection, plan derivation, live acquisition, parsing, validation,
checkpoint update, persistent skip-queue update, collision-audit
rerun, and final report — with ONE command, so nobody needs to chain
separate discovery/acquisition/parser/validation/audit/reporting
commands by hand.

LOCAL WINDOWS (or any machine with real network access to
klpga.co.kr) IS THE DATA-COLLECTION ENVIRONMENT. This script makes
real HTTP requests when `--live` is passed — it must be run somewhere
with that access, never from a sandbox that has none.

WHAT THIS SCRIPT DOES THIS ROUND (the "FIRST MILESTONE"):
  Wraps the already-existing, already-tested bounded missing-evidence
  acquisition (`klpga.discovery.missing_evidence_acquisition` — the
  exact same logic `scripts/32_bounded_missing_evidence_request_plan.
  py`'s own `--live` uses) behind one command, adding:
    - a durable, atomic checkpoint (`klpga.discovery.b2_checkpoint`,
      reused unchanged) recording every identity this collector has
      ever attempted, across every run;
    - a durable, atomic, deduplicated SKIP QUEUE recording every
      non-systemic ("LOCAL") failure with a recommended next action —
      never silently dropped, never blocking the rest of the run;
    - one consolidated, human-readable Markdown report plus a
      machine-readable checkpoint/skip-queue state, written to disk
      AND printed, every run.
  Safe by default: with no `--live` flag, this makes ZERO HTTP
  requests — it only inspects existing local state (taxonomy, raw
  evidence already on disk, the checkpoint, the skip queue, the
  identity-key collision audit) and prints/writes the exact plan that
  `--live` would execute. This mirrors every other script in this
  project (a mandatory, safe preview before any live mode) rather than
  firing unconditionally the moment this command is run.

WHAT THIS SCRIPT DOES **NOT** DO YET (honest scope limits — read
before assuming 100-tournament readiness):
  - Does NOT enumerate tournaments or players. It operates entirely at
    the metric-`identity_key` level this project's Phase A/B discovery
    already established — there is no tournament-scoped work-item list
    yet, and none is invented here.
  - Does NOT write to the production database, `predictions/`, or any
    table the live prediction site reads. Every artifact this script
    produces is a plain file under `--raw-samples-dir`/`--checkpoint-
    path`/`--skip-queue-path`/`--report-path` (all default to
    `docs/discovery/...`), completely separate from the production
    pipeline's own tables and files.
  - Does NOT implement a "normalized database" storage layer for
    collected metrics — that is real, additional engineering work
    (schema design + migration + upsert logic, following this
    project's existing `db/upsert.py` conventions) that has not been
    started.
  - Is deliberately bounded to the CURRENT `UNRESOLVED_INSUFFICIENT_
    EVIDENCE` set — it will never expand into the full Phase B2
    canonical sweep (281+ requests) or a 100-tournament collection on
    its own; that requires a separate, explicitly-authorized round, on
    top of the not-yet-built tournament/player enumeration layer above.

SAFETY (unchanged from every prior round): reuses `PoliteHttpClient`'s
existing rate limiting (1.5s+jitter, 4-attempt retry/backoff) and its
immediate, never-retried hard stop on 401/403/429
(`RateLimitBlockedError`) — a hard stop here halts all FURTHER live
requests this run, but this script still completes every safe offline
step afterward (checkpoint update, skip-queue update, audit rerun,
report) rather than crashing. A per-item HTTP failure (exhausted
retries) is a LOCAL failure: recorded in the skip queue, and
acquisition continues to the next identity. No concurrency, no proxy
rotation, no alternate endpoints, no bypass of any kind.

RESUMABILITY / IDEMPOTENCY: safe to interrupt (Ctrl+C) and re-run at
any point. Already-saved raw evidence is never re-requested (the audit
re-checks the file's existence fresh, every run) and never overwritten
by a failed/empty response. The checkpoint and skip queue are both
written atomically (temp file + os.replace) — a crash mid-write always
leaves the previous, valid file intact, never a half-written one.

Usage — MANDATORY preview first (zero HTTP requests, zero files
written beyond the report):
    python scripts\\run_klpga_collector.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
        --season 2025

Usage — live acquisition (real HTTP requests, only after reviewing
the preview):
    python scripts\\run_klpga_collector.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
        --season 2025 ^
        --live
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.local_collector import (  # noqa: E402
    EXIT_COMPLETE,
    EXIT_HARD_STOP,
    EXIT_TAXONOMY_LOAD_FAILED,
    run_local_collection,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "docs" / "discovery" / "local_collector"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--season", required=True, help="Season value the raw samples were/would be fetched for")
    parser.add_argument(
        "--raw-samples-dir",
        default=str(ROOT / "docs" / "discovery" / "raw_samples"),
        help="Directory of already-saved raw responses (the project-wide raw_samples/ convention).",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(ROOT / "data" / "raw_cache" / "http"),
        help="PoliteHttpClient's own disk cache directory (--live only; same one Phase B1/B2 use).",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=str(DEFAULT_OUT_DIR / "COLLECTOR_CHECKPOINT.json"),
        help="This collector's own durable, atomic run ledger (separate from the HTTP disk cache).",
    )
    parser.add_argument(
        "--skip-queue-path",
        default=str(DEFAULT_OUT_DIR / "SKIP_QUEUE.json"),
        help="Durable, deduplicated review queue for every non-systemic failure.",
    )
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_OUT_DIR / "LOCAL_COLLECTOR_REPORT.md"),
        help="Human-readable Markdown report, rewritten every run.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Fire real HTTP requests, bounded to the current UNRESOLVED_INSUFFICIENT_EVIDENCE "
            "set only. Omit for a safe preview (zero HTTP requests) — the default."
        ),
    )
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    client = None
    if args.live:
        from klpga.http_client import PoliteHttpClient

        client = PoliteHttpClient(
            cache_dir=Path(args.cache_dir), on_retry=lambda msg: print(f"[HTTP RETRY] {msg}", flush=True)
        )

    exit_code, _report = run_local_collection(
        client,
        taxonomy,
        args.season,
        raw_samples_dir=Path(args.raw_samples_dir),
        checkpoint_path=Path(args.checkpoint_path),
        skip_queue_path=Path(args.skip_queue_path),
        report_path=Path(args.report_path),
        live=args.live,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
