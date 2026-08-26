"""Phase B1 — KLPGA response-schema discovery over a REPRESENTATIVE
SAMPLE only (~12-20 metrics). Read-only, no DB writes, no Prediction/
model/archive access.

Reads an already-produced Phase A taxonomy JSON (see
scripts/26_discover_klpga_record_taxonomy.py), selects a small,
deterministic, cross-family sample (never the full discovered
taxonomy — see klpga.discovery.sampler), fires exactly one live
request per sampled metric against the already-confirmed
`/load/record/loadLocationRecord` endpoint, parses and analyzes each
response (schema fingerprint, raw-count-pair detection, sample-size
fields, RTP presence, data-quality checks), and writes:

  docs/discovery/KLPGA_RESPONSE_SCHEMA_SAMPLES.json
  docs/discovery/KLPGA_RESPONSE_SCHEMA_SAMPLES.csv
  docs/discovery/KLPGA_RESPONSE_SCHEMA_REPORT.md
  docs/discovery/KLPGA_RAW_FIELD_INVENTORY.md
  docs/discovery/NEO_RAW_INPUT_CANDIDATES.md
  docs/discovery/KLPGA_RAW_COUNT_METRICS.csv
  docs/discovery/KLPGA_PLAYER_IDENTITY_REPORT.md
  docs/discovery/KLPGA_RESPONSE_FAILURES.csv
  docs/discovery/KLPGA_PHASE_B1_REQUEST_LOG.json / .csv
  docs/discovery/raw_samples/<identity_key>__<season>.html  (one per
    sampled metric — Phase B1.1 raw-evidence preservation, see Mission
    3; gitignored, never auto-committed; disable with --no-raw-samples)

Then STOPS. This script does NOT proceed to a full 283-metric sweep —
that is Phase B2, a separate, not-yet-authorized step. An optional
minimal historical-season probe (--historical-season) tests at most 3
of the sampled metrics against a second season value — never a sweep
across many years.

Every metric is classified `pit_status="PIT_UNVERIFIED"` unconditionally
— see klpga.discovery.response_schema's module docstring. Nothing in
this script may promote a metric to PIT-safe.

Failure behavior: a 401/403/429 (RateLimitBlockedError) from the site
halts the ENTIRE run immediately — partial results collected so far
are still written, but no further request is attempted. An individual
metric's malformed/unexpected response does NOT halt the run; it is
classified FAILED/AMBIGUOUS and the run continues to the next sampled
metric.

Usage (on a machine with real internet access to klpga.co.kr):
    python scripts\\27_klpga_response_schema_sample.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
        --season 2025

Phase B1.1 diagnostic instrumentation: every meaningful step prints a
flushed `[STEP nn]`/`[REQUEST i/N]`/`[RESPONSE i/N]`/`[PARSE i/N]`
marker (see `_log()` below) — added after a Windows run produced no
visible output at all before it had to be Ctrl+C'd, so it was
impossible to tell whether it hung during imports, taxonomy loading,
HTTP setup, or a request. `flush=True` on every print defeats Python's
default line-buffering-only-on-a-real-console behavior, which is the
most likely single explanation for "zero output" when nothing in this
script was actually silent before this round — see
docs/KLPGA_OFFICIAL_DATA_MAP.md's Phase B1.1 diagnostic section for
the full reasoning and the worst-case-per-request timing math.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

print("[STEP 01] script started (stdlib imports complete)", flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.discovery.request_log import build_log_entry, to_log_csv, to_log_jsonl  # noqa: E402
from klpga.discovery.response_parser import parse_record_response  # noqa: E402
from klpga.discovery.response_schema import (  # noqa: E402
    analyze_response,
    build_player_identity_report,
    classify_historical_availability,
)
from klpga.discovery.sampler import (  # noqa: E402
    SampledLeaf,
    find_duplicate_identities,
    reject_malformed_leaves,
    reject_navigation_container_leaves,
    select_representative_sample,
)
from klpga.discovery.schema_report import (  # noqa: E402
    build_request_outcome_counts,
    build_sample_record,
    render_neo_raw_input_candidates_markdown,
    render_player_identity_report_markdown,
    render_raw_field_inventory_markdown,
    render_schema_report_markdown,
    write_raw_count_metrics_csv,
    write_response_failures_csv,
    write_samples_csv,
    write_samples_json,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

print("[STEP 02] klpga package imports complete", flush=True)

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_BLOCKED = 4
EXIT_TAXONOMY_LOAD_FAILED = 5

DEFAULT_SAMPLE_SIZE = 20
DEFAULT_MAX_REQUESTS = 28  # sample_size + headroom for the historical probe (<=3), a hard circuit breaker

_LAST_MARKER = {"text": "no marker recorded yet"}
"""Updated by every `_log()` call — read by the top-level
KeyboardInterrupt handler so a Ctrl+C can report exactly where
execution was, per Mission 4's diagnostic requirement."""


