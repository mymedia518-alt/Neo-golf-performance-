# KLPGA Historical Database pipeline

Collects an official-source-only Historical Database (CSV + SQLite) of
the 100 most-recently-completed KLPGA **regular tour** events, built
entirely from `klpga.co.kr` / `data.klpga.co.kr` responses — no
third-party (blogs/news/wiki) data is used as a substitute for official
data.

## Current status

Two endpoints and the HTML player-row structure behind them have been
**confirmed** via a real browser DevTools Network capture:

- `POST /ajax/tourInfo/getGameList` — tournament list, JSON
- `POST /load/leaderboard/roundLeaderboard` — per-round leaderboard, HTML
  fragment

The collectors, parser, and database layer are built as real adapters
against that confirmed structure (not CSS-selector placeholders). See
`docs/SITE_STRUCTURE_TODO.md` for the exact field-by-field confirmation
log — several fields (tournament start date, other tour-type codes,
player performance-statistics endpoints on `data.klpga.co.kr`, robots.txt)
are still unconfirmed and intentionally left `NULL` rather than guessed.

**Live collection has not run successfully yet**: outbound network access
to `klpga.co.kr` / `data.klpga.co.kr` has been blocked at this
environment's egress proxy every time it's been attempted. The code below
is ready to run as soon as that access works — nothing has been
fabricated in its place.

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

scripts/
  00_discover_site.py           robots.txt + link discovery (recon only, writes nothing to the DB)
  01_collect_tournaments.py     season walk-back -> tournament_master
  02_collect_leaderboards.py    per-tournament leaderboard -> player_master/player_event/player_round
  03_validate.py                exactly-100 check, duplicate check, FK integrity check

tests/
  test_leaderboard_parser.py    parser tests against a synthetic fixture (see its header comment)
  test_tournaments_collector.py  getGameList adapter tests (fake HTTP client, no network)
  test_leaderboard_collector.py  request-optimization tests (fake HTTP client, no network)
  test_upsert.py                 UPSERT idempotency + collection_runs lifecycle tests
```

## Running the pipeline

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite
python scripts/01_collect_tournaments.py --season <current_season> --db data/klpga.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga.sqlite
python scripts/03_validate.py --db data/klpga.sqlite
python src/klpga/db/export_csv.py --db data/klpga.sqlite --out data/csv
```

Every collection script logs a `collection_runs` row (`running` ->
`success`/`error`/`blocked`). A `RateLimitBlockedError` (401/403/429 from
the site) is never retried past `http_client.py`'s built-in backoff and
is surfaced as a `blocked` run rather than silently failing or
substituting fake data.

## Running tests

```bash
pip install -r requirements.txt   # includes pytest
pytest
```
