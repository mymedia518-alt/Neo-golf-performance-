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
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_BLOCKED = 4
EXIT_TAXONOMY_LOAD_FAILED = 5

DEFAULT_SAMPLE_SIZE = 20
DEFAULT_MAX_REQUESTS = 28  # sample_size + headroom for the historical probe (<=3), a hard circuit breaker


def _request_form(leaf: SampledLeaf, season: str) -> dict:
    """TYPE A (menu2-level) or TYPE B (menu3-level) request shape, per
    the already-confirmed evidence — never a third shape."""
    form = {"season": season, "menu1": leaf.menu1, "menu2": leaf.menu2}
    if leaf.leaf_level == "menu3":
        form["menu3"] = leaf.menu3
    return form


def fetch_and_analyze(client: PoliteHttpClient, leaf: SampledLeaf, season: str):
    """Returns (parsed, analysis, log_entry). Raises RateLimitBlockedError
    unmodified — the caller decides whether that halts the whole run."""
    form = _request_form(leaf, season)
    timestamp = datetime.now(timezone.utc).isoformat()
    html = client.post_text(config.RECORD_TAXONOMY_ENDPOINT, data=form)
    parsed = parse_record_response(html)
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
) -> int:
    raw_leaves = taxonomy.get("leaves", [])
    valid_leaves, rejected_leaves = reject_malformed_leaves(raw_leaves)
    if rejected_leaves:
        print(
            f"Rejected {len(rejected_leaves)} malformed taxonomy leaf(ies) before sampling "
            f"(blank/missing menu1 or menu2 — never a requestable metric): "
            f"{[d.get('source_metric_key', d) for d in rejected_leaves]}"
        )
    sample = select_representative_sample({**taxonomy, "leaves": valid_leaves}, target_count=sample_size)
    print(f"Selected {len(sample)} representative metrics from a taxonomy of {len(raw_leaves)} leaves ({len(valid_leaves)} valid).")

    duplicates = find_duplicate_identities(sample)
    if duplicates:
        print(f"WARNING: sampler produced duplicate identities (sampler bug, not a taxonomy finding): {duplicates}")

    records: list[dict] = []
    parsed_by_key = {}  # source_metric_key -> ParsedRecordResponse, kept for the historical comparison below
    log_entries = []
    request_count = 0
    http_failure_count = 0
    blocked = False

    for leaf in sample:
        if request_count >= max_requests:
            print(f"Reached --max-requests={max_requests} — stopping before {leaf.source_metric_key}.")
            break
        try:
            parsed, analysis, log_entry = fetch_and_analyze(client, leaf, season)
            request_count += 1
        except RateLimitBlockedError as exc:
            print(f"BLOCKED on {leaf.source_metric_key}: {exc}")
            print("Not retrying, not bypassing — halting the run per instruction. Partial results below are still written.")
            blocked = True
            break
        except Exception as exc:  # noqa: BLE001 — an HTTP-layer failure must not abort the whole sample run.
            # parse_record_response() never raises (it degrades to
            # parse_status="FAILED" internally per its own docstring),
            # so any exception reaching here is treated as an
            # HTTP_FAILURE, not a parse failure — see Mission 7.
            print(f"HTTP_FAILURE fetching {leaf.source_metric_key}: {exc}")
            request_count += 1
            http_failure_count += 1
            continue

        record = build_sample_record(leaf, season=season, http_status=200, parsed=parsed, analysis=analysis)
        records.append(record)
        parsed_by_key[leaf.source_metric_key] = parsed
        log_entries.append(log_entry)
        print(f"  [{parsed.parse_status}] {leaf.source_metric_key} — {len(parsed.rows)} rows, schema={analysis.schema_fingerprint}")

    historical_probe_records: list[dict] = []
    if historical_season and not blocked and records:
        probe_leaves = _pick_historical_probe_leaves(sample, records)
        for leaf, current_record in probe_leaves:
            if request_count >= max_requests:
                print(f"Reached --max-requests={max_requests} — stopping historical probe.")
                break
            try:
                hist_parsed, hist_analysis, hist_log = fetch_and_analyze(client, leaf, historical_season)
                request_count += 1
            except RateLimitBlockedError as exc:
                print(f"BLOCKED during historical probe on {leaf.source_metric_key}: {exc}")
                blocked = True
                break
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED historical probe for {leaf.source_metric_key}: {exc}")
                request_count += 1
                continue

            log_entries.append(hist_log)
            current_parsed = parsed_by_key[leaf.source_metric_key]
            classification = classify_historical_availability(current=current_parsed, historical=hist_parsed)
            current_record["historical_availability"] = classification
            historical_probe_records.append(current_record)
            print(f"  [historical probe] {leaf.source_metric_key} @ {historical_season}: {classification}")

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
    print(f"Cross-metric playerCode identity consistency: {identity_overall}")
    print(f"Live requests made: {request_count}")
    print(
        f"HTTP_SUCCESS: {outcome_counts['http_success']}  HTTP_FAILURE: {outcome_counts['http_failure']}  "
        f"PARSE_SUCCESS: {outcome_counts['parse_success']}  PARSE_EMPTY: {outcome_counts['parse_empty']}  "
        f"PARSE_AMBIGUOUS_OR_FAILED: {outcome_counts['parse_ambiguous_or_failed']}"
    )
    print(f"Metrics with real parsed data (PARSE_SUCCESS): {outcome_counts['parse_success']}")
    print(f"Output written to: {out_dir}")

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
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        print("Run scripts/26_discover_klpga_record_taxonomy.py first.")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    return run(
        client,
        taxonomy,
        args.season,
        Path(args.out_dir),
        sample_size=args.sample_size,
        max_requests=args.max_requests,
        historical_season=args.historical_season,
    )


if __name__ == "__main__":
    raise SystemExit(main())
