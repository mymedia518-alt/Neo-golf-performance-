# Historical Official-Metrics Collection — Design Proposal (Round 11 continued)

**Status: DESIGN ONLY. Nothing in this document has been executed,
implemented, or wired into any running script.** No schema migration,
no new collector code, no live requests. This exists so the next round
— once (a) the identity-key collision audit is genuinely clean and
(b) explicit authorization is given — can implement against a plan
instead of starting from scratch, per this project's standing "prepare,
never silently execute" instruction.

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
  putting`. This mapping can only be built once the canonical plan is
  clean (zero unresolved identity-key collisions) — mapping a
  colliding, ambiguous identity_key to a named column would encode a
  guess into the schema layer, which must never happen.
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

## 4. Proposed storage: reuse `player_stats_snapshot`, do not invent a new table

`player_stats_snapshot`'s existing shape already fits. The only schema
change genuinely needed — **not applied in this round** — is additive:
add columns for whichever canonical metrics don't already have a named
column (the current 15 named group-(a) columns were guessed at an
earlier round, before Phase A/B's real taxonomy existed, and may not
exactly match the real discovered `menu1`/`menu2`/`menu3` set). Any
such addition must be driven by the real, clean canonical plan, never
guessed ahead of it.

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

1. Get the real, current `docs/discovery/KLPGA_RECORD_TAXONOMY_
   DISCOVERED.json` and `docs/discovery/raw_samples/*.html` (all 13
   newly-acquired files plus whatever already existed) into an
   environment that can run `identity_key_audit.py` against them —
   this round's actual blocker, see the main report.
2. Classify the 15 remaining collision groups for real, with that
   evidence.
3. Rebuild the canonical plan; confirm `duplicate_identity_key_group_
   count == 0` (or document exactly which groups remain and why).
4. Only then: design the exact identity_key → `player_stats_snapshot`
   column mapping (or the additive schema columns for anything with no
   existing match) — grounded in the real, final canonical plan, never
   before it.
5. Only then: build and offline-test the season-level acquisition
   script this document outlines in §5 — mirroring `run_klpga_
   collector.py`'s already-proven checkpoint/skip-queue/heartbeat/
   report pattern.
6. Verify PIT safety (§3) with real evidence before ever attaching a
   collected value to a past event as a model feature.
7. Only after all of the above, and explicit authorization: execute
   the season-level live acquisition.
