"""Round 12 — THE SEASON-LEVEL METRICS COLLECTOR: a single Windows
entry point that chains state inspection, live acquisition (all 248
canonical official metrics, one or more seasons), parsing, validation,
identity-mapping, and DB ingestion into `official_metric_value` — one
command, one final report, matching `scripts/run_klpga_collector.py`'s
already-proven safe-by-default / SKIP+LOG+CONTINUE pattern.

LOCAL WINDOWS (or any machine with real network access to
klpga.co.kr) IS THE DATA-COLLECTION ENVIRONMENT — this script makes
real HTTP requests when `--live` is passed.

WHAT THIS SCRIPT DOES:
  For each `--seasons` value (comma-separated, e.g. "2023,2024,2025"):
    1. (only with `--live`) acquire every canonical identity_key not
       yet evidenced for that season — reusing `PoliteHttpClient`'s
       existing rate limiting/retry/hard-stop, unchanged. A per-item
       HTTP failure is SKIP + LOG + CONTINUE; a 401/403/429 is a HARD
       STOP that halts only further LIVE requests — every other
       season already queued still gets its offline ingestion step.
    2. Ingest whatever evidence now exists on disk (this run's or a
       prior run's — resumable/idempotent by construction) into
       `official_metric_value`, when `--db-path` is given. Every
       canonical identity/label this run could NOT confidently map to
       a response field (`identity_mapping.py`'s `UNMAPPED_*`
       statuses) is preserved as a structured, reported record —
       never silently dropped, never guessed.
  Prints ONE consolidated final report across every season, only after
  every safe step has run — never intermediate per-command output.

Safe by default: omitting `--live` makes ZERO HTTP requests — only
existing on-disk evidence is ingested (if any) and reported on. This
mirrors `run_klpga_collector.py` and every other script in this
project.

WHAT REMAINS OUT OF SCOPE THIS ROUND (see docs/HISTORICAL_METRICS_
COLLECTION_DESIGN.md): this script never queries a season list from
the database itself (pass `--seasons` explicitly); it never verifies
`loadLocationRecord` player_code against `player_master` (see `klpga.
discovery.season_metric_collector.verify_player_code_identity_space`
— callable separately once a real, populated database exists); PIT
(point-in-time) safety is never asserted, only ever reported as
`PIT_UNVERIFIED`, matching this project's standing policy.

Usage — MANDATORY preview first (zero HTTP requests):
    python scripts\\run_klpga_season_metrics_collector.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
        --seasons 2025

Usage — live acquisition + ingestion:
    python scripts\\run_klpga_season_metrics_collector.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
        --seasons 2023,2024,2025 ^
        --db-path data\\klpga.sqlite ^
        --live
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.season_metric_collector import (  # noqa: E402
    acquire_season_metrics,
    build_official_metric_value_rows,
    ingest_official_metric_value_rows,
)

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_HARD_STOP = 4
EXIT_TAXONOMY_LOAD_FAILED = 5
EXIT_DB_NOT_INITIALIZED = 3


def run(
    client,
    taxonomy: dict,
    seasons: list[str],
    *,
    raw_samples_dir: Path,
    db_path: "Path | None",
    live: bool,
    log=print,
) -> int:
    start = time.perf_counter()
    hard_stop_seasons: list[str] = []
    acquisition_by_season: dict[str, dict] = {}
    mapping_status_totals: Counter = Counter()
    ingested_rows_total = 0
    skipped_total = 0

    conn = None
    if db_path is not None:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")

    for season in seasons:
        log(f"=== SEASON {season} ===")
        if live:
            result = acquire_season_metrics(client, taxonomy, season, raw_samples_dir, log=log)
            acquisition_by_season[season] = result
            skipped_total += len(result["skipped"])
            if result["hard_stop"] is not None:
                hard_stop_seasons.append(season)
                log(f"HARD STOP this season ({season}) — skipping further live requests for it; continuing safe offline work.")

        rows, mapping = build_official_metric_value_rows(taxonomy, season=season, raw_samples_dir=raw_samples_dir)
        for m in mapping:
            mapping_status_totals[m.status] += 1

        if conn is not None and rows:
            n = ingest_official_metric_value_rows(conn, rows)
            ingested_rows_total += n
            log(f"[SEASON {season}] ingested {n} official_metric_value rows")
        elif rows:
            log(f"[SEASON {season}] {len(rows)} rows built but NOT ingested (no --db-path given)")

    if conn is not None:
        conn.close()

    runtime_seconds = time.perf_counter() - start

    log("")
    log("=== FINAL REPORT ===")
    log(f"seasons processed: {seasons}")
    log(f"live acquisition: {live}")
    log(f"runtime: {round(runtime_seconds, 3)}s")
    if live:
        for season, result in acquisition_by_season.items():
            http_success = sum(1 for it in result["items"] if it["http_outcome"] == "HTTP_SUCCESS")
            http_failure = sum(1 for it in result["items"] if it["http_outcome"] == "HTTP_FAILURE")
            log(
                f"  season {season}: expected={result['expected_identities']} "
                f"http_success={http_success} http_failure={http_failure} "
                f"skipped={len(result['skipped'])} hard_stop={result['hard_stop'] is not None}"
            )
    log(f"official_metric_value rows ingested (this run, across all seasons): {ingested_rows_total}")
    log(f"identity/label mapping status totals (cumulative across seasons processed):")
    for status, count in sorted(mapping_status_totals.items()):
        log(f"  {status}: {count}")
    log(f"seasons hard-stopped: {hard_stop_seasons or 'none'}")

    return EXIT_HARD_STOP if hard_stop_seasons else EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument("--seasons", required=True, help="Comma-separated season values, e.g. 2023,2024,2025")
    parser.add_argument(
        "--raw-samples-dir",
        default=str(ROOT / "docs" / "discovery" / "raw_samples"),
        help="Directory of already-saved raw responses (the project-wide raw_samples/ convention).",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(ROOT / "data" / "raw_cache" / "http"),
        help="PoliteHttpClient's own disk cache directory (--live only).",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="klpga.sqlite path to ingest official_metric_value rows into. Omit to skip ingestion (report only).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fire real HTTP requests for every not-yet-evidenced canonical identity, per season. Omit for a safe preview.",
    )
    args = parser.parse_args()

    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.exists():
        print(f"Taxonomy file not found: {taxonomy_path}")
        return EXIT_TAXONOMY_LOAD_FAILED
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]

    db_path = Path(args.db_path) if args.db_path else None
    if db_path is not None and not db_path.exists():
        print(
            f"ERROR: {db_path} does not exist — run src/klpga/db/init_db.py first "
            f"(python -m klpga.db.init_db --db {db_path})."
        )
        return EXIT_DB_NOT_INITIALIZED

    client = None
    if args.live:
        from klpga.http_client import PoliteHttpClient

        client = PoliteHttpClient(
            cache_dir=Path(args.cache_dir), on_retry=lambda msg: print(f"[HTTP RETRY] {msg}", flush=True)
        )

    return run(
        client,
        taxonomy,
        seasons,
        raw_samples_dir=Path(args.raw_samples_dir),
        db_path=db_path,
        live=args.live,
    )


if __name__ == "__main__":
    raise SystemExit(main())
