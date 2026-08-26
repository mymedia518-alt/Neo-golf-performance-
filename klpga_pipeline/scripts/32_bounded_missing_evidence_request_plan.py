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
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.discovery.canonical_plan import build_canonical_plan  # noqa: E402
from klpga.discovery.identity_key_audit import (  # noqa: E402
    CATEGORY_INSUFFICIENT_EVIDENCE,
    CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW,
    CATEGORY_UNRESOLVED,
    audit_identity_key_collisions,
)
from klpga.discovery.record_fetch import fetch_and_analyze, request_form, sanitize_identity_key_for_filename  # noqa: E402
from klpga.discovery.sampler import _canonical_entry_to_leaf_dict, _leaf_from_dict  # noqa: E402
from klpga.http_client import RateLimitBlockedError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_TAXONOMY_LOAD_FAILED = 5
EXIT_DRY_RUN_REQUIRED = 2
EXIT_HARD_STOP = 4
"""Mirrors scripts/29's EXIT_BLOCKED=4 — a 401/403/429 hard stop is not
a script bug, but it is not a clean completion either: the caller
should notice."""

_UNRESOLVED_AUDIT_CATEGORIES = frozenset(
    {CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW, CATEGORY_UNRESOLVED, CATEGORY_INSUFFICIENT_EVIDENCE}
)


def build_missing_evidence_request_plan(
    taxonomy: dict, *, season: str, raw_samples_dir: Path
) -> list[dict]:
    """Returns one row per `UNRESOLVED_INSUFFICIENT_EVIDENCE`
    `request_identity_key`, sorted for determinism. Every field is
    derived from evidence/logic that already exists elsewhere in this
    project (`build_canonical_plan`, `audit_identity_key_collisions`,
    `request_form`, `sanitize_identity_key_for_filename`) — nothing
    new is invented here."""
    counts, plan = build_canonical_plan(taxonomy)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    missing = [a for a in audits if a.category == CATEGORY_INSUFFICIENT_EVIDENCE]
    missing_keys = sorted(a.request_identity_key for a in missing)

    by_key: dict[str, dict] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], entry)

    rows: list[dict] = []
    for key in missing_keys:
        entry = by_key.get(key)
        if entry is None:
            # Should not happen — every audited identity_key comes
            # directly from this same canonical plan — but never
            # silently skip a real inconsistency.
            rows.append(
                {
                    "identity_key": key,
                    "menu1": None,
                    "menu2": None,
                    "menu3": None,
                    "season": season,
                    "expected_raw_sample_path": None,
                    "raw_sample_exists": None,
                    "warning": "No matching canonical plan entry found for this identity_key.",
                }
            )
            continue
        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        form = request_form(leaf, season)
        raw_path = raw_samples_dir / f"{sanitize_identity_key_for_filename(key)}__{season}.html"
        rows.append(
            {
                "identity_key": key,
                "menu1": form.get("menu1"),
                "menu2": form.get("menu2"),
                "menu3": form.get("menu3"),
                "season": form.get("season"),
                "expected_raw_sample_path": str(raw_path),
                "raw_sample_exists": raw_path.exists(),
                "warning": None,
            }
        )
    return rows


def _category_counts(audits: list) -> dict:
    """Tallies one audit run's `GroupAudit.category` values, plus a
    `total_unresolved` (PARTIAL + D_UNRESOLVED + INSUFFICIENT_EVIDENCE
    — matching scripts/31's own SUMMARY definition exactly, so a
    BEFORE/AFTER comparison here means the same thing it does there)
    and `total_groups`. Never forces any count to zero — this is a
    plain tally of whatever the audit actually returned."""
    counts: dict[str, int] = {}
    for a in audits:
        counts[a.category] = counts.get(a.category, 0) + 1
    counts["total_unresolved"] = sum(counts.get(c, 0) for c in _UNRESOLVED_AUDIT_CATEGORIES)
    counts["total_groups"] = len(audits)
    return counts


def _cache_live_distinction(client, leaf, season: str) -> str:
    """Best-effort, NEVER guessed: "CACHE_HIT" if `PoliteHttpClient`'s
    own disk cache already held this exact request's response before
    this run touched it, "LIVE_FETCH" if not, "NOT_AVAILABLE" if this
    cannot be determined at all (e.g. a test double that doesn't
    expose the same cache internals, or any other lookup failure) —
    per explicit instruction, an undeterminable distinction is reported
    honestly rather than guessed either way."""
    try:
        form = request_form(leaf, season)
        cache_path = client._cache_path(config.RECORD_TAXONOMY_ENDPOINT, {"data": form})
        return "CACHE_HIT" if cache_path.exists() else "LIVE_FETCH"
    except Exception:  # noqa: BLE001 — genuinely any lookup failure means "cannot determine", not a bug.
        return "NOT_AVAILABLE"


