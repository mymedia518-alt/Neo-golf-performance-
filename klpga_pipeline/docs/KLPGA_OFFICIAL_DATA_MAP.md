# KLPGA Official Data Taxonomy Map — Phase 1

**Status: research/discovery only, 2026-08-26 (Round 1), updated
2026-08-26 (Round 2).** Maps what the official KLPGA records interface
exposes through the `loadLocationRecord` XHR family, based on evidence
the user captured manually in Chrome DevTools. This document does not
implement a collector, does not touch the database, the model, the
archive, or Prediction #001. It is the "MAP FIRST" deliverable — the
"COLLECT LATER" phase has not started.

## Round 2 status — what could and couldn't be done this round

Round 2 asked for five missions requiring live KLPGA capture (request
mapping resolution, PIT/season testing, expanded metric discovery,
data-rights evidence) plus three requiring only reasoning over
already-confirmed evidence (raw-count schema gaps, a NEO
transformation map, cross-tour portability). **This session re-verified
the network block immediately before starting Round 2** — a fresh
`curl` to both `klpga.co.kr` and `data.klpga.co.kr` still returns
`403` at the egress proxy (`CONNECT tunnel failed`), identical to
every prior check in this project's history. Nothing changed.

Consequence, mission by mission:

| Mission | Requires live capture? | Status this round |
|---|---|---|
| 1 — Resolve `loadLocationRecord` taxonomy (the `010102` ambiguity) | Yes | **Not executable this session.** No new request/response pairs to add. Open question below is unchanged from Round 1. |
| 2 — PIT / historical availability (multi-season test) | Yes | **Not executable this session.** No season other than `2026` has ever been tested by anyone. |
| 3 — Expand metric discovery (Approach/ATG/Putting/Player/Course/Location/Live) | Yes | **Not executable this session.** All still `UNKNOWN`, unchanged from Round 1. |
| 4 — Raw counts + schema gaps | No — reasoning over existing evidence + repo schema | **Done** — expanded below. |
| 5 — Data rights evidence | Yes (reading actual ToS/robots.txt text) | **Not executable this session.** `docs/NEO_DATA_RIGHTS_MATRIX.md` created as a framework only — every row is `UNKNOWN`, no real clause was read. |
| 6 — NEO transformation map | No — uses only Round-1 CONFIRMED metrics | **Done** — see `docs/NEO_DERIVED_METRIC_MAP.md`. |
| 7 — Cross-tour portability | No — general golf-statistics domain reasoning | **Done** — see `docs/NEO_DERIVED_METRIC_MAP.md`. |

**No row in Table 1 or Table 2 below has moved status since Round 1.**
Nothing has been upgraded from `DISCOVERED-NOT-VALIDATED`/`UNKNOWN` to
`CONFIRMED` without new direct evidence, because no new direct evidence
exists — this session cannot browse the live site. Missions 1, 2, 3,
and 5 are still waiting on the user's own next DevTools round; see
"Recommended next collection phase" at the end of this document, which
is unchanged in substance from Round 1.

## Methodology limitation — read this before the tables

This session, like every prior research pass in this project, has
**no network access to `klpga.co.kr` or `data.klpga.co.kr`** (confirmed
again via direct `curl` — `403` at the egress proxy — during the prior
audit turn). That means the "PRIMARY TASK" instruction to inspect live
HTML/JS/event-handler code to determine how `menu1`/`menu2`/`menu3`
and any hidden request state are actually generated **could not be
performed by this session**. Everything below that requires reading
KLPGA's own JavaScript is marked `UNKNOWN` and deferred to the next
DevTools round, done by the user directly, the only party with real
access.

What this document *does* do: organize the user's own directly-observed
evidence into the requested taxonomy, cross-reference it against what
NEO's existing schema and codebase already anticipate (`schema.sql`
already reserves `sg_total`/`sg_off_the_tee`/`sg_approach`/
`sg_around_green`/`sg_putting` columns, all still NULL), and apply the
project's existing point-in-time discipline to what was found.