def _log(msg: str) -> None:
    """print() with flush=True, always — see module docstring. Also
    records the message as the last-known execution point for the
    top-level KeyboardInterrupt handler."""
    _LAST_MARKER["text"] = msg
    print(msg, flush=True)


def _request_form(leaf: SampledLeaf, season: str) -> dict:
    """TYPE A (menu2-level) or TYPE B (menu3-level) request shape, per
    the already-confirmed evidence — never a third shape."""
    form = {"season": season, "menu1": leaf.menu1, "menu2": leaf.menu2}
    if leaf.leaf_level == "menu3":
        form["menu3"] = leaf.menu3
    return form


def _sanitize_identity_key_for_filename(key: str) -> str:
    """"Approach::Approach01::020101" -> "Approach__Approach01__020101"
    — filesystem-safe, still human-readable and traceable back to the
    exact canonical identity, unlike PoliteHttpClient's own hash-keyed
    cache filenames."""
    return key.replace("::", "__").replace("/", "_").replace("\\", "_")


def fetch_and_analyze(
    client: PoliteHttpClient, leaf: SampledLeaf, season: str, *, tag: str = "?", raw_dir: Path | None = None
):
    """Returns (parsed, analysis, log_entry). Raises RateLimitBlockedError
    unmodified — the caller decides whether that halts the whole run.
    `tag` (e.g. "3/20" or "HIST 1/3") is purely for the REQUEST/
    RESPONSE/PARSE diagnostic markers below — it plays no role in the
    request itself.

    `raw_dir`, if given, saves the exact raw response body to
    `raw_dir/<identity_key>__<season>.html` — Phase B1.1's raw-evidence
    preservation (see Mission 3): PoliteHttpClient already caches every
    response under data/raw_cache/http/ keyed by an opaque content
    hash, which technically preserves the bytes but makes finding "the
    Putt::Putt01::040101 response" by hand impractical. This writes a
    second, small, human-named copy — bounded by the sample size (the
    same hard cap already governing live requests), never unbounded."""
    form = _request_form(leaf, season)
    _log(f"[REQUEST {tag}] menu1={leaf.menu1!r} menu2={leaf.menu2!r} menu3={leaf.menu3!r} season={season!r}")
    timestamp = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    html = client.post_text(config.RECORD_TAXONOMY_ENDPOINT, data=form)
    elapsed = time.perf_counter() - start
    _log(f"[RESPONSE {tag}] status=200(assumed — client raises on 401/403/429/5xx) bytes={len(html)} elapsed={elapsed:.2f}s")
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{_sanitize_identity_key_for_filename(leaf.source_metric_key)}__{season}.html"
        raw_path.write_text(html, encoding="utf-8")
        _log(f"[RAW SAVED {tag}] {raw_path}")
    parsed = parse_record_response(html)
    _log(f"[PARSE {tag}] parse_status={parsed.parse_status} rows={len(parsed.rows)}")
    analysis = analyze_response(parsed)
    log_entry = build_log_entry(
        timestamp=timestamp,
        endpoint=config.RECORD_TAXONOMY_ENDPOINT,
        method="POST",
        season=season,
        menu1=leaf.menu1,
        menu2=leaf.menu2,
        menu3=leaf.menu3,
        canonical_identity=leaf.source_metric_key,
        http_status=200,  # PoliteHttpClient raises rather than returning a non-2xx Response
        response_size=len(html),
        parse_status=parsed.parse_status,
    )
    return parsed, analysis, log_entry


