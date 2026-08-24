# KLPGA Historical Database pipeline

Collects an official-source-only Historical Database (CSV + SQLite) of
the 100 most-recently-completed KLPGA **regular tour** events, built
entirely from `klpga.co.kr` / `data.klpga.co.kr` responses — no
third-party (blogs/news/wiki) data is used as a substitute for official
data.

## Current status — read this carefully, these are different things

**Tests passing is NOT the same as real data collection succeeding.**

- ✅ **Unit tests: 45/45 passing.** These run against a synthetic HTML
  fixture (`tests/fixtures/round_leaderboard_sample.html`) hand-built to
  match the confirmed `data-*`/`_playerCode`-style structure, and against
  fake in-process HTTP clients for the collector logic. They prove the
  parsing/merge/UPSERT *code* is correct for that structure.
- ⚠️ **Live single-tournament and 5-tournament collections both ran,
  and had three real bugs found and fixed in sequence from their own
  diagnostics** (see `docs/SITE_STRUCTURE_TODO.md` section 5 for the
  full writeup of each):
  1. Players who didn't reach the final round were silently dropped
     from collection entirely (fixed — player discovery confirmed
     correct: 602 player_event / 1,862 player_round rows, a real spread).
  2. `made_cut`/`withdrawn`/`disqualified` stayed all-zero even with
     players correctly discovered, because those flags were only ever
     derived from a literal `"CUT"`/`"WD"`/`"DQ"` string in `data-rank`
     — confirmed via raw HTML inspection
     (`scripts/07_inspect_status_markup.py`) that the real site never
     uses that text at all. Missed-cut players get a plain real numeric
     rank; players who don't complete their last-appeared round get a
     `data-rank="999"` sentinel instead (with score/to-par fields reset
     to placeholder `"0"`s alongside it) — no marker anywhere
     distinguishes WD from DQ. Fixed: `made_cut` is now derived from
     whether the player has a real score for the tournament's actual
     final round; a literal `"0"` score is never treated as real;
     `withdrawn`/`disqualified` are honestly left `0` for the `999`
     group (not guessed) while `finish_position="999"` stays preserved
     so that group remains identifiable.
  **Needs one more re-collection of the 5-tournament checkpoint to
  confirm this fix live** before scaling to 100 — not done yet as of
  this entry.
- ❌ **Full 100-tournament collection: not attempted yet.** Blocked on
  confirming the classification fix above on real data first.

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

## Current goal: re-validate the 5-tournament checkpoint with the fix

The CUT/WD/DQ drop bug (see status above) means the full 100-tournament
run shouldn't happen yet — re-run the same 5-tournament checkpoint first
with the fixed code, and check whether it now surfaces real CUT/WD/DQ
rows (or confirms these specific 5 tournaments genuinely have none).
Only after that looks right does it make sense to scale to 100. See
"Running a small multi-tournament validation" below.

Known, expected gap even after a clean 100-tournament run:
**`player_stats_snapshot` will still be empty.** `data.klpga.co.kr` (the
Performance Statistics data center) has not been reached from any
environment yet — nothing about it is confirmed, so no snapshot
collection has started. This isn't an oversight to silently work around;
it's the next data source after tournament/leaderboard collection is
solid.

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
  04_collect_single_tournament.py  ONE known gameCode end-to-end — used for the first validation checkpoint
  07_inspect_status_markup.py   diagnostic: dump raw cached HTML around finish_position='999' player
                                 rows, to find any CUT/WD/DQ marker beyond the bare rank sentinel

tests/
  test_leaderboard_parser.py    parser tests against a synthetic fixture (see its header comment)
  test_tournaments_collector.py  getGameList adapter tests (fake HTTP client, no network)
  test_leaderboard_collector.py  request-optimization tests (fake HTTP client, no network)
  test_aggregate.py              resolve_winner_score tests (no fabrication on ties/missing data)
  test_upsert.py                 UPSERT idempotency + collection_runs lifecycle tests, incl. the
                                  winner_score NOT NULL regression found in the live 5-tournament run
  test_validate.py               03_validate.py's per-tournament coverage-gap check
  test_cut_player_integration.py  full collector->merge->build pipeline test for the CUT/WD/DQ
                                   drop regression found in the live 5-tournament run
  test_inspect_status_markup.py   find_row_context() extraction logic for the 999-sentinel diagnostic
```

## Running a single-tournament validation (ran once — result now known-incomplete, see status above)

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite --reset
python scripts/04_collect_single_tournament.py --season 2026 --game-code 2026080002 --db data/klpga.sqlite
```

Prints the raw `getGameList` entry it matched, how many
`roundLeaderboard` requests it made, sample parsed player rows, and a
raw HTML snippet. Re-running with `--reset` replaces the earlier
incomplete result.

## Running a small multi-tournament validation (ran twice — see status above)

```bash
python src/klpga/db/init_db.py --db data/klpga_small.sqlite --reset
python scripts/01_collect_tournaments.py --season 2026 --target 5 --db data/klpga_small.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga_small.sqlite
python scripts/03_validate.py --db data/klpga_small.sqlite --target 5
python src/klpga/db/export_csv.py --db data/klpga_small.sqlite --out data/csv_small
```

`--reset` on `init_db.py` discards whatever was there before, so this
same command sequence is what re-collects `data/klpga_small.sqlite`
after any further fix, too — no separate "second run" instructions
needed each time. **Current goal**: run it once more now that the
made_cut/withdrawn/disqualified fix (see status above) is in, and
check the CUT/WD/DQ counts before moving to the full run below.

`scripts/07_inspect_status_markup.py` (raw HTML inspection around
`finish_position='999'` rows, zero new network requests since it reads
the same disk cache) is what surfaced the real markup behind that fix —
kept in the repo for any future investigation of remaining open
questions (e.g. whether some other endpoint distinguishes WD from DQ).

## Running the full pipeline (later — after the classification fix is confirmed live)

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite --reset
python scripts/01_collect_tournaments.py --season <current_season> --target 100 --db data/klpga.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga.sqlite
python scripts/03_validate.py --db data/klpga.sqlite --target 100
python src/klpga/db/export_csv.py --db data/klpga.sqlite --out data/csv
```

Use `--reset` on `init_db.py` here since earlier checkpoints may have
left a stale single-tournament row in this exact DB path — the full run
should start from a clean slate so the `--target 100` row count is
unambiguous.

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
