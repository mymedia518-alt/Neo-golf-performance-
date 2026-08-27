"""Round 13 — THE SEASON-LEVEL METRICS COLLECTOR: a single Windows
entry point that chains state inspection, live acquisition (all 248
canonical official metrics, one or more seasons), parsing, validation,
identity-mapping, DB ingestion into `official_metric_value`, and
post-acquisition verification — one command, one final report,
matching `scripts/run_klpga_collector.py`'s already-proven
safe-by-default / SKIP+LOG+CONTINUE pattern.

LOCAL WINDOWS (or any machine with real network access to
klpga.co.kr) IS THE DATA-COLLECTION ENVIRONMENT — this script makes
real HTTP requests when `--live` is passed.

WHAT THIS SCRIPT DOES:
  0. Season selection: pass `--seasons` explicitly (comma-separated,
     e.g. "2023,2024,2025"), OR omit it and pass `--db-path` — the
     script then reads the DISTINCT `season` values already present in
     `tournament_master` (the 100-tournament corpus this project's
     earlier phases already collected) using Python's built-in
     `sqlite3` module. No external `sqlite3` CLI is used anywhere in
     this project; none is required on the machine running this
     script.
  For each season:
    1. (only with `--live`) acquire every canonical identity_key not
       yet evidenced for that season — reusing `PoliteHttpClient`'s
       existing rate limiting/retry/hard-stop, unchanged. A per-item
       HTTP failure is SKIP + LOG + CONTINUE; a 401/403/429 is a HARD
       STOP that halts only further LIVE requests — every other
       season already queued still gets its offline ingestion step.
       Checkpoint/resume is the same ground-truth-on-disk pattern this
       project already uses everywhere: a raw response file already
       present for an identity/season IS the checkpoint, so re-running
       this script (after an interruption, or on a later day) only
       ever requests what is still missing — never re-fetches, never
       loses prior progress.
    2. Ingest whatever evidence now exists on disk (this run's or a
       prior run's) into `official_metric_value`, when `--db-path` is
       given. Every canonical identity/label this run could NOT
       confidently map to a response field (`identity_mapping.py`'s
       `UNMAPPED_*` statuses) is preserved as a structured, reported
       record — never silently dropped, never guessed.
    3. Re-run the canonical-plan sanity invariants and the identity-
       key collision audit against the evidence now on disk for that
       season (the same read-only diagnostics scripts 28/31 already
       provide — reused, not reimplemented).
  After every season:
    4. Player identity verification: compares the REAL set of
       `player_code` values seen across every saved raw response
       against the REAL set of `player_master.player_id` values in
       `--db-path` (when given) — matched count, unmatched count,
       match %, sample unmatched, and an explicit verdict on whether a
       direct join is safe. Never assumes compatibility; never
       fabricates either input set.
    5. Database completeness check: a plain read-only tally over
       `official_metric_value` itself — total rows, seasons present,
       distinct identities/players covered, rows with a NULL parsed
       value, and FLAGGED rows.
  Prints ONE consolidated final report covering all of the above, only
  after every safe step has run — never intermediate per-command
  output.

Safe by default: omitting `--live` makes ZERO HTTP requests — only
existing on-disk evidence is ingested (if any) and reported on. This
mirrors `run_klpga_collector.py` and every other script in this
project.

WHAT REMAINS OUT OF SCOPE THIS ROUND (see docs/HISTORICAL_METRICS_
COLLECTION_DESIGN.md): PIT (point-in-time) safety is never asserted,
only ever reported as `PIT_UNVERIFIED`, matching this project's
standing policy — a past season's official metrics request is not yet
confirmed to return that season's OWN final stats rather than always-
current data.

Usage — MANDATORY preview first (zero HTTP requests, seasons
auto-derived from the DB):
    python scripts\\run_klpga_season_metrics_collector.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
        --db-path data\\klpga.sqlite

Usage — the ONE live command (acquisition + ingestion + verification,
seasons auto-derived from the 100 tournaments already in the DB):
    python scripts\\run_klpga_season_metrics_collector.py ^
        --taxonomy docs\\discovery\\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
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
    build_official_metric_value_completeness_report,
    build_official_metric_value_rows,
    build_post_acquisition_validation_report,
    derive_seasons_from_tournament_master,
    extract_player_codes_from_raw_samples,
    ingest_official_metric_value_rows,
    read_player_master_ids,
    verify_player_code_identity_space,
)

ROOT = Path(__file__).resolve().parents[1]

EXIT_COMPLETE = 0
EXIT_DB_NOT_INITIALIZED = 3
EXIT_HARD_STOP = 4
EXIT_TAXONOMY_LOAD_FAILED = 5
EXIT_SEASONS_NOT_DERIVABLE = 6


def run(
    client,
    taxonomy: dict,
    seasons: "list[str] | None",
    *,
    raw_samples_dir: Path,
    db_path: "Path | None",
    live: bool,
    log=print,
) -> int:
    start = time.perf_counter()

    conn = None
    if db_path is not None:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")

    if seasons is None:
        if conn is None:
            log("ERROR: no --seasons given and no --db-path to auto-derive seasons from tournament_master.")
            return EXIT_SEASONS_NOT_DERIVABLE
        derived = derive_seasons_from_tournament_master(db_path)
        if not derived:
            log(f"ERROR: tournament_master has zero rows in {db_path} — cannot auto-derive seasons.")
            conn.close()
            return EXIT_SEASONS_NOT_DERIVABLE
        seasons = [str(s) for s in derived]
        log(f"Seasons auto-derived from tournament_master: {seasons}")

    hard_stop_seasons: list[str] = []
    acquisition_by_season: dict[str, dict] = {}
    validation_by_season: dict[str, dict] = {}
    mapping_status_totals: Counter = Counter()
    ingested_rows_total = 0

    for season in seasons:
        log(f"=== SEASON {season} ===")
        if live:
            result = acquire_season_metrics(client, taxonomy, season, raw_samples_dir, log=log)
            acquisition_by_season[season] = result
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

        validation_by_season[season] = build_post_acquisition_validation_report(
            taxonomy, raw_samples_dir=raw_samples_dir, season=season
        )

    identity_report = None
    completeness_report = None
    if conn is not None:
        loadloc_codes = extract_player_codes_from_raw_samples(raw_samples_dir)
        player_master_ids = read_player_master_ids(conn)
        identity_report = verify_player_code_identity_space(loadloc_codes, player_master_ids)
        completeness_report = build_official_metric_value_completeness_report(conn)
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
    log("identity/label mapping status totals (cumulative across seasons processed):")
    for status, count in sorted(mapping_status_totals.items()):
        log(f"  {status}: {count}")
    log(f"seasons hard-stopped: {hard_stop_seasons or 'none'}")

    log("")
    log("=== POST-ACQUISITION VALIDATION (per season) ===")
    for season, v in validation_by_season.items():
        log(
            f"  season {season}: canonical_metrics={v['canonical_requestable_metric_count']} "
            f"unique_identities={v['unique_identity_key_count']} "
            f"collision_groups={v['collision_group_count']} "
            f"invariant_warnings={len(v['sanity_invariant_warnings'])}"
        )
        for category, count in v["collision_category_totals"].items():
            log(f"    {category}: {count}")
        for warning in v["sanity_invariant_warnings"]:
            log(f"    WARNING: {warning}")

    log("")
    log("=== PLAYER IDENTITY VERIFICATION ===")
    if identity_report is None:
        log("  not run (no --db-path given)")
    else:
        log(f"  verdict: {identity_report['overall_status']}")
        log(f"  loadLocationRecord player_codes seen: {identity_report['total_loadlocationrecord_codes']}")
        log(f"  player_master.player_id values: {identity_report['total_player_master_ids']}")
        log(f"  matched: {identity_report['matched']}")
        log(f"  unmatched: {identity_report['unmatched_loadlocationrecord_only']}")
        log(f"  match_rate: {identity_report['match_rate']}")
        log(f"  sample_unmatched: {identity_report['sample_unmatched']}")
        log(
            "  direct join safe: "
            + ("YES" if identity_report["overall_status"] == "PLAYER_CODE_IDENTITY_CONFIRMED" else "NO")
        )

    log("")
    log("=== DATABASE COMPLETENESS ===")
    if completeness_report is None:
        log("  not run (no --db-path given)")
    else:
        log(f"  total_rows: {completeness_report['total_rows']}")
        log(f"  seasons_present: {completeness_report['seasons_present']}")
        log(f"  distinct_identity_keys_present: {completeness_report['distinct_identity_keys_present']}")
        log(f"  distinct_players_present: {completeness_report['distinct_players_present']}")
        log(f"  null_value_raw_rows: {completeness_report['null_value_raw_rows']}")
        log(f"  flagged_rows: {completeness_report['flagged_rows']}")

    return EXIT_HARD_STOP if hard_stop_seasons else EXIT_COMPLETE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", required=True, help="Path to KLPGA_RECORD_TAXONOMY_DISCOVERED.json")
    parser.add_argument(
        "--seasons",
        default=None,
        help=(
            "Comma-separated season values, e.g. 2023,2024,2025. Omit to auto-derive from the DISTINCT "
            "seasons already present in --db-path's tournament_master table."
        ),
    )
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
        help=(
            "klpga.sqlite path. Used to ingest official_metric_value rows, to auto-derive --seasons when "
            "omitted, and to run player identity verification. Omit only for a taxonomy-only preview."
        ),
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

    db_path = Path(args.db_path) if args.db_path else None
    if db_path is not None and not db_path.exists():
        print(
            f"ERROR: {db_path} does not exist — run src/klpga/db/init_db.py first "
            f"(python -m klpga.db.init_db --db {db_path})."
        )
        return EXIT_DB_NOT_INITIALIZED

    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()] if args.seasons else None
    if seasons is None and db_path is None:
        print("ERROR: --seasons omitted and no --db-path given to auto-derive seasons from tournament_master.")
        return EXIT_SEASONS_NOT_DERIVABLE

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