def run(
    client: PoliteHttpClient,
    taxonomy: dict,
    season: str,
    out_dir: Path,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    max_requests: int = DEFAULT_MAX_REQUESTS,
    historical_season: str | None = None,
    save_raw_responses: bool = True,
) -> int:
    raw_dir = (out_dir / "raw_samples") if save_raw_responses else None
    _log("[STEP 03] taxonomy loading (rejecting malformed leaves and navigation containers)")
    raw_leaves = taxonomy.get("leaves", [])
    valid_leaves, rejected_leaves = reject_malformed_leaves(raw_leaves)
    valid_leaves, rejected_navigation = reject_navigation_container_leaves(valid_leaves)
    _log(f"[STEP 04] taxonomy loaded: {len(raw_leaves)} leaves ({len(valid_leaves)} requestable)")
    if rejected_leaves:
        _log(
            f"[STEP 05] malformed leaves rejected: {len(rejected_leaves)} "
            f"(blank/missing menu1 or menu2 — never a requestable metric): "
            f"{[d.get('source_metric_key', d) for d in rejected_leaves]}"
        )
    else:
        _log("[STEP 05] malformed leaves rejected: 0")
    if rejected_navigation:
        _log(
            f"[STEP 05b] navigation/container leaves rejected: {len(rejected_navigation)} "
            f"(e.g. menu1=\"All\" — confirmed by real evidence to return a navigation menu "
            f"page, not player data, never a requestable metric): "
            f"{[d.get('source_metric_key', d) for d in rejected_navigation]}"
        )
    else:
        _log("[STEP 05b] navigation/container leaves rejected: 0")
    sample = select_representative_sample({**taxonomy, "leaves": valid_leaves}, target_count=sample_size)
    _log(f"[STEP 06] representative sample selected: {len(sample)} (from {len(valid_leaves)} requestable leaves)")

    duplicates = find_duplicate_identities(sample)
    if duplicates:
        _log(f"WARNING: sampler produced duplicate identities (sampler bug, not a taxonomy finding): {duplicates}")

    records: list[dict] = []
    parsed_by_key = {}  # source_metric_key -> ParsedRecordResponse, kept for the historical comparison below
    log_entries = []
    request_count = 0
    http_failure_count = 0
    blocked = False

    for i, leaf in enumerate(sample, start=1):
        if request_count >= max_requests:
            _log(f"Reached --max-requests={max_requests} — stopping before {leaf.source_metric_key}.")
            break
        try:
            parsed, analysis, log_entry = fetch_and_analyze(
                client, leaf, season, tag=f"{i}/{len(sample)}", raw_dir=raw_dir
            )
            request_count += 1
        except RateLimitBlockedError as exc:
            _log(f"BLOCKED on {leaf.source_metric_key}: {exc}")
            _log("Not retrying, not bypassing — halting the run per instruction. Partial results below are still written.")
            blocked = True
            break
        except Exception as exc:  # noqa: BLE001 — an HTTP-layer failure must not abort the whole sample run.
            # parse_record_response() never raises (it degrades to
            # parse_status="FAILED" internally per its own docstring),
            # so any exception reaching here is treated as an
            # HTTP_FAILURE, not a parse failure — see Mission 7.
            _log(f"HTTP_FAILURE fetching {leaf.source_metric_key}: {exc}")
            request_count += 1
            http_failure_count += 1
            continue

        record = build_sample_record(leaf, season=season, http_status=200, parsed=parsed, analysis=analysis)
        records.append(record)
        parsed_by_key[leaf.source_metric_key] = parsed
        log_entries.append(log_entry)
        _log(f"  [{parsed.parse_status}] {leaf.source_metric_key} — {len(parsed.rows)} rows, schema={analysis.schema_fingerprint}")

    historical_probe_records: list[dict] = []
    if historical_season and not blocked and records:
        probe_leaves = _pick_historical_probe_leaves(sample, records)
        for j, (leaf, current_record) in enumerate(probe_leaves, start=1):
            if request_count >= max_requests:
                _log(f"Reached --max-requests={max_requests} — stopping historical probe.")
                break
            try:
                hist_parsed, hist_analysis, hist_log = fetch_and_analyze(
                    client, leaf, historical_season, tag=f"HIST {j}/{len(probe_leaves)}", raw_dir=raw_dir
                )
                request_count += 1
            except RateLimitBlockedError as exc:
                _log(f"BLOCKED during historical probe on {leaf.source_metric_key}: {exc}")
                blocked = True
                break
            except Exception as exc:  # noqa: BLE001
                _log(f"FAILED historical probe for {leaf.source_metric_key}: {exc}")
                request_count += 1
                continue

            log_entries.append(hist_log)
            current_parsed = parsed_by_key[leaf.source_metric_key]
            classification = classify_historical_availability(current=current_parsed, historical=hist_parsed)
            current_record["historical_availability"] = classification
            historical_probe_records.append(current_record)
            _log(f"  [historical probe] {leaf.source_metric_key} @ {historical_season}: {classification}")

    out_dir.mkdir(parents=True, exist_ok=True)
    discovered_at = datetime.now(timezone.utc).isoformat()

    (out_dir / "KLPGA_RESPONSE_SCHEMA_SAMPLES.json").write_text(
        write_samples_json(records, discovered_at=discovered_at, source_taxonomy=str(taxonomy.get("source_url", "unknown"))),
        encoding="utf-8",
    )
    (out_dir / "KLPGA_RESPONSE_SCHEMA_SAMPLES.csv").write_text(write_samples_csv(records), encoding="utf-8")
    outcome_counts = build_request_outcome_counts(records, http_failure_count=http_failure_count)
    (out_dir / "KLPGA_RESPONSE_SCHEMA_REPORT.md").write_text(
        render_schema_report_markdown(
            records,
            request_count=request_count,
            historical_probe_records=historical_probe_records or None,
            outcome_counts=outcome_counts,
        ),
        encoding="utf-8",
    )
    (out_dir / "KLPGA_RAW_FIELD_INVENTORY.md").write_text(render_raw_field_inventory_markdown(records), encoding="utf-8")
    (out_dir / "NEO_RAW_INPUT_CANDIDATES.md").write_text(render_neo_raw_input_candidates_markdown(records), encoding="utf-8")
    (out_dir / "KLPGA_RAW_COUNT_METRICS.csv").write_text(write_raw_count_metrics_csv(records), encoding="utf-8")
    (out_dir / "KLPGA_RESPONSE_FAILURES.csv").write_text(write_response_failures_csv(records), encoding="utf-8")

    identity_overall, identity_records = build_player_identity_report(parsed_by_key)
    (out_dir / "KLPGA_PLAYER_IDENTITY_REPORT.md").write_text(
        render_player_identity_report_markdown(identity_overall, identity_records), encoding="utf-8"
    )

    (out_dir / "KLPGA_PHASE_B1_REQUEST_LOG.json").write_text(to_log_jsonl(log_entries), encoding="utf-8")
    (out_dir / "KLPGA_PHASE_B1_REQUEST_LOG.csv").write_text(to_log_csv(log_entries), encoding="utf-8")

    print()
    _log(f"Cross-metric playerCode identity consistency: {identity_overall}")
    _log(f"Live requests made: {request_count}")
    _log(
        f"HTTP_SUCCESS: {outcome_counts['http_success']}  HTTP_FAILURE: {outcome_counts['http_failure']}  "
        f"PARSE_SUCCESS: {outcome_counts['parse_success']}  PARSE_EMPTY: {outcome_counts['parse_empty']}  "
        f"PARSE_AMBIGUOUS_OR_FAILED: {outcome_counts['parse_ambiguous_or_failed']}"
    )
    _log(f"Metrics with real parsed data (PARSE_SUCCESS): {outcome_counts['parse_success']}")
    _log(f"Output written to: {out_dir}")
    if raw_dir is not None:
        _log(f"Raw response HTML saved to: {raw_dir} (one file per sampled metric, human-named)")

    if blocked:
        return EXIT_BLOCKED
    return EXIT_COMPLETE


