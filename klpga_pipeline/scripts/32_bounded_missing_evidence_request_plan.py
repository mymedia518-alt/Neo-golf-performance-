"""Round 10 continued — bounded, missing-evidence-ONLY request plan
for the identity_key collision audit's `UNRESOLVED_INSUFFICIENT_
EVIDENCE` groups (docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 10 section).

Two modes, mutually exclusive:

  `--dry-run` — makes ZERO HTTP requests. Prints the exact plan (see
  `build_missing_evidence_request_plan`) and exits. This is still the
  required first step before ever passing `--live`.

  `--live` (Round 10 continued, "bounded missing-evidence acquisition"
  authorization) — fires real HTTP requests, but ONLY for the
  identity_keys currently classified `UNRESOLVED_INSUFFICIENT_
  EVIDENCE`, derived FRESH from the audit at the moment this runs
  (never hardcoded, never assumed to still be the same set as a prior
  run). Reuses, unmodified: `PoliteHttpClient` (same rate limiting,
  retry/backoff, and immediate hard stop — never a retry or bypass —
  on 401/403/429 via `RateLimitBlockedError`), `klpga.discovery.
  record_fetch.fetch_and_analyze` (the exact request/parse/log-entry
  logic already proven in Phase B1/B2), and the `raw_samples/`
  identity-named-file convention every other script in this project
  already uses. Never requests an identity outside that exact set —
  in particular never a `PARTIAL_MATCH_NEEDS_REVIEW`/`D_UNRESOLVED`/
  already-resolved group, and never an identity whose expected raw
  sample file already exists on disk (checked immediately before each
  request, not just once at plan-build time, so evidence that appears
  mid-run is never overwritten). A per-item HTTP failure (exhausted
  retries on a 5xx/timeout, etc.) is recorded and the run continues to
  the next identity; a 401/403/429 halts ALL further live requests
  this run immediately, without retrying or bypassing, while still
  returning a full report of whatever was collected before the stop.
  After acquisition (or a hard stop), the identity-key collision audit
  is rerun fresh and BEFORE/AFTER category counts are reported — never
  forcing a category to zero.

Usage (fully offline — reads only local files already on disk):
    python scripts\\32_bounded_missing_evidence_request_plan.py \\
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json \\
        --season 2025 \\
        --dry-run

Usage (live, real HTTP requests — only after reviewing the dry run):
    python scripts\\32_bounded_missing_evidence_request_plan.py \\
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json \\
        --season 2025 \\
        --live

Round 11 note: the request-plan/acquisition LOGIC now lives in
`klpga.discovery.missing_evidence_acquisition` (re-exported below
unchanged) so `scripts/run_klpga_collector.py`'s local-collector
orchestrator can reuse it directly — this script itself is now a thin
CLI wrapper, exactly like scripts/27/29 already are around
`record_fetch.py`. Every name and behavior below is unchanged from
before this extraction; all of this script's own tests still pass
without modification.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.identity_key_audit import CATEGORY_INSUFFICIENT_EVIDENCE, audit_identity_key_collisions  # noqa: E402
from klpga.discovery.canonical_plan import build_canonical_plan  # noqa: E402
from klpga.discovery.missing_evidence_acquisition import (  # noqa: E402
    EXIT_HARD_STOP,
    acquire_missing_evidence,
    build_missing_evidence_request_plan,
)

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_TAXONOMY_LOAD_FAILED = 5
EXIT_DRY_RUN_REQUIRED = 2


def run_live(client, taxonomy: dict, season: str, raw_samples_dir: Path) -> int:
    """Runs `acquire_missing_evidence` and prints the single
    consolidated report (EXECUTION SUMMARY / HTTP-CACHE / PARSER /
    COLLISION AUDIT / SKIPPED_ITEMS_REVIEW / HARD_STOPS). Returns
    `EXIT_HARD_STOP` if a 401/403/429 halted the run partway through,
    `EXIT_COMPLETE` otherwise — a completed run with zero identities
    left to acquire, or one that finished its full bounded list, are
    both `EXIT_COMPLETE`."""
    print("Bounded missing-evidence LIVE acquisition (real HTTP requests)")
    print(f"season: {season}")
    print(
        "Scope: ONLY identity_keys the identity-key collision audit currently classifies "
        "UNRESOLVED_INSUFFICIENT_EVIDENCE, derived fresh right now. Every PARTIAL_MATCH_NEEDS_REVIEW "
        "/ D_UNRESOLVED / already-resolved group is out of scope and is never requested."
    )
    print()

    result = acquire_missing_evidence(client, taxonomy, season, raw_samples_dir, log=print)
    items = result["items"]
    skipped = result["skipped"]

    http_success = sum(1 for it in items if it["http_outcome"] == "HTTP_SUCCESS")
    http_failure = sum(1 for it in items if it["http_outcome"] == "HTTP_FAILURE")
    parse_success = sum(1 for it in items if it.get("parse_status") in ("CONFIRMED", "DISCOVERED_NOT_VALIDATED"))
    parse_empty = sum(1 for it in items if it.get("parse_status") == "EMPTY")
    parse_ambiguous_or_failed = sum(1 for it in items if it.get("parse_status") in ("AMBIGUOUS", "FAILED"))
    remaining_missing = result["expected_missing_evidence_identities"] - http_success
    completion_percent = (
        round(100.0 * http_success / result["expected_missing_evidence_identities"], 1)
        if result["expected_missing_evidence_identities"]
        else 100.0
    )

    print()
    print("=== EXECUTION SUMMARY ===")
    print(f"EXPECTED_MISSING_EVIDENCE_IDENTITIES = {result['expected_missing_evidence_identities']}")
    print(f"PROCESSED = {result['processed']}")
    print(f"HTTP_SUCCESS = {http_success}")
    print(f"HTTP_FAILURE = {http_failure}")
    print(f"RAW_SAMPLES_SAVED = {http_success}")
    print(f"PARSE_SUCCESS = {parse_success}")
    print(f"PARSE_EMPTY = {parse_empty}")
    print(f"PARSE_AMBIGUOUS_OR_FAILED = {parse_ambiguous_or_failed}")
    print(f"SKIPPED_NEEDS_REVIEW = {len(skipped)}")
    print(f"REMAINING_MISSING_EVIDENCE = {remaining_missing}")
    print(f"UNRESOLVED_BEFORE = {result['before_counts']['total_unresolved']}")
    print(f"UNRESOLVED_AFTER = {result['after_counts']['total_unresolved']}")
    print(f"COMPLETION_PERCENT = {completion_percent}")
    print()

    print("=== HTTP / CACHE ===")
    if not items:
        print("  (no identities attempted)")
    for it in items:
        print(
            f"  {it['identity_key']}: {it['http_outcome']} "
            f"cache_live_distinction={it['cache_live_distinction']} "
            f"raw_sample_path={it['raw_sample_path']} response_size={it['response_size']} "
            f"timestamp={it['timestamp']}"
        )
    print()

    print("=== PARSER ===")
    parser_rows = [it for it in items if it["http_outcome"] == "HTTP_SUCCESS"]
    if not parser_rows:
        print("  (no successfully-fetched identities)")
    for it in parser_rows:
        print(
            f"  {it['identity_key']}: parse_status={it['parse_status']} "
            f"player_row_count={it['player_row_count']} schema_fingerprint={it['schema_fingerprint']} "
            f"missing_player_code={it['missing_player_code']} missing_player_name={it['missing_player_name']} "
            f"blank_values={it['blank_values']} non_numeric_numeric_fields={it['non_numeric_numeric_fields']} "
            f"duplicate_player_rows={it['duplicate_player_rows']} "
            f"data_quality_any_flagged={it['data_quality_any_flagged']}"
        )
    print()

    print("=== COLLISION AUDIT ===")
    print(f"  BEFORE: {result['before_counts']}")
    print(f"  AFTER:  {result['after_counts']}")
    print()

    print("=== SKIPPED_ITEMS_REVIEW ===")
    if not skipped:
        print("  (none)")
    for s in skipped:
        print(f"  identity_key={s['identity_key']} stage={s['stage']} reason={s['reason']}")
    print()

    print("=== HARD_STOPS ===")
    if result["hard_stop"] is None:
        print("  (none)")
    else:
        print(f"  {result['hard_stop']}")
    print()

    return EXIT_HARD_STOP if result["hard_stop"] is not None else EXIT_COMPLETE


def run(taxonomy: dict, season: str, raw_samples_dir: Path, *, dry_run: bool) -> int:
    if not dry_run:
        print(
            "STOP: pass --dry-run (prints the plan, zero HTTP requests) or --live "
            "(real HTTP requests, bounded to the current UNRESOLVED_INSUFFICIENT_EVIDENCE set)."
        )
        return EXIT_DRY_RUN_REQUIRED

    counts, plan = build_canonical_plan(taxonomy)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    rows = build_missing_evidence_request_plan(taxonomy, season=season, raw_samples_dir=raw_samples_dir)
    excluded = [a for a in audits if a.category != CATEGORY_INSUFFICIENT_EVIDENCE]

    print("Bounded missing-evidence-only request plan (DRY RUN — zero HTTP requests)")
    print(f"season: {season}")
    print(f"total canonical entries: {counts.canonical_requestable_metric_count}")
    print(f"total colliding identity_key groups audited: {len(audits)}")
    print(
        f"excluded (existing-evidence / already-classified) groups NOT in this plan: "
        f"{len(excluded)}"
    )
    print()
    print(f"exact request count: {len(rows)}")
    print()

    for row in rows:
        print(f"identity_key: {row['identity_key']}")
        print(f"  menu1: {row['menu1']}")
        print(f"  menu2: {row['menu2']}")
        print(f"  menu3: {row['menu3']}")
        print(f"  season: {row['season']}")
        print(f"  expected_raw_sample_path: {row['expected_raw_sample_path']}")
        print(f"  raw_sample_exists: {row['raw_sample_exists']}")
        if row["raw_sample_exists"]:
            print(
                "  WARNING: a raw sample now exists at this path but the audit still classified "
                "this identity as INSUFFICIENT_EVIDENCE — investigate before treating this plan "
                "as accurate (possible timing/consistency issue between the audit and this script)."
            )
        if row["warning"]:
            print(f"  WARNING: {row['warning']}")
        print()

    print(
        "Zero HTTP requests made. Phase B2 not authorized. Re-run with --live to actually "
        "fire these requests. This plan excludes every existing-evidence group "
        "(PARTIAL_MATCH_NEEDS_REVIEW / D_UNRESOLVED / already-resolved)."
    )
    return EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--season", required=True, help="Season value the raw samples were/would be fetched for")
    parser.add_argument(
        "--raw-samples-dir",
        default=str(ROOT / "docs" / "discovery" / "raw_samples"),
        help="Directory of already-saved raw responses (scripts/27's/29's raw_samples/ convention).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prints the plan, makes zero HTTP requests. Pass this or --live, not both.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Fires real HTTP requests, bounded to the current UNRESOLVED_INSUFFICIENT_EVIDENCE "
            "set only. Pass this or --dry-run, not both."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=str(ROOT / "data" / "raw_cache" / "http"),
        help="PoliteHttpClient's own disk cache directory (--live only; same one Phase B1/B2 use).",
    )
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    if args.live and args.dry_run:
        print("Pass exactly one of --dry-run or --live, not both.")
        return EXIT_DRY_RUN_REQUIRED

    if args.live:
        from klpga.http_client import PoliteHttpClient

        client = PoliteHttpClient(
            cache_dir=Path(args.cache_dir), on_retry=lambda msg: print(f"[HTTP RETRY] {msg}", flush=True)
        )
        return run_live(client, taxonomy, args.season, Path(args.raw_samples_dir))

    return run(taxonomy, args.season, Path(args.raw_samples_dir), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