**Status legend** (per the audit brief's own definitions):

- `CONFIRMED` — both the request (params) *and* the response content
  (real example values) were directly observed by the user this
  session, with enough detail to sanity-check (e.g. the SG arithmetic
  check).
- `DISCOVERED-NOT-VALIDATED` — a menu path, UI label, or request was
  observed/clicked, but no example response values were captured for
  it.
- `UNKNOWN` — not observed at all, by anyone, this session.

No row below has been upgraded from `DISCOVERED-NOT-VALIDATED` to
`CONFIRMED` without an example value backing it.

---

## Key open question carried into Round 2

The user's own evidence already surfaces the single most important
unresolved fact about this API: **`menu3=010102` was observed for two
visibly different stat selections** — "280야드 이상(RTP)" (a tee-shot
rate/count) and "Par4,5 페어웨이 안착률 → 260~280야드 미만" (a fairway
accuracy/count in a distance band). Same `season`/`menu1`/`menu2`/`menu3`
triplet, different displayed category. This proves the simple
"menu2/menu3 → subcategory" mapping the brief warned against assuming
is genuinely false — there is hidden state (an additional form field,
a DOM/session-scoped selector value, or something not yet in the
captured payload) that this session cannot identify without live JS
access. **Do not build a collector against `menu1/menu2/menu3` alone
until this is resolved** — see "Recommended next collection phase" at
the end of this document.

---

## TABLE 1 — Category map

| Category | Subcategory | Visible Korean label | menu1 | menu2 | menu3 | Other request state | Endpoint | Method | Response format | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Strokes Gained | Total (component breakdown) | SG (전체) | `Sg` | `Total` | *(blank)* | `season=2026` | `loadLocationRecord` (exact full path not stated this session — plausibly `/load/record/loadLocationRecord`, unconfirmed) | POST *(inferred from "form-data parameters"; not explicitly stated — quick confirm in Round 2)* | JSON/HTML *(not stated which)* | **CONFIRMED** |
| Tee | 평균 티샷 거리 (avg tee-shot distance) | 티샷 → Par4,5 티샷 비율 → 평균 티샷 거리 | `Tee` | `Tee01` | `010101` | `season=2026` | `loadLocationRecord` | POST *(inferred)* | *(not stated)* | DISCOVERED-NOT-VALIDATED *(request path clicked/captured; no example values given)* |
| Tee | 280야드 이상(RTP) — rate + qualifying count | 티샷 → Par4,5 티샷 비율 → 280야드 이상(RTP) | `Tee` | `Tee01` | `010102` | `season=2026` | `loadLocationRecord` | POST *(inferred)* | *(not stated)* | **CONFIRMED** (김나현2: 21.78%/110, 김민솔: 12.83%/103) |
| Tee | Par4,5 페어웨이 안착률 → 260~280야드 미만 — accuracy + qualifying count | 티샷 → Par4,5 페어웨이 안착률 → 260~280야드 미만 | `Tee` | `Tee01` | `010102` ⚠️ *same triplet as the row above, different category — see open question above* | `season=2026` | `loadLocationRecord` | POST *(inferred)* | *(not stated)* | **CONFIRMED** (김리안: 85.71%/24, 조은채: 83.08%/54) |
| Tee | Par4,5 페어웨이 안착률 (general), Par5 티샷 비율, Par5 페어웨이…, 240~260야드 미만, and further horizontally-scrollable metrics | *(various, seen as menu labels only)* | `Tee` (assumed) | `Tee01` (assumed) | not captured | not captured | `loadLocationRecord` (assumed) | not captured | not captured | DISCOVERED-NOT-VALIDATED *(label seen in UI only — not clicked, per the brief's own "do not treat HTML labels as proof of API response fields")* |
| Approach | GIR, GIR by distance, proximity, distance buckets, Par-3 approach, fairway-vs-rough split | — | — | — | — | — | — | — | — | **UNKNOWN** — not observed this session |
| Around the Green | scrambling, sand save, rough save, fringe, bunker, recovery, proximity | — | — | — | — | — | — | — | — | **UNKNOWN** |
| Putting | putting average, one-putt/3-putt rate, distance-bucket make%, attempts/makes | — | — | — | — | — | — | — | — | **UNKNOWN** |
| Overall/Total records | "전체기록보기" and related pages | 전체기록보기 | — | — | — | — | — | — | — | **UNKNOWN** — label referenced in the brief, not captured this session |
| Player profile | birth year, nationality, team/sponsor, career starts/wins/earnings, season splits | — | — | — | — | — | — | — | — | **UNKNOWN** |
| Tournament/course | course name, par, yardage, hole-by-hole par/yardage, field scoring avg | — | — | — | — | — | — | — | — | **UNKNOWN** *(a separate, PROBABLE `/web/tourInfo/course` page was identified in the prior audit round via search-engine indexing — not the same evidence tier as this round's directly-observed `loadLocationRecord` findings)* |
| Shot/location | hole, shot #, start/end coordinates, distance, lie, club, result | — | — | — | — | — | — | — | — | **UNKNOWN** — "the name `loadLocationRecord` is NOT evidence by itself," per the brief; nothing observed this session shows coordinate- or shot-level fields |
| Live tournament | leaderboard update, round/hole score, current hole, thru, position, tee status, refresh mechanism | — | — | — | — | — | — | — | — | **UNKNOWN** |

---

## TABLE 2 — Field map

Only fields with directly-observed example values are included as full
rows; everything else in Table 1 stays `UNKNOWN`/`DISCOVERED-NOT-VALIDATED`
and has no field-level detail to map yet.

| Official field | Korean label | Unit | Raw/Derived | Sample count available? | Season availability | Historical availability | PIT classification | Potential NEO use |
|---|---|---|---|---|---|---|---|---|
| SG Total | SG Total | strokes (per round, **inferred** — see note below) | OFFICIAL DERIVED (SG is itself a computed stat, not a raw count) | Partial — `measured rounds` gives the round-count denominator, not attempt-level detail | `season=2026` confirmed as a request parameter; other season values untested | **UNKNOWN** — untested this session | **CURRENT-ONLY** (as observed) → **PIT-RECONSTRUCTABLE at best, season-granularity only** (see PIT note) | NEO-DERIVABLE input to a "Strokes Gained DNA" feature — see Table 4 |
| SG Tee Shot | SG Tee Shot | strokes (inferred per-round) | OFFICIAL DERIVED | same as above | same | same | same | Same, component-level explanation ("어디서 스트로크를 버는가") |
| SG Approach | SG Approach | strokes (inferred per-round) | OFFICIAL DERIVED | same | same | same | same | Same |
| SG Around the Green | SG Around the Green | strokes (inferred per-round) | OFFICIAL DERIVED | same | same | same | same | Same |
| SG Putting | SG Putting | strokes (inferred per-round) | OFFICIAL DERIVED | same | same | same | same | Same |
| measured rounds | 측정 라운드 수 | count | OFFICIAL RAW | — (is itself the sample-size field) | same | same | same as its parent SG record | Sample-size / reliability weighting for any SG feature — directly reusable with NEO's existing shrinkage pattern (`prior_events_n`-style confidence) |
| 280야드 이상(RTP) rate | 280야드 이상(RTP) | % | OFFICIAL DERIVED | **YES** — paired qualifying-shot count confirmed | `season=2026` only, untested beyond that | UNKNOWN | CURRENT-ONLY / season-granularity at best | Component of a "Power" feature |
| 280야드 이상(RTP) count | (qualifying tee-shot count) | count | OFFICIAL RAW | — (is the count itself) | same | UNKNOWN | same | Sample-size gate before trusting the paired rate |
| Par4,5 페어웨이 안착률 (260–280yd) rate | 260~280야드 미만 페어웨이 안착률 | % | OFFICIAL DERIVED | **YES** — paired qualifying count confirmed | `season=2026` only | UNKNOWN | same | Component of a "Control" feature |
| Par4,5 페어웨이 안착률 (260–280yd) count | (qualifying count) | count | OFFICIAL RAW | — | same | UNKNOWN | same | Sample-size gate |

**Unit note on SG values:** the user did not state an explicit unit
label. `2.38` total across `61` measured rounds is implausibly small
if it were a *cumulative* season total (that would put an elite
player at roughly +0.04 strokes/round, far below realistic SG
leaderboards) — the far more plausible reading, by the ordinary
magnitude convention used on every tour that publishes SG, is that
`2.38` **is already a per-round average**, and `measured rounds`
is the sample size behind that average, not a divisor still to be
applied. This is an inference from typical SG magnitude, not a
directly observed label — confirm the literal unit text next to the
number in Round 2.

**Reconciliation with the existing schema:** `schema.sql`'s
`player_stats_snapshot` table already reserves `sg_total`,
`sg_off_the_tee`, `sg_approach`, `sg_around_green`, `sg_putting`
(+ `_rank` companions) — all still NULL in every row. KLPGA's own
label is "SG Tee Shot," which is the same concept as the schema's
`sg_off_the_tee` column under a different name — worth normalizing in
whatever collector eventually lands this data. **The schema currently
has no column at all for `measured rounds`** (the SG sample-size
field) — that is a real gap to fix in the schema design once this
data source is confirmed, not now.

---

## PIT (point-in-time) analysis — the load-bearing finding of this round

This is more consequential than a routine status label, so it gets
its own section rather than just a table column.

NEO's existing feature engine (`klpga.backtest.point_in_time_features`)
computes every `prior_*` feature strictly from a player's **prior
tournaments** relative to a specific target tournament's start date —
never a season aggregate. The `loadLocationRecord` data confirmed this
round is structured completely differently: it is scoped by `season`
(a single confirmed value, `2026`), not by tournament or date.

Two distinct possibilities exist, and this session cannot distinguish
between them without a live test:

1. **`season` only accepts the current season** → the data is
   `CURRENT-ONLY`. It cannot be used as a feature for any of the 100
   already-collected historical tournaments at all, and cannot be
   safely used as a live feature for an upcoming tournament either
   (since "2026 season SG" mid-season already includes results from
   tournaments the model would need to predict).

2. **`season` accepts past years (e.g. `2024`, `2025`) and returns
   that season's real cumulative numbers** → the data becomes
   `PIT-RECONSTRUCTABLE`, but **only at season granularity, not
   tournament granularity**. Even in this best case, "2024 season SG"
   would still leak information into any prediction for a tournament
   that occurred *before* that season ended — e.g. a March 2024
   tournament would leak April–December 2024 results if the full
   season's SG were used as its feature. This is a materially weaker
   safety guarantee than every other feature NEO's model currently
   uses, and must never be treated as equivalent to the existing
   `prior_*` engine's strict per-tournament cutoff.

**Recommendation, not yet actioned:** the very first thing to test in
Round 2 is changing the `season` parameter to a prior year on the same
menu path and confirming whether the response changes to that year's
real values, is empty, or silently returns the current season's data
mislabeled. Until that's tested, treat every metric in this family as
`CURRENT-ONLY` for modeling purposes — safe to use only in a strictly
non-prediction, descriptive/content context (e.g. a "current form"
fan-facing card), never as a `prior_*`-style model feature.

---

## TABLE 3 — Coverage

| Family | Known metrics (this round) | Unknown metrics | Technical accessibility | Historical depth | Priority |
|---|---|---|---|---|---|
| SG | Total, Tee Shot, Approach, Around the Green, Putting, measured rounds (5 components + 1 sample-size field) | Whether a genuinely tournament-scoped SG view exists (distinct from this season-level one — see the separate `strokesGained_detail` endpoint identified in the prior audit round, unconfirmed, possibly the safer PIT source) | 🟡 request pattern confirmed, exact endpoint path + method unconfirmed | UNKNOWN (season param exists, range untested) | **P0** |
| Tee | 6+ labeled subcategories seen, 2 fully validated with response data (distance-bucket rate+count, fairway-accuracy-bucket rate+count) | Exact menu mapping for every other visible Tee label; the menu3-reuse ambiguity itself | 🟡 same as SG | UNKNOWN | P1 |
| Approach | none | GIR, GIR-by-distance, proximity, Par-3 approach, lie splits — all of it | 🔴 UNKNOWN | UNKNOWN | **P0** *(highest value if it exists, per the prior audit's own grading — still needs first contact)* |
| ATG (Around the Green) | none | scrambling, sand save, proximity, lie splits | 🔴 UNKNOWN | UNKNOWN | P1 |
| Putting | none | putting average, 1-putt/3-putt, distance-bucket make%, attempts/makes | 🔴 UNKNOWN | UNKNOWN | P1 |
| Player | none this round | birth year/nationality/sponsor (schema columns already exist, unconfirmed fill), career/season splits | 🔴 UNKNOWN | UNKNOWN | P1 |
| Course | none this round (a separate PROBABLE page exists from the prior audit) | par, yardage, hole-by-hole detail | 🔴 UNKNOWN | UNKNOWN | **P0** |
| Shot | none | everything — existence itself unconfirmed | 🔴 UNKNOWN | UNKNOWN | Not gradable until existence is shown |
| Live | none | leaderboard/hole/round live state, refresh mechanism | 🔴 UNKNOWN | N/A | P1 |

---

## TABLE 4 — NEO feature opportunities

Naming/mapping only, per instruction — **no formula implemented**.

| Official raw inputs | → Possible NEO derived feature | → Fan-facing interpretation | Status of underlying raw data |
|---|---|---|---|
| SG Total + 4 components + measured rounds | → **STROKES GAINED DNA** | "이 선수는 어디서 스트로크를 벌고, 어디서 잃는가?" | Raw fields CONFIRMED this round; PIT status still open |
| Avg tee-shot distance + distance-bucket rate/count + fairway-accuracy-bucket rate/count | → **POWER-CONTROL BALANCE** *(the brief's own example — now grounded in real confirmed numbers)* | "멀리 치면서도 정확도를 얼마나 유지하는 선수인가?" | Partially CONFIRMED (2 of 6+ subcategories validated) |
| measured rounds / qualifying-shot counts across any category | → **RELIABILITY WEIGHT** (a meta-feature, not fan-facing on its own) | *(internal use — feeds confidence into every other DNA feature, mirrors the existing `prior_events_n` shrinkage design)* | CONFIRMED as a real, paired field wherever a rate is shown |
| GIR/proximity by distance *(if confirmed)* | → **APPROACH DNA** *(brief's own example)* | "어느 거리에서 가장 많은 타수를 만드는가?" | Underlying raw fields **UNKNOWN** — aspirational, pending Round 2 |
| Putting distance buckets + attempts/makes *(if confirmed)* | → **PUTTING DNA** *(brief's own example)* | "짧은 퍼트형인가, 중거리에서 차이를 만드는가?" | Underlying raw fields **UNKNOWN** — aspirational, pending Round 2 |

---

## TABLE 5 — Model value

Prioritization only — not model weighting.

| Metric | Pre-tournament prediction | Course fit | Player explanation | Live prediction | Overall |
|---|---|---|---|---|---|
| SG Total | P0 *(if PIT-safe reconstruction works)* | P2 | P0 | P1 | **P0**, gated on PIT test |
| SG components (4-way) | P0 *(same gate)* | P1 | P0 | P1 | **P0**, gated on PIT test |
| measured rounds | P1 (as a confidence gate on the above) | — | P2 | — | P1 |
| Tee distance-bucket rate+count | P1 | P1 *(course length fit)* | P1 | P2 | P1 |
| Avg tee-shot distance | P1 | P1 | P1 | P2 | P1 |
| Fairway-accuracy-bucket rate+count | P1 | P1 | P1 | P2 | P1 |
| Approach/ATG/Putting families | Not gradable — no raw fields confirmed yet | Not gradable | Not gradable | Not gradable | Pending Round 2 |
| Course par/yardage | P0 *(field-difficulty normalization, a documented existing gap)* | P0 | P2 | P1 | **P0** |

---

## Data scale estimate — explicitly estimates, not measurements

No bulk collection was performed to produce these; they are
order-of-magnitude reasoning only.

- **Statistical categories:** at least 2 confirmed top-level (`Sg`,
  `Tee`); if KLPGA mirrors the conventional Driving/Approach/
  Around-Green/Putting/Scoring structure seen across most tours, a
  reasonable **estimate** is 5–8 top-level `menu1`-equivalent
  categories total.
- **Individual metrics:** the `Tee` category alone showed 6+ distinct
  labels plus "additional horizontally scrollable metrics" — a single
  category could plausibly hold 15–30 individual metric/bucket
  combinations. Extrapolated across an estimated 5–8 categories, a
  rough **estimate is 100–300 individual statistical views** total.
  This could easily be wrong by 2x in either direction.
- **Seasons potentially available:** UNKNOWN — the `season` parameter
  exists and is confirmed real, but no value other than `2026` was
  tested. Do not assume it spans the same historical range as NEO's
  own 100-tournament corpus.
- **Approximate player-season rows:** if season history works, roughly
  (KLPGA's active player pool, ~120–150/season, matching NEO's own
  120-entrant field size for one tournament) × (however many seasons
  are actually supported) × (however many of the ~100–300 metric views
  are collected) — this could span anywhere from a few thousand to
  tens of thousands of cells. **Wide, low-confidence estimate.**
- **Potential player-event rows:** only reachable if a genuinely
  tournament-scoped SG/stat source is separately confirmed (distinct
  from this round's season-level `loadLocationRecord` findings) — if
  so, roughly 120 players × ~20–30 tournaments/season, i.e. low
  thousands of rows per season, per metric family.
- **Potential shot-level scale, if it exists at all:** industry-typical
  order of magnitude would be roughly 60–70 shots/round × 4 rounds ×
  ~120 players × ~20–30 tournaments/season — hundreds of thousands of
  shot-rows per season. **This is a hypothetical upper bound on an
  entirely unconfirmed data source (Category I) — treat as
  illustrative only, not planning input.**

---

## Legal / commercial use track — separate from technical accessibility

**This section could not be grounded in KLPGA's actual Terms of
Use, robots.txt, or copyright notices — this session has no network
access to read them**, exactly the same block already documented for
`data.klpga.co.kr` in the prior audit (`docs/SITE_STRUCTURE_TODO.md`
§4: robots.txt for either host has never been fetched by this project,
from any environment). The classifications below are a **generic
prudence framework**, not a reading of KLPGA's real terms. Nothing
here should be treated as a legal conclusion.

| Intended NEO usage | Classification | Why |
|---|---|---|
| A. Displaying KLPGA tables verbatim | REVIEW REQUIRED, likely closer to HIGH RISK | Closest to wholesale reproduction of the source site's own presentation |
| B. Storing official raw statistics internally (never published) | REVIEW REQUIRED | Lower exposure than publishing, but automated-collection restrictions in a ToS would still apply regardless of whether output is public |
| C. Transforming statistics into NEO-derived metrics (e.g. Power-Control Balance) | REVIEW REQUIRED | Likely lower risk than (A)/(E), but "derived work" protection varies by jurisdiction; Korea has its own Database Protection Act framework relevant here — not evaluated this session |
| D. Publishing NEO rankings/probabilities (what Prediction #001 already does) | REVIEW REQUIRED | Already in production; built from a transformation (a probability), not a raw KLPGA number, which is the more defensible end of the spectrum, but still ultimately sourced from official data |
| E. Publishing selected supporting official statistics (e.g. showing "SG Total: 2.38" next to a prediction) | HIGH RISK / DO NOT ASSUME | This is close to direct redistribution of the raw official number — the most exposed use case short of (A) |
| F. Publishing historical databases | HIGH RISK / DO NOT ASSUME | Bulk redistribution as a database product is the highest-exposure use case, most likely to implicate both ToS redistribution clauses and database-rights law |
| G. Commercial subscription/API access | HIGH RISK / DO NOT ASSUME | Cannot be assessed technically at all — this is a licensing/business conversation, not an engineering question |

**Concrete recommendation for Round 2:** while already in the browser
with real access, visit `klpga.co.kr/robots.txt` and the site's own
이용약관(terms of use)/저작권 page directly and capture the actual
text — this closes the single biggest gap in this section cheaply,
without any additional risk, in the same session as the data capture.

---

## Red team

1. **Are we accidentally rebuilding KLPGA's records page?** Real risk
   if the confirmed category tables (SG components, distance-bucket
   splits) get surfaced on NEO's own site as raw tables. The stated
   product principle (RAW → NEO DATA LAYER → DERIVED FEATURES → PLAYER
   DNA → PREDICTION) is the actual mitigation — enforce it as a hard
   rule: no `menu1/menu2/menu3`-shaped table ever renders directly in
   NEO's UI.
2. **Which metrics genuinely improve prediction?** SG Total/components
   are the strongest candidate, *if* the PIT gate above resolves
   favorably. Distance-bucket splits are more marginal standalone —
   likely more valuable as inputs to a composite feature than as raw
   model inputs individually.
3. **Which are merely interesting trivia?** Very fine-grained
   distance buckets (e.g. a single 20-yard band) risk being trivia-tier
   for prediction once combined with small per-bucket sample counts
   (see #8) — better suited to fan-facing "profile" cards than raw
   model features.
4. **Which fields are impossible to reconstruct point-in-time?**
   Anything from this round's `loadLocationRecord` family, in the
   worst case where `season` doesn't accept historical values at all —
   see the PIT analysis section above.
5. **Which data could disappear if KLPGA changes the site?** The
   entire undocumented `menu1/menu2/menu3` mapping — already shown to
   be non-obvious (the `010102` reuse) — is exactly the kind of
   internal API surface that can change without notice. Recommend
   capturing and saving raw response fixtures immediately once
   confirmed (mirroring this project's existing
   `tests/fixtures/entry_list_sample.html` precedent), rather than
   relying on being able to re-query the same menu path indefinitely.
6. **What requires caching?** Season-level aggregates change at most
   once per completed event — safe to cache for days, not seconds.
   Once a season is fully over, that season's data should be treated
   as immutable and cached permanently.
7. **What breaks if menu IDs change?** Any collector that hard-codes
   `menu1`/`menu2`/`menu3` constants without validating the *response
   content* against expected field/label markers could silently start
   returning data for the wrong category and never error — exactly
   the failure mode the `010102` ambiguity already demonstrates is
   possible. Any future collector must validate response shape/labels,
   not just trust that the request succeeded, mirroring this project's
   existing `SiteBuildIntegrityError` hard-fail discipline.
8. **Which metrics have dangerous small-sample problems?** Already
   visible in the confirmed data: qualifying-shot counts of 24, 54,
   103, 110 across just four example players — a player with only a
   handful of qualifying shots in a bucket would have a wildly
   unreliable rate. This is exactly why the brief calls for tracking
   raw counts, and it plugs directly into NEO's existing shrinkage
   pattern (the `prior_events_n`-gated confidence already used in
   `point_in_time_features.py`/`candidates.py`) rather than needing a
   new mechanism invented.
9. **Which statistics would fans actually understand?** SG Total (fits
   the existing win-probability narrative directly), a tee-shot
   distance/accuracy trade-off ("power vs. control," intuitive), and
   measured-rounds as a plain-language trust signal ("61라운드 기준").
   Raw distance-bucket tables (e.g. "260–280야드 페어웨이 안착률
   83.08%") are not fan-intuitive presented raw — they're better as
   inputs synthesized into a named profile than shown directly.
10. **What can NEO uniquely infer that the official site doesn't
    show?** Point-in-time historical reconstruction itself — KLPGA's
    own site only shows current/latest state, never "what was true
    right before tournament X." A synthesized cross-category profile
    (Power-Control Balance, eventually Approach/Putting DNA) that no
    single KLPGA page shows as one number. And tying any of this back
    to NEO's own win-probability output to explain *why* a player
    ranks where she does — that synthesis, not any individual raw
    statistic, is NEO's actual differentiation.

---

## Schema gap inventory (Mission 4) — raw counts NEO cannot currently store

This is reasoning over already-confirmed Round-1 evidence and the
existing `schema.sql`, not new capture — no live access was needed or
used to produce this section.

Every rate KLPGA has shown so far came paired with its denominator
(measured rounds for SG; qualifying-shot count for both Tee distance
buckets). NEO's current schema was not designed to keep that pairing:

| KLPGA raw pair (rate + count) | NEO column for the rate | NEO column for the count | Gap |
|---|---|---|---|
| SG Total % + measured rounds | `player_stats_snapshot.sg_total` (exists, NULL) | **none** | No column anywhere stores an SG sample-size/measured-rounds figure |
| SG Tee Shot + measured rounds | `sg_off_the_tee` (exists, NULL) | **none** | Same gap |
| SG Approach + measured rounds | `sg_approach` (exists, NULL) | **none** | Same gap |
| SG Around the Green + measured rounds | `sg_around_green` (exists, NULL) | **none** | Same gap |
| SG Putting + measured rounds | `sg_putting` (exists, NULL) | **none** | Same gap |
| 280yd+ tee-shot rate + qualifying count | **none** | **none** | No column reserved for any distance-bucket driving metric at all, rate or count |
| Fairway-accuracy-bucket rate + qualifying count | `driving_accuracy` (exists, NULL — but this is a single scalar, not bucketed) | **none** | The single `driving_accuracy` column cannot hold a per-distance-band breakdown even if populated; would need a new table, not a new column |

**Why this matters now, without changing anything now:** the existing
16 official `player_stats_snapshot` columns (`scoring_average` through
`scrambling`) were designed as flat, single-value-per-season scalars.
Round 1's own confirmed evidence already shows KLPGA's real data is
richer than that shape in two ways this schema has no slot for: (1) a
sample-size/count companion for every rate, and (2) distance-bucketed
sub-splits within a single stat family (driving alone has at least the
6+ Tee subcategories observed). **Neither of these needs to be fixed
now** — this is Mission 4's deliverable (documenting the gap), not
Mission-in-a-later-round's deliverable (closing it). Any future schema
change should design for count-paired, bucketed storage from the
start rather than retrofitting flat scalar columns again.

---

## Recommended next collection phase

Not started. For the user's own next DevTools round, in priority
order:

1. **Resolve the `010102` ambiguity** — capture the *full* form-data
   payload (every key, not just `season`/`menu1`/`menu2`/`menu3`) for
   both requests side by side and diff them exactly. This blocks
   everything else technically.
2. **Test the `season` parameter against a prior year** on the same
   confirmed SG path — this single test resolves the PIT question that
   gates whether any of this data can ever enter the prediction model.
3. **Capture `robots.txt` and the site's 이용약관/저작권 page text** —
   cheap, closes the legal-track gap, no additional access risk.
4. Only after (1) and (2): begin mapping the still-`UNKNOWN` categories
   (Approach, Around the Green, Putting, Player profile, Course,
   Shot/location, Live) using the same discipline — click first,
   capture request + response together, never assume from a label
   alone.

---

*Numbers · Evidence · Oracle — Golf Intelligence. Research only. No
database, model, archive, or website changes were made to produce this
document.*