def _pick_historical_probe_leaves(sample: list[SampledLeaf], records: list[dict]) -> list[tuple[SampledLeaf, dict]]:
    """Prefer one SG metric, one rate/count metric, one distance/
    average metric — capped at 3, per instruction. Selection is over
    ALREADY-SAMPLED metrics only, never a new pick outside the sample."""
    by_key = {leaf.source_metric_key: leaf for leaf in sample}
    picked: list[tuple[SampledLeaf, dict]] = []

    sg = next((r for r in records if r["menu1"] == "Sg"), None)
    if sg:
        picked.append((by_key[sg["identity_key"]], sg))

    rate_count = next(
        (r for r in records if r["raw_pair_status"] in ("CONFIRMED_RAW_PAIR", "PARTIAL_RAW_PAIR") and r is not sg),
        None,
    )
    if rate_count:
        picked.append((by_key[rate_count["identity_key"]], rate_count))

    remaining = [r for r in records if r not in (sg, rate_count)]
    if remaining:
        picked.append((by_key[remaining[0]["identity_key"]], remaining[0]))

    return picked[:3]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to a Phase A KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--season", required=True, help="Season value to request (e.g. 2025) — not guessed")
    parser.add_argument("--historical-season", default=None, help="Optional prior season for a minimal (<=3 metric) historical probe")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS, help="Hard cap on live requests this run, independent of --sample-size")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "discovery"))
    parser.add_argument(
        "--no-raw-samples",
        action="store_true",
        help=(
            "Skip saving a human-named raw HTML copy per sampled metric to <out-dir>/raw_samples/ "
            "(Phase B1.1 evidence preservation — on by default, bounded by --sample-size/--max-requests)."
        ),
    )
    args = parser.parse_args()

    _log(f"[STEP 03] taxonomy loading: {args.taxonomy}")
    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        _log(f"Taxonomy file not found: {taxonomy_path}")
        _log("Run scripts/26_discover_klpga_record_taxonomy.py first.")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    _log(f"[STEP 04] taxonomy loaded: {len(taxonomy.get('leaves', []))} leaves")

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir), on_retry=lambda msg: _log(f"[HTTP RETRY] {msg}"))
    _log(
        f"[STEP 07] HTTP client initialized "
        f"(timeout={client.timeout_sec}s, min_interval={client.min_interval_sec}s, cache_dir={client.cache_dir})"
    )
    # NOTE: STEP 05/06 (malformed-leaf rejection, representative sample
    # selection) print from inside run() itself, since they operate on
    # the taxonomy dict run() receives, not on anything main() computes
    # separately.
    return run(
        client,
        taxonomy,
        args.season,
        Path(args.out_dir),
        sample_size=args.sample_size,
        max_requests=args.max_requests,
        historical_season=args.historical_season,
        save_raw_responses=not args.no_raw_samples,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # Diagnostic only — the interrupt is NEVER swallowed, it is
        # re-raised immediately after reporting where execution was.
        print(f"\n[INTERRUPTED] Last known step: {_LAST_MARKER['text']}", flush=True)
        raise
