# Historical Official-Metrics Collection — Design + Implementation (Round 11 continued / Round 12)

**Status as of Round 12: the mapping, storage schema, ingestion, and
season-level collector described below are IMPLEMENTED and offline-
tested** (see `docs/KLPGA_OFFICIAL_DATA_MAP.md`'s Round 12 section for
the full change log) — `src/klpga/discovery/identity_mapping.py`,
`src/klpga/discovery/season_metric_collector.py`, `official_metric_
value` in `schema.sql`, `scripts/run_klpga_season_metrics_collector.
py`. **No LIVE acquisition has been executed** — this sandbox still
has no network route to klpga.co.kr; see that section's LOCAL_
EXECUTION_REQUIRED note for the exact command to run for real. §2-§7
below are kept as the original design record (still accurate); §4 is
updated in place to state the actual chosen architecture, per Round
12's explicit "prefer extensibility, document the decision" instruction.

## 1. What already exists (confirmed, already built and live-run)

Two previously-separate subsystems in this repo need to be connected;
neither currently talks to the other.

**A. The 100-tournament production pipeline** (`src/klpga/collectors/`,
`src/klpga/db/schema.sql`, `scripts/01-05`) — already confirmed live
(2026-08-24 100-tournament run) and already stores, per `docs/SITE_
STRUCTURE_TODO.md`:
- `tournament_master` — event identity/metadata (100 most-recent
  completed regular-tour events).
- `player_master` — one row per player_id.
- `player_event` — one row per (player, event): finish position,
  made_cut/withdrawn/disqualified, rounds_played, r1-r4 scores, total
  score, score_to_par, prize_money.
- `player_round` — one row per (player, event, round_number): round
  score, round_to_par, birdies/eagles/pars/bogeys/double_bogey_plus.
- `player_stats_snapshot` — ALREADY has a `snapshot_type` column with
  exactly the values `pre_event` / `season_to_date` / `season_final` /
  `derived_trailing100`, an `as_of_date`, and a nullable
  `related_event_id` — plus named columns for `scoring_average`,
  `sg_total`, `sg_off_the_tee`, `sg_approach`, `sg_around_green`,
  `sg_putting`, `gir`, `driving_distance`, `driving_accuracy`,
  `putting_average`, `sixties_rate`, `top10_rate`, `birdie_average`,
  `par_breakers`, `sand_save`, `scrambling` — **every one of these
  columns is still NULL in every row today**, per that table's own
  schema comment: "This host [`data.klpga.co.kr`] has never been
  reached from any environment this project has run in."

