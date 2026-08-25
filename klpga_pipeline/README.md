# KLPGA Historical Database pipeline

Collects an official-source-only Historical Database (CSV + SQLite) of
the 100 most-recently-completed KLPGA **regular tour** events, built
entirely from `klpga.co.kr` / `data.klpga.co.kr` responses — no
third-party (blogs/news/wiki) data is used as a substitute for official
data.

## Current status — read this carefully, these are different things

**Tests passing is NOT the same as real data collection succeeding.**

- ✅ **Unit tests: 73/73 passing.** These run against a synthetic HTML
  fixture (`tests/fixtures/round_leaderboard_sample.html`) hand-built to
  match the confirmed `data-*`/`_playerCode`-style structure, and against
  fake in-process HTTP clients for the collector logic. They prove the
  parsing/merge/UPSERT *code* is correct for that structure.
- ✅ **Live 5-tournament collection: CONFIRMED WORKING**, after finding
  and fixing four real bugs in sequence from the run's own diagnostics
  (see `docs/SITE_STRUCTURE_TODO.md` section 5 for the full writeup of
  each):
  1. Players who didn't reach the final round were silently dropped
     from collection entirely — fixed (player discovery confirmed:
     602 player_event / 1,862 player_round rows, a real spread).
  2. `made_cut`/`withdrawn`/`disqualified` stayed all-zero even with
     players correctly discovered — the real site never uses literal
     `"CUT"`/`"WD"`/`"DQ"` text at all (confirmed via raw HTML
     inspection); missed-cut players get a plain numeric rank, and a
     player who doesn't complete their last-appeared round gets a
     `data-rank="999"` sentinel instead. Fixed: `made_cut` now derives
     from whether the player has a real score for the tournament's
     actual final round.
  3. A follow-up: `rounds_played` was stored as `NULL` instead of a
     confirmed `0` for players with zero valid rounds anywhere — fixed.
  4. **Explicit decision, not a bug**: `withdrawn`/`disqualified` are
     deliberately left `0` for every non-completing player. No marker
     anywhere in this endpoint's data distinguishes WD from DQ — adding
     a split would mean guessing. `rounds_played` + `finish_position`
     (`"999"` vs. a real rank) already let downstream consumers tell a
     normal missed-cut apart from an abnormal early exit.
  **Confirmed live, 2026-08-24**: `made_cut` split `(0, 266), (1, 336)`
  across 602 player_event rows, `03_validate.py --target 5` ->
  `VALIDATION PASSED`.
- ✅ **Full 100-tournament collection: CONFIRMED COMPLETE, 2026-08-25**
  (Windows production DB, after the `gameMethod` fix below). Validated:
  100 distinct tournaments, 0 excluded special-format gameCodes
  remaining, 0 zero-player tournaments, `03_validate.py --target 100`
  -> `VALIDATION PASSED`. Row counts: `tournament_master` 100,
  `player_master` 546, `player_event` 11,850, `player_round` 33,215,
  CSV export 45,711 total rows.
  **This raw dataset is now the validated checkpoint — it is not to be
  modified or recollected unless a genuine data-integrity bug is
  found.** (The first attempt, 2026-08-24, got 94/100 — 6 tournaments
  failed with zero leaderboard data. Root-caused via
  `scripts/08_inspect_failed_leaderboards.py`: all 6 had
  `gameMethod != "0"` — 3 Match Play, 3 Modified Stableford, both
  confirmed to return zero player rows at every round via
  `roundLeaderboard`. Fixed by requiring `gameMethod == "0"` in
  `filter_completed_regular_tour`, then re-collected clean.)
- ✅ **Derived analytics layer (`player_stats_snapshot`): built,
  2026-08-25.** 19 `derived_*` columns per player (tournaments played,
  rounds played, made cuts/cut rate, wins, top 5/10, best finish,
  scoring average, average score-to-par, scoring std dev, recent form
  at 5/10/20 events with sample-size companions, weighted recent form),
  computed straight from the validated 100-tournament dataset — see
  "Analytics layer" below and `docs/SITE_STRUCTURE_TODO.md` section 6
  for the full formula/provenance writeup. **True Strokes Gained and
  GIR are confirmed NOT computable** from this dataset (no shot-level
  distance/lie/hole-by-hole data exists or is exposed by the confirmed
  endpoint) — no proxy was built for either, and the official Data
  Center columns (`sg_*`, `gir`, driving/putting/scrambling/etc.) stay
  NULL, same as before.

Two endpoints and the HTML player-row structure behind them have been
**confirmed** both via browser DevTools Network capture and by an actual
live run against the site:

- `POST /ajax/tourInfo/getGameList` — tournament list, JSON. Confirmed
  fields: `gameCode`, `gameTitle`, `gameEngTitle`, `tourType`,
  `courseText`, `courseEngText`, `outCourseText`, `inCourseText`,
  `startDate`, `endDate`, `gameFinish`, `prizeMoney`, `winnerCode`,
  `winnerName`, `gameMethod` (tournament format — `"0"`=stroke play,
  the only format `roundLeaderboard` actually returns data for;
  `"1"`=Match Play, `"2"`=Modified Stableford, both confirmed
  unavailable via this endpoint).
- `POST /load/leaderboard/roundLeaderboard` — per-round leaderboard, HTML
  fragment, player data on `data-*`/`_playerCode`-style attributes.

The collectors, parser, and database layer are real adapters against
that confirmed structure (not CSS-selector placeholders). See
`docs/SITE_STRUCTURE_TODO.md` for the exact field-by-field confirmation
log — some fields (other tour-type codes, non-`F` `gameFinish` values,
player performance-statistics endpoints on `data.klpga.co.kr`,
robots.txt) are still unconfirmed and intentionally left `NULL` rather
than guessed.

## Current goal: red-team the derived feature set before the win-probability model

The raw 100-tournament dataset is validated, the derived
`player_stats_snapshot` feature set is built (546/546 players
populated on the production DB), but a red-team check on
`derived_avg_score_to_par` is in progress — see "Analytics layer" below
and `docs/SITE_STRUCTURE_TODO.md` section 6 for the full trace. **The
win-probability model is deliberately NOT started until this check is
run against the real production DB and the output reviewed.**

Known, permanent gap regardless of any future re-run: the OFFICIAL
`player_stats_snapshot` columns (`scoring_average`, `sg_*`, `gir`,
`driving_distance`, `driving_accuracy`, `putting_average`,
`sixties_rate`, `top10_rate`, `birdie_average`, `par_breakers`,
`sand_save`, `scrambling`) are still all NULL. `data.klpga.co.kr` (the
Performance Statistics data center) has not been reached from any
environment yet — nothing about it is confirmed. This isn't an
oversight to silently work around; it's a separate, still-unstarted
data source, distinct from the derived analytics layer below.

## Analytics layer: derived `player_stats_snapshot` metrics

`src/klpga/analytics/player_stats.py` (`compute_player_stats`) computes
19 `derived_*` columns per `player_id` (the confirmed real KLPGA
playerCode, never player_name) from the validated `tournament_master` /
`player_event` / `player_round` dataset — tournaments played, rounds
played, made cuts + cut rate, wins, top 5, top 10, best finish, a true
per-round scoring average, average score-to-par, scoring standard
deviation, recent-form averages over the 5/10/20 most recent events
(each with a companion `_n` sample-size column), and a linearly-weighted
recent-form figure over up to the 10 most recent events. **Every
metric's exact source field, formula, sample size, and missing-data
treatment is documented in that module's docstring.**

These are clearly separated in `schema.sql` from the pre-existing
OFFICIAL Data Center columns (which stay NULL) via a
`snapshot_type='derived_trailing100'` row and a `derived_` column-name
prefix — never conflated with an official KLPGA statistic.
`src/klpga/db/migrate.py` safely adds the new columns to an existing DB
(only when `player_stats_snapshot` is still empty; refuses and raises
rather than ever dropping populated rows).

```bash
python scripts/09_build_player_stats_snapshot.py --db data/klpga.sqlite
python scripts/10_print_snapshot_samples.py --db data/klpga.sqlite --limit 10
python scripts/11_diagnose_avg_score_to_par.py --db data/klpga.sqlite
```

`09` always fully regenerates every `derived_trailing100` row (DELETE +
re-INSERT) rather than an incremental upsert — see that script's
docstring for the specific SQLite NULL-uniqueness pitfall this avoids.
`10` and `11` are read-only. None of the three touch
`tournament_master`/`player_event`/`player_round` except to SELECT from
them — all are safe to run repeatedly against the already-validated
production DB without resetting or recollecting it.

