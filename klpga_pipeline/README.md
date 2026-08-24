# KLPGA Historical Database pipeline

Collects an official-source-only Historical Database (CSV + SQLite) of
the 100 most-recently-completed KLPGA **regular tour** events, built
entirely from `klpga.co.kr` / `data.klpga.co.kr` responses — no
third-party (blogs/news/wiki) data is used as a substitute for official
data.

## Current status — read this carefully, these are different things

**Tests passing is NOT the same as real data collection succeeding.**

- ✅ **Unit tests: 32/32 passing.** These run against a synthetic HTML
  fixture (`tests/fixtures/round_leaderboard_sample.html`) hand-built to
  match the confirmed `data-*`/`_playerCode`-style structure, and against
  fake in-process HTTP clients for the collector logic. They prove the
  parsing/merge/UPSERT *code* is correct for that structure.
- ✅ **Live single-tournament collection: SUCCEEDED once, from a
  Windows PC with real internet access** (this dev environment's own
  egress to `klpga.co.kr` is still blocked). `gameCode=2026080002`
  ("BC카드 · 한경 제48회 KLPGA 챔피언십", season 2026) was collected
  end-to-end: 1 tournament, 72 players, 72 player_event rows, 288
  player_round rows. Winner 서교림 (playerCode `11134`), 70-67-69-74=280
  (-8), confirmed against `getGameList`'s `winnerCode`/`winnerName` and
  matched by the parser's own rank-1 result. See
  `docs/SITE_STRUCTURE_TODO.md` for the full confirmation log from this
  run (including a real duplicate-DOM-row quirk in the leaderboard HTML
  that the merge-by-`player_code` step already handles correctly).
- ❌ **Full 100-tournament collection: not attempted yet.** The current
  goal is a small 3-5 tournament run next (see below) before scaling to
  100 — see "Running a small multi-tournament validation".

Two endpoints and the HTML player-row structure behind them have been
**confirmed** both via browser DevTools Network capture and by an actual
live run against the site:

- `POST /ajax/tourInfo/getGameList` — tournament list, JSON. Confirmed
  fields: `gameCode`, `gameTitle`, `gameEngTitle`, `tourType`,
  `courseText`, `courseEngText`, `outCourseText`, `inCourseText`,
  `startDate`, `endDate`, `gameFinish`, `prizeMoney`, `winnerCode`,
  `winnerName`.
- `POST /load/leaderboard/roundLeaderboard` — per-round leaderboard, HTML
  fragment, player data on `data-*`/`_playerCode`-style attributes.

The collectors, parser, and database layer are real adapters against
that confirmed structure (not CSS-selector placeholders). See
`docs/SITE_STRUCTURE_TODO.md` for the exact field-by-field confirmation
log — some fields (other tour-type codes, non-`F` `gameFinish` values,
player performance-statistics endpoints on `data.klpga.co.kr`,
robots.txt) are still unconfirmed and intentionally left `NULL` rather
than guessed.

## Current goal: 3-5 real tournaments, not 100 yet

One tournament collected cleanly. Before attempting the full
100-tournament walk-back, the next checkpoint is a **small multi-
tournament run (3-5 completed regular-tour events)** — this exercises
the season walk-back logic in `scripts/01_collect_tournaments.py` across
multiple `gameCode`s in one run, which the single-tournament script
doesn't test. See "Running a small multi-tournament validation" below.

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
    tournaments.py             getGameList adapter (season walk-back to N completed events)
    leaderboard.py              roundLeaderboard adapter (minimal-request strategy, section 5 of spec)
    aggregate.py                 merge raw round rows -> player_master/player_event/player_round dicts,
                                  resolve_winner_score() from real collected data
  parsers/
    leaderboard_parser.py       HTML fragment -> per-player round data, via data-*/_ attributes
  db/
    schema.sql                  SQLite schema (5 spec tables + collection_runs audit log)
    init_db.py                  create/reset klpga.sqlite
    upsert.py                   idempotent UPSERT helpers + collection_runs logging
    export_csv.py               SQLite -> the 5 spec CSV files

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
  test_aggregate.py              resolve_winner_score tests (no fabrication on ties/missing data)
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

## Running a small multi-tournament validation (current goal)

`scripts/01_collect_tournaments.py` already takes `--target`, so a small
3-5 tournament run doesn't need a separate script — just point it at a
fresh DB and a small target count:

```bash
python src/klpga/db/init_db.py --db data/klpga_small.sqlite --reset
python scripts/01_collect_tournaments.py --season 2026 --target 5 --db data/klpga_small.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga_small.sqlite
python scripts/03_validate.py --db data/klpga_small.sqlite --target 5
python src/klpga/db/export_csv.py --db data/klpga_small.sqlite --out data/csv_small
```

Using a separate `klpga_small.sqlite` keeps this checkpoint's row counts
clean and easy to validate (`--target 5`) without mixing in the earlier
single-tournament run's row.

## Running the full pipeline (later — after the small run looks solid)

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