**B. The Phase A/B official-record discovery subsystem**
(`src/klpga/discovery/`, `scripts/26-32`, this round's local collector)
— has spent many rounds discovering, parsing, and validating
`klpga.co.kr/load/record/loadLocationRecord` (the "거리기록 / 전체기록보기"
official-record interface), NOT `data.klpga.co.kr`.

### The connection nobody has stated explicitly yet

`player_stats_snapshot` group (a)'s column names (`sg_total`, `sg_off_
the_tee`, `sg_approach`, `sg_around_green`, `sg_putting`,
`driving_distance`, `driving_accuracy`, `putting_average`, ...) are
**the same statistics** the Phase A/B discovery subsystem's `menu1`
families describe (`Sg`, `Tee`, `Approach`, `Around`, `Putt`). This
strongly suggests `loadLocationRecord` is a real, reachable substitute
data source for the previously-assumed-unreachable `data.klpga.co.kr`
gap `SITE_STRUCTURE_TODO.md` section 3 describes — via a different
host/endpoint than originally assumed, not a different underlying
statistic. **This has never been independently confirmed** (no
side-by-side comparison of a `data.klpga.co.kr` value against a
`loadLocationRecord` value for the same player/stat/season exists,
because `data.klpga.co.kr` has never been reachable at all) — it is a
strong, evidence-grounded hypothesis, not a proven fact, and must be
stated as such wherever it's used.

## 2. Critical architectural fact: these metrics are SEASON-level, not tournament-level

`RECORD_TAXONOMY_ENDPOINT`'s confirmed request form (`src/klpga/
config.py`, `record_fetch.request_form`) is exactly:

```
{season: <year>, menu1: <code>, menu2: <code>, [menu3: <code>]}
```

**There is no tournament/game identifier in this request at all.**
Every `loadLocationRecord` response is therefore a *season-wide*
ranking/stat page (KLPGA's "기록실"), not a per-tournament breakdown.
This is NOT a gap to work around — it is exactly what `player_stats_
snapshot`'s own pre-existing design already anticipated: `snapshot_
type` distinguishes `pre_event` (as of just before one specific event)
from `season_to_date`/`season_final`, and `as_of_date` + nullable
`related_event_id` model "a season-level stat, captured at a point in
time, optionally associated with one event for point-in-time
reconstruction" — precisely the season-level shape `loadLocationRecord`
actually has. **Do not design a per-tournament breakdown of these
metrics — the real site does not offer one via this endpoint, and
inventing one would be exactly the kind of fabricated field this
project's evidence discipline forbids.**

Practical implication: collecting these metrics for "100 tournaments"
does NOT mean 100× the canonical-metric request count. It means one
request per (season, canonical metric) — the 100 target tournaments
span some smaller number of distinct seasons (`tournament_master.
season`, already collected) — multiplied by however many `as_of_date`
snapshots point-in-time correctness requires per season (see §4).

## 3. What is genuinely NOT yet built

- **The identity_key → `player_stats_snapshot` column mapping.**
  Nothing in this repo currently maps e.g. `Sg::Putting` (or whatever
  the real, evidence-confirmed identity_key turns out to be — this
  must come from the real canonical plan, never guessed) to `sg_
  putting`. As of Round 11 continued (collision-audit resolution — see
  `docs/KLPGA_OFFICIAL_DATA_MAP.md`), 248/248 unique request identities
  are request-count-clean, so this mapping CAN now be started for
  247 of them; one (`Around::Around01::030101`) has one still-
  unexplained canonical label and stays unmapped in the SKIP_QUEUE
  until resolved with real evidence.

  **New finding from that round, relevant here**: for 14 of the
  30 colliding identity_key groups, the response's own real `menuName`
  is exactly `"<context label> - <measured-value label>"` — e.g.
  `Approach::Approach02::020201`'s two canonical labels ("그린 적중 시
  남은 거리" / "평균 남은 거리") are the two halves of ONE compound page
  title for ONE displayed column. This means the generic half
  ("평균 남은 거리", "평균 티샷 거리", etc.) is NOT a stable, reusable
  column name across the whole taxonomy — the SAME generic phrase
  recurs across `Approach02`/`Approach08`/`Approach10`/`Around02`/
  `Around04` etc., each in a DIFFERENT context, each a DIFFERENT real
  statistic. The identity_key → column mapping must key off the FULL
  compound title (or the `menu3` code) for these groups, never the
  generic half alone — using the generic half alone would silently
  collapse several genuinely distinct per-context stats onto one
  column.
- **A season-level acquisition script**, structurally parallel to
  `scripts/29_execute_phase_b2_full_sweep.py`/`run_klpga_collector.py`
  but iterating over `(season, canonical_metric)` pairs instead of
  `identity_key` alone for the missing-evidence set — reusing the same
  `PoliteHttpClient`/`fetch_and_analyze`/checkpoint/skip-queue pattern
  already proven twice in this project.
- **An ingestion step** that takes a parsed, validated
  `loadLocationRecord` response and writes `player_stats_snapshot`
  rows keyed by `(player_id, season, as_of_date, snapshot_type,
  related_event_id)` — including resolving `loadLocationRecord`'s
  player_code to `player_master.player_id`. `tournament_entry`'s
  schema comment states player_code "is the same identity space as
  player_master.player_id" for the *entry-list* endpoint — this has
  **never been independently confirmed for `loadLocationRecord`'s own
  player_code values**, and must be checked (not assumed) the first
  time real `loadLocationRecord` evidence with player rows is
  available.
- **Point-in-time (PIT) safety.** Every `MetricSchemaAnalysis` this
  project has ever produced carries `pit_status = "PIT_UNVERIFIED"` as
  a hardcoded constant (`response_schema.py`) — by explicit standing
  instruction, no round has been allowed to promote this to PIT-safe
  just because a `season=<year>` parameter happened to return data.
  Before any `loadLocationRecord` value is attached to a past event as
  a `pre_event`/`season_to_date` snapshot for model-feature use, this
  project needs real evidence answering: does `season=<a past year>`
  return that season's OWN final stats, or does it silently return
  current/live data regardless of the season parameter? This is
  exactly the same class of check `response_schema.classify_
  historical_availability` was already built for in Phase B1 — it has
  simply never been run against a real response, because none has
  existed in this sandbox.

## 4. Storage architecture decision (Round 12 — DECIDED, IMPLEMENTED)

Three options were weighed, per explicit instruction, before writing
any schema:

  **A. ~250 additive typed columns on `player_stats_snapshot`.**
  Rejected. Brittle by construction — every future taxonomy change
  (a new metric, a corrected label) needs a migration; most columns
  are NULL for most rows (no player has all 248 official stats
  populated at once in practice); and Round 11's own finding
  (§3 below) that the SAME generic label recurs across different
  `menu3` contexts means a naive label→column mapping would silently
  collapse genuinely distinct stats onto one column.

  **B. A normalized fact table, one row per `(season, player_code,
  identity_key, official_label)`.** CHOSEN. Every canonical metric —
  present today or discovered later — fits the SAME four columns of
  natural key without a migration; the taxonomy's own `menu1`/`menu2`/
  `menu3`/label vocabulary IS the schema, so adding coverage for the
  216 not-yet-evidenced identities never touches DDL. Matches this
  project's own established pattern for entities that scale
  unboundedly (`player_round`, `player_event` are already normalized-
  row tables, not flattened per-stat columns). Full provenance
  (`raw_sample_path`, `acquired_at`, `source_url`, `schema_
  fingerprint`, `parse_status`, `validation_status`, `pit_status`) is
  carried on every row, not bolted on separately.

  **C. A JSON metric payload column.** Rejected. Loses SQL-level
  queryability/indexing/typed validation; this project's schema.sql
  has never used a JSON blob anywhere, for exactly this reason —
  every other table spells out its columns explicitly, even where
  that meant tables like `player_stats_snapshot` growing large.
  A JSON blob would also make `official_metric_value`'s honest
  per-row status fields (parse/validation/PIT) harder to query in
  bulk than a real column.

**Implemented as `official_metric_value`** (`schema.sql` section 8,
`src/klpga/db/upsert.py`'s `upsert_official_metric_value`) — see that
table's own extensive schema comment for the full field list and
rationale, including why `identity_key` and `player_code` are
deliberately NOT foreign keys (the taxonomy is tracked in `docs/
discovery/`, not this database; the player_code identity-space match
is unconfirmed — see §3). `player_stats_snapshot` itself is
UNTOUCHED — its existing `derived_*`/group-(a) columns keep working
exactly as before; this is a wholly additive table.

## 5. Proposed request architecture (once the canonical plan is clean)

1. Enumerate distinct seasons spanned by the 100 target tournaments
   (`SELECT DISTINCT season FROM tournament_master` — already
   collected, zero new requests).
2. For each `(season, canonical_metric)` pair not yet in the
   checkpoint: one `loadLocationRecord` request — reusing `PoliteHttp
   Client`'s existing rate limiting/retry/hard-stop, unchanged.
3. Parse + validate exactly as `missing_evidence_acquisition.py`
   already does; write one `player_stats_snapshot` row per player
   row in the response, per the identity_key → column mapping (§3).
4. Checkpoint by `(season, canonical_metric)`, atomic, reusing
   `b2_checkpoint.py` unchanged — resumable/idempotent by construction,
   the same guarantee `local_collector.py` already has.
5. Skip queue: any player row that can't resolve to a `player_master.
   player_id` (per the unconfirmed-identity-space question in §3) goes
   to the SAME persistent skip-queue mechanism `local_collector.py`
   already built — never silently dropped, never blocking the rest of
   the run.

## 6. Explicitly NOT proposed

- A per-tournament breakdown of these season-level metrics (§2 — the
  real site doesn't offer one via this endpoint).
- Any Strokes-Gained-from-shot-data recomputation — `schema.sql`'s own
  comment already states true SG is not derivable from this project's
  round-level dataset; if `loadLocationRecord`'s `Sg` family turns out
  to BE KLPGA's own published SG figures (not this project computing
  them), that is a direct copy of a published statistic, not a
  derivation, and is fine — but this must be confirmed against real
  evidence before being treated as fact, not assumed here.
- Guessed identity_key → column mappings for any of the still-
  unresolved 15 collision groups — those stay unmapped until resolved
  with real evidence (see this round's SKIP_QUEUE / collision-audit
  report).

## 7. Next executable step, in order

1. ✅ DONE (Round 11 continued) — real `docs/discovery/KLPGA_RECORD_
   TAXONOMY_DISCOVERED.json` and `docs/discovery/raw_samples/*.html`
   transferred into this environment.
2. ✅ DONE — 14 of 15 previously-unresolved collision groups classified
   with real evidence (`CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED`); one
   (`Around::Around01::030101`) remains genuinely unresolved, logged in
   `docs/discovery/local_collector/SKIP_QUEUE.json`.
3. ✅ DONE — canonical plan rebuilt: 281 canonical metric entries, 248
   unique request identities, all 248 request-count-clean (see
   `docs/KLPGA_OFFICIAL_DATA_MAP.md` for the full numbers).
4. ✅ DONE (Round 12) — `identity_mapping.py` built and tested: 248
   identities → per-label `MAPPED`/`UNMAPPED_*` resolution, applying
   the compound-title finding above; `official_metric_value` (§4)
   implemented as the chosen normalized-fact-table architecture.
5. ✅ DONE — `season_metric_collector.py` + `scripts/run_klpga_
   season_metrics_collector.py` built and offline-tested: acquisition
   (reusing `PoliteHttpClient`/`acquire_canonical_rows` unchanged),
   ingestion, one consolidated final report, all in one command.
6. STILL OPEN — verify PIT safety (§3) with real evidence before ever
   attaching a collected value to a past event as a model feature. No
   real evidence exists yet to do this with.
7. STILL OPEN, LOCAL_EXECUTION_REQUIRED — execute the season-level
   live acquisition for real (see `docs/KLPGA_OFFICIAL_DATA_MAP.md`'s
   Round 12 section for the exact command); verify `loadLocationRecord`
   player_code against a REAL, populated `player_master` (no database
   file exists in this sandbox to check this against at all).