def acquire_missing_evidence(
    client, taxonomy: dict, season: str, raw_samples_dir: Path, *, log: Callable[[str], None] = print
) -> dict:
    """Live-fire acquisition. Makes a real HTTP request (via `client` —
    a `PoliteHttpClient` or, in tests, a compatible fake) for EVERY
    identity_key `build_missing_evidence_request_plan` currently lists
    — i.e. every `UNRESOLVED_INSUFFICIENT_EVIDENCE` group, derived
    fresh right now — and only those. Never touches a `PARTIAL_MATCH_
    NEEDS_REVIEW`/`D_UNRESOLVED`/already-resolved group; never fires a
    request for an identity whose expected raw-sample file already
    exists (re-checked immediately before each request, not just once
    at plan-build time).

    A per-item HTTP failure (exhausted retries on a 5xx/timeout, etc.)
    is a LOCAL blocker: recorded in `items` with `http_outcome=
    "HTTP_FAILURE"`, and acquisition continues to the next identity. A
    `RateLimitBlockedError` (401/403/429) is a HARD safety blocker: it
    halts every further live request for the REMAINDER of this run
    (never retried, never bypassed) — every identity not yet attempted
    is recorded in `skipped` with a reason naming the hard stop, and
    this function still returns a full, valid report of whatever was
    collected before it. Never raises.

    Reruns `audit_identity_key_collisions` twice — once before any
    request (to capture the true BEFORE baseline) and once after
    acquisition (or the hard stop) completes — and returns both as
    plain category-count dicts, never forcing a category to zero."""
    _counts, plan = build_canonical_plan(taxonomy)
    by_key: dict[str, dict] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], entry)

    audits_before = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    before_counts = _category_counts(audits_before)

    rows = build_missing_evidence_request_plan(taxonomy, season=season, raw_samples_dir=raw_samples_dir)

    items: list[dict] = []
    skipped: list[dict] = []
    hard_stop: dict | None = None

    for i, row in enumerate(rows, start=1):
        identity_key = row["identity_key"]
        expected_path = Path(row["expected_raw_sample_path"]) if row["expected_raw_sample_path"] else None

        if hard_stop is not None:
            skipped.append(
                {
                    "identity_key": identity_key,
                    "stage": "acquisition",
                    "reason": (
                        f"not attempted — a hard safety stop already occurred this run on "
                        f"{hard_stop['identity_key']}"
                    ),
                }
            )
            continue

        entry = by_key.get(identity_key)
        if entry is None:
            skipped.append(
                {
                    "identity_key": identity_key,
                    "stage": "plan_lookup",
                    "reason": row.get("warning") or "no matching canonical plan entry found",
                }
            )
            continue

        if expected_path is not None and expected_path.exists():
            skipped.append(
                {
                    "identity_key": identity_key,
                    "stage": "pre_request_check",
                    "reason": (
                        "a raw sample already exists at the expected path — outside this run's "
                        "scope, never overwritten, never requested"
                    ),
                }
            )
            continue

        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        cache_live = _cache_live_distinction(client, leaf, season)
        attempt_timestamp = datetime.now(timezone.utc).isoformat()

        try:
            parsed, analysis, _log_entry = fetch_and_analyze(
                client, leaf, season, tag=f"{i}/{len(rows)}", raw_dir=raw_samples_dir, log=log
            )
        except RateLimitBlockedError as exc:
            hard_stop = {"identity_key": identity_key, "error": str(exc), "timestamp": attempt_timestamp}
            log(f"HARD STOP on {identity_key}: {exc} — not retrying, not bypassing, halting further live requests this run.")
            skipped.append(
                {"identity_key": identity_key, "stage": "acquisition", "reason": f"hard safety stop: {exc}"}
            )
            continue
        except Exception as exc:  # noqa: BLE001 — a per-item HTTP failure must not abort the whole run.
            log(f"HTTP_FAILURE for {identity_key}: {exc}")
            items.append(
                {
                    "identity_key": identity_key,
                    "menu1": entry.get("menu1"),
                    "menu2": entry.get("menu2"),
                    "menu3": entry.get("menu3"),
                    "season": season,
                    "cache_live_distinction": cache_live,
                    "http_outcome": "HTTP_FAILURE",
                    "error": str(exc),
                    "raw_sample_path": None,
                    "response_size": None,
                    "timestamp": attempt_timestamp,
                    "parse_status": None,
                    "player_row_count": None,
                    "schema_fingerprint": None,
                    "missing_player_code": None,
                    "missing_player_name": None,
                    "blank_values": None,
                    "non_numeric_numeric_fields": None,
                    "duplicate_player_rows": None,
                    "data_quality_any_flagged": None,
                }
            )
            continue

        dq = analysis.data_quality
        response_size = expected_path.stat().st_size if expected_path is not None and expected_path.exists() else None
        items.append(
            {
                "identity_key": identity_key,
                "menu1": entry.get("menu1"),
                "menu2": entry.get("menu2"),
                "menu3": entry.get("menu3"),
                "season": season,
                "cache_live_distinction": cache_live,
                "http_outcome": "HTTP_SUCCESS",
                "error": None,
                "raw_sample_path": str(expected_path) if expected_path is not None else None,
                "response_size": response_size,
                "timestamp": attempt_timestamp,
                "parse_status": parsed.parse_status,
                "player_row_count": len(parsed.rows),
                "schema_fingerprint": analysis.schema_fingerprint,
                "missing_player_code": dq.missing_player_code,
                "missing_player_name": dq.missing_player_name,
                "blank_values": dq.blank_values,
                "non_numeric_numeric_fields": dq.non_numeric_numeric_fields,
                "duplicate_player_rows": dq.duplicate_player_rows,
                "data_quality_any_flagged": dq.any_flagged,
            }
        )

    audits_after = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    after_counts = _category_counts(audits_after)

    return {
        "expected_missing_evidence_identities": len(rows),
        "processed": len(items) + len(skipped),
        "items": items,
        "skipped": skipped,
        "hard_stop": hard_stop,
        "before_counts": before_counts,
        "after_counts": after_counts,
    }


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
