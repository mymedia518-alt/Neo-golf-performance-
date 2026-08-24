# KLPGA Historical Database pipeline

Collects an official-source-only Historical Database (CSV + SQLite) of
the 100 most-recently-completed KLPGA **regular tour** events, built
entirely from `klpga.co.kr` / `data.klpga.co.kr` responses — no
third-party (blogs/news/wiki) data is used as a substitute for official
data.

## Current status — read this carefully, these are two different things

**Tests passing is NOT the same as real data collection succeeding.**

- ✅ **Unit tests: 26/26 passing.** These run against a synthetic HTML
  fixture (`tests/fixtures/round_leaderboard_sample.html`) hand-built to
  match the confirmed `data-*`/`_playerCode`-style structure, and against
  fake in-process HTTP clients for the collector logic. They prove the
  parsing/merge/UPSERT *code* is correct for that structure. They prove
  **nothing** about whether a live KLPGA response actually looks the way
  the fixture assumes.
- ❌ **Real collected tournaments: 0.** No script has successfully
  reached `klpga.co.kr` from this development environment — every
  attempt has failed at the environment's egress proxy (`403` on the
  CONNECT tunnel, before ever reaching the site). No data has been
  fabricated to fill that gap.

Two endpoints and the HTML player-row structure behind them have been
**confirmed** via a real browser DevTools Network capture (not by this
codebase fetching them):

- `POST /ajax/tourInfo/getGameList` — tournament list, JSON
- `POST /load/leaderboard/roundLeaderboard` — per-round leaderboard, HTML
  fragment

The collectors, parser, and database layer are built as real adapters
against that confirmed structure (not CSS-selector placeholders). See
`docs/SITE_STRUCTURE_TODO.md` for the exact field-by-field confirmation
log — several fields (tournament start date, other tour-type codes,
player performance-statistics endpoints on `data.klpga.co.kr`, robots.txt)
are still unconfirmed and intentionally left `NULL` rather than guessed.

## Current goal: ONE real tournament, not 100

The next milestone is **not** the full 100-tournament collection — it's
proving the adapters work at all against a live response, using
`gameCode=2026080002` as the known validation case. Only after that
succeeds and any surprises it reveals are folded back into the parser/
`docs/SITE_STRUCTURE_TODO.md` does it make sense to scale up to
`scripts/01_collect_tournaments.py`'s full season walk-back.

Use `scripts/04_collect_single_tournament.py` for this (see "Running a
single-tournament validation" below) — it collects exactly one gameCode
and prints a structured, copy-pasteable report including the raw
`getGameList` entry and a raw HTML snippet, specifically so the report
can be reviewed against what the code assumes.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Layout

```
src/klpga/
  config.py                  confirmed endpoints/constants (+ open assumptions, clearly marked)
  http_client.py              rate-limited / retrying / disk-cached requests wrapper
  collectors/
    tournaments.py             getGameList adapter (season walk-back to 100 completed events)
    leaderboard.py              roundLeaderboard adapter (minimal-request strategy, section 5 of spec)
  parsers/
    leaderboard_parser.py       HTML fragment -> per-player round data, via data-*/_ attributes
  db/
    schema.sql                  SQLite schema (5 spec tables + collection_runs audit log)
    init_db.py                  create/reset klpga.sqlite
    upsert.py                   idempotent UPSERT helpers + collection_runs logging
    export_csv.py               SQLite -> the 5 spec CSV files

  collectors/
    aggregate.py                merge raw round rows -> player_master/player_event/player_round dicts
    tournaments.py               getGameList adapter (season walk-back to N completed events)
    leaderboard.py                roundLeaderboard adapter (minimal-request strategy, section 5 of spec)

scripts/
  00_discover_site.py           robots.txt + link discovery (recon only, writes nothing to the DB)
  01_collect_tournaments.py     season walk-back -> tournament_master (full 100-event run)
  02_collect_leaderboards.py    every tournament_master row -> player_master/player_event/player_round
  03_validate.py                exactly-N check, duplicate check, FK integrity check
  04_collect_single_tournament.py  ONE known gameCode end-to-end — current validation checkpoint

tests/
  test_leaderboard_parser.py    parser tests against a synthetic fixture (see its header comment)
  test_tournaments_collector.py  getGameList adapter tests (fake HTTP client, no network)
  test_leaderboard_collector.py  request-optimization tests (fake HTTP client, no network)
  test_upsert.py                 UPSERT idempotency + collection_runs lifecycle tests
```

## Running a single-tournament validation (current goal)

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite
python scripts/04_collect_single_tournament.py --season 2026 --game-code 2026080002 --db data/klpga.sqlite
```

This is the script to run first on a machine with real internet access.
It prints the raw `getGameList` entry it matched, how many
`roundLeaderboard` requests it made, sample parsed player rows, and a
raw HTML snippet — copy the full output for review.

## Running the full pipeline (later — after single-tournament validation passes)

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite
python scripts/01_collect_tournaments.py --season <current_season> --db data/klpga.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga.sqlite
python scripts/03_validate.py --db data/klpga.sqlite
python src/klpga/db/export_csv.py --db data/klpga.sqlite --out data/csv
```

Every collection script logs a `collection_runs` row (`running` ->
`success`/`error`/`blocked`). A `RateLimitBlockedError` (401/403/429
returned directly by the site) is never retried past
`http_client.py`'s built-in backoff and is surfaced as a `blocked` run;
a lower-level network/proxy failure is caught separately and reported
as a clean error — neither path silently fails or substitutes fake
data.

## Running tests

```bash
pip install -r requirements.txt   # includes pytest
pytest
```