`11` is the red-team check on `derived_avg_score_to_par` (see "Current
goal" above and `docs/SITE_STRUCTURE_TODO.md` section 6): for 5
representative players it prints raw round scores, the sparse per-round
`round_to_par`, the tournament `total_score`/`score_to_par`, and a
reverse-engineered implied par per round (should land near 68-74 for
every event if `score_to_par` is a self-consistent tournament total).
`--names "이예원,박지영,김민솔,서교림,박민지"` picks specific players by
exact name match (falls back to the players with the most
`derived_tournaments_played` for any name that doesn't match).

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
    export_csv.py               SQLite -> the 5 spec CSV files (stdlib csv/sqlite3 only, no pandas —
                                 see docs/SITE_STRUCTURE_TODO.md section 5 for why)
    migrate.py                  safe (0-rows-only) player_stats_snapshot schema migration for the
                                 derived_* columns
  analytics/
    player_stats.py             derived player_stats_snapshot metrics — formulas/provenance in its
                                 own docstring, see "Analytics layer" above

scripts/
  00_discover_site.py           robots.txt + link discovery (recon only, writes nothing to the DB)
  01_collect_tournaments.py     season walk-back -> tournament_master (full 100-event run)
  02_collect_leaderboards.py    every tournament_master row -> player_master/player_event/player_round
  03_validate.py                exactly-N check, duplicate check, FK integrity check
  04_collect_single_tournament.py  ONE known gameCode end-to-end — used for the first validation checkpoint
  07_inspect_status_markup.py   diagnostic: dump raw cached HTML around finish_position='999' player
                                 rows, to find any CUT/WD/DQ marker beyond the bare rank sentinel
  08_inspect_failed_leaderboards.py  diagnostic: raw getGameList diff (failed tournaments vs. a
                                      working baseline) + round=1..8 probe against the live
                                      roundLeaderboard endpoint — found the gameMethod fix
  09_build_player_stats_snapshot.py  migrate + compute + fully regenerate the derived_*
                                      player_stats_snapshot columns from the validated dataset
  10_print_snapshot_samples.py       read-only: print sample player_stats_snapshot rows for a
                                      quick eyeball check after running 09
  11_diagnose_avg_score_to_par.py    read-only red-team check: raw round scores + implied-par
                                      sanity check for derived_avg_score_to_par, see "Analytics layer"

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
  test_export_csv.py              export_all() row counts, TRUE/FALSE mapping, NULL handling, and the
                                   missing-`--db` FileNotFoundError path
  test_player_stats.py            compute_player_stats() formulas, hand-computed against a synthetic
                                   scenario (see "Analytics layer" above)
  test_migrate.py                 player_stats_snapshot schema migration: migrates a 0-row old-shape
                                   table, no-ops once current, refuses to drop a populated old-shape one
  test_build_player_stats_snapshot.py  end-to-end: snapshot metadata, official columns stay NULL,
                                        re-running replaces rather than duplicates rows
  test_print_snapshot_samples.py  read-only sample printer: 2dp formatting, never writes to the DB
  test_diagnose_avg_score_to_par.py  implied-par sanity check fires on corrupted data, never
                                      writes to the DB
```

`tests/test_tournaments_collector.py` also covers the `gameMethod`
filter: `test_filter_completed_regular_tour_excludes_match_play_and_stableford`.

## Running a single-tournament validation (ran once — result now known-incomplete, see status above)

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite --reset
python scripts/04_collect_single_tournament.py --season 2026 --game-code 2026080002 --db data/klpga.sqlite
```

Prints the raw `getGameList` entry it matched, how many
`roundLeaderboard` requests it made, sample parsed player rows, and a
raw HTML snippet. Re-running with `--reset` replaces the earlier
incomplete result.

## Running a small multi-tournament validation (confirmed working — see status above)

```bash
python src/klpga/db/init_db.py --db data/klpga_small.sqlite --reset
python scripts/01_collect_tournaments.py --season 2026 --target 5 --db data/klpga_small.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga_small.sqlite
python scripts/03_validate.py --db data/klpga_small.sqlite --target 5
python src/klpga/db/export_csv.py --db data/klpga_small.sqlite --out data/csv_small
```

`--reset` on `init_db.py` discards whatever was there before, so this
same command sequence is what re-collects `data/klpga_small.sqlite`
after any future fix, too — no separate "second run" instructions
needed each time.

`scripts/07_inspect_status_markup.py` (raw HTML inspection around
`finish_position='999'` rows, zero new network requests since it reads
the same disk cache) is what surfaced the real markup behind the
made_cut/withdrawn/disqualified fix — kept in the repo for any future
investigation of remaining open questions (e.g. whether some other
endpoint distinguishes WD from DQ).

## Running the full pipeline (confirmed complete — see status above)

```bash
python src/klpga/db/init_db.py --db data/klpga.sqlite --reset
python scripts/01_collect_tournaments.py --season <current_season> --target 100 --db data/klpga.sqlite
python scripts/02_collect_leaderboards.py --db data/klpga.sqlite
python scripts/03_validate.py --db data/klpga.sqlite --target 100
python src/klpga/db/export_csv.py --db data/klpga.sqlite --out data/csv
python scripts/09_build_player_stats_snapshot.py --db data/klpga.sqlite
```

Use `--reset` on `init_db.py` here since earlier checkpoints may have
left a stale single-tournament row in this exact DB path — the full run
should start from a clean slate so the `--target 100` row count is
unambiguous. **Do not re-run steps 1-4 (through `01`-`03`/CSV export)
against the already-validated production DB unless a genuine
data-integrity bug is found** — that dataset is the checkpoint everything
in "Analytics layer" reads from. `09_build_player_stats_snapshot.py` is
safe and cheap to re-run any time (it only touches
`player_stats_snapshot`, and fully regenerates its own rows each run).

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
