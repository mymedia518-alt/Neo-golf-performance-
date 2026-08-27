# KLPGA Historical Database pipeline

Collects an official-source-only Historical Database (CSV + SQLite) of
the 100 most-recently-completed KLPGA **regular tour** events, built
entirely from `klpga.co.kr` / `data.klpga.co.kr` responses — no
third-party (blogs/news/wiki) data is used as a substitute for official
data.

## Current status — read this carefully, these are different things

**Tests passing is NOT the same as real data collection succeeding.**

- ✅ **Unit tests: 308/308 passing.** Most run against a synthetic HTML
  fixture (`tests/fixtures/round_leaderboard_sample.html`) hand-built to
  match the confirmed `data-*`/`_playerCode`-style structure, and against
  fake in-process HTTP clients for the collector logic — they prove the
  parsing/merge/UPSERT *code* is correct for that structure. The
  entry-list parser tests are different: they run against
  `tests/fixtures/entry_list_sample.html`, the COMPLETE real HTML of a
  live entry-list page pasted verbatim by the user (see "Entry-list
  collection" below) — not synthetic.
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
  2026-08-25, then red-teamed twice.** 21 `derived_*` columns per
  player (tournaments played, rounds played, made cuts/cut rate, wins,
  top 5/10, best finish, per-round scoring average + std dev,
  event-average and round-rate score-to-par, recent form at 5/10/20
  events with sample-size companions, weighted recent form), computed
  straight from the validated 100-tournament dataset — see "Analytics
  layer" below and `docs/SITE_STRUCTURE_TODO.md` section 6 for the full
  formula/provenance writeup. **True Strokes Gained and GIR are
  confirmed NOT computable** from this dataset (no shot-level
  distance/lie/hole-by-hole data exists or is exposed by the confirmed
  endpoint) — no proxy was built for either, and the official Data
  Center columns (`sg_*`, `gir`, driving/putting/scrambling/etc.) stay
  NULL, same as before.
  **Red-team round 1**: a `derived_avg_score_to_par` metric looked
  unrealistically low for real players — traced to the code (confirmed:
  it's a tournament-total average, not a bug) and confirmed against the
  real production DB (김민주: `implied_avg_par/round = 72.00` across all
  97 valid events, zero implausible events — `score_to_par` is
  genuinely self-consistent).
  **Red-team round 2**: even though it wasn't a bug, that metric's OLD
  NAME didn't say it was a tournament-total average. Every
  tournament-total-based column was renamed to say `_event_` or
  `_round_` explicitly (see "Analytics layer" below), a new
  `derived_avg_round_score_to_par` rate metric was added, and its
  formula was verified against real per-round `round_to_par` data —
  see `scripts/12_verify_round_to_par_reliability.py`. **Confirmed
  against the real production DB, 2026-08-25**: `round_to_par` coverage
  99.4% (33,006/33,215), CHECK B 11,179/11,179 exact matches, cross-check
  both formulas = 0.51 -> AGREE. Both red-team rounds are now closed.
- ✅ **Win-probability model design report: written and approved in
  direction, 2026-08-25.** Recommended approach — Model B's mechanism
  (standardized strength -> softmax), with weights and temperature fit
  by Model C's point-in-time walk-forward backtest, not hand-picked —
  approved. **Not implemented.** Implementation is blocked on the
  entry-list investigation below.
- ✅ **Upcoming-tournament entry list: source CONFIRMED, collection +
  storage layer DONE, live-verified 2026-08-25.** `GET
  /web/tourInfo/entry?gameCode=<code>` returns a full HTML page (not
  JSON) whose `<h2>전체 선수</h2>` table is the real, confirmed roster.
  **Live production run against gameCode=2026080001 on the Windows PC:
  120/120 rows parsed, 0 unparseable, 0 duplicate `player_code`s, 119
  matched / 1 unmatched against `player_master`** (unmatched:
  `player_code=13355`, "배윤철 0908(A)" — a legitimate new/rookie
  entrant, stored without fuzzy name matching, now a real test case for
  a future rookie fallback). `tournament_entry` (idempotent UPSERT
  keyed on `game_code`+`player_code`, additive migration, no
  `entry_status`/WD/DNS/SG/GIR — no confirmed source for any of those)
  is implemented and tested; see `docs/SITE_STRUCTURE_TODO.md` section 7.
- ✅ **Point-in-time features + walk-forward backtest layer: DONE,
  2026-08-25.** New `src/klpga/backtest/` package computes every
  feature strictly from a player's OTHER tournaments before a target
  tournament's confirmed start date (never the target's own rows,
  never a later tournament, fail-safe exclusion on same-day/missing-
  date ambiguity). **5 mandatory adversarial leakage tests — inserting
  future tournaments, the target tournament's own rows, and an extreme
  "canary" future score/win — all confirm a target's features never
  change.** No SG/GIR/driving/putting/course-par proxy, and no
  probability/weight/cap/calibration constant, anywhere in this layer.
  See `docs/SITE_STRUCTURE_TODO.md` section 8 for the full architecture
  and feature definitions.
- ✅ **Production diagnostics for the backtest layer: built, 2026-08-25.**
  6 read-only scripts (`17`-`21`, plus the existing `16`) — eligibility
  sweep, a real-production-data leakage invariance check (companion to
  the synthetic adversarial tests, not a replacement), a field-relative
  audit proving the leave-one-out exclusion arithmetic, a feature
  redundancy report (correlation only — no feature removed, no weight
  chosen), and a data coverage report. 25 new tests, 178/178 full suite
  passing.
- ✅ **Population-definitions audit, 2026-08-25: a real discrepancy
  report (script `17` at threshold=5: 95 targets/11,189 rows vs. script
  `21`: 100 usable targets/11,850 rows) audited and proven, in code, to
  be EXPECTED — not a bug.** Script `17` reports an
  ELIGIBLE-AT-THRESHOLD-k SUBSET of script `21`'s unconditional USABLE
  population; they're definitionally identical at threshold=0 and
  intentionally diverge above it (100−5=95 tournaments, and the row
  drop equals exactly those 5 earliest tournaments' field size). Proven
  by 4 new tests (`tests/test_population_definitions.py`) before any
  wording changed — no filtering/threshold logic touched, only output
  wording clarified so the two populations can't be misread as the
  same one. See `docs/SITE_STRUCTURE_TODO.md` section 8. 182/182 full
  suite passing.
- ✅ **Win-probability model evaluation spec: FROZEN, 2026-08-25** —
  `docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`. Written and
  committed BEFORE any model is fit, so the promotion rules can't move
  after seeing results: primary metrics (per-tournament log loss +
  field-size-normalized Brier), mandatory baselines (uniform + a
  single-feature MLE-fit softmax), a 7-model core ablation ladder plus
  one-at-a-time challengers, walk-forward fitting/calibration
  discipline, 5-slice rookie/sparse-history evaluation, paired
  significance-based promotion criteria, and 15+ red-team failure
  modes addressed explicitly. **Still no model code, no fitted
  coefficients, no live probabilities of any kind.**
- ✅ **M0-M6 model comparison: IMPLEMENTED, 2026-08-25** — new
  `src/klpga/models/` package fits the frozen ladder (uniform baseline
  through field-relative+recent10) walk-forward, via a deterministic
  grid-search MLE fit (no numpy/scipy, no randomness — the only seeded
  step anywhere is the calibration bootstrap CI). Training-only,
  sample-size-aware shrinkage handles zero/sparse-history players (a
  rookie's missing feature shrinks fully to the training fold's mean,
  never a dropped row, never probability zero). 53 new tests, including
  the full adversarial set (sums to 1, target/future-tournament
  leakage, rookie retention, field-size handling, determinism).
  `scripts/22_compare_win_probability_models.py` runs it read-only
  against production with live progress + elapsed time. 235/235 full
  suite passing at implementation time — see "M0-M6 model comparison"
  below for the exact commands.
- ✅ **M4 frozen as the v1 production model, 2026-08-25** — run against
  the real production DB at eligibility thresholds 5/8/10, M4
  (`prior_avg_round_score_to_par` + `prior_recent_form_10`) had the
  best mean log loss at every threshold. No M7/challenger was created,
  M4 was not retuned on the KG Ladies Open, and no probability cap/
  manual weight/hand-set rookie probability/post-hoc calibration was
  added. A known, documented, NOT-yet-corrected limitation: coarse
  calibration diagnostics suggest over-confidence in the ~10-20%
  probability bins. See `docs/SITE_STRUCTURE_TODO.md` section 10 for
  the exact evidence.
- ✅ **Read-only production inference layer: IMPLEMENTED, 2026-08-25** —
  `src/klpga/models/inference.py` + `scripts/23_predict_tournament_win_probabilities.py`
  predict an upcoming tournament's live `tournament_entry` field under
  frozen M4, reusing every existing feature/shrinkage/fitting component
  unchanged. Never guesses a historical cutoff date; a zero-history or
  `player_master`-unmatched entrant (e.g. player_code=13355) is never
  dropped, zeroed, or hand-assigned a probability. 21 new tests,
  including the 12 mandatory adversarial tests. 256/256 full suite
  passing. **No KG Ladies Open probability has been computed or
  displayed inside this sandbox** — see "Live tournament-field
  win-probability inference" below for the exact production command to
  run on the Windows machine.
- ✅ **First production inference run completed, 2026-08-26** — the
  Windows production run against gameCode=2026080001 (제15회 KG
  레이디스 오픈) succeeded: field 120, cutoff 2026-08-27 (explicit_arg),
  100 historical training tournaments, entrants predicted 120, dropped
  0, probability sum 1.00000000, 5/5 required checks PASS. Its
  complete 120-row output was not captured to a machine-readable file
  at the time — see the **NEO Prediction Archive** below for how this
  is honestly preserved (as a cross-checked `rerun_reconstruction`,
  never labeled "original").
- ✅ **NEO Prediction Archive: IMPLEMENTED, 2026-08-26** —
  `src/klpga/archive/` + `scripts/24_archive_prediction.py`: an
  immutable, append-only JSON+CSV snapshot of exactly what M4 predicted
  before a tournament began. Computes nothing — only reshapes and
  atomically persists an already-computed `InferenceResult`. A
  duplicate `(prediction_id, game_code)` always aborts loudly before
  any write; a `rerun_reconstruction` (for a run whose output wasn't
  captured, like #001) is only ever archived after passing a hard
  cross-check against independently-recorded facts from the real run.
  18 new tests. 274/274 full suite passing. See
  `docs/PREDICTION_ARCHIVE.md` and "NEO Prediction Archive" below.
- ✅ **Prediction #001 archived, 2026-08-26** — as a cross-checked
  `rerun_reconstruction` (never labeled "original") against the exact
  first-run facts (top player 서교림/11134, ~10.097% display
  probability, 100 training tournaments, field 120). See
  `predictions/2026/prediction_001_2026080001.json`.
- ✅ **NEO Predictions public site: IMPLEMENTED, 2026-08-26** —
  `src/klpga/site/` + `scripts/25_build_predictions_site.py`: a static-
  site generator reading ONLY the immutable archive — never the DB,
  never `run_inference` (source-checked, not just intended).
  Korean-first, mobile-first, no sportsbook visual language. The build
  hard-fails on a field_size mismatch, a rank gap, or a non-positive
  `maximum_probability` — never a partial/wrong-looking page.
  Percent rounding is display-only; ranking can never be altered by
  search/filter (verified at the DOM level with Playwright — already
  a declared dependency, not a new one). 21 new tests (15 build-level +
  6 real browser tests). 295/295 full suite passing. Generated output
  is a build artifact, not committed to git. See
  `docs/PREDICTIONS_SITE.md` and "NEO Predictions — public site" below.
- ✅ **Public-site v1.1 copy release, 2026-08-26** — removed all
  reader-facing "M4"/model-version/calibration-limitation/internal-
  docs references (the archive JSON's `model_id`/`model_version`/
  `known_limitations` are untouched — only no longer rendered as
  visible prose); added a "왜 이 선수의 우승확률이 높을까요?" section
  (archived data only) and a public summary strip; simplified the
  Prediction Record panel to 4 public facts. `prior_recent_form_10` is
  never described as a per-round figure (it's a per-tournament
  average — confirmed by re-reading the source formula, not assumed);
  `prior_avg_round_score_to_par` is the only metric legitimately
  labeled "per round." 9 new regression tests guard against SG/GIR/
  driving/putting ever being claimed as inputs. 304/304 full suite
  passing. Prediction #001's archive JSON/CSV are unmodified (byte-
  identical, confirmed via `git diff`/hash).
- ✅ **Public-site v1.2 visual-hierarchy pass, 2026-08-26** — a brand
  architecture (master brand `NEO`, acronym meaning "Numbers ·
  Evidence · Oracle" shown in the hero only, category descriptor "Golf
  Intelligence," product name "NEO Predictions" for `<title>`/footer
  only) replaces the retired "NEO GOLF PREDICTIONS" brand string
  everywhere on the site. A new hero section is now the dominant
  visual object on a prediction page — brand lockup, then `NEO
  PREDICTION #001` / tournament / player name + `10.10%` / "우승확률 ·
  전체 120명 중 1위" / "PRE-TOURNAMENT · LOCKED" — with the player name
  never rendering smaller than the probability (equal `font-size` at
  every breakpoint, verified live via a Playwright computed-style
  comparison, not just a CSS rule). The WHY section was rebuilt as
  three scannable cards (LONG-TERM / RECENT FORM / EXPERIENCE, still
  only archived values — no new metric introduced), with the
  recent-form-10 unit clarifier rendered inside its own card rather
  than a page-bottom footnote. Ranking now defaults to TOP 10
  (`TOP 10 | TOP 20 | 전체 120명`), server-rendered so it holds even
  without JS — all 120 entrants still always render, none dropped.
  Fixed a real bug this surfaced: with `top10` as the default filter,
  a search hit outside the top 10 briefly returned zero results;
  an active search query now bypasses the rank filter, so all 120
  entrants stay reachable by search regardless of which filter pill is
  active. 4 new/rewritten tests. 308/308 full suite passing.
  Prediction #001's archive JSON/CSV remain byte-identical (confirmed
  via `git diff`/hash). See `docs/PREDICTIONS_SITE.md` "Brand
  architecture, v1.2."
- ✅ **KLPGA official record-taxonomy discovery, Rounds 1-3,
  2026-08-26** — a separate research track (not the tournament-results
  pipeline above): `docs/KLPGA_OFFICIAL_DATA_MAP.md`,
  `docs/NEO_DERIVED_METRIC_MAP.md`, `docs/NEO_DATA_RIGHTS_MATRIX.md`,
  and `docs/HISTORICAL_METRICS_COLLECTION_DESIGN.md` (design-only
  proposal connecting this track's discovered `loadLocationRecord`
  taxonomy to the `player_stats_snapshot` table below — not yet
  implemented)
  document what the official `/load/record/loadLocationRecord` API
  (Strokes Gained, tee/approach/putting category stats) exposes,
  entirely from evidence the user captured manually in DevTools — this
  project's own environment has never once reached `klpga.co.kr`. Round
  3 built (and 339/339-tested) `src/klpga/discovery/` — menu-taxonomy
  discovery, a response parser, and collision detection — plus
  `scripts/26_discover_klpga_record_taxonomy.py`, a **Phase A only**
  tool (discovers the menu structure, never fires a live
  `loadLocationRecord` request). Real regression value already paid
  off during implementation: the collision-detection logic's first
  draft would have missed the actual Round-1 finding (`menu3=010102`
  reused under the same menu1/menu2 with a different label) until a
  test built directly from that real evidence caught the bug. Not yet
  run against the live site — awaiting the exact Windows command in
  that doc. No SG/driving/approach/putting data has entered
  `klpga.sqlite`, the prediction model, or the archive from this track.

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

## Current goal: run the M0-M6 comparison on real production data and judge it

The raw 100-tournament dataset is validated, the derived analytics
layer is fully verified against production, the entry-list source is
confirmed and live-verified end-to-end, the point-in-time feature +
walk-forward backtest layer is implemented and leakage-tested, the
model EVALUATION methodology is frozen
(`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`), and the `M0`-`M6`
walk-forward comparison ITSELF is now implemented and tested (see
status above and `docs/SITE_STRUCTURE_TODO.md` sections 7-9).
**No model has been run against real production data, and no model has
been selected** — per explicit instruction, this session stops here.
Next: run `scripts/22_compare_win_probability_models.py` on the
Windows PC at threshold 5, then 8 and 10 as a sensitivity check, and
judge the results against the frozen spec's Section 11 promotion
criteria — not a redesigned process chosen after seeing results.

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
21 `derived_*` columns per `player_id` (the confirmed real KLPGA
playerCode, never player_name) from the validated `tournament_master` /
`player_event` / `player_round` dataset — tournaments played, rounds
played, made cuts + cut rate, wins, top 5, top 10, best finish, a true
per-round scoring average + std dev, a per-EVENT average score-to-par
and a per-ROUND rate score-to-par (see naming convention below),
recent-form averages over the 5/10/20 most recent events (each with a
companion `_n` sample-size column), and a linearly-weighted recent-form
figure over up to the 10 most recent events. **Every metric's exact
source field, formula, sample size, and missing-data treatment is
documented in that module's docstring.**

**Naming convention (added after a red-team check — see status above):**
`player_event.score_to_par` is a per-tournament CUMULATIVE total (the
site's own `data-totunderpar`), not a per-round figure. Any `derived_*`
column built from it MUST include `_event_` in its name; any column
built from real per-round data (`player_round.round_score` /
`round_to_par`) or expressed as a per-round rate MUST include `_round_`
— so a tournament-total metric can never be mistaken for a per-round
one just from its name. `derived_avg_event_score_to_par` averages
`score_to_par` one-event-one-vote; `derived_avg_round_score_to_par` is
`sum(score_to_par)/sum(rounds_played)`, a rounds-weighted rate
comparable in magnitude to a single round's performance.
`scripts/12_verify_round_to_par_reliability.py` mathematically verifies
the round-rate formula against real per-round `round_to_par` data.

These are clearly separated in `schema.sql` from the pre-existing
OFFICIAL Data Center columns (which stay NULL) via a
`snapshot_type='derived_trailing100'` row and a `derived_` column-name
prefix — never conflated with an official KLPGA statistic.
`src/klpga/db/migrate.py` safely adds new/renamed columns to an
existing DB, even one already populated with `derived_trailing100`
rows (those are always fully reproducible by re-running `09`, so
dropping and rebuilding them is safe) — it refuses and raises only if a
row exists under any OTHER snapshot_type (real, non-reproducible
official-stat data).

```bash
python scripts/09_build_player_stats_snapshot.py --db data/klpga.sqlite
python scripts/10_print_snapshot_samples.py --db data/klpga.sqlite --limit 10
python scripts/11_diagnose_avg_score_to_par.py --db data/klpga.sqlite
python scripts/12_verify_round_to_par_reliability.py --db data/klpga.sqlite
```

`09` always fully regenerates every `derived_trailing100` row (DELETE +
re-INSERT) rather than an incremental upsert — see that script's
docstring for the specific SQLite NULL-uniqueness pitfall this avoids.
`10` and `11` are read-only. None of the three touch
`tournament_master`/`player_event`/`player_round` except to SELECT from
them — all are safe to run repeatedly against the already-validated
production DB without resetting or recollecting it.

`11` is the red-team check on `derived_avg_score_to_par` (see
`docs/SITE_STRUCTURE_TODO.md` section 6): for 5 representative players
it prints raw round scores, the sparse per-round `round_to_par`, the
tournament `total_score`/`score_to_par`, and a reverse-engineered
implied par per round (should land near 68-74 for every event if
`score_to_par` is a self-consistent tournament total).
`--names "이예원,박지영,김민솔,서교림,박민지"` picks specific players by
exact name match (falls back to the players with the most
`derived_tournaments_played` for any name that doesn't match). `12` is
the round_to_par reliability check — confirmed AGREE against production
(see status above).

## Entry-list collection — DONE, live-verified

Confirmed source: `GET /web/tourInfo/entry?gameCode=<code>` — a full
HTML page whose `<h2>전체 선수</h2>` table is the real entry list (a
second `<h2>즐겨찾기 선수</h2>` table is a hidden client-side favorites
duplicate and is excluded). See `docs/SITE_STRUCTURE_TODO.md` section 7
for the full confirmation log, the real HTML structure, and the
`tournament_entry` schema.

**Confirmed production run, 2026-08-25 (gameCode=2026080001, Windows
PC):** 120/120 rows parsed, 0 unparseable, 0 duplicate `player_code`s,
119 matched / 1 unmatched against `player_master` (99.17% match rate;
unmatched: `player_code=13355`, "배윤철 0908(A)" — a legitimate
new/rookie entrant, stored without fuzzy name matching).

```bash
# read-only diagnostic — no DB writes
python scripts/14_inspect_entry_list.py --game-code <code>
python scripts/14_inspect_entry_list.py --game-code <code> --db data/klpga.sqlite

# live collection — writes/UPSERTs tournament_entry, idempotent to re-run
python scripts/15_collect_entry_list.py --game-code <code> --db data/klpga.sqlite
```

Both require a machine with real internet access to `klpga.co.kr` (this
dev sandbox's own egress is confirmed blocked by policy for that host,
not just unreachable). `14` prints: the page's own summary-box counts,
the parsed entrant total (flagged if it doesn't match the summary), any
row that looked like an entrant but had no extractable `playerCode`
(never silently dropped), duplicate `playerCode`s, matched/unmatched
counts against `player_master` when `--db` is given (matched by
`player_code` only, never by name), and 10 sample entrants — and makes
no DB writes. `15` does the same fetch/parse/report, then UPSERTs every
parsed entrant into `tournament_entry` keyed on
`(game_code, player_code)` — safe to re-run for the same gameCode (no
duplicate rows), additively creates the table on a DB that predates it,
and never touches `tournament_master`/`player_master`/`player_event`/
`player_round`. Only genuinely confirmed fields are stored
(`player_name_display`, `nationality`, `qualification_category`,
`qualification_reason`, `source`, `collected_at`) — no `entry_status`,
WD/DNS, SG, GIR, or course-par field exists, since none has a confirmed
source on this page (see `docs/SITE_STRUCTURE_TODO.md` section 7).

`scripts/13_discover_entry_list.py` (the earlier, now-superseded
automatable half of the original investigation — broadened-keyword link
discovery) remains in the repo for reference; the confirmed source above
supersedes it.

## Point-in-time backtest layer + production diagnostics (current goal — see status above)

`src/klpga/backtest/` computes every feature strictly from a player's
OTHER tournaments before a target tournament's confirmed start date —
see `docs/SITE_STRUCTURE_TODO.md` section 8 for the full architecture,
feature definitions, and leakage-test results. **None of the commands
below have been run against the real production DB yet** — this is
the exact set to run on the Windows PC before any model-design
decision.

**Two related but DIFFERENT population definitions, audited
2026-08-25** (see section 8's "population-definitions audit" for the
full write-up): script `17`'s rows are the **eligible-at-threshold-k**
subset (an additional prior-history filter on top); script `21`
reports the full **usable** population unconditionally (no filter at
all — identical to script `17`'s own threshold=0 row). Don't expect a
threshold>0 row from `17` to match `21`'s totals — that gap is the
trade-off `17` exists to show.

```bash
# Point-in-time audit — one target tournament, selected players: exact
# cutoff, exact prior tournaments/recent-form events used, every
# feature value, target outcome shown separately as LABEL.
python scripts/16_backtest_diagnostic.py --db data/klpga.sqlite --game-code <code>
python scripts/16_backtest_diagnostic.py --db data/klpga.sqlite --game-code <code> --players <code1>,<code2>

# Eligibility sweep — eligible targets/rows, % of usable corpus,
# earliest eligible target, prior_events_n distribution, across a
# threshold range. Chooses nothing.
python scripts/17_eligibility_report.py --db data/klpga.sqlite
python scripts/17_eligibility_report.py --db data/klpga.sqlite --thresholds 0,1,2,3,5,10,20,30

# Leakage invariance check on REAL production data (companion to the
# synthetic adversarial tests, not a replacement) — auto-picks a
# mid-corpus target + a real player with events on both sides of its
# cutoff, proves prior_event_ids_used excludes every after-cutoff event.
python scripts/18_leakage_invariance_check.py --db data/klpga.sqlite
python scripts/18_leakage_invariance_check.py --db data/klpga.sqlite --game-code <code> --player-code <code>

# Field-relative audit — round score, field benchmark, leave-one-out
# benchmark, field-relative score, and the exclusion-arithmetic proof.
# Never labeled Strokes Gained.
python scripts/19_field_relative_audit.py --db data/klpga.sqlite
python scripts/19_field_relative_audit.py --db data/klpga.sqlite --game-code <code> --round 2 --players <code1>,<code2>

# Feature redundancy report — pairwise correlation across the prior_*
# performance features. Reports only; removes/weights nothing.
python scripts/20_feature_redundancy_report.py --db data/klpga.sqlite
python scripts/20_feature_redundancy_report.py --db data/klpga.sqlite --min-n 50 --notable-threshold 0.6

# Data coverage report — non-NULL % and companion _n distribution for
# the sparser derived features (career rate, sparse round_to_par,
# field-relative, recent form 5/10/20).
python scripts/21_data_coverage_report.py --db data/klpga.sqlite
```

All six are read-only and never write to `tournament_master`/
`player_master`/`player_event`/`player_round`/`tournament_entry`.

## M0-M6 model comparison — DONE against real production data, M4 frozen as v1

`src/klpga/models/` implements exactly the ablation ladder frozen in
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` — no other feature. See
`docs/SITE_STRUCTURE_TODO.md` section 9 for the full architecture.
**Run against real production data, 2026-08-25** — M4
(`prior_avg_round_score_to_par` + `prior_recent_form_10`) had the best
mean log loss at every eligibility threshold swept (5, 8, 10) and is
now **frozen as the v1 production model**. See
`docs/SITE_STRUCTURE_TODO.md` section 10 for the exact evidence
(N/log-loss/paired-comparison numbers per threshold) and the known,
documented, NOT-yet-corrected calibration limitation (over-confidence
in the ~10-20% probability bins).

```bash
# Primary comparison at the v1 candidate threshold.
python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 5

# Sensitivity checks — run separately, compare, do not pick whichever
# threshold makes a model look best.
python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 8
python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 10

# All three in one run (repeats the full report per threshold):
python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 5,8,10

# A quick subset (e.g. just the baselines) for a fast sanity check:
python scripts/22_compare_win_probability_models.py --db data/klpga.sqlite --thresholds 5 --models M0,M1,M2
```

Read-only, prints progress per (target tournament, model) pair with
elapsed time so the terminal never appears frozen, then the full
report (leaderboard, paired Wilcoxon comparisons vs `M0` and `M1`,
calibration, time-stability, rookie/sparse-history audit) for each
threshold. Runtime may be substantial (a deterministic grid-search MLE
fit is re-run for every eligible target × every model) — this is
expected, not a hang. Makes no DB writes and selects no winning
model — judge the output against
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md` Section 11.

## Live tournament-field win-probability inference (production, read-only)

`src/klpga/models/inference.py` + `scripts/23_predict_tournament_win_probabilities.py`
— read-only production inference for one UPCOMING tournament's live
`tournament_entry` field, under the frozen v1 model M4. See
`docs/SITE_STRUCTURE_TODO.md` section 10 for the full architecture,
the strictly-prior cutoff policy, and rookie/unmatched handling.

```bash
# Production command — works if tournament_master already has a row
# for this gameCode with a resolvable start_date/end_date:
python scripts/23_predict_tournament_win_probabilities.py --db data/klpga.sqlite --game-code 2026080001

# If tournament_master has NO row (or no usable date) for this
# gameCode, --cutoff-date is required — this script never guesses a
# cutoff (e.g. "today"):
python scripts/23_predict_tournament_win_probabilities.py --db data/klpga.sqlite \
    --game-code 2026080001 --cutoff-date 2026-08-28 --tournament-name "제15회 KG 레이디스 오픈"
```

Read-only (`mode=ro` connection) — never writes to
`tournament_master`/`player_master`/`player_event`/`player_round`/
`tournament_entry`/`player_stats_snapshot`, and creates no probability
table. Prints the tournament header (name, gameCode, field size,
historical cutoff date + source, training tournament count, model
ID/features, the documented calibration limitation), the full
descending probability table (rank, player_code, player_name,
win_probability, win_probability_pct, prior_events_n,
prior_avg_round_score_to_par, prior_recent_form_10,
prior_recent_form_10_n, history_slice, an explicit `[UNMATCHED vs
player_master]` marker for entrants like player_code=13355), the
sum/min/max probability and zero-history/unmatched/predicted counts,
and 5 required final checks (entrants parsed/predicted = field size,
dropped entrants = 0, duplicate player_codes = 0, probability sum =
1.000000 +/- 1e-6). Every entrant in `tournament_entry` is guaranteed
to appear in the output — none is ever silently dropped.

## NEO Prediction Archive — immutable pre-tournament records

`src/klpga/archive/` + `scripts/24_archive_prediction.py` — runs
`scripts/23`'s inference exactly once and archives the EXACT output as
an immutable, append-only JSON+CSV snapshot under `predictions/`. See
`docs/PREDICTION_ARCHIVE.md` for the full schema, the
MODEL VERSION / PREDICTION ID / PREDICTION DATE-CUTOFF / POST-TOURNAMENT
RESULT distinction, and the immutability/provenance guarantees.

```bash
# Live prediction (#002 onward) — the sanctioned command going forward.
python scripts/24_archive_prediction.py --db data/klpga.sqlite --game-code 2026080001 \
    --prediction-id 002 --source live_atomic_inference

# Prediction #001 — a controlled RECONSTRUCTION of the first successful
# pre-tournament run, whose complete 120-row output was never captured
# to a machine-readable file. Requires cross-checking against facts
# observed from that real run; aborts on any mismatch and never labels
# the result "original."
python scripts/24_archive_prediction.py --db data/klpga.sqlite --game-code 2026080001 \
    --cutoff-date 2026-08-27 --tournament-name "제15회 KG 레이디스 오픈" \
    --prediction-id 001 --source rerun_reconstruction \
    --verify-training-tournament-count 100 --verify-field-size 120 \
    --verify-dropped-entrants 0 --verify-probability-sum 1.000000 \
    --verify-top-player-code 11134 --verify-top-player-name "서교림" \
    --verify-top-player-display-pct 10.097
```

Read-only against the source DB (`mode=ro`, identical to `scripts/23`)
and append-only against the archive: a duplicate `(prediction_id,
game_code)` aborts loudly before anything is written — never
overwritten, never regenerated from newer data. JSON is authoritative;
the CSV is a regenerable convenience representation. Post-tournament
evaluation (design only, not yet implemented) will always read an
archived snapshot and write a separate file — never mutate the
original.

## NEO WIN % v0.1 — BETA #001 (new, separate from Prediction #001)

`src/klpga/neo_win/` + `src/klpga/analytics/neo_performance_dataset.py`
+ `scripts/33_predict_neo_win.py` — a second, standalone win-probability
pipeline, reusing the M0-M6 ladder's already-validated pure math
(shrinkage, softmax, MLE fitting) but with its OWN feature set (career
scoring + recent form + a new point-in-time consistency/downside-risk
feature + a validated prior-season official KLPGA metric) and its OWN
frozen-snapshot archive at `neo_win_predictions/` — never touching
`klpga.models`, `predictions/`, or the frozen M4 model in any way. See
`docs/NEO_WIN_V0_1_METHODOLOGY.md` for the full design writeup
(feature definitions, leakage validation, missing-data treatment,
orientation allowlist for the official-metric feature).

`scripts/34_audit_neo_win_player.py` — read-only diagnostic audit of an
already-frozen prediction (identity trace, DB-confirmed season/win
reconstruction, refit-and-verify feature decomposition, TOP10 sanity
sweep, rule-based verdict) — never modifies the frozen artifact.

`scripts/35_predict_neo_win_post_r1.py` (`src/klpga/neo_win/round_
update.py`) — BETA #001-R1: combines the frozen PRE prediction with the
real, already-collected Round-1 leaderboard via a Monte Carlo
tournament simulation over the remaining rounds, producing WIN/TOP5/
TOP10/TOP20/MAKE_CUT probabilities for the full field. Verified from
real evidence that KLPGA tournaments in this dataset use a single
36-hole cut with no subsequent cut (docs/SITE_STRUCTURE_TODO.md) —
never simulates an R3/R4 cut. Writes its own separate, append-only
`neo_win_001-R1_<game_code>.json` snapshot alongside (never overwriting)
the PRE snapshot.

```
python scripts/33_predict_neo_win.py --db data/klpga.sqlite --game-code <code> --cutoff-date YYYY-MM-DD
python scripts/33_predict_neo_win.py --db data/klpga.sqlite --game-code <code> --cutoff-date YYYY-MM-DD --freeze --prediction-id 001
```

## BETA #001-C — data integrity + official metric integration

A corrected, evidence-driven rebuild of BETA #001's identity resolution
and official-metric feature layer, triggered by a real bug the Seo
Gyo-rim diagnostic exposed and a follow-up audit confirmed: the label
"평균 티샷 거리" is not globally unique across identity_keys (it names
three semantically different driving-distance metrics), so BETA #001's
original label-only pivot could non-deterministically pick the wrong
one. `klpga.neo_win.official_metrics`/`metric_domain_map.py` now pin
every candidate to `(identity_key, label)`, never a bare label — BETA
#001's own pipeline is otherwise completely unmodified.

New, parallel modules (never touching `klpga.neo_win.dataset`/
`official_metrics.py`'s existing 4-slot design, `klpga.neo_win.archive`,
or `predictions/`):

- `klpga.neo_win.identity_resolution.build_full_identity_crosswalk` —
  CLEAN/PARTIAL/AMBIGUOUS/BROKEN/UNMATCHED classification for every
  player identity seen anywhere in the DB.
- `klpga.discovery.flag_recovery` — separates VALUE_VALIDITY from
  RANK_VALIDITY for a FLAGGED `official_metric_value` response (a pure
  rank-column artifact never proven to corrupt the paired value).
- `klpga.neo_win.metric_domain_map` — classifies every canonical
  metric into DRIVING/APPROACH/SHORT_GAME/PUTTING/SCORING/OVERALL and
  gates `usable_for_model`.
- `klpga.neo_win.feature_matrix` / `beta001c_dataset` — domain-
  aggregate official-metric features (`neo_driving`, `neo_approach`,
  `neo_short_game`, `neo_putting`, `neo_overall_skill`; `neo_scoring`
  is always excluded — duplicate representation of the existing
  `prior_avg_round_score_to_par` base feature) plus five win-feature
  candidates (`klpga.neo_win.win_features`).
- `klpga.neo_win.backtest_eval` — a NEW, standalone walk-forward
  evaluator (never `klpga.models.walk_forward_eval`, which is
  hard-coded to the frozen M0-M6 ladder) comparing MODEL_A (base),
  MODEL_B (+ official-metric domains), and MODEL_C (+ win features).
  `select_best_beta001c_model` applies the SAME evidence-only
  complexity tie-break `docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`
  already established for M0-M6: a more complex model is promoted only
  on a statistically significant paired-log-loss improvement.
- `klpga.neo_win.beta001c_archive` — a separate, append-only frozen
  archive at `neo_win_c_predictions/` (never `neo_win_predictions/`,
  never `predictions/`; `prediction_id="001"` is refused outright).
- `klpga.neo_win.comparison` / `redteam` — BETA #001 vs #001-C
  per-player comparison and a TOP20 red-team audit
  (CLEAN/DATA_WARNING/IDENTITY_WARNING/MODEL_WARNING).

```
python scripts/36_build_beta001c_feature_matrix.py --db data/klpga.sqlite --game-code <code> --cutoff-date YYYY-MM-DD
python scripts/37_beta001c_model_backtest.py --db data/klpga.sqlite --threshold 10
python scripts/38_predict_beta001c.py --db data/klpga.sqlite --game-code <code> --cutoff-date YYYY-MM-DD --freeze --prediction-id 001-C
python scripts/39_compare_beta001_vs_c.py --pre-001-json neo_win_predictions/<year>/neo_win_001_<code>.json --c-json neo_win_c_predictions/<year>/neo_win_c_001-C_<code>.json --highlight <exact real player names>
python scripts/40_redteam_beta001c_top20.py --db data/klpga.sqlite --c-json neo_win_c_predictions/<year>/neo_win_c_001-C_<code>.json
```

## NEO Predictions — public site

`src/klpga/site/` + `scripts/25_build_predictions_site.py` — a static-
site generator over the immutable prediction archive. Read-only,
Korean-first, mobile-first. See `docs/PREDICTIONS_SITE.md` for the
full architecture, routes, data flow, and every derived Korean label
(with rationale).

```bash
# Build the static site.
python scripts/25_build_predictions_site.py --predictions-dir predictions --output-dir web/dist

# Local preview (root-relative links require an HTTP server, not file://).
python -m http.server 8000 --directory web/dist
# then open http://localhost:8000/
```

Reads only `predictions/*/*.json` via the existing, unmodified
`klpga.archive.prediction_archive.read_prediction_snapshot` — never
opens the SQLite database, never calls
`klpga.models.inference.run_inference`. The build hard-fails (writes
nothing) if a rendered player count doesn't match the archive's
`field_size`, the rank sequence has a gap, or `maximum_probability`
isn't strictly positive — never a partial or silently-wrong page.
Percent rounding happens only at render time; the embedded per-page
JSON and every underlying value stay at the archive's full precision.
Search/filter only toggle visibility of already-rendered rows — there
is no client-side sort anywhere, so ranking can never be altered by
user interaction (verified at the DOM level with Playwright, already
declared in `requirements.txt`). The generated `web/dist/` output is a
build artifact and is **not committed to git** — see
`docs/PREDICTIONS_SITE.md`.

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
    entry_list.py                 /web/tourInfo/entry adapter: fetch, match to player_master by
                                   player_code, cross-check against a completed tournament's
                                   player_event — see "Entry-list collection" above
  parsers/
    leaderboard_parser.py       HTML fragment -> per-player round data, via data-*/_ attributes
    entry_list_parser.py        entry-list HTML page -> per-entrant rows (excludes the hidden
                                 favorites table, tracks 자격자/추천자/초청자 category, reports
                                 unparseable rows explicitly — see "Entry-list collection" above)
  db/
    schema.sql                  SQLite schema (5 spec tables + tournament_entry + collection_runs
                                 audit log)
    init_db.py                  create/reset klpga.sqlite
    upsert.py                   idempotent UPSERT helpers (incl. tournament_entry) + collection_runs
                                 logging
    export_csv.py               SQLite -> the 5 spec CSV files (stdlib csv/sqlite3 only, no pandas —
                                 see docs/SITE_STRUCTURE_TODO.md section 5 for why)
    migrate.py                  safe additive migrations: player_stats_snapshot derived_* columns
                                 (0-rows-only), and tournament_entry (purely additive, brand-new table)
  analytics/
    player_stats.py             derived player_stats_snapshot metrics — formulas/provenance in its
                                 own docstring, see "Analytics layer" above
  backtest/
    temporal.py                  the single source of truth for tournament date ordering: confirmed
                                  start_date preferred, end_date fallback, fail-safe exclusion on
                                  same-day/missing-date ambiguity — see docs section 8
    historical_field.py          reconstructs a historical target tournament's evaluation field from
                                  player_event (documented limitation: a RESULT field, not a confirmed
                                  historical ENTRY list — tournament_entry doesn't exist historically)
    point_in_time_features.py    the leakage-critical feature engine: every prior_* feature computed
                                  strictly from a player's OTHER tournaments before the target's
                                  effective date — see docs section 8 for the full feature reference
    walk_forward.py              build_walk_forward_dataset() + eligibility_sweep() (the
                                  minimum-history trade-off report, no hard-coded threshold)
  models/
    math_utils.py                 dependency-free deterministic grid-search MLE optimizer, softmax,
                                   clip-and-renormalize floor, Wilcoxon signed-rank test
    candidates.py                  the frozen M0-M6 feature sets, training-only shrinkage/
                                    standardization, MLE fitting, field-probability prediction
    metrics.py                     log loss, normalized Brier, rank/hit-rate diagnostics, coarse-bin
                                    calibration with tournament-level bootstrap CIs, paired comparison
    walk_forward_eval.py           run_multi_model_walk_forward() (the walk-forward fit/predict loop),
                                    time_stability_report(), rookie_slice_report()
    report.py                      leaderboard/paired-comparison/calibration/time-stability/rookie
                                    report formatting for scripts/22
    inference.py                   read-only PRODUCTION inference for an upcoming tournament's live
                                    tournament_entry field under the frozen v1 model M4 — orchestration
                                    only, reuses walk_forward/point_in_time_features/candidates/
                                    math_utils unchanged; see "Live tournament-field win-probability
                                    inference" above
  archive/
    prediction_archive.py          immutable prediction snapshot schema, atomic append-only writer,
                                    reader, and the rerun-reconstruction cross-check — computes
                                    nothing, only reshapes/persists an InferenceResult; see
                                    "NEO Prediction Archive" above and docs/PREDICTION_ARCHIVE.md
  site/
    build.py                       static-site generator: loads archived predictions (read-only,
                                    never the DB, never inference), hard-validates each one, writes
                                    the full static site — see "NEO Predictions — public site" above
    templates.py                   HTML rendering + every derived Korean label, with rationale, for
                                    the public site — see docs/PREDICTIONS_SITE.md
    static/app.js, styles.css      vanilla JS (search/filter/expand — never re-sorts rows) and
                                    mobile-first CSS

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
                                      sanity check for score_to_par, see "Analytics layer"
  12_verify_round_to_par_reliability.py  read-only red-team check: is player_round.round_to_par
                                          reliable enough to use directly, and does
                                          derived_avg_round_score_to_par's formula agree with it
  13_discover_entry_list.py          read-only: getGameList non-F breakdown + broadened
                                      entry/roster keyword link discovery — superseded once the
                                      real endpoint was confirmed, kept for reference
  14_inspect_entry_list.py           read-only entry-list diagnostic: fetch, parse, cross-check
                                      against the page's own summary count, report unparseable
                                      rows/duplicates, optional player_master matching — see
                                      "Entry-list collection" above; no DB writes
  15_collect_entry_list.py           live collection: fetch, parse, UPSERT tournament_entry
                                      (idempotent), report matched/unmatched vs player_master,
                                      collection_runs audit log — see "Entry-list collection" above
  16_backtest_diagnostic.py          read-only: for one target tournament + selected players, prints
                                      the exact feature cutoff date, exact prior tournaments/recent-
                                      form events used, every point-in-time feature value, and the
                                      target's real outcome shown separately as a LABEL — see
                                      docs/SITE_STRUCTURE_TODO.md section 8; no DB writes
  17_eligibility_report.py           read-only: eligibility_sweep() as a table across a threshold
                                      range — targets/rows retained, % of corpus, earliest eligible
                                      target, prior_events_n distribution. Chooses no threshold.
  18_leakage_invariance_check.py     read-only: auto-picks a real mid-corpus target + a real player
                                      with events on both sides of its cutoff, proves
                                      prior_event_ids_used excludes every after-cutoff event —
                                      production-data companion to the synthetic leakage tests
  19_field_relative_audit.py         read-only: round score, field benchmark, leave-one-out
                                      benchmark, field-relative score, and the exclusion-arithmetic
                                      proof for selected player/round examples. Never labeled SG.
  20_feature_redundancy_report.py    read-only: pairwise Pearson correlation (stdlib-only) across
                                      the prior_* performance features, with sample size shown.
                                      Reports only — removes no feature, picks no weight.
  21_data_coverage_report.py         read-only: non-NULL % and companion _n distribution for the
                                      sparser derived features (career rate, sparse round_to_par,
                                      field-relative, recent form 5/10/20)
  22_compare_win_probability_models.py  read-only: fits/predicts M0-M6 walk-forward at one or more
                                         thresholds, prints per-(target,model) progress + elapsed
                                         time, then the full comparison report — see "M0-M6 model
                                         comparison" above; no DB writes, selects no winning model
  23_predict_tournament_win_probabilities.py  read-only PRODUCTION inference: frozen model M4 against
                                               one upcoming tournament's live tournament_entry field —
                                               see "Live tournament-field win-probability inference"
                                               above; no DB writes, no probability table created
  24_archive_prediction.py           runs scripts/23's inference exactly once and archives the exact
                                      output atomically as an immutable JSON+CSV prediction snapshot
                                      (plus an explicitly-labeled, cross-checked rerun_reconstruction
                                      mode for Prediction #001) — see "NEO Prediction Archive" above
  25_build_predictions_site.py       builds the static NEO Predictions site from predictions/
                                      only — no DB, no inference; see "NEO Predictions — public site" above

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
  test_tournament_entry.py        tournament_entry migration safety (never touches the validated
                                   tables), upsert idempotency, the confirmed unmatched-rookie-entrant
                                   case (player_code=13355), pure row-shaping
  test_collect_entry_list.py      scripts/15's full collection flow against the real 120-row fixture:
                                   matched/unmatched reporting, idempotent re-collection, untouched
                                   validated tables, collection_runs audit log
  test_build_player_stats_snapshot.py  end-to-end: snapshot metadata, official columns stay NULL,
                                        re-running replaces rather than duplicates rows
  test_print_snapshot_samples.py  read-only sample printer: 2dp formatting, never writes to the DB
  test_diagnose_avg_score_to_par.py  implied-par sanity check fires on corrupted data, never
                                      writes to the DB
  test_verify_round_to_par_reliability.py  check A/B pass on consistent synthetic data and fire
                                            on deliberately corrupted data, never writes to the DB
  test_discover_entry_list.py     keyword-link matcher + getGameList candidate-selection logic
                                   against a fake client, no network
  test_entry_list_parser.py       entry_list_parser tests against the real captured
                                   entry_list_sample.html fixture — 문정민 -> playerCode 10296
                                   cross-check, 5 more real players, summary/row-count
                                   reconciliation, favorites-table exclusion
  test_entry_list_collector.py    fetch_entry_list/match_entries_to_player_master/
                                   cross_check_against_player_event against a fake client and a
                                   real schema.sql-built temp DB, no network
  test_inspect_entry_list.py      scripts/14's report logic against the real fixture: summary
                                   match, unparsed-row/duplicate reporting, player_master
                                   matched/unmatched counts
  test_point_in_time_features.py  klpga.backtest's leakage-critical feature engine — baseline
                                   correctness, same-day/missing-date fail-safe exclusion, and the
                                   MANDATORY adversarial leakage tests (future tournaments,
                                   target-tournament rows, extreme canary scores/wins — target
                                   features never change)
  test_historical_field.py        historical field reconstruction from player_event, and the
                                   identity/label field separation
  test_walk_forward.py            walk-forward dataset row shape, rookie retention with zero prior
                                   events, no silent drops, eligibility sweep math on a
                                   hand-computable 4-tournament synthetic corpus
  test_backtest_diagnostic.py     scripts/16's report logic: cutoff date, feature/label separation,
                                   unknown gameCode and not-in-field player handling
  test_eligibility_report.py      scripts/17's report matches eligibility_sweep() exactly, does not
                                   choose a threshold, reports skipped undated tournaments
  test_leakage_invariance_check.py  scripts/18's real-data classification: auto-select middle
                                     target + prolific player, explicit target/player, unknown
                                     gameCode, and the no-qualifying-player edge case
  test_field_relative_audit.py    scripts/19's leave-one-out arithmetic against hand-computed
                                   scores, auto-select-largest-field, never-labeled-SG, n=1 field
  test_feature_redundancy_report.py  hand-rolled Pearson correlation against known values,
                                      pairwise-deletion sample sizing, no-decision framing
  test_data_coverage_report.py    coverage/_n-distribution math against hand-built rows, empty
                                   dataset handling
  test_population_definitions.py  the 2026-08-25 population-definitions audit: proves script 17's
                                   threshold=0 is definitionally identical to script 21's
                                   unconditional totals, and that threshold=k removes exactly the k
                                   earliest tournaments (and exactly their field-size row count) —
                                   not a bug, see docs/SITE_STRUCTURE_TODO.md section 8
  test_model_math_utils.py        deterministic grid-search optimizer, softmax, clip-and-renormalize
                                   floor, Wilcoxon test against known values
  test_model_candidates.py        frozen M0-M6 feature sets match the spec exactly (and no forbidden
                                   feature leaks in), shrinkage/standardization math, valid probability
                                   distributions for every model
  test_model_metrics.py           log loss/Brier/rank/calibration/paired-comparison hand-computed
                                   against known values
  test_model_walk_forward_eval.py  the mandatory adversarial set: sums to 1/finite/non-negative,
                                    target/future-tournament leakage, rookie retention with p>0,
                                    field-size handling, determinism
  test_compare_win_probability_models_script.py  scripts/22's report output, progress printing, no
                                                  DB writes, unknown-model-id rejection
  test_model_inference.py         scripts/23's production inference layer — the 12 mandatory
                                   adversarial tests (target/future-tournament leakage, all entrants
                                   survive, zero-history/unmatched entrants get p>0, duplicate
                                   player_code rejection, finite/non-negative/sums-to-1 probabilities,
                                   run-to-run and entry-row-order determinism, target excluded from
                                   feature histories, no feature outside frozen M4) plus cutoff/
                                   tournament-name resolution and the read-only-DB guarantee
  test_prediction_archive.py      the archive layer's required properties: duplicate prediction_id
                                   cannot overwrite, every entrant preserved (incl. zero-history and
                                   unmatched), field_size == row count, probability sum preserved
                                   exactly, player_code uniqueness, a later DB mutation cannot modify
                                   an already-written archive, reading never needs write access,
                                   deterministic serialization, and a partial/failed CSV write never
                                   leaves a corrupt file at the final name — plus the reconstruction
                                   cross-check's match/mismatch/skip-unset-fields behavior
  test_predictions_site_build.py  the public site never reads the DB/inference (source-checked), all
                                   entrants rendered/available, displayed ranking always follows
                                   archive rank order, percent rounding is display-only (embedded
                                   full-precision value asserted untouched), zero-history/unmatched
                                   entrants remain visible, reading an archive needs no write access,
                                   and the build hard-fails (writes nothing) on a field_size mismatch,
                                   a rank gap, or a non-positive maximum_probability
  test_predictions_site_browser.py  Playwright, DOM-level: search and TOP10/TOP20 filters never
                                     reorder rows (only hide/show), expand/collapse toggles correctly,
                                     a 360px mobile viewport needs no horizontal scroll — skips
                                     gracefully (never fails the suite) if Chromium isn't available
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
