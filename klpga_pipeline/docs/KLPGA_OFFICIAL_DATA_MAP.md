# KLPGA Official Data Taxonomy Map — Phase 1

**Status: research/discovery only, 2026-08-26 (Round 1), updated
2026-08-26 (Round 2), Phase A tooling implemented 2026-08-26 (Round
3), Phase A patched same day for 2-level/3-level metric leaves (Round
3 patch), Phase B1 (response-schema sampling) tooling built same day —
NOT yet run live (Round 3 Phase B1).** Maps what the official KLPGA records interface
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

---

## Round 3 — Phase A discovery tooling implemented

**Status: code written and tested, 2026-08-26. NOT yet run against the
live site** — this session still has no network access to
`klpga.co.kr` (re-confirmed before Round 3 began, unchanged). Every
new module below is tested exclusively against fixtures.

### What was authorized and built

Per the conditional approval, only **Phase A** (menu-taxonomy
discovery) and the parser/test architecture were implemented — Phase B
(actually firing `loadLocationRecord` requests) stays deliberately
unimplemented and unrun. No `scripts/27` exists yet.

New package `src/klpga/discovery/`:

- **`menu_taxonomy.py`** — parses a supplied HTML page for
  `data-menu1/2/3` attributes into `MenuLeaf` records. Canonical
  identity is the full `(menu1, menu2, menu3)` triple; `menu3` is
  never treated as globally unique — `build_source_metric_key()`
  produces `menu1::menu2::menu3` for reporting, never for
  deduplication. Reports completeness **per menu1 category**
  (`incomplete_menu1_categories`) rather than one global flag, and
  never invents a second endpoint when a category's submenu isn't
  found in the static DOM.
- **`response_parser.py`** — parses one `loadLocationRecord` response
  into rows + column semantics, preferring an embedded metadata block
  (`menu`/`menuName`/`recordNote`/`order`) over table-header text over
  positional guessing; never assumes `record`/`record1..4` mean the
  same thing across two different metrics. **Not yet validated against
  a real response** — built and tested against fixtures reconstructed
  from the user's own reported field values (Approach GIR 160–180yd
  and 140–160yd), which is explicitly flagged in the module's own
  docstring as a working assumption pending real HTML.
- **`collision_report.py`** — implements every collision check Round 3
  asked for. **Real regression coverage of the actual Round-1 finding**:
  a bug was caught and fixed here during implementation — the first
  version of `collisions` only flagged menu3 codes appearing under
  *different* `(menu1, menu2)` pairs, which would have completely
  missed the real `menu3=010102` case (same menu1, same menu2,
  different label). Fixed to flag any menu3 code appearing as more
  than one leaf at all, then classify the *more specific* differing-
  menu1/differing-menu2 buckets as a subset.
- **`taxonomy_report.py`** — the JSON/CSV writers and the exact counts
  Round 3's §9 asked for (menu1/menu2/menu3-combination/unique-menu3/
  collision counts).

New script `scripts/26_discover_klpga_record_taxonomy.py` (Phase A
only): fetches exactly one page (`--source-url`, **required, no
default** — this script does not guess the landing-page URL, matching
the same discipline as `RECORD_TAXONOMY_SOURCE_URL` in `config.py`
being left unset rather than filled with a guess), inspects it, writes
the three output files, and stops. Exits with a distinct code
(`EXIT_INCOMPLETE_NEEDS_INVESTIGATION`) if any menu1 category has zero
resolved menu3 leaves, printing exactly which categories need further
investigation rather than attempting a guessed follow-up request.

`config.py` gained `RECORD_TAXONOMY_ENDPOINT` (now fully CONFIRMED —
the complete path `POST /load/record/loadLocationRecord` was given
directly in Round 3, closing the "exact full path not stated" gap from
Round 1's Table 1) and `RECORD_TAXONOMY_SOURCE_URL = None`, documented
as intentionally unset.

### What was deliberately NOT built this round

- `scripts/27` (Phase B live validation orchestrator) — not created.
- `season_validator.py` — not implemented. Building it now would have
  required either leaving it untested, or fabricating a plausible-
  looking "season=2025 vs season=2026 differs" test fixture pair with
  no real evidence behind either value — exactly the kind of invented
  evidence this whole discovery effort exists to avoid. It will be
  built once real two-season response data exists (Phase B).
- Any live request of any kind.

### Test coverage (all fixture-based, zero network access)

31 new tests across `test_menu_taxonomy.py`, `test_record_response_parser.py`,
`test_collision_report.py`, `test_discover_klpga_record_taxonomy_script.py`,
using 5 new fixtures under `tests/fixtures/`:

- `record_menu_static_tree_sample.html` — synthetic, built from the
  real confirmed `(menu1, menu2, menu3, label)` tuples reported across
  Rounds 1–3 (SG Total, Tee 평균 티샷 거리, Approach 020104/020105).
- `record_menu_partial_tree_sample.html` — synthetic, adds a "Putting"
  category with no discoverable submenu, to test missing-level
  detection.
- `record_menu_collision_sample.html` — **reconstructed from the real
  Round-1 evidence**, not synthetic: `menu3=010102` under Tee/Tee01
  mapped to two different labels. This is what the fixed `collisions`
  bug above was caught against.
- `loadLocationRecord_approach_020104_sample.html` /
  `_020105_sample.html` — reconstructed from the real field values the
  user reported this round (김수지 70.49%/43/61/73rounds/-0.0465;
  임희정 74.45%/169/227/84rounds/-0.0769). The 020104 fixture includes
  a synthetic metadata block (to exercise the metadata-detection path)
  and the 020105 fixture deliberately omits one (to exercise the
  table-header fallback path) — every fixture's header comment states
  plainly that it is a reconstruction, not captured markup.

Full suite: 339/339 passing (308 before this round + 31 new).

### Exact Windows command for the next real run

```
python scripts\26_discover_klpga_record_taxonomy.py --source-url "<paste the exact record/거리기록 page URL from your own browser's address bar>"
```

Replace the `--source-url` value with whatever URL you're actually on
when you click the menu tabs that fire `getRecord(menu1, menu2,
menu3)` — this script will not run without it and will not guess one.
Output lands in `docs\discovery\` by default (`--out-dir` to change
it), and every fetched page is cached under `data\raw_cache\http\` via
the existing `PoliteHttpClient` (gitignored, matching every other
collection step in this project).

If the run reports `INCOMPLETE`, it will name exactly which menu1
categories had zero resolved submenu — that's the next thing to
inspect directly in DevTools before Phase A can be called complete.

---

---

## Round 3 patch — metric leaves can terminate at menu2, not only menu3

**Status: code patched and tested, 2026-08-26. Still not re-run against
the live site by this session** — corrected by the user's own live
Windows Phase A run (the first real execution of this tooling) plus
direct DevTools follow-up.

### Why the original menu3-only leaf detection was wrong

The first live Phase A run against `https://klpga.co.kr/web/record/locationRecord`
returned real counts for the first time:

- menu1 categories found: **6**
- menu2 families found: **5**
- menu3 combinations found: **276**
- unique menu3 codes: **241**
- menu3 collisions: **31**
- menu1 categories with NO resolved menu3 leaves: **2** (`Sg`, `All`)

That last number was the tell. The original implementation assumed
every valid metric request needed all three of `menu1`/`menu2`/`menu3`
— an assumption never actually stated as confirmed anywhere in Rounds
1–3, just implicit in the code. Direct DevTools follow-up disproved it
directly: the real request for SG Total is

```
POST https://klpga.co.kr/load/record/loadLocationRecord
season=2025
menu1=Sg
menu2=Total
```

with **no `menu3` form field at all** — not a missing value, a
legitimately shorter, valid request that KLPGA's own UI uses
successfully. `Sg`/`All` weren't broken or lazily-loaded; the parser
simply didn't know a metric could stop at menu2.

### The fix

`src/klpga/discovery/menu_taxonomy.py`'s `MenuLeaf` now carries a
`leaf_level` field (`"menu2"` or `"menu3"`), with `menu3`/`menu3_label`
`Optional[str]` — `None` for a menu2-level leaf, never fabricated.
`inspect_menu_dom()` runs two independent detection passes over the
same tag list: the original menu3-level detection (own-attrs then
ancestor-walk, unchanged), plus a new menu2-level pass that recognizes
a tag with its own `data-menu1`/`data-menu2`, a blank-or-absent
`data-menu3`, **and no menu3-bearing descendant** (so a container
wrapping real menu3-level buttons is never miscounted as an extra
menu2-level leaf itself).

**Canonical identity, per explicit instruction, is never menu3 alone**:
`MenuLeaf.identity` is `(menu1, menu2)` for a menu2-level leaf,
`(menu1, menu2, menu3)` for a menu3-level leaf — the live run's own 31
collisions among 241 unique menu3 codes is the direct evidence for why
identity must include the hierarchy. `source_metric_key` stays a
string serialization of that same identity, for reporting only, never
for deduplication.

**Completeness logic changed**: `Menu1Coverage.has_resolved_leaves` is
now true if EITHER `menu2_leaf_count` or `menu3_leaf_count` is
positive. A category is only reported incomplete if neither level
resolved anything — exactly the case this patch was written to stop
over-reporting.

### Real regression value already paid during implementation

Nothing new this round — the same discipline that caught the Round 3
`menu3=010102` collision-detection bug caught another edge case while
writing this patch: the naive version of the menu2-level detection
pass (checking only for own `data-menu1`/`data-menu2` with blank
`data-menu3`) would have double-counted a container `<div>` wrapping
real menu3-level buttons as an extra, spurious menu2-level leaf. Fixed
by also requiring "no menu3-bearing descendant" before accepting a tag
as a genuine leaf — covered by
`test_menu3_container_with_no_own_menu3_is_not_a_spurious_menu2_leaf`.

### Collision reporting now distinguishes three categories

`collision_report.py` previously conflated "same code, different
menu1/menu2" with "same code, different label." It now reports:

- **A.** same menu3 reused under different menu1/menu2 paths (further
  split into A1: different menu2 same menu1, A2: different menu1
  entirely)
- **B.** same menu3 reused with a different label — the real
  `menu3=010102` finding lives here specifically, since both leaves
  share the same menu1/menu2
- **C.** exact duplicate DOM entries — the identical
  `(menu1, menu2, menu3, label)` tuple appearing more than once, a
  markup/parsing artifact, never conflated with category B

### Regenerating the discovery output artifacts

`docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.json`/`.csv` and
`KLPGA_METRIC_COLLISION_REPORT.md` from the user's first live run were
never pushed to this repository (they exist only on the Windows
machine's local filesystem) — there is nothing in git for this session
to "regenerate." The next live run of the patched
`scripts/26_discover_klpga_record_taxonomy.py` will produce fresh
artifacts under the new schema (`leaf_level`, nullable `menu3`,
`menu2_level_leaf_count`/`menu3_level_leaf_count`/`total_leaf_count`
alongside the OLD-style `menu3_combination_count` for auditability). If
those artifacts should be version-controlled going forward, that's the
next thing to decide, not something this patch assumes.

### What remains unverified without a live re-run

- Whether `Sg` now resolves as `COMPLETE` in the real DOM — this
  patch's logic is proven correct against fixtures built from the
  directly-confirmed `season=2025&menu1=Sg&menu2=Total` request, but
  the real page's actual markup (own-attrs vs. ancestor-nested) has
  never been read by this session.
  `record_menu_sg_menu2_leaf_sample.html` covers the own-attrs shape;
  an ancestor-nested menu2-level leaf is an explicitly flagged gap (no
  ancestor-walk variant exists yet for menu2-level detection).
  Documented in the module docstring, not silently assumed.
  Provisional evaluation: **likely** `COMPLETE` for `Sg`, since the
  directly-confirmed request shape matches this patch's supported
  case.
  Confidence: **medium** — the confirmed evidence covers the request
  parameters, not the DOM markup shape.
- Whether `All` (전체기록보기) resolves at all — the user confirmed
  its request also lacks menu3, but gave no confirmed menu2 value or
  DOM structure for it. No fixture models "All" specifically; per
  explicit instruction, this patch does not fabricate one. If the real
  run still reports `All` incomplete, that is a legitimate finding to
  investigate live, not a bug in this patch.
- The real counts (menu2-level vs. menu3-level split, updated
  collision categories A/B/C) across the actual live taxonomy — only a
  fixture-scale version of this has been exercised.

---

---

## Round 3, Phase B1 — response-schema sampling tooling (built, not yet run live)

**Status: code written and tested, 2026-08-26. NOT run against the
live site by this session** — no network access, unchanged since
Round 1. Confirmed Phase A baseline (from the user's live Windows
run): 6 menu1 categories, 11 menu2 nodes, 7 menu2-level leaves, 276
menu3-level leaves, 283 total, 241 unique menu3 codes, 31 collisions,
0 unresolved categories — `COMPLETE`.

### What Phase B1 does

Given an already-produced Phase A taxonomy JSON, deterministically
selects a small (~12-20), cross-family representative sample — never
the full 283 — fires exactly one live request per sampled metric
against the already-confirmed `/load/record/loadLocationRecord`
endpoint, and analyzes each response for: schema fingerprint, raw
numerator/denominator-pair detection (with a validated cross-check
against the displayed rate, never a silent replacement of it),
distinct sample-size fields (never merged across types), RTP presence,
player-code extraction method, and data-quality anomalies. An optional
minimal historical-season probe (≤3 metrics) classifies
`HISTORICAL_SEASON_AVAILABLE` / `CURRENT_ONLY` / `UNKNOWN` — a
structurally different, weaker claim than PIT safety. **Every metric's
`pit_status` is the hardcoded constant `PIT_UNVERIFIED`, with a
dedicated static-source test asserting the literal string "PIT_SAFE"
does not appear anywhere in the analysis module** — nothing in this
tooling can promote a metric to PIT-safe.

New package additions: `src/klpga/discovery/response_schema.py`
(fingerprinting, raw-pair/sample-size/RTP/data-quality analysis, the
PIT constant), `sampler.py` (representative selection, deterministic —
no randomness), `request_log.py` (structurally redacted audit log — no
field capable of holding a header/cookie/token exists in the schema at
all), `schema_report.py` (the five required output-file writers).
`scripts/27_klpga_response_schema_sample.py` is the Phase B1-only
orchestrator; Phase B2 (a full 283-metric sweep) has no script and was
not implemented, per instruction.

### A real correction made during this round

The response-parser's record-field count (`response_parser.py`,
Round 3 Phase A) was hardcoded at exactly 5 (`record`..`record4`) —
built before any evidence suggested otherwise. This round's directly
reported SG Total evidence (six named values: Total/Tee Shot/Approach/
Around the Green/Putting/measured rounds — see the Strokes Gained
section above) doesn't fit that assumption. Fixed:
`_discover_record_fields()` now scans each response for whichever
`data-record*` attributes actually exist, rather than assuming a fixed
count — verified by a new SG Total fixture with six `record`..`record5`
values matching the real reported figures (2.38/0.67/1.00/0.17/0.54/61,
whose arithmetic — 0.67+1.00+0.17+0.54=2.38 — is the same check that
originally confirmed this evidence). That fixture also exercises the
other real reported player-identity pattern (a
`/web/profile/mainRecord?playerCode=...` link) as a fallback player-code
source, distinct from the `data-playercode` attribute the Approach/Tee
fixtures already covered.

The two existing Approach fixtures (`020104`/`020105`) were also
updated: this round's evidence gave the *exact* column header text
("그린 적중률(%)", "그린 적중 횟수", "샷 시도 횟수", "측정 라운드")
where Round 3 Phase A's fixtures had used abbreviated placeholders
("GIR"/"성공"/"시도") pending that more precise evidence — now
corrected, and a second real reported row (배소현: 64.94%/50/77/87/0.04)
was added to `020104` alongside the original (김수지: 70.49%/43/61/73/
-0.0465), both independently reported, both arithmetic-consistent.

### What was deliberately NOT built or run this round

- No live request was made — the sample/analysis/report pipeline is
  fully tested against fixtures only.
- Phase B2 (full 283-metric enumeration) — no script, no design
  commitment beyond "the same per-metric analysis, at scale."
- `docs/discovery/KLPGA_RESPONSE_SCHEMA_SAMPLES.json/.csv`,
  `KLPGA_RESPONSE_SCHEMA_REPORT.md`, `KLPGA_RAW_FIELD_INVENTORY.md`,
  `NEO_RAW_INPUT_CANDIDATES.md`, and the Phase B1 request log —
  none of these exist yet in this repository. They are Phase A's
  taxonomy files' sibling problem: this session has no live output to
  write, and fabricating them would defeat the entire point of this
  evidence discipline. The next live Windows run produces them for
  real.

### Exact Windows command for the next real run

```
python scripts\27_klpga_response_schema_sample.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
    --season 2025
```

Add `--historical-season 2024` (or whichever prior year the site's own
`#searchSeason` selector actually offers) to also run the minimal
3-metric historical probe. Output lands in `docs\discovery\` by
default (`--out-dir` to change it); every fetched response is cached
under `data\raw_cache\http\` via the existing `PoliteHttpClient`,
unchanged rate-limit/retry behavior, no concurrency, one request per
sampled metric plus up to 3 for the optional historical probe — a hard
`--max-requests` cap (default 24) stops the run regardless. A 401/403/
429 from the site halts the entire run immediately (`EXIT_BLOCKED`) —
partial results already collected are still written, but nothing
further is attempted.

## Round 3, Phase B1 amendment — scope conflict resolved, taxonomy/output additions

A follow-up message re-specified Phase B1 with different script/output
names and language suggesting the full 283-leaf set as the request
plan (with dedup of exact-duplicate DOM entries only) — in direct
conflict with every prior round's own definition of Phase B1 as a
small representative sample, and with Phase B2 (a full 283-metric
sweep) explicitly gated as "not yet authorized" in each version of the
spec seen so far, including that same message's own historical
framing. Rather than silently picking a side on a scope question with
real consequences (283 live HTTP requests to an external site vs.
~20), this was put back to the user directly. **Decision: keep the
sample-based Phase B1 scope** (`scripts/27_klpga_response_schema_sample.py`,
never a full sweep) and layer the new message's other requirements on
top of it where they don't require bulk collection.

Built this round, additive to the already-committed Phase B1 tooling,
zero live requests made (still no network access in this session):

- **Expanded primary-value type taxonomy** in `response_schema.py`:
  `classify_column_kind` now distinguishes `SG` (a bare `sg`/`SG`
  token — confirmed against the real SG Total fixture's table-header
  labels, e.g. "SG Total"/"SG Tee Shot"), `PERCENTAGE` (an explicit
  `%` unit — e.g. "그린 적중률(%)") from the narrower `RATE` (a bare
  `률`/`비율` label with no `%` unit), and `PUTT_COUNT` (a `퍼트`-plus-
  count label, checked before the generic `COUNT` bucket so a putt
  count is never silently merged with an unrelated shot-attempt
  count). `TEXT` exists as a classification target (`구분`/`상태`/
  `유형` keywords) but nothing in the current fixture set actually
  triggers it — per evidence discipline, the capability exists without
  a fabricated example. `PERCENTAGE` and `RATE` are treated
  identically by raw-pair detection and range validation (both are
  "the displayed rate," just with/without an explicit unit) — see
  `_RATE_KINDS` in the module.
- **Cross-metric playerCode identity-consistency classification**
  (`build_player_identity_report`, new in `response_schema.py`):
  groups rows by `player_name` across every metric sampled in one run
  and checks whether the SAME player resolves to the SAME
  `player_code` everywhere they appear. `CONFIRMED` (every
  cross-checkable player — one seen in 2+ sampled metrics — has one
  consistent code), `PARTIAL` (at least one cross-checkable player has
  different codes across metrics), or `NOT_AVAILABLE` (nobody in the
  sample appears in more than one sampled metric — nothing to
  cross-check, not a claim of failure). A player seen in only one
  sampled metric is listed for completeness but never counted toward
  the overall status.
- **Historical-availability label renamed** for precision:
  `classify_historical_availability` now returns
  `HISTORICAL_SEASON_RESPONSE_CONFIRMED` (previously
  `HISTORICAL_SEASON_AVAILABLE`) — the new name states what was
  actually observed (a genuinely different parsed response for a prior
  season parameter), not an assumption about how far back historical
  data goes. Still never a PIT classification.
- **Three new output files**, additive to the five already-implemented
  ones (nothing renamed or removed, to avoid breaking the
  already-tested Phase A/B1 pipeline for no functional gain):
  `KLPGA_RAW_COUNT_METRICS.csv` (the subset of the sample carrying a
  raw numerator/denominator pair or a bare count column — excludes
  rate-only/not-applicable/unknown metrics rather than padding them),
  `KLPGA_PLAYER_IDENTITY_REPORT.md` (renders the cross-metric identity
  report above), `KLPGA_RESPONSE_FAILURES.csv` (isolates
  FAILED/AMBIGUOUS/EMPTY-status sampled metrics from the main samples
  file).
- **Default sample size raised from 16 to 20** (`--sample-size`,
  default `--max-requests` raised from 24 to 28 to keep the same
  historical-probe headroom) — closer to the newest message's
  20-item NEO raw-input candidate table language, while staying a
  small representative sample, never the full 283.

Test coverage: 21 new tests (`tests/test_response_schema.py` — value-
type classification, identity-consistency CONFIRMED/PARTIAL/
NOT_AVAILABLE; `tests/test_schema_report.py`, new file — the three new
output-file writers in isolation; `tests/test_klpga_response_schema_sample_script.py`
— end-to-end file presence and content). Two existing assertions
changed as a direct, expected consequence of splitting `RATE` into
`RATE`/`PERCENTAGE` (the Approach GIR% schema fingerprint is now
`PERCENTAGE_COUNT_COUNT_ROUNDS_RTP`, not `RATE_COUNT_COUNT_ROUNDS_RTP`)
and of the historical-label rename. Full suite: 437/437 passing.

Still not run live: 0 real HTTP responses observed by this session for
any `loadLocationRecord` call. The Windows command above is unchanged
by this amendment — same script, same flags, now with a slightly
larger default sample and the additional output files written
alongside the original five.

## Round 3, Phase B1.1 — live Windows evidence, one confirmed defect fixed, three genuinely blocked

**Status: 2026-08-26. The user's live Windows Phase B1 run produced
real evidence** (13/20 sample selected — target reduced by malformed
leaves and taxonomy shape; 4 named EMPTY_SCHEMA metrics with 215-232
rows each; a duplicate-identity warning for `('', '', '010101')`;
`Cross-metric playerCode identity consistency: NOT_AVAILABLE`). This
was the first real live traffic this whole discovery track has ever
received.

**Critical scoping fact: this session never received the Windows
run's raw response cache or output files.** `docs/discovery/` does not
exist in this git checkout, and `data/raw_cache/http/` does not exist
either (both confirmed via `git log`, `git status`, and directory
listing at the start of this round) — this remote session is a fresh,
ephemeral container, entirely separate from the user's Windows
machine, and nothing was pushed. This matters because four of the
seven missions requested this round (raw-HTML root-cause diagnosis,
parser fixes validated against real structure, playerCode extraction
validated against real structure, real-response regression fixtures)
are **not possible without that HTML** — and per the round's own
explicit instruction ("Do not modify parser behavior until the exact
mismatch is identified"), no parser change was made on a guess.

### What WAS fixed this round — real, code-level, no cache required

**Mission 4 (malformed identity) — root-caused and fixed with full
confidence**, because it is a defect in this project's own code, not a
question about the live site's HTML:

- Root cause: `('', '', '010101')` was never a *sampler* bug. It comes
  from `menu_taxonomy.py`'s `inspect_menu_dom` Pass 1 fallback (lines
  ~299-310): a tag carrying a non-blank `data-menu3` whose ancestor
  chain never resolves a `data-menu1`/`data-menu2` identity is
  preserved as a `MenuLeaf(menu1="", menu2="", ...,
  label_resolution_method="unknown")` rather than dropped — correct
  and already covered by an existing test
  (`test_unresolvable_menu3_is_preserved_not_dropped`), since this
  project's discipline is "preserve every discovered thing, never
  silently drop it," and this *is* real discovery evidence (the DOM
  scan found *something* referencing `010101` that it could not fully
  identify). The report showing it TWICE (a genuine
  `find_duplicate_identities` hit, which only fires on count > 1)
  means at least two independent DOM tags shared this blank-identity
  shape — plausibly a desktop+mobile duplicate of the same nav
  element, though the exact real DOM cause is unconfirmed without the
  cache.
- The actual defect: nothing downstream ever rejected such a leaf
  before it reached the sampler's candidate pool.
- Fix: new `klpga.discovery.sampler.reject_malformed_leaves()` splits
  `taxonomy["leaves"]` into (valid, rejected) BEFORE sampling — any
  leaf with a blank/missing `menu1` or `menu2` is excluded and
  reported by name/count (`scripts/27_klpga_response_schema_sample.py`
  now prints `Rejected N malformed taxonomy leaf(ies)...` with their
  `source_metric_key`s). `select_representative_sample` also filters
  defensively itself (belt-and-suspenders), so a malformed leaf can
  never reach a live request even if a future caller forgets the
  separate rejection step.

**Mission 5 (sample quality, partial) — the "All" navigation-family
over-representation, fixed structurally:** the sampler's family
round-robin was plain alphabetical (`sorted(per_family_candidates)`),
and `"All"` sorts before `"Approach"`/`"Around"` — meaning it competed
for an early slot on equal footing with genuine stat families in every
round of the cycle. Added `_PRIORITY_FAMILIES = ["Sg", "Tee",
"Approach", "Around", "Putt"]`; any other family (in particular `All`)
now sorts after all five confirmed families. This is a **selection-
order heuristic**, not a claim that `All`'s schema is uninteresting —
determining that requires seeing its actual live response, which this
session doesn't have.

**Mission 7 (HTTP success ≠ parse success) — fully implemented:** new
`build_request_outcome_counts()` in `schema_report.py` buckets every
completed request into `http_success` / `http_failure` /
`parse_success` (CONFIRMED or DISCOVERED_NOT_VALIDATED) /
`parse_empty` / `parse_ambiguous_or_failed`, rendered as its own table
in `KLPGA_RESPONSE_SCHEMA_REPORT.md` and printed in the script's final
summary. "Metrics successfully sampled" was silently conflating HTTP
success with parse success before this — the exact complaint in the
mission brief. The script's broad `except Exception` around
`fetch_and_analyze` is now explicitly labeled `HTTP_FAILURE` in logs
(reasoned, not guessed: `parse_record_response` is documented and
tested to never raise — it degrades to `parse_status="FAILED"`
internally — so any exception reaching that catch in practice
originates from the HTTP layer).

### What is BLOCKED — genuinely need the real evidence, not guessed

**Mission 1 (EMPTY_SCHEMA root cause) — HYPOTHESIS ONLY, NOT APPLIED.**
Structural reasoning from the given Windows output text (not from any
HTML this session has seen): `build_schema_fingerprint` returns
`"EMPTY_SCHEMA"` only when every `ColumnSemantics.label` is falsy.
`parse_status="DISCOVERED_NOT_VALIDATED"` (as reported for all four
named metrics) requires rows to be non-empty AND NOT all columns
`source="unknown"` AND no metadata block found — meaning at least one
column *did* get a `table_header`-sourced label. The only way both
facts hold simultaneously is if a `<th>` (or `tr th`) element exists
structurally but its extracted text is an **empty string** — e.g.
blank/icon-only header cells, or a real label living in a second
header row / nested element the current `thead th`-then-`tr
th`-fallback selector doesn't reach. Separately, the mission brief's
own description of embedded JS variables (`recordName`, `record1`,
`record2`, ...) does **not** match what `_extract_metadata()` actually
looks for (`_METADATA_KEYS = ["menu", "menuName", "recordNote",
"order"]`, and a regex requiring a JSON-object literal with a `"menu"`
or `"menuName"` key) — if the real site instead emits separate
`var recordName = "...";` assignments, `_extract_metadata` would never
find them, which independently explains why every live-run metric
came back `DISCOVERED_NOT_VALIDATED` and never `CONFIRMED`. **Both of
these are plausible, evidence-consistent hypotheses, not confirmed
root causes** — confirming either requires the actual response HTML.

**Mission 2 (parser fix) — NOT DONE**, for the same reason: fixing
`response_parser.py` against a guessed DOM/JS shape risks the same
mistake Round 3 Phase A already made once (assuming a fixed 5-field
shape that broke on real SG evidence) — this time with zero real
evidence at all, only Mission 1's hypothesis above.

**Mission 3 (playerCode on real data) — NOT VERIFIABLE THIS SESSION.**
The dual-path extraction (`data-playercode` attribute, then href
`?playerCode=` fallback) is unchanged and still passes its existing
tests, but `Cross-metric playerCode identity consistency:
NOT_AVAILABLE` in the live report could mean either "no player
appeared in 2+ sampled metrics" (expected/benign — see
`build_player_identity_report`'s own docstring) or "playerCode
extraction failed on the real HTML shape" (a real defect) — these are
indistinguishable without seeing the actual rows.

**Mission 6 (real fixture regression tests) — NOT DONE**, because it
requires sanitized copies of the real cached responses, which don't
exist in this session.

### What's needed to unblock Missions 1/2/3/6

Either:
1. Push the cache into this branch — even just the 4 named responses
   (`Approach::Approach01::020101`, `Around::Around01::030101`,
   `Putt::Putt01::040101`, `Tee::Tee01::010101`) from
   `data\raw_cache\http\` (or wherever `PoliteHttpClient`'s cache
   actually wrote them), plus `docs\discovery\KLPGA_RESPONSE_SCHEMA_SAMPLES.json`
   for the full run's context; or
2. Paste the raw HTML for at least one of those four responses
   directly into chat.

Once real HTML is available, Missions 1/2/3/6 can be done with the
same evidence discipline as every other round of this project — a
confirmed root cause, a parser fix validated against what the site
actually returns, and regression fixtures built from sanitized real
data (matching how `loadLocationRecord_sg_total_sample.html` and the
Approach fixtures were built from directly reported real evidence,
never invented).

### Files changed this round

`src/klpga/discovery/sampler.py` (`reject_malformed_leaves`, family
priority ordering), `src/klpga/discovery/schema_report.py`
(`build_request_outcome_counts`, outcome table in
`render_schema_report_markdown`), `scripts/27_klpga_response_schema_sample.py`
(malformed-leaf rejection wired in, HTTP_FAILURE vs parse-outcome
counting/printing), `src/klpga/discovery/menu_taxonomy.py` (docstring
cross-reference only, no behavior change), plus new/updated tests in
`tests/test_sampler.py`, `tests/test_schema_report.py`,
`tests/test_klpga_response_schema_sample_script.py`. `response_parser.py`
was **not modified** (see Mission 2 above). Full suite: 448/448
passing. No change to Prediction #001, `predictions/`, model/
inference/probability logic, the production DB, the archive, or the
public website.

## Round 3, Phase B1.1 diagnostic patch — hang instrumentation

**Status: 2026-08-26.** A Windows run of `scripts/27_klpga_response_schema_sample.py`
produced **no visible output at all** and had to be Ctrl+C'd, with no
traceback — leaving it unknown whether it hung during imports,
taxonomy loading, HTTP setup, or a request. Per instruction, no root
cause was guessed and no bulk requests were made; this round is pure
instrumentation plus a review of the existing HTTP timeout/retry path.

### A. Most likely hang locations, by code inspection

1. **Most likely: stdout buffering hid real output that was already
   there.** Every meaningful step in this script already printed
   something (`"Selected N representative metrics..."` etc.) before
   any HTTP request — if truly zero output appeared before Ctrl+C,
   plain `print()` without `flush=True` writing to a non-interactive
   or redirected stream on Windows is the single most consistent
   explanation. This is now defeated: every print in the script's
   execution path uses `flush=True` (via a new `_log()` helper).
2. **Second: a genuinely slow/stalled request, stacking across
   retries.** See B-F below — bounded, but the worst case (~3 minutes
   for one metric) could look indistinguishable from a hang without
   visible progress. Now surfaced via `[REQUEST i/N]`/`[RESPONSE
   i/N]`/`[PARSE i/N]` markers and an `on_retry` callback that prints
   before every backoff sleep.
3. **Less likely but not ruled out**: a DNS/proxy-level stall that
   `requests`' timeout parameter doesn't fully bound (rare, but
   possible depending on the Windows machine's network stack) — the
   instrumentation will show a `[REQUEST i/N]` marker with no matching
   `[RESPONSE i/N]` for an extended period if this is happening, which
   distinguishes it from both 1 and 2 above.

None of these was picked as *the* cause — the next Windows run's
output (all flushed, all timestamped via elapsed= on each RESPONSE
line) will show which one it actually was.

### B. Existing HTTP timeout values (unchanged)

`PoliteHttpClient.timeout_sec = 20.0`, applied by `requests` to BOTH
the connect phase and the read phase separately (a single float
argument covers both) — so one attempt can take up to ~2×20s = ~40s
in the worst case (slow connect, then a stalled read).

### C. Existing retry/backoff values (unchanged)

`stop_after_attempt(4)` (1 initial + 3 retries), `wait_exponential_jitter(initial=2, max=30)`
(waits between attempts scale ~2s → ~4s → ~8s + jitter, capped at 30s)
— only for retryable exceptions (5xx, connection errors, timeouts,
chunked-encoding errors), never for `RateLimitBlockedError` (401/403/429),
which raises immediately with no retry.

### D. Existing rate-limit delay (unchanged)

`min_interval_sec = 1.5s` + `random.uniform(0, jitter_sec=0.8)` before
each top-level client call (`post_text` etc.) — once per call, not
once per retry attempt.

### E. Maximum theoretical wait per request, BEFORE this patch

Already finite: throttle (~2.3s) + 4 attempts × up to ~40s each
(worst-case connect+read stall) + ~14s of backoff waits between
attempts ≈ **~176s (~3 minutes), bounded, never infinite.**

### F. Maximum theoretical wait per request, AFTER this patch

**Unchanged — no timeout/retry/rate-limit value was modified**, per
instruction not to weaken rate-limit protection and because a finite
timeout already existed (Mission 3's "if no finite timeout, add one"
did not trigger). Same ~176s worst case, now fully visible via
`[REQUEST]`/`[RESPONSE]`/`[HTTP RETRY]` markers instead of silent.

### What was added

- `_log()` in `scripts/27_klpga_response_schema_sample.py`: every
  print in the script's execution path now uses `flush=True` and
  records itself as the last-known execution point.
- `[STEP 01]`–`[STEP 07]` markers covering script start, imports,
  taxonomy loading, malformed-leaf rejection, sample selection, and
  HTTP client init.
- `[REQUEST i/N]` (menu1/menu2/menu3/season, printed BEFORE the
  network call — so even a failed fetch leaves a trace of which
  metric was being attempted), `[RESPONSE i/N]` (status/bytes/measured
  elapsed time), `[PARSE i/N]` (parse_status/row count) for every
  sampled metric and every historical-probe request (tagged `HIST
  j/M`).
- `PoliteHttpClient.on_retry` (new, optional, defaults to `None`):
  fires with a diagnostic message before every retry's backoff sleep.
  `None` by default so every OTHER existing caller of this client
  (scripts 01, 02, 04, 07, 08, 13, 14, 15, 26, and 00) is completely
  unaffected. Script 27 sets it to print `[HTTP RETRY] ...`.
- Top-level `KeyboardInterrupt` handler in `if __name__ == "__main__":`:
  prints the last-known `_LOG` marker, then re-raises unconditionally
  — the interrupt is never swallowed.

### G. Files changed

`scripts/27_klpga_response_schema_sample.py` (instrumentation
throughout — `_log()`, STEP/REQUEST/RESPONSE/PARSE markers,
KeyboardInterrupt handler), `src/klpga/http_client.py` (`on_retry`
callback, `_before_sleep_log`, docstring documenting the timeout/retry/
throttle math above), `docs/KLPGA_OFFICIAL_DATA_MAP.md` (this
section). New test file `tests/test_http_client_retry_instrumentation.py`;
new tests added to `tests/test_klpga_response_schema_sample_script.py`.
`response_parser.py`, the sampler logic, and every other collection
script (01–26) are unchanged.

### H. Tests passed

458/458.

### I. Confirmation

No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. Phase B2 was not started; no bulk live requests were made
(this session made zero live requests, as always — no network
access).

## Round 3, Phase B1 — CLASS 1 / CLASS 2 investigation (evidence still needed)

**Status: 2026-08-26.** The Windows Phase B1.1 diagnostic run
completed successfully on commit `7231954`: 9 live requests,
`HTTP_SUCCESS=9 HTTP_FAILURE=0 PARSE_SUCCESS=4 PARSE_EMPTY=5`. Two
distinct failure shapes were reported and must NOT be treated as one
bug:

- **CLASS 1** — HTTP success + real player rows (>0) + `EMPTY_SCHEMA`.
  Example: `Putt::Putt01::040101`, bytes=192516, 231 rows,
  `parse_status=DISCOVERED_NOT_VALIDATED`.
- **CLASS 2** — HTTP success + zero rows + `EMPTY_SCHEMA`/`EMPTY`.
  Examples: `All::Approach`/`All::Around`/`All::Putt`/`All::Sg`, each
  bytes=33543, 0 rows.

### A/B. Root cause: NOT YET CONFIRMED for either class

This session still has no access to the actual raw HTML — only the
byte counts, row counts, and status strings quoted above. That is
metadata about the response, not the response. Per instruction ("do
not modify parser behavior until the exact mismatch is identified" /
"if real raw HTML is still unavailable ... do not guess"), no parser
change was made. Two prior hypotheses (blank `<th>` text; the site
using separate `recordName`/`record1..4` JS variables rather than a
JSON `menu`/`menuName` object) remain **unconfirmed** for CLASS 1, and
CLASS 2 has four live, undistinguished hypotheses per Mission 4
(navigation-only leaf / invalid request leaf / legitimate zero-data
endpoint / parser-taxonomy false positive) — none preferred without
the HTML. `bytes=33543` for CLASS 2 is a real, non-trivial page (not a
blank/error response), which rules out "the request outright failed"
but nothing more specific than that.

### What WAS done: raw-evidence preservation (Mission 3/6)

`scripts/27_klpga_response_schema_sample.py` now saves a second,
**human-named** copy of every sampled metric's raw response HTML to
`docs/discovery/raw_samples/<identity_key>__<season>.html` (e.g.
`Putt__Putt01__040101__2025.html`), on by default (`--no-raw-samples`
to disable), bounded by the same `--sample-size`/`--max-requests` cap
already governing live requests — never unbounded. This directory is
now gitignored (`docs/discovery/raw_samples/`), so it is never
auto-committed; specific files get handed over deliberately.

**Important: PoliteHttpClient already caches every response** under
`data/raw_cache/http/<hash>.json` (keyed by a content hash of
url+params, containing the exact `body_text`) — this has been true
since Round 1 and was never disabled. That means **the run that just
completed already has these exact 9 raw responses sitting on the
Windows machine right now**, just under opaque hash-named files. The
fastest path to real evidence is extracting them from that existing
cache rather than waiting for a new run — see the PowerShell snippet
below.

### Extracting the ALREADY-CACHED responses from the run that just completed

```powershell
cd klpga_pipeline
$targets = @(
  @{menu1="Tee";      menu2="Tee01";      menu3=$null},
  @{menu1="Approach";  menu2="Approach01"; menu3=$null},
  @{menu1="Around";    menu2="Around01";   menu3=$null},
  @{menu1="Putt";      menu2="Putt01";     menu3="040101"},
  @{menu1="All";       menu2="Approach";   menu3=$null},
  @{menu1="All";       menu2="Around";     menu3=$null},
  @{menu1="All";       menu2="Putt";       menu3=$null},
  @{menu1="All";       menu2="Sg";         menu3=$null}
)
New-Item -ItemType Directory -Force -Path docs\discovery\raw_samples | Out-Null
Get-ChildItem data\raw_cache\http\*.json | ForEach-Object {
  $j = Get-Content $_.FullName -Raw | ConvertFrom-Json
  $p = $j.params.data
  foreach ($t in $targets) {
    if ($p.menu1 -eq $t.menu1 -and $p.menu2 -eq $t.menu2 -and ($t.menu3 -eq $null -or $p.menu3 -eq $t.menu3)) {
      $name = "$($p.menu1)__$($p.menu2)" + $(if ($p.menu3) { "__$($p.menu3)" } else { "" }) + "__$($p.season).html"
      $j.body_text | Out-File -Encoding utf8 "docs\discovery\raw_samples\$name"
      Write-Host "Extracted: $name"
    }
  }
}
```

(Adjust the `menu2` values above if the real sample used different
menu2 nodes than these placeholders — check
`docs\discovery\KLPGA_RESPONSE_SCHEMA_SAMPLES.json`'s `identity_key`
field for the exact menu1/menu2/menu3 actually sampled this run.)
Once extracted, paste or push at least the CLASS 1 (`Putt`) and one
CLASS 2 (`All::*`) file back for real root-cause analysis.

### E–I. Schema/playerCode results

Not yet determinable from metadata alone — genuinely blocked pending
the raw HTML above, per Missions 2 and 5.

### J. All::* classification

Not yet proven — see the four live hypotheses under A/B above.

### Files changed

`scripts/27_klpga_response_schema_sample.py` (`raw_dir`/`--no-raw-samples`,
raw HTML preservation wired into both the main sample loop and the
historical probe), `.gitignore` (`docs/discovery/raw_samples/`),
`docs/KLPGA_OFFICIAL_DATA_MAP.md` (this section). `response_parser.py`
was **not modified** — no root cause confirmed yet. New/updated tests
in `tests/test_klpga_response_schema_sample_script.py`. Full suite:
462/462 passing.

### Next Windows command (unchanged; now also saves raw_samples/ automatically)

```
python scripts\27_klpga_response_schema_sample.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
    --season 2025
```

No change needed to re-run — the PowerShell extraction snippet above
against the ALREADY-COMPLETED run is faster than waiting for a new
one, since the raw bytes are already on disk.

## Round 3, Phase B1 — CLASS 1 root cause CONFIRMED, dynamic-header parser fix

**Status: 2026-08-26.** Direct real-evidence quotes from a Windows-side
cache inspection (playerCode/player_name/record values, and — most
importantly — the literal `var record = "그린 적중률(%)"; ...` /
`$(".recordName").html(record);` JS pattern) confirmed the CLASS 1 root
cause hypothesized in the prior round and fixed it, evidence-first, per
instruction.

### Mission 0 — cache identity: NOT independently verified

This session has no access to the actual cache file or its stored
`params` (season/menu1/menu2/menu3) — only the quoted body content. **I
cannot independently confirm the response's true request identity** —
per instruction, saying so explicitly rather than assuming it. What
CAN be said from the content itself: the recovered labels ("그린
적중률(%)" / "그린 적중 횟수" / "샷 시도 횟수" / "측정 라운드") are
semantically a GIR (green-in-regulation) metric, identical in *meaning*
to the already-confirmed Approach-family evidence (020104/020105) from
earlier rounds — and have nothing to do with putting. This strongly
suggests the response is **NOT** `Putt::Putt01::040101` as the prior
round's "Example A" label assumed; it is far more likely an
Approach/GIR-family response, possibly under a previously-unseen
menu3 code. Whether "040101" genuinely collides across menu1 families,
or the earlier substring search simply matched a DIFFERENT field
inside an Approach response, remains **unproven** — the cache's own
`params` field (or a fresh run's `raw_samples/<identity_key>__<season>.html`
filename, which IS self-identifying) is required to settle it. No
menu-code collision was silently resolved; this is flagged, not
assumed, per Mission 5.

### Mission 1 — CLASS 1 root cause: CONFIRMED

`response_parser.py`'s `_extract_metadata()` looks for a JSON-object
literal containing a `"menu"`/`"menuName"` key; the real response
instead carries **separate top-level JS variable declarations**
(`var record = "...";`, `var record1 = "...";`, ...) that a client-side
jQuery call (`$(".recordName").html(record);`) uses to fill `<th
class="recordName">` (etc.) text **at render time, in a real browser**.
This parser only ever sees the static HTTP response body — no JS
executes — so those `<th>` elements are present but **empty** in every
fetch this parser makes. The existing table-header fallback
(`_extract_column_semantics`) read that blank text as-is, and
`build_schema_fingerprint` filters out falsy labels entirely, producing
`EMPTY_SCHEMA` despite 231 real player rows and real, present
`data-record*` values. **This is now proven, not hypothesized** — the
real evidence explicitly contains the exact JS pattern predicted in the
prior round's Phase B1.1 report.

### Mission 2 — minimal parser fix

New `_extract_dynamic_header_labels(html, record_fields)` in
`response_parser.py`: scans the raw response body (not the parsed DOM
— script-tag text extraction via BeautifulSoup is unreliable across
mixed content) with `var\s+(record\d*)\s*=\s*"([^"]*)"\s*;`, returning
only **non-blank** labels for known `record_fields`. Wired into
`_extract_column_semantics` as a new priority layer, ranked between the
existing JSON-metadata layer (still tried first, unchanged) and the
static table-header fallback (now used only when neither of the first
two layers has a label — and, as a related correctness fix, only when
the `<th>` text is itself non-blank, so a blank header can never again
be silently treated as "found"). All requirements satisfied:
non-hardcoded (labels come only from the response's own text),
menu-code-blind (nothing here reads menu1/menu2/menu3 to infer
meaning), playerCode extraction untouched (row scanning is independent
of column-header resolution), and every existing parsing path
(metadata block, plain table header, `unknown`) preserved and still
covered by its original tests.

### Mission 3 — regression fixture

New `tests/fixtures/loadLocationRecord_dynamic_header_sample.html`,
modeled directly on the real evidence (exact reported values: playerCode
9807/김새로미 40·36·90·5·0.0, playerCode 9812/전예성 33.33·12·36·5·0.0,
the exact `var record.../record1.../record4=""` block) with `<th
class="recordName">` (etc.) left deliberately blank, matching the real
render-time-only population. 10 new tests across
`tests/test_record_response_parser.py` and `tests/test_response_schema.py`
prove: schema is not `EMPTY_SCHEMA` (`PERCENTAGE_COUNT_COUNT_ROUNDS`),
all four non-blank labels recovered with `source="dynamic_header_vars"`,
blank `record4` resolves to `label=None`/`source="unknown"` (never a
fake metric), values map to the correct fields, playerCode is
recovered for both rows, a `CONFIRMED_RAW_PAIR` is detected between
record1/record2 with both rows' arithmetic checking out
(36/90×100=40.0, 12/36×100=33.33̄), RTP correctly reads `RTP_ABSENT`
(not conflated with the blank record4), and a static-blank-`<th>`-only
case (no dynamic vars at all) resolves to `unknown`/`AMBIGUOUS` rather
than a fabricated empty-string label — a regression guard on the fix
itself.

### Mission 4 — re-evaluating the prior sample (`HTTP_SUCCESS:9 PARSE_SUCCESS:4 PARSE_EMPTY:5`)

**Not the EMPTY bucket.** `parse_status="EMPTY"` requires **zero player
rows** (`if not rows: status="EMPTY"` — a check that runs before column
semantics are ever examined). The dynamic-header defect only affects
*column-label* resolution for responses that already have rows; it
cannot turn a genuinely 0-row response into a populated one. **None of
the 5 `PARSE_EMPTY` responses are explained or fixed by this round's
change** — they remain CLASS 2 (`All::*` and possibly one more
unnamed 0-row response — the prior round's evidence named 4 `All::*`
examples but reported `PARSE_EMPTY=5`; the 5th has not been identified
and is **not assumed** to be another `All::*` instance) — genuinely
separate from CLASS 1, exactly as Mission 5 requires.

**Possibly the PARSE_SUCCESS bucket.** The one CLASS 1 response
directly investigated (the 231-row, `DISCOVERED_NOT_VALIDATED`,
`EMPTY_SCHEMA` one) was already counted among the 4 `PARSE_SUCCESS`
responses before this fix — `DISCOVERED_NOT_VALIDATED` is a
`PARSE_SUCCESS` outcome; `EMPTY_SCHEMA` is a separate, finer-grained
quality signal about the *schema*, not the top-level outcome bucket.
This fix should make that one response's schema fingerprint real
(`PERCENTAGE_COUNT_COUNT_ROUNDS`-shaped, going by the evidence) instead
of `EMPTY_SCHEMA` on the next run. **Whether the other 3 `PARSE_SUCCESS`
responses were ALSO silently EMPTY_SCHEMA before this fix is
unproven** — only one was directly evidenced this round; claiming all
4 benefit without independently checking each would be exactly the
kind of unproven generalization the instructions warn against.

### Files changed

`src/klpga/discovery/response_parser.py` (`_extract_dynamic_header_labels`,
`_extract_column_semantics` gains the new priority layer + blank-`<th>`
correctness fix, `parse_record_response` wiring and a new
`DISCOVERED_NOT_VALIDATED` note variant, module docstring layer list
updated), new fixture `tests/fixtures/loadLocationRecord_dynamic_header_sample.html`,
new/updated tests in `tests/test_record_response_parser.py` and
`tests/test_response_schema.py`, this section of
`docs/KLPGA_OFFICIAL_DATA_MAP.md`. No change to `response_schema.py`'s
classification logic itself, `sampler.py`, or any script — this round
is parser-only, per Mission 2's scope.

### Tests / protected areas

473/473 tests passing. No change to Prediction #001, `predictions/`,
model/inference/probability logic, the production DB, the archive, or
the public website. Phase B2 not started; no bulk requests made; no
menu-code collision was silently resolved (see Mission 0 above).

### Exact next Windows command

Unchanged — the fix applies automatically to every future parse, live
or cached-replay:

```
python scripts\27_klpga_response_schema_sample.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json ^
    --season 2025
```

To settle Mission 0's open identity question, check
`docs\discovery\raw_samples\` from this run (filenames are
self-identifying: `<menu1>__<menu2>__<menu3>__<season>.html`) or the
cache JSON's own `params` field for whichever file contains the
`playerCode=9807`/`전예성` evidence quoted above.

## Round 3, Phase B1 — CLASS 2 root cause CONFIRMED, navigation/container node classification

**Status: 2026-08-26.** Direct evidence from `docs/discovery/raw_samples/All__Sg__2025.html`
(the request that produced it was `menu1="All" menu2="Sg" menu3=None`,
returning HTTP 200, 33543 bytes, 0 rows) confirmed CLASS 2's root
cause: that response's own BODY contains the full record navigation
menu tree (`data-menu1="Sg" data-menu2="Total"`, `data-menu1="Sg"
data-menu2="TeeToGreen"`, `data-menu1="Tee" data-menu2="Tee01"
data-menu3="010101"/"010102"/"010103"`, and more) — the SAME kind of
markup Phase A's own `inspect_menu_dom()` scrapes to build the
taxonomy in the first place. `menu1="All"` is not a metric family at
all; it is the site's own "show the full menu" navigation/container
page.

### A/B. CLASS 2 root cause: CONFIRMED. All::* were false metric leaves.

Phase A's Pass 2 (menu2-level leaf detection) classifies a tag as a
metric leaf whenever it carries its own `data-menu1`+`data-menu2`, a
blank/absent `data-menu3`, and no menu3-bearing descendant — a purely
STATIC-DOM rule, evaluated only against the landing/menu page. On that
landing page, an `All`-family element apparently satisfies that
shape (own attrs, no menu3 descendant in that markup), so Phase A
correctly-by-its-own-rules recorded it as a menu2-level leaf. What
Phase A's static-DOM rule cannot know — because it never fires a
`loadLocationRecord` request itself — is that when that "leaf" is
actually REQUESTED, the response returned is a navigation page, not
player data. This is now proven, not inferred from the name "All": the
classification is grounded in the observed response shape (0 rows +
the menu tree itself in the body), scoped to exactly this evidenced
value.

### Mission 2 — taxonomy semantic classes

New `node_type` on `MenuLeaf` (`src/klpga/discovery/menu_taxonomy.py`):
`REQUESTABLE_METRIC_LEAF` (default) or `NAVIGATION_CONTAINER`
(`menu1` in `CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES = frozenset({"All"})`
— scoped to exactly this confirmed value, never a broader name-pattern
guess). Canonical identity rules are UNCHANGED: `(menu1, menu2)` for a
menu2-level metric, `(menu1, menu2, menu3)` for a menu3-level metric —
`node_type` is an orthogonal classification, not a replacement for
identity. `taxonomy_report.py`'s JSON/CSV output now includes
`node_type` per leaf and new counts
(`requestable_menu2_leaf_count`/`requestable_menu3_leaf_count`/`navigation_container_count`).

### Mission 3 — the canonical request plan: REAL NUMBERS NOT YET COMPUTABLE

**This session does not have `docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.json`**
(confirmed — `docs/discovery/` does not exist in this repo/session, as
in every prior round; nothing from any Windows run has ever been
pushed here). Per instruction ("do NOT assume the previous 283 number
remains correct"), **items C–I below are NOT filled in with real
numbers** — computing them requires your actual taxonomy file. What
WAS built: `src/klpga/discovery/canonical_plan.py` (`build_canonical_plan`)
and `scripts/28_build_canonical_metric_request_plan.py`, a fully
OFFLINE script (reads your existing local
`KLPGA_RECORD_TAXONOMY_DISCOVERED.json`, zero network access) that
computes all of C–I and writes `docs/discovery/KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json`
in exactly the schema Mission 3 specifies (menu1/menu2/menu3/leaf_level/
identity_key/label/node_type/evidence_source per entry). It works
whether or not your existing file already has `node_type` (falls back
to the same confirmed-menu1-value rule if not — no re-run of script 26
required).

Run this locally to get the real answer to "how many REAL KLPGA metric
requests exist after removing navigation/container nodes?":

```
python scripts\28_build_canonical_metric_request_plan.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json
```

### Mission 4 — sampler fix

New `sampler.reject_navigation_container_leaves()`, parallel to (and
kept distinct from — never silently merged with) the existing
`reject_malformed_leaves()`: a malformed leaf has no usable identity
at all, while a navigation container has a perfectly valid identity
that simply doesn't point at player data. Wired into
`select_representative_sample()` as defense-in-depth (a navigation
leaf can never reach a live request even if a caller forgets the
separate rejection step) and into `scripts/27_klpga_response_schema_sample.py`
as an explicit `[STEP 05b]` pre-filter step, reported by name — mirroring
the existing malformed-leaf pattern. The prior round's "All"-deprioritization
heuristic (`_PRIORITY_FAMILIES`) is now largely moot for "All" specifically
(it's rejected outright before family-grouping even happens) but is
left in place, unchanged, for any other not-yet-classified family.

### Mission 5 — verified locally against fixtures (no live requests)

New regression tests in `tests/test_sampler.py` build a taxonomy
mirroring the exact real evidence (`All::Sg`/`All::Tee`/`All::Approach`/
`All::Around`/`All::Putt` alongside real Sg/Tee/Approach/Around/Putt
leaves) and confirm: `select_representative_sample()` never selects
any `All::*` leaf, while still covering all five confirmed families.
Also covered end-to-end at the script-orchestration level
(`tests/test_klpga_response_schema_sample_script.py`): an `All::Sg`
leaf injected into the fixture taxonomy is rejected and never fetched
(`client_2025.requests` never contains a `menu1="All"` request).

### Mission 6 — dynamic-header (CLASS 1) fix verified unregressed

Directly re-checked this round (not merely re-run via the suite):
`parse_record_response()` over the real-evidence dynamic-header
fixture still produces schema fingerprint `PERCENTAGE_COUNT_COUNT_ROUNDS`
and both playerCodes (`9807`/`김새로미`, `9812`/`전예성`) intact. No
line of `response_parser.py` was touched this round — this round is
taxonomy/sampler-only, per Mission 2's scope.

### Files changed

`src/klpga/discovery/menu_taxonomy.py` (`node_type`, `CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES`,
`requestable_leaves`/`navigation_container_leaves` properties),
`src/klpga/discovery/taxonomy_report.py` (new counts, `node_type` in
JSON/CSV output), `src/klpga/discovery/sampler.py`
(`reject_navigation_container_leaves`, wired into
`select_representative_sample`), `src/klpga/discovery/canonical_plan.py`
(new — Mission 3), `scripts/27_klpga_response_schema_sample.py`
(`[STEP 05b]` navigation-rejection reporting), `scripts/28_build_canonical_metric_request_plan.py`
(new — Mission 3), new tests `tests/test_taxonomy_report.py` and
`tests/test_canonical_plan.py` and `tests/test_build_canonical_metric_request_plan_script.py`,
updates to `tests/test_menu_taxonomy.py`, `tests/test_sampler.py`,
`tests/test_klpga_response_schema_sample_script.py`. `response_parser.py`
untouched (Mission 6).

### Tests / safety

502/502 tests passing. No change to Prediction #001, `predictions/`,
model/inference/probability logic, the production DB, the archive, or
the public website. Phase B2 not started; no bulk canonical sweep
performed — `scripts/28` only WRITES a plan file, it never fires any
of the requests it lists.

## Round 3, Phase B1 — the 272-malformed-node investigation

**Status: 2026-08-26.** The real Windows run of `scripts/28_build_canonical_metric_request_plan.py`
against the actual `KLPGA_RECORD_TAXONOMY_DISCOVERED.json` reported:

```
total DOM-discovered nodes:          283
malformed leaves (blank identity):   272
requestable menu2-level metrics:       1
requestable menu3-level metrics:       4
navigation/container nodes:            6
exact duplicate DOM entries:           0
CANONICAL requestable metric count:     5
menu3 collisions (canonical set):       0
```

96.1% malformed is not acceptable as a validated plan — this section
documents the investigation, the diagnostic tooling built, and why no
speculative parser fix was applied.

### A. Exact cause of the 272 malformed nodes — BEST-EVIDENCE HYPOTHESIS, NOT PROVEN

This session still has no access to the real taxonomy JSON file
itself (confirmed — `docs/discovery/` does not exist in this
repo/session, as in every prior round). What WAS possible: a
field-by-field code audit of every commit that ever touched the
serializer (`taxonomy_report.to_taxonomy_json`) against every reader
(`canonical_plan.py`, `sampler.py`), plus new round-trip regression
tests (`tests/test_taxonomy_json_roundtrip.py`) that serialize a real
DOM through this project's OWN current pipeline and confirm zero
malformed leaves come out the other end. **Result: no serializer/reader
field-name mismatch was found anywhere in this codebase's history** —
see B/C/D below for the literal comparison.

With a schema mismatch ruled out by direct code audit, the only
evidence-consistent explanation left is: **the real DOM,at Phase-A-scrape
time, genuinely produced 272 leaves via `inspect_menu_dom`'s Pass-1
"unknown" fallback** — a `data-menu3` tag whose ancestor chain (a
`<div>`/container carrying `data-menu1`/`data-menu2`) could not be
found, so `menu1`/`menu2` were correctly left blank rather than
guessed (per this module's own "never invent an identity" rule — see
`test_unresolvable_menu3_is_preserved_not_dropped`). This is
consistent with everything the numbers show:

- The arithmetic is exact and leaves no room for a hidden third
  category: 272 malformed + 6 navigation + 5 requestable = 283, with 0
  duplicates — every single leaf is accounted for.
- 6 navigation + 5 requestable = **11 leaves with a real, resolved
  identity** — matching the ORIGINAL Phase A run's own reported "11
  menu2 nodes" count almost exactly. This strongly suggests only
  `own_attrs`-resolved leaves (identifiers all present directly on one
  clickable tag) survived, while `ancestor_walk` resolution — which
  requires a real containing DOM element carrying `data-menu1`/
  `data-menu2` — failed for the overwhelming majority of the real
  page's menu3-level tags.
- `unique_menu3_count`/`collision_count`/`incomplete_menu1_count` in
  the ORIGINAL Phase A summary are all computed independently of
  whether a leaf's menu1/menu2 resolved (a menu3 CODE is counted
  whether or not its identity resolved) — so a majority-blank dataset
  could still report "241 unique codes, 31 collisions, 0 incomplete
  categories" and read as a clean, "COMPLETE" run, exactly as happened.

**This is a hypothesis about the real site's DOM structure, not a
code bug this session can fix without guessing.** The user's
individually-inspected DevTools captures (SG Total, Approach GIR,
Tee distance buckets — all confirmed elsewhere in this project) happen
to be exactly the kind of element where `own_attrs` resolution
succeeds; the BULK of the real page's menu tree, at scale, apparently
uses a different structure this project has never had full real HTML
for. Confirming this precisely (and only then safely patching
`inspect_menu_dom`'s ancestor-walk) requires the real page HTML or at
minimum a sample of the real malformed rows — see the new
`KLPGA_MALFORMED_LEAF_REPORT.csv` below.

### B. Taxonomy JSON schema actually found: UNKNOWN (file not available this session)

### C. Schema expected by canonical_plan.py before this round's fix

`menu1`, `menu1_label`, `menu2`, `menu2_label`, `menu3`, `menu3_label`,
`leaf_level`, `source_metric_key`, `label_resolution_method`,
`is_menu3_collision`, optionally `node_type` — exactly what
`taxonomy_report.to_taxonomy_json` has written since the Round 3 patch
(commit `1a54320`) onward, confirmed by direct git-history diff against
every version of that function this project has ever shipped.

### D. Exact mismatch: NONE FOUND in this codebase's history

Diffed `to_taxonomy_json` across commits `6647684` (original,
pre-patch — no `leaf_level` key at all), `1a54320` (the patch that
introduced 2-level/3-level leaves and `leaf_level`), and current HEAD
(adds `node_type`, additive only). `canonical_plan.py`'s readers
(`_is_malformed`, `_node_type`, `_identity_key_tuple`, `_label`) match
the POST-patch schema exactly, field for field. If the real file were
still in the ORIGINAL pre-patch shape (no `leaf_level` at all), that
alone would NOT explain 272 malformed leaves — `_is_malformed` never
inspects `leaf_level`, only `menu1`/`menu2`. New diagnostic
(`classify_malformation_reason`) explicitly distinguishes this
possibility (`"legacy_taxonomy_format_missing_leaf_level"`) from the
Pass-1-unknown-fallback signature (`"missing_menu1_and_menu2"`) so the
real report (once generated) settles this directly rather than by
further inference.

### E/F. Nodes recovered / still malformed

**Not applicable this session — no code change was made to
`inspect_menu_dom`, `taxonomy_report.py`, or `canonical_plan.py`'s
rejection logic.** Per instruction ("fix only the confirmed root
cause… do not fabricate menu values… do not reconstruct identities
from labels"), no speculative fix was applied without the real
evidence to validate it against. What WAS built is entirely diagnostic
and safety-guard tooling — see Missions 2/6/7 below.

### Mission 2 — malformed diagnostic report

New `canonical_plan.classify_malformation_reason()` (categories:
`missing_menu1_and_menu2`, `missing_menu1`, `missing_menu2`,
`missing_menu3_when_required`, `legacy_taxonomy_format_missing_leaf_level`,
`unrecognized_fields:<...>`, `other`) and `build_malformed_leaf_report()` /
`to_malformed_leaf_report_csv()`, wired into `scripts/28` to always
write `docs/discovery/KLPGA_MALFORMED_LEAF_REPORT.csv` (original_index,
raw_menu1/2/3, leaf_level, label, node_type, identity_key,
rejection_reason per row) — even when the sanity check below fails, so
the real data is on disk to actually settle A/B/D above.

### Mission 3 — schema contract verified via round-trip tests

New `tests/test_taxonomy_json_roundtrip.py`: DOM → `MenuLeaf` →
`to_taxonomy_json` → `json.loads` → `select_representative_sample` /
`build_canonical_plan`, for both a menu2-level identity (`Sg::Total`)
and a menu3-level identity (`Tee::Tee01::010101`) — confirms the
identity tuple survives the full round-trip unchanged, and that this
project's own current pipeline produces ZERO malformed leaves from
clean, resolvable evidence (isolating the 272-node problem to the real
site's DOM shape, not this codebase).

### Mission 4 — 241 unique codes / 31 collisions vs 5 canonical / 0 collisions: explained, not contradicted

Fully consistent, not a contradiction: the OLD stats
(`unique_menu3_count`/`collision_count` in the Phase A taxonomy JSON)
are computed over EVERY menu3-level leaf's CODE, regardless of whether
its menu1/menu2 identity resolved. The NEW canonical-plan collision
count is computed only over the 4 SURVIVING (non-malformed,
non-navigation) menu3-level leaves — with only 4 candidates, there is
essentially no room for a collision to appear (need 2+ surviving
leaves sharing a code). The old evidence is not declared invalid —
the 241/31 figures remain real, accurate facts about the raw DOM scan;
they simply describe a different (larger, identity-unresolved)
population than the canonical (identity-resolved) one.

### Mission 5 — no fix applied without confirmed root cause

Per instruction, `menu_taxonomy.py`'s ancestor-walk was NOT modified —
doing so without the real page HTML would mean guessing at a DOM
structure this session has never seen in full, risking exactly the
"reconstruct identities from labels" / "fabricate menu values" outcome
the instructions explicitly forbid. `All::*` → `NAVIGATION_CONTAINER`
remains unchanged and confirmed (Mission 8).

### Mission 6 — canonical plan now includes per-family counts

`scripts/28` now prints total DOM-discovered nodes, valid identity
nodes, malformed nodes, requestable menu2/menu3 counts, navigation
count, exact duplicates, canonical count, collisions, AND a per-family
breakdown (Sg/Tee/Approach/Around/Putt/other — grouped strictly by
each leaf's own `menu1`, so an `All::Sg` navigation entry counts under
"other," not "Sg," since its real menu1 is "All").

### Mission 7 — sanity invariants added

New `canonical_plan.check_sanity_invariants()`: fails when
`malformed_ratio > 10%` OR the canonical count is `>80%` smaller than
the valid-identity leaf count. `scripts/28` now returns a distinct
`EXIT_SANITY_CHECK_FAILED` (6) and prints `SANITY CHECK FAILED` with
the specific violation(s) whenever either trips — **the exact
272/283 result from this round is regression-tested to fail this
check** (`test_run_returns_sanity_check_failed_on_the_windows_shaped_result`).
Both output files are still written on failure (the data is real and
worth having on disk), but the exit code and console output make clear
this is NOT a trustworthy, ready-to-use canonical plan.

### Mission 8 — confirmed fixes verified unregressed

Re-checked directly this round (not merely re-run via the suite):
`All::*` → `NAVIGATION_CONTAINER` classification, the dynamic-header
(`var record/record1/.../record4`) parser fix (still produces
`PERCENTAGE_COUNT_COUNT_ROUNDS` with both playerCodes intact), raw-count-pair
detection, and measured-round detection — all unchanged, all still
passing their existing tests.

### Files changed

`src/klpga/discovery/canonical_plan.py` (`classify_malformation_reason`,
`build_malformed_leaf_report`, `to_malformed_leaf_report_csv`,
`group_counts_by_family`, `check_sanity_invariants`),
`scripts/28_build_canonical_metric_request_plan.py` (malformed-report
writing, per-family printing, sanity-check exit code), new
`tests/test_taxonomy_json_roundtrip.py`, updates to
`tests/test_canonical_plan.py` and
`tests/test_build_canonical_metric_request_plan_script.py`. No change
to `menu_taxonomy.py`, `response_parser.py`, `sampler.py`'s rejection
logic, or `taxonomy_report.py` this round.

### Tests / safety

526/526 tests passing. No change to Prediction #001, `predictions/`,
model/inference/probability logic, the production DB, the archive, or
the public website. No live requests made; Phase B1/B2 not started.

### Next step

Push (or paste key rows from) `docs/discovery/KLPGA_MALFORMED_LEAF_REPORT.csv`
from the real Windows run — its `rejection_reason` column directly
answers whether A's hypothesis (Pass-1 ancestor-resolution failure,
`missing_menu1_and_menu2`) is correct, or whether something else
(`legacy_taxonomy_format_missing_leaf_level` / `unrecognized_fields:...`)
is actually going on. That is the evidence needed before any parser
fix can be made safely.

## Round 3, Phase B1 — DOM ancestry fix: `preceding_context` resolution

**Status: 2026-08-26.** `docs/discovery/KLPGA_MALFORMED_LEAF_REPORT.csv`
from the real Windows run confirmed the hypothesis from the prior
round with direct evidence: all 272 malformed rows have
`rejection_reason=missing_menu1_and_menu2`, and representative real
rows (`010101`/"Par4,5 티샷 비율", `010109`/"Par4,5 페어웨이 안착률",
`010201`/"Par5 티샷 비율", `020101`/"그린 적중률",
`020201`/"그린 적중 시 남은 거리", `020301`/"그린 적중률(페어웨이)")
show menu3 and label were discovered CORRECTLY — only the menu1/menu2
ancestry relationship failed to resolve. This is a genuine
`inspect_menu_dom()` DOM-resolution gap, not a canonical-plan or
serialization bug (confirmed already in the prior round's round-trip
tests).

### A. Exact DOM structural reason ancestry failed

Not provable with certainty this session — the malformed-leaf CSV
carries menu3 codes and labels only, never the surrounding raw HTML,
and this session still has no access to the real page source. What
IS certain from the evidence: `_find_ancestor_with_attr`'s PARENT-CHAIN
walk (checking `tag.parents` only) found no ancestor carrying
`data-menu1`/`data-menu2` for 272 of 283 real menu3-level tags. Per
the mission's own list of structural hypotheses (siblings rather than
ancestors, a preceding section header, separate anchor elements, DOM
ordering rather than parent ancestry, a wrapper whose own attributes
differ from the anchor) — all of these share one property: the
identifying element is NOT an ancestor of the `data-menu3` tag, so a
pure parent-chain walk can never find it regardless of which specific
one of these shapes the real page actually uses.

### B. Old resolver behavior

Three tiers, in order: (1) `own_attrs` — all three identifiers on one
tag; (2) `ancestor_walk` — `data-menu1`/`data-menu2` found by walking
UP through `tag.parents` only; (3) `unknown` — blank identity,
preserved rather than dropped. Tier 2 requires a true parent/ancestor
DOM relationship, which the real page's markup evidently does not use
for the vast majority of its menu3-level tags.

### C. New resolver behavior

New tier 2.5 (`preceding_context`), tried after `ancestor_walk` fails
and before falling back to `unknown`: `_find_nearest_preceding_attr()`
scans BACKWARD through the fully flattened document (in document
order — siblings, cousins, anything, no ancestor relationship
required) for the nearest EARLIER element carrying `data-menu1`
(searched independently of `data-menu2`, since the mission's own
hypotheses include "separate anchor elements"). This is a purely
STRUCTURAL, DOM-order search — it never reads `menu3` codes, labels,
or golf semantics, and never invents an identity when genuinely
nothing precedes a tag (verified by two dedicated regression tests:
the ORIGINAL single-tag Round-1 case, and a fresh orphaned-tag case
placed before any context in the new fixture). `own_attrs` and
`ancestor_walk` are completely unchanged and still tried first — this
is purely additive.

### D. Files changed

`src/klpga/discovery/menu_taxonomy.py` (`_find_nearest_preceding_attr`,
wired into Pass 1's fallback chain, `label_resolution_method`
docstring updated), new fixture
`tests/fixtures/record_menu_preceding_context_sample.html`, new
`tests/test_preceding_context_resolution.py` (13 tests). No change to
`taxonomy_report.py`, `canonical_plan.py`, `sampler.py`'s rejection
logic, `response_parser.py`, or Pass 2 (menu2-level leaf detection,
out of this round's scope — the malformed-leaf report covered only
menu3-level rows).

### E. Regression fixture source/shape

`tests/fixtures/record_menu_preceding_context_sample.html` — built
from the SIX real code/label pairs quoted above (Tee 010101/010109/
010201, Approach 020101/020201/020301), plus the already-confirmed Sg
own_attrs leaves and an All::Sg navigation entry, using a SIBLING
section-header DOM shape (menu1/menu2 identifiers on preceding
`<div>` headers, never wrapping the `<a data-menu3=...>` tags as an
ancestor) — the structural pattern the mission specifically asked to
be tested, not a simplified ancestor-nesting shape. Around/Putt
entries reuse this project's existing placeholder codes/labels
(030101/040101) for structural coverage only; the fixture's own header
comment is explicit that only the six Tee/Approach rows are this
round's real evidence. **This fixture is a constructed hypothesis
about the real page, consistent with the evidence, not a literal HTML
capture** — no raw page source has been available to this project at
any point.

### Mission 6 — structural validation, not hardcoded counts

`test_malformed_ratio_collapses_dramatically_on_this_fixture` asserts
the malformed ratio is small on the new fixture (1 genuinely orphaned
leaf out of 12, ≈8%) — a structural target, never a specific expected
count. The REAL validation is Mission 5 below: rerun Phase A against
the live page and check whether the real malformed ratio actually
collapses from 96%.

### Mission 7 — collision preservation re-verified

New test `test_same_menu3_code_under_different_parents_stays_distinct_not_deduplicated`
constructs the same `menu3="010102"` collision shape as the real
Round-1 finding, now resolved via `preceding_context` instead of
`ancestor_walk` — confirms two leaves with the SAME menu3 code but
different (menu1, menu2) resolve to two DISTINCT canonical identities
and still appear in `collisions`, never silently deduplicated. Once
ancestry is recovered for the real 272 nodes, the collision count
computed over the (much larger) canonical set will very likely rise
again from the current 0 — that is an expected, evidence-driven
consequence of more leaves having real identities to collide on, not
something this round predicts a specific number for.

### Tests / safety

539/539 tests passing. No change to Prediction #001, `predictions/`,
model/inference/probability logic, the production DB, the archive, or
the public website. No live requests made; Phase B1/B2 not started;
no bulk metric sweep.

### H. Exact Windows command to regenerate Phase A taxonomy

```
python scripts\26_discover_klpga_record_taxonomy.py ^
    --source-url "https://klpga.co.kr/web/record/locationRecord"
```

This overwrites `docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json`/`.csv`
and `KLPGA_METRIC_COLLISION_REPORT.md` with a fresh scrape using this
round's fixed resolver. Zero-to-one HTTP request (the landing page
itself), unchanged from every prior round.

### I. Exact Windows command to rerun script 28

```
python scripts\28_build_canonical_metric_request_plan.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json
```

Fully offline. Compare its new `malformed leaves (blank identity)`
count and `KLPGA_MALFORMED_LEAF_REPORT.csv` against this round's
272/283 baseline — if the ratio collapses as expected, the sanity
check should pass (`EXIT_COMPLETE`) instead of failing
(`EXIT_SANITY_CHECK_FAILED`). If a meaningful number of nodes are
STILL malformed after this fix, their `rejection_reason` rows are the
next real evidence to investigate — still `missing_menu1_and_menu2`
would mean a real page structure this new tier still doesn't cover.

## Round 3, Phase B1 — scope the NAVIGATION_CONTAINER rule to the confirmed shape

**Status: 2026-08-26.** The `preceding_context` fix worked exactly as
intended against the real page: the real Windows rerun of script 26
reported malformed leaves collapsed from 272 to **0** (283/283 valid
identity nodes, 6/11/7/276/283/241/31/0/COMPLETE — matching the
original Phase A summary numbers exactly). But script 28 then failed
its sanity check for a NEW reason: 278 of those 283 valid nodes were
classified `NAVIGATION_CONTAINER`, collapsing the canonical count to 5.

### A. Exact root cause of the 278 navigation classifications

`MenuLeaf.node_type` (menu_taxonomy.py) and `canonical_plan._node_type()`
both checked ONLY `menu1 == "All"`, with no `leaf_level` restriction.
The CONFIRMED navigation evidence (a live `All`/`Sg` request with NO
menu3 — a menu2-level shape) never covered menu3-level leaves at all.
Once `preceding_context` started resolving real menu3-level leaves'
`menu1` field from a shared, page-level container that itself happens
to be tagged `data-menu1="All"` (evidently how the real page's full
metric-link listing is wrapped), 272 genuine menu3-level metrics
inherited `menu1="All"` structurally — and the leaf_level-blind rule
then wrongly excluded them as if they matched the confirmed evidence,
which it never did.

### B. Old classification rule

```python
if self.menu1 in CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES:
    return NODE_TYPE_NAVIGATION_CONTAINER
```

Basis: `menu1` string value alone. Not DOM structure, not
`leaf_level`, not descendants, not `label_resolution_method` — a
name/value heuristic added when "All" was first confirmed navigation,
which implicitly (and, it turns out, incorrectly) assumed EVERY leaf
with that menu1 value shared the same confirmed shape.

Five leaves escaped this bug only because they resolved via
`own_attrs`/`ancestor_walk` directly to their true family (one each:
Sg/Tee/Approach/Around/Putt) rather than via `preceding_context`
finding the shared "All"-tagged container — these are almost certainly
the same individually-confirmed DevTools examples from the earliest
rounds of this project.

### C. New classification rule

```python
if self.leaf_level == LEAF_LEVEL_MENU2 and self.menu1 in CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES:
    return NODE_TYPE_NAVIGATION_CONTAINER
```

Scoped to the EXACT confirmed request shape (menu2-level, no menu3).
A menu3-level leaf is never excluded on menu1 value alone, regardless
of resolution method or DOM position — per Mission 2's own framing,
"a navigation link may itself represent a real metric request," and
the only affirmative evidence this project has is specifically about
the menu2-level shape. Mirrored in `canonical_plan._node_type()`'s
fallback and `sampler._is_navigation_container_leaf_dict()`'s fallback
(both used only when a taxonomy JSON lacks an explicit `node_type` —
an explicit stored value, e.g. from a STALE pre-fix JSON, is still
trusted as-is; regenerate via script 26 to get the corrected value).

### D. Files changed

`src/klpga/discovery/menu_taxonomy.py` (`MenuLeaf.node_type`,
`CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES` docstring), `canonical_plan.py`
(`_node_type()` fallback), `sampler.py`
(`_is_navigation_container_leaf_dict()` fallback), new
`tests/test_navigation_container_scope_fix.py`. `_find_nearest_preceding_attr`
and every other part of the `preceding_context` resolution logic —
untouched (Mission 8's item I: no behavior change there, none was
needed).

### E. Tests added

`tests/test_navigation_container_scope_fix.py` (11 tests, matching
Mission 4's A-E): confirmed menu2-level `All::*` still excluded
(taxonomy-level AND full sampler/canonical-plan pipeline); a menu3-level
`own_attrs` leaf with `menu1="All"` (the direct getRecord click shape)
is requestable; SG menu2 leaves unaffected; a `preceding_context`-resolved
menu3 leaf sharing an "All"-tagged container with other real leaves is
requestable, including a multi-leaf case proving bulk-exclusion doesn't
recur; exact-duplicate dedup and cross-parent menu3-collision
preservation both re-verified unaffected by this fix.

### F. Tests passed

550/550.

### G. Why All::* remains excluded

The original evidence is unchanged and still applies exactly as
confirmed: a real `menu1=All, menu2=Sg, menu3=None` request returned
0 rows and the full navigation tree in its body. That evidence was
always specifically about the menu2-level shape — nothing about this
round's fix removes or weakens that exclusion; it only stops
OVER-APPLYING it to a shape (menu3-level) the evidence never covered.

### H. Why real menu3 metric links are now requestable

Because the confirmed navigation evidence never said anything about
menu3-level requests, and per Mission 2's own click-mechanism evidence
(`getRecord(menu1, menu2, menu3)` firing from `data-menu1`/`data-menu2`/
`data-menu3` on the clicked element), a menu3-bearing link represents
a genuine, distinct metric request regardless of which container
happens to structurally precede it in the DOM.

### I. preceding_context behavior

Unchanged — confirmed by diff (no function signature or logic touched)
and by all 13 of last round's regression tests still passing unmodified.
Only `node_type` classification (a separate, downstream concern) changed.

### Tests / safety

550/550 passing. No change to Prediction #001, `predictions/`,
model/inference/probability logic, the production DB, the archive, or
the public website. No live requests made; Phase B1/B2 not started; no
bulk metric sweep. The sanity-check thresholds themselves
(`check_sanity_invariants`) were NOT weakened — this round fixes the
classifier feeding it, not the guard itself.

### J. Expected Windows verification commands (unchanged from the prior round)

```
python scripts\26_discover_klpga_record_taxonomy.py ^
    --source-url "https://klpga.co.kr/web/record/locationRecord"

python scripts\28_build_canonical_metric_request_plan.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json
```

Per explicit instruction, the final canonical requestable-metric count
is NOT predicted here. Expected direction only: malformed stays at or
near 0 (unaffected by this round), navigation/container count should
collapse from 278 to something close to the real number of genuine
menu2-level `All::<family>` navigation entries (structurally, likely
in the single digits — 6-7 menu2-level leaves existed in total per
Phase A's own count), canonical requestable count should rise
materially above 5, and menu3 collisions should be recomputed over
that much larger canonical population — a real number this round does
not predict.

---

## Round 4 — Phase A confirmed complete; Phase B1 sampling now sourced from the canonical plan

### A. Real Windows verification result (Phase A, final)

The real rerun of `scripts/26_discover_klpga_record_taxonomy.py` +
`scripts/28_build_canonical_metric_request_plan.py` against the live
site confirmed the Round 3 `node_type` fix is correct end-to-end:

| Metric | Count |
|---|---|
| Total DOM-discovered nodes | 283 |
| Valid identity nodes | 283 |
| Malformed leaves | 0 |
| Requestable menu2-level metrics | 1 |
| Requestable menu3-level metrics | 276 |
| Navigation/container nodes | 6 |
| Exact duplicate DOM entries | 0 |
| **Canonical requestable metric count** | **277** |
| menu3 collisions (canonical set) | 31 |

`check_sanity_invariants` passed. Per instruction, Phase A taxonomy
discovery and canonical request-plan construction are now treated as
COMPLETE — this round does not touch `menu_taxonomy.py` or
`canonical_plan.py`'s classification logic at all.

### B. Phase B1 scope for this round

Per instruction: build a bounded (~12-20), structurally-selected
sample sourced from the canonical plan (`KLPGA_CANONICAL_METRIC_
REQUEST_PLAN.json`'s 277 entries) as the source of truth — not the raw
Phase A taxonomy JSON with its own separate malformed/navigation
filtering. Phase B2 (the full 277-metric sweep) remains explicitly
out of scope and was not started; no bulk or live request of any kind
was made this round — all preparation work is pure code (adapters,
sampler logic, script wiring) validated against small in-memory
fixtures.

### C. What changed

**`src/klpga/discovery/sampler.py`** — two additions, no changes to
any existing function:

- `_canonical_entry_to_leaf_dict(entry)` — adapts one canonical-plan
  entry (`{menu1, menu2, menu3, leaf_level, identity_key, label,
  node_type, evidence_source}`) into the taxonomy-leaf dict shape
  `_leaf_from_dict`/`select_representative_sample` already consume.
  Every field is copied directly from the entry — nothing inferred.
- `select_representative_sample_from_canonical_plan(plan, target_count=20, per_family_cap=4)`
  — reuses the existing family round-robin sampler via the adapter
  (the canonical plan is already malformed-free and navigation-free by
  construction, so no separate rejection pass runs), then
  deterministically guarantees the sample includes at least one
  COLLIDING menu3 identity (menu3 code shared by >1 canonical entry)
  and at least one NON-colliding one — computed by grouping the
  plan's own menu3-level entries by menu3 code. The top-up is
  deterministic (sorted by `(menu1, menu2, menu3)`, never random) and
  never introduces a duplicate identity. If the plan has zero
  collisions, the top-up is a no-op.

**`scripts/27_klpga_response_schema_sample.py`**:

- New `--canonical-plan` CLI argument, mutually exclusive with
  `--taxonomy` (exactly one of the two is required). When given, its
  `canonical_requestable_metrics` list is loaded and passed to `run()`
  as the new `canonical_plan` parameter.
- `run()` gained an optional `canonical_plan` parameter. When set, it
  calls `select_representative_sample_from_canonical_plan` instead of
  the raw-taxonomy rejection+sampling path, and STEP 05/05b print
  `N/A` (the canonical plan has nothing left to reject at this stage).
  `--taxonomy` continues to work completely unchanged when
  `--canonical-plan` is not given.
- New `[STEP 06b]` pre-flight printout — immediately after sample
  selection, BEFORE the fetch loop starts, every selected metric's
  identity key plus its menu1/menu2/menu3/leaf_level is printed, along
  with the total request count. Satisfies the explicit instruction:
  "Before making live requests, print the exact selected Phase B1
  request plan and request count." Verified by a test that makes the
  very first live request always raise, confirming the plan is already
  in stdout before any request is attempted.

### D. Tests

`tests/test_sampler_canonical_plan.py` (new) — adapter field mapping,
determinism, empty-plan handling, bounded sample size, collision/
non-collision coverage guarantee (including a case constructed so the
plain round-robin sampler would miss the collision without the
top-up), no-duplicate-identity guarantee, and an end-to-end check
against `canonical_plan.build_canonical_plan`'s real output shape.

`tests/test_klpga_response_schema_sample_script.py` (extended) —
`--canonical-plan` CLI wiring, mutual exclusivity with `--taxonomy`,
missing-file handling, the STEP 06b pre-flight printout (both its
before-any-request ordering and that it lists every selected identity
key), and that canonical-plan mode samples only from the given plan.

**570/570 tests passing** (was 550/550 before this round). No change
to Prediction #001, `predictions/`, model/inference/probability logic,
the production DB, the archive, or the public website. No live
requests made this round.

### E. Windows command to execute the bounded Phase B1 validation

Requires the real `KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json` already
on disk from Round 3's Phase A rerun (regenerate it first if it is not
already present):

```
python scripts\28_build_canonical_metric_request_plan.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json

python scripts\27_klpga_response_schema_sample.py ^
    --canonical-plan docs\discovery\KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json ^
    --season 2025
```

This selects a bounded (~12-20, plus at most 2 for guaranteed
collision/non-collision coverage) sample from the real 277-entry
canonical plan, prints the exact selected request plan and count
before firing any request, then fires exactly one live request per
sampled metric. It does NOT request all 277 canonical metrics, and it
STOPS after writing its output files — Phase B2 is not started by this
command.

---

## Round 5 — the real bounded B1 run exposed a genuine Phase A resolver bug: fixed from literal real-page HTML evidence

### A. What the real bounded B1 run found

10 live requests, HTTP_SUCCESS=10, PARSE_SUCCESS=4, PARSE_EMPTY=6.
Succeeded: `Tee::Tee01::010101`, `Approach::Approach01::020101`,
`Around::Around01::030101`, `Putt::Putt01::040101` (each 200+ rows).
Empty (HTTP 200, 33543 bytes, 0 rows, every time): `All::Approach01::020201`,
`All::Approach02::020301`, `All::Approach03::020401`,
`All::Approach04::020501`, `All::Putt08::010102`. This proved the
canonical plan itself — built entirely offline from Phase A's taxonomy
JSON — contained wrong identities: real menu3-level metrics were being
requested under the wrong menu1/menu2.

### B. Evidence trail (all real, literal, Windows-side)

Five escalating rounds of PowerShell extraction against the actual
cached Phase A source page (`https://klpga.co.kr/web/record/locationRecord`,
recovered from `data/raw_cache/http/` by its GET-with-no-params cache
signature) established, in order:

1. Early "evidence" pulled from `docs/discovery/raw_samples/*.html`
   turned out to be `loadLocationRecord` AJAX response bodies — a
   *different document* from the one Phase A's `inspect_menu_dom()`
   ever parses. That evidence was correctly discarded rather than used
   to justify a fix (see the mid-round correction in this project's
   own history — no code was changed on the strength of it).
2. Literal markup from the real source page then showed: the Approach
   family's menu2-level sub-tabs are flat siblings, each carrying its
   OWN `data-menu2` + `data-menu3` but NO own `data-menu1` — e.g.
   `<button data-menu2="Approach02" data-menu3="020201">그린 적중 시
   남은 거리</button>`.
3. A literal structural trace (own tag / nearest preceding
   `data-menu1` / nearest preceding `data-menu2` / nearest ancestor
   `<div id="...">`) of the `Putt08::010102` case showed the button is
   genuinely nested inside `<div id="Tee01">`, while the OLD resolver
   had independently borrowed `menu1="All"` from a distant top-nav
   button and `menu2="Putt08"` from an unrelated earlier tab — neither
   of which is any ancestor of that tag.

### C. Root cause (two defects, both proven against literal real HTML)

**DEFECT 1 — partial own identity discarded.** `inspect_menu_dom()`
Pass 1's `own_attrs` check required BOTH `data-menu1` AND `data-menu2`
present on the same tag before using EITHER. A tag with its own
reliable `data-menu2` (Approach02's own tab) but no own `data-menu1`
had that real value thrown away entirely, then re-derived from
scratch — producing the proven "menu2 off-by-one" bug: Approach02's
own request ended up labeled `menu2="Approach01"`, Approach03 got
`"Approach02"`, etc. (Pass 2, the menu2-level leaf pass, had the
identical defect — proven by the real `<div id="Sg">` evidence: `SG :
전체`/`SG : 티샷 to 그린`'s own tabs carry only `data-menu2`, no own
`data-menu1`, meaning Sg's real menu2-level metrics were being
silently skipped by Phase A entirely, not merely mis-tagged.)

**DEFECT 2 — missing components resolved by an unbounded,
independent, per-component document-order scan.** The `preceding_context`
tier (`_find_nearest_preceding_attr`) searched backward through the
ENTIRE flattened document for the nearest earlier tag carrying
`data-menu1`, and *independently* the nearest earlier tag carrying
`data-menu2` — with no requirement that either have any structural
relationship to the tag being resolved, or to each other. This is what
produced the synthetic `All::Putt08::010102` identity: `menu1="All"`
and `menu2="Putt08"` came from two different, unrelated, non-ancestor
tags, combined into a tuple that never existed anywhere in the real
DOM.

### D. The fix (`src/klpga/discovery/menu_taxonomy.py`)

- `_find_nearest_preceding_attr` (the unbounded scan) is **removed
  entirely** — no code path resolves menu1/menu2 from document-order
  position any more, in either Pass 1 or Pass 2.
- New `_find_ancestor_ids(tag)`: an ordered (nearest-to-farthest) list
  of the literal `id` attribute value on every genuine ANCESTOR of
  `tag` — grounded in the confirmed real container-nesting evidence
  (`<div id="Sg">` wrapping Sg's own tabs; `<div id="Tee01">` wrapping
  Tee01's own menu3-only detail buttons). Nothing about the `id`
  VALUES themselves — their text, digit suffixes, or naming pattern —
  is inspected; only genuine ancestor presence and nesting order.
- Both Pass 1 and Pass 2 now resolve identity component-by-component:
  an own attribute already on the tag is ALWAYS used directly and
  never discarded; a still-missing component is resolved first via a
  genuine ancestor's own `data-menu1`/`data-menu2` attribute
  (`_find_ancestor_with_attr`, unchanged), then via the ancestor `id`
  chain — nearest ancestor id fills menu2 if menu2 is still open,
  the next ancestor id further up fills menu1 if menu1 is still open.
  Whatever still can't be resolved falls to `"unknown"`, preserving
  whatever component WAS genuinely resolved rather than blanking both
  out (this project's "preserve every discovered thing" discipline) —
  and per `sampler.reject_malformed_leaves`, any leaf with a blank
  menu1 or menu2 is still never eligible for a live request regardless.
- This design is **safe-by-construction**: the bare family-level
  `<div id="Tee">`/`<div id="Approach">` containers (one level above
  the confirmed `<div id="Tee01">`/`<div id="Approach02">` subgroup
  containers) were inferred by direct structural analogy with the one
  bare family container independently confirmed (`<div id="Sg">`), not
  independently observed for every family. If that analogy is wrong
  for some family, the affected leaves simply fall to `"unknown"` —
  visible and auditable in the malformed-leaf report — rather than
  silently producing another wrong-but-confident identity like the bug
  being fixed. Under- resolving is the safe failure mode here;
  over-resolving (the old behavior) is not.
- `MenuLeaf.label_resolution_method` no longer has a `"preceding_context"`
  value — only `"own_attrs"`, `"ancestor_walk"` (now covering both the
  data-attribute and the container-id ancestor mechanisms), and
  `"unknown"`.

### E. What did NOT change

`_find_ancestor_with_attr` (genuine ancestor data-attribute walk),
`CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES`/`node_type`'s
`leaf_level == "menu2"` scoping (Round 3's fix), `canonical_plan.py`,
`sampler.py`, `response_parser.py`'s dynamic-header handling, and every
sanity-check threshold in `check_sanity_invariants` are all untouched.
Menu3 collision handling (`DomInspectionResult.collisions`, keyed by
bare menu3 code regardless of parent) is unaffected — collisions are
still never silently resolved.

### F. Tests

- Deleted `tests/fixtures/record_menu_preceding_context_sample.html`
  and `tests/test_preceding_context_resolution.py` — both were built
  on a hypothesis (a preceding-sibling-header DOM shape) that this
  round's literal real-page evidence directly disproved. Its own
  header comment always flagged it as "NOT a literal HTML capture."
- Added `tests/fixtures/record_menu_confirmed_container_structure_sample.html`
  — built directly from the literal real HTML pasted this round (top-
  level family nav buttons, `<div id="Sg">`, `<div id="Tee">`/
  `<div id="Tee01">`, `<div id="Approach">`/`<div id="Approach02">`,
  `<div id="Around">`, `<div id="Putt">`), with the not-independently-
  observed bare family containers flagged transparently in the
  fixture's own comment.
- Added `tests/test_container_id_resolution.py`: the Approach off-by-one
  fix (every Approach0N tab keeps its own menu2), the Tee01/010102 fix
  (resolves to `Tee::Tee01::010102`, explicit assertion that
  `("All","Putt08","010102")` can never appear), the two-level
  ancestor-id chain (a menu3-only button nested inside a subgroup
  detail div inside a family div), Sg's Pass 2 fix, "All" navigation
  exclusion still intact, and the safe-unknown-fallback behavior.
- Trimmed two now-structurally-impossible tests out of
  `tests/test_navigation_container_scope_fix.py` (their sibling-header
  premise no longer applies to how the resolver works); its
  canonical-plan-level test (a different, untouched layer) is
  unchanged.

**571/571 tests passing** (was 570 before this round — net effect of
removing ~15 obsolete tests and adding a larger, evidence-grounded
replacement suite). No live requests made this round. No change to
Prediction #001, `predictions/`, model/inference/probability logic,
the production DB, the archive, or the public website. Phase B2 was
not started.

### G. Windows commands — regenerate and rerun the bounded B1 validation

```
git pull

python scripts\26_discover_klpga_record_taxonomy.py ^
    --source-url "https://klpga.co.kr/web/record/locationRecord"

python scripts\28_build_canonical_metric_request_plan.py ^
    --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json

python scripts\27_klpga_response_schema_sample.py ^
    --canonical-plan docs\discovery\KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json ^
    --season 2025
```

Expected direction only, not a predicted count: `Approach::Approach02::020201`
(and 03/04/05) should now request as `Approach::ApproachNN::0N0N01`
rather than `All::ApproachN-1::...`; `Tee::Tee01::010102` should now
appear instead of `All::Putt08::010102`; Sg's `Total`/`TeeToGreen`
menu2-level leaves should now actually appear in the taxonomy (Pass 2
fix) where they may have been silently absent before. This command
STOPS after writing its bounded output — it does not request all 277
canonical metrics and does not start Phase B2.

---

## Round 6 — Round 4's ancestor-id fallback was too broad: fixed with a document-wide known-value filter + cross-reference registry

### A. What the fresh Round 4 taxonomy showed

A provenance-first rerun (confirming `fef2af7` was actually in the
checkout and forcing script 26/28 to regenerate from a fresh fetch,
rather than consuming stale artifacts) proved Round 4's menu2
off-by-one fix genuinely worked — every `ApproachNN` tab kept its own
`menu2`. But `menu1` recovery was now wrong in a NEW way:
`menu1="nav-scroll"` and `menu1="menu3"` appeared in the regenerated
taxonomy for `020501` and `010102`. Round 4's "next ancestor id fills
menu1" rule was accepting ANY `id`-bearing ancestor, including generic
layout infrastructure.

### B. The full real ancestor chain (literal, pasted directly)

A read-only PowerShell ancestor-chain walker (tag-stack tracker over
the actual cached `locationRecord` source page) printed the complete
chain for every occurrence of `020101`/`020201`/`020301`/`020401`/
`020501`/`010102`. The decisive finding:

```
020501 occurrence #1 (outer tab-row entry, own data-menu2="Approach05"):
  li -> ul -> div#nav-scroll.nav-scroll.scroll-button
     -> div#Approach -> div#menu2 -> section -> body -> html

020501 occurrence #2 (inner menu3-only detail button):
  li -> ul -> div.nav-scroll -> div#Approach05
     -> div#menu3 -> section -> body -> html

010102 (inner menu3-only detail button):
  li -> ul -> div.nav-scroll -> div#Tee01
     -> div#menu3 -> section -> body -> html
```

This proves the real page is a 3-pane layout: `id="menu2"` is a SINGLE
shared pane holding every family's own `<div id="Family">` tab-row
container; `id="menu3"` is a SEPARATE shared pane holding every
subgroup's own `<div id="FamilySubgroup">` detail-button container.
`<div id="Approach">` and `<div id="Approach05">` are SIBLINGS under
two different panes — never nested in each other. There is therefore
**no ancestor path at all** from a menu3-only detail button to its
family identity; Round 4's two-level "next ancestor id" assumption was
simply wrong for this shape.

### C. Root cause

Round 4's `_find_ancestor_ids` accepted ANY `id`-bearing ancestor, with
no way to distinguish a genuine semantic container (`id="Approach"`,
`id="Approach05"`) from a generic, reused layout wrapper
(`id="nav-scroll"`, `id="menu2"`, `id="menu3"`) — all four "look" the
same to a plain ancestor-id walk.

### D. New structural rule

**No hardcoded family names, no generic-id blacklist.** Instead: a
literal string only counts as a semantic menu identity if it ALSO
appears, somewhere else in the SAME document, as the real value of a
`data-menu1` or `data-menu2` attribute — confirmed directly: `"Approach"`
matches the top-nav button's own `data-menu2="Approach"`;
`"Approach05"` matches its own tab's own `data-menu2="Approach05"`;
`"nav-scroll"`/`"menu2"`/`"menu3"` never appear as such a value
anywhere. `_collect_known_menu_identity_values(all_tags)` builds this
set once per document; `_find_ancestor_ids` now filters against it.

### E. Duplicate-occurrence handling

Since `<div id="Approach">` and `<div id="Approach05">` are siblings,
not ancestor/descendant, a menu3-only detail button (e.g. inside
`<div id="Approach05">`) has genuinely no ancestor path to its family
at all. Resolving Stage 1 first (every tag that DOES carry its own
`data-menu2` — the outer tab-row entries, which DO have a real
ancestor path) builds `subgroup_menu1_registry["Approach05"] =
"Approach"` along the way; Stage 2 (the menu3-only detail buttons)
looks up that registry by whichever subgroup id it resolved via the
filtered ancestor-id chain — a real cross-reference to another tag's
own resolution, never a label, menu3 number, or hardcoded name. Both
of `020501`'s real duplicate occurrences (outer tab + inner detail
item) now resolve to the SAME true identity
(`Approach::Approach05::020501`), reported by the existing, unchanged
collision machinery rather than producing two different false
identities.

### F. Expected six identities

```
020101 -> Approach::Approach01::020101
020201 -> Approach::Approach02::020201
020301 -> Approach::Approach03::020301
020401 -> Approach::Approach04::020401
020501 -> Approach::Approach05::020501
010102 -> Tee::Tee01::010102
```

### G. Files changed

`src/klpga/discovery/menu_taxonomy.py` (new
`_collect_known_menu_identity_values`, `_find_ancestor_ids` gained a
`known_values` filter parameter, Pass 1 restructured into two stages
with `subgroup_menu1_registry`, Pass 2 reuses the shared
`_resolve_menu1_via_ancestor` helper); new
`tests/fixtures/record_menu_confirmed_pane_structure_sample.html` +
`tests/test_pane_structure_resolution.py` (13 tests, built directly
from this round's literal ancestor-chain evidence); the Round 4
fixture's header comment was corrected to flag that its nested-div
shape doesn't match the real page (kept anyway — the resolver still
handles genuine nesting correctly, it's just not what the real site
does).

**584/584 tests passing** (571 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. Phase B2 not started.

---

## Round 7 — Sg-family parser gap: a third dynamic-header pattern (`var menu="X"` + branch-keyed `data1..data5`)

### A. Context

The bounded 20-request B1 rerun against the Round 6-fixed canonical
plan came back 16 `PARSE_SUCCESS`, and — after a provenance-first
audit of the taxonomy/canonical-plan/B1 outputs — 4 non-success cases,
all traced to the Sg family specifically: `Sg::All` × 2 (a genuine
duplicate canonical-plan entry — same identity, different label,
untouched by this round) returning a legitimate empty response (no
matching branch in the site's own JS switch), and `Sg::Approach` /
`Sg::Around` both returning 223 real rows classified
`AMBIGUOUS`/`EMPTY_SCHEMA`. The resolver itself audited clean — every
one of the 281 canonical entries has a real, structurally valid
`menu1`; this was a downstream parser gap only.

### B. Root cause

The real saved `Sg::Around` response body (pasted directly by the user
from the actual raw-sample file) showed a THIRD, distinct client-side
templating pattern `response_parser.py` had never seen: a `var menu =
"<identity>";` declaration followed by an `if(menu == "X") { ... }
else if(menu == "Y") { ... }` chain, each branch assigning
`menuName`/`recordNote`/`order` and up to five `data1`.."data5"
value-column labels. Neither the existing `metadata` layer (a
JSON-object blob) nor `dynamic_header_vars` (`var record<N> =
"...";`) recognizes this shape — hence real rows classifying
`EMPTY_SCHEMA`. Both non-empty failures showed `missing_player_name:
223` (100% of rows) in their data-quality flags, but this round's
fix does not address that — no real `<td>`/`<tr>` row markup for an
Sg-family response was available to this session, only the `<script>`
header block, so the row/player-name extraction gap remains open
pending that evidence.

### C. The fix (`src/klpga/discovery/response_parser.py`)

New `_extract_menu_switch_metadata(html)`: finds `var menu =
"<value>";`, locates the ONE `if`/`else if(menu == "<value>")` block
matching that exact value (a brace-depth counter, `_find_matching_
brace_block`), and extracts `menuName`/`recordNote`/`order` plus the
`data1`.."data5" labels from ONLY that block — every other branch
describes a different Sg sub-metric and is never read. The Nth `dataN`
label maps positionally to the `(N-1)`th `record*` field, the same
correspondence principle the existing `table_header` layer already
uses. Wired into `_extract_column_semantics` as a new `menu_switch_
vars` tier (same priority rank as `dynamic_header_vars`) and into
`parse_record_response` (only consulted when the layer-1 JSON
metadata block wasn't found). Deliberately **never sets `metadata.
found = True`** — the per-column mapping isn't confirmed by real
row-level markup for this family, so it stays at the same honesty
tier as `dynamic_header_vars`, landing on `DISCOVERED_NOT_VALIDATED`,
never `CONFIRMED`. When `var menu` doesn't match any branch (the real
confirmed `Sg::All` case — no `else if(menu == "All")` exists in the
switch at all), the function returns not-found rather than fabricating
anything; combined with that response's real zero rows, it still
classifies `EMPTY`.

### D. Tests

New `tests/fixtures/loadLocationRecord_sg_menu_switch_sample.html` —
its `<script>` block is VERBATIM from the real saved response (the
`Total`/`TeeToGreen`/`Tee`/`Approach`/`Around` branches, all confirmed
complete; the real evidence's `Putt` branch was truncated mid-string
and is deliberately omitted rather than completed with invented text).
Its `<table>` row markup was not part of the real evidence — it reuses
this project's already-confirmed `data-playercode`/`data-name`/
`data-rank`/`data-record` convention as a flagged working assumption,
exactly as this module's own docstring already does for every other
pre-real-evidence fixture. New `tests/test_menu_switch_metadata.py`
(12 tests): branch-isolation (only the matching branch's labels are
ever read), the real no-match `Sg::All` case (never fabricated, stays
`EMPTY` with real zero rows), end-to-end `Sg::Around` now reaching
`DISCOVERED_NOT_VALIDATED` with correct `record`/`record1` labels, and
non-Sg fixtures (`020104`, the dynamic-header sample) proven completely
unaffected.

**596/596 tests passing** (584 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. Phase B2 not started.

## Round 8 — Windows-only CSV newline corruption (`\r\n` doubled to `\r\r\n` by `Path.write_text`)

### A. Context

After syncing the Windows checkout to the Round 7 fix (commit
`39bd812`) and rerunning both the targeted Round 7 tests and the full
suite there, exactly one failure remained:
`tests/test_build_canonical_metric_request_plan_script.py::
test_run_writes_malformed_leaf_report_csv`, asserting `55 == (1 +
27)` — the real Windows run produced 55 lines from
`KLPGA_MALFORMED_LEAF_REPORT.csv` where 28 (1 header + 27 malformed
rows) was expected. The same test, and the full 596-test suite, passed
cleanly in this project's Linux sandbox. That Linux/Windows split was
the first signal this was a platform-dependent bug, not a stale test
expectation or a resolver/parser regression.

### B. Root cause

`git log -- src/klpga/discovery/canonical_plan.py` confirmed the
module that builds this CSV (`to_malformed_leaf_report_csv`) has been
untouched since commit `4a63951`, well before the Round 4-7 taxonomy/
resolver work — ruling out a stale assertion or a resolver-driven
regression. The actual defect: `to_malformed_leaf_report_csv` uses
`csv.DictWriter` writing into an `io.StringIO()`, so its returned
string already contains `csv.writer`'s own `\r\n` row terminators,
untouched by `io.StringIO` (it performs no newline translation). Every
one of scripts 26/27/28's CSV writes then passed that string to
`Path.write_text(data, encoding="utf-8")` with the default
`newline=None`, which enables Python's universal-newline *write*
translation: every `\n` character in the string is rewritten to
`os.linesep`. On Windows, `os.linesep == "\r\n"`, so the `\n` already
sitting inside each pre-existing `\r\n` pair gets rewritten too,
turning every row terminator into `\r\r\n` on disk. On read-back
(`Path.read_text()`, universal-newline *read* mode), each `\r\r\n`
(3 bytes: CR, CR, LF) is interpreted as `\r` immediately followed by
`\r\n`, i.e. two line breaks — an extra blank line after every row.
28 real lines therefore read back as `28 + 27 = 55` (27 data rows each
gaining one extra blank line; the header/last-row boundary accounts
for the exact arithmetic). This is a genuine, pre-existing,
Windows-only production defect — not caused by, and not exposed by,
any of the Round 4-7 taxonomy/resolver changes; it was simply never
triggered by a Linux-only test run before a real Windows run existed.

### C. The fix

Added `newline=""` to every `Path.write_text(...)` call in the
scripts directory that writes CSV content — the standard,
`csv`-module-documented way to disable both write- and read-side
newline translation so a string already carrying its own row
terminators reaches disk (and is read back) unmodified. Six call
sites across three scripts, found via `grep -rn "write_text(" scripts/
*.py | grep -i "csv\|_csv"` and confirmed to be the only
`write_text` calls susceptible (JSON/Markdown/HTML/plain-text writes
never contain pre-embedded `\r\n` and are unaffected):

- `scripts/26_discover_klpga_record_taxonomy.py` — `KLPGA_RECORD_
  TAXONOMY_DISCOVERED.csv`
- `scripts/27_klpga_response_schema_sample.py` — `KLPGA_RESPONSE_
  SCHEMA_SAMPLES.csv`, `KLPGA_RAW_COUNT_METRICS.csv`,
  `KLPGA_RESPONSE_FAILURES.csv`, `KLPGA_PHASE_B1_REQUEST_LOG.csv`
- `scripts/28_build_canonical_metric_request_plan.py` —
  `KLPGA_MALFORMED_LEAF_REPORT.csv`

The existing test assertion (`len(lines) == 1 + 27`) was **not**
changed — it was always correct; only the production write path was
wrong. `canonical_plan.py` itself was not touched: the CSV-building
logic was correct, only the write-to-disk step corrupted its output.

### D. Tests

Since this sandbox is Linux and cannot reproduce the Windows-only
corruption directly, added a new regression test in
`tests/test_build_canonical_metric_request_plan_script.py`,
`test_malformed_leaf_report_csv_bytes_are_not_newline_translated`:
it runs the script exactly as the existing test does, then asserts
the report file's raw on-disk bytes (`Path.read_bytes()`) are
byte-identical to the string `to_malformed_leaf_report_csv` actually
returned, UTF-8 encoded — true only when zero newline translation
occurred on the write, on any OS. This directly exercises the
`newline=""` fix and would fail if it were ever reverted, regardless
of which platform runs the test.

**597/597 tests passing** (596 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. Phase B1 not rerun. Phase B2 not started, and remains
unauthorized.

## Round 9 — Sg-family player_name row-extraction fix (real row markup evidence)

### A. Context

Following Round 8's CSV fix and a Windows sync to `2454d78`, a fresh
bounded 20-request B1 rerun confirmed the Round 7 `menu_switch_vars`
header fix works end-to-end against a live response:
`HTTP_SUCCESS=20/20, PARSE_SUCCESS=18, PARSE_EMPTY=2,
PARSE_AMBIGUOUS_OR_FAILED=0`, and `Sg::Around` specifically reached
`parse_status=DISCOVERED_NOT_VALIDATED` with `schema_fingerprint=
SG_ROUNDS` and 223 real rows — the exact CLASS 1 defect Round 7 fixed.
That same rerun's `data_quality_flags` for the Sg-family entries,
read from `KLPGA_RESPONSE_SCHEMA_SAMPLES.json`, showed
`player_row_count=231, missing_player_code=0, missing_player_name=
231` — the row-level gap Round 7 had explicitly flagged as open and
deferred (real `<tbody>`/`<tr>` row markup for the Sg family had never
been captured).

### B. Root cause

The user extracted and pasted the first real `<tr>` elements from the
actual saved response (`docs\discovery\raw_samples\Sg__Around__2025
.html`) via a targeted PowerShell regex. This proved the Sg family's
real rows are NOT the `<tr data-playercode="..." data-name="...">`
shape this project had been assuming (proven correct only for the
sibling `roundLeaderboard` endpoint and for other, non-Sg,
`loadLocationRecord` fixtures) — there is no name/code attribute on
the `<tr>` at all. The real shape is semantic table markup: a
`<td class="td-like">` holding a favorite-toggle `<input
_favoritPlayerCode="9134">`, a rank `<td>`, a country-flag `<td>`, and
critically a `<td class="text-start player_name"><a href="/web/
profile/mainRecord?playerCode=9134">Name</a></td>` cell. `player_code`
was already being found (`missing_player_code=0`) purely by luck: the
existing `_extract_player_code_from_href` fallback already searches
every `<a>` in the row for a `playerCode=` query parameter, and that
anchor happens to live inside this same cell. Nothing in
`_extract_rows` read a name from anywhere except a `data-name`/
`data-playername` attribute, so `player_name` came back `None` for
every one of the 231 rows.

### C. The fix (`src/klpga/discovery/response_parser.py`)

New `_extract_player_name_from_cell(tr)`: finds the row's
`class="player_name"` cell (matches `class="text-start player_name"`
regardless of its other classes), reads the text of its nested `<a>`
if present, else the cell's own text. Wired into `_extract_rows` as a
fallback used ONLY when no `data-name`/`data-playername` attribute is
present, so the already-working data-attribute convention (confirmed
for other real evidence, e.g. `loadLocationRecord_approach_020104_
sample.html`) is unaffected and still takes precedence. Purely
additive — no existing extraction path was removed or reordered.

**Still open, not addressed this round:** whether the `record`/
`record1`... VALUE cells (the actual SG numeric stats, as opposed to
player identity) are being extracted correctly for this same real row
shape is unconfirmed. The existing `values[field_name] = _attr(tr,
f"data-{field_name}")` reads attributes directly on the `<tr>`, and
this round's real evidence shows the `<tr>` carries none — so those
values may also currently be silently `None` for the Sg family. This
was NOT investigated or fixed this round (out of the explicitly
requested scope: player-name extraction only) and is not caught by
any current `DataQualityFlags` check (a `None` value is skipped, not
counted as `blank_values`). Recommend checking the full
`data_quality_flags` object — and the actual `record`/`record1`...
values, not just their presence/absence — for the Sg entries in the
next rerun before treating this data as analytics-ready.

### D. Tests

Updated `tests/fixtures/loadLocationRecord_sg_menu_switch_sample.html`
(the Round 7 fixture) with the real row shape — header row and player
identity cells verbatim from this round's pasted evidence; the exact
`<a href=...>` query string and visible name text were cut off in the
capture, so they reuse the separately-already-confirmed `/web/profile/
mainRecord?playerCode=<code>` href convention with the real
`_favoritPlayerCode` values (9134, 8770) seen in evidence — flagged
in the fixture's own comment as not independently confirmed for that
specific span. Updated `tests/test_menu_switch_metadata.py`'s row
assertions to match (player_code now resolved via href fallback,
`values["record"]` correctly `None` since no such attribute exists on
this real shape). Added three new unit tests to `tests/
test_record_response_parser.py`: name resolved from `td.player_name >
a` when no data-attribute exists, data-attribute still takes
precedence when both are present, and cell-text fallback when no `<a>`
is nested.

**600/600 tests passing** (597 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. Phase B2 not started, and remains unauthorized.

### E. Live validation found a second identity-extraction gap: `missing_player_code=9/232`

A targeted live rerun against exactly `Sg::Approach`/`Sg::Around`
(after syncing the fix above to `4de11d5`) confirmed
`missing_player_name=0/232` for both — the Round 9 fix above works
against a real response, not just fixtures. But it also surfaced a
NEW real gap: `missing_player_code=9/232`, `data_quality_any_
flagged=true`, even though `missing_player_name=0`.

**Root cause**: a PowerShell diagnostic scan (`-notmatch 'playerCode='`)
appeared to contradict this — only 1 of 233 real `<tr>` elements (the
header) seemed to lack a `playerCode=` reference. That diagnostic was
misleading: PowerShell's `-match`/`-notmatch` are case-insensitive by
default, so it also matched the checkbox's `_favoritPlayerCode="..."`
attribute (present on every row) — a completely different thing from
the `<a href=".../mainRecord?playerCode=...">` the Python parser's
`_extract_player_code_from_href` actually requires. The real cause:
9 of 232 rows have a `td.player_name` cell with no nested `<a>` at
all (consistent with `missing_player_name=0`, since the Round 9 name
fix falls back to the cell's plain text either way) — so there is
nothing for the href-regex to match, and (as established this same
round) no `data-playercode`-style attribute exists on this real row
shape either. The player's actual code is not missing from the
source; nothing was reading the one place it's still present for
those rows: the checkbox's `_favoritPlayerCode` attribute.

**The fix**: `_extract_player_code_from_favorite_checkbox(tr)`, a
third, lowest-precedence `player_code` fallback in `_extract_rows` —
reads `_favoritPlayerCode` off the row's nested favorite-toggle
`<input>` (matched case-insensitively via the existing `_attr()`
helper, since bs4's lxml-backed HTML parser lowercases attribute
names). Used ONLY when both the existing `data-playercode`-style
attribute and href-based lookups find nothing, so the 223/232 rows
already resolved via `href_query_param` are unaffected. New
`PlayerRecordRow.player_code_source` value: `"favorite_checkbox_
attribute"`.

**Tests**: two new cases in `tests/test_record_response_parser.py` —
the exact real shape (no `<a>`, checkbox present) now resolves
`player_code` from the checkbox, and a precedence test confirming the
existing href-derived code still wins when both sources are present
on the same row (no regression to the already-working 223/232).

**602/602 tests passing** (600 before this fix). No live requests
made by this fix itself (the triggering evidence came from a rerun
the user already ran and pasted). No change to Prediction #001,
`predictions/`, model/inference/probability logic, the production DB,
the archive, or the public website. Phase B2 not started, and remains
unauthorized.

## Round 10 — B2_GATE = GO; Phase B2 full-sweep tooling built (NOT executed)

### A. B2_GATE decision

A targeted live rerun against exactly `Sg::Approach`/`Sg::Around`
(post Round 9-E fix) confirmed: `player_row_count=232`,
`missing_player_code=0`, `missing_player_name=0`,
`duplicate_player_rows=0`, `blank_values=0`,
`data_quality_any_flagged=false` for both, plus
`HTTP_SUCCESS=2/2, HTTP_FAILURE=0, PARSE_SUCCESS=2/2, PARSE_EMPTY=0,
PARSE_AMBIGUOUS_OR_FAILED=0`, and cross-metric playerCode identity
consistency CONFIRMED. Combined with the earlier bounded 20-request
B1 run (`HTTP_SUCCESS=20/20, PARSE_AMBIGUOUS_OR_FAILED=0`, its 2
`PARSE_EMPTY` cases independently confirmed legitimate — real
zero-row `Sg::All` duplicate canonical entries, no matching branch,
correctly not fabricated), every evidence-backed blocker raised
across Rounds 7–9 is closed. **B2_GATE = GO.**

### B. Phase B2 tooling — built this round, NOT executed

No script in this repo could previously run a full, uncapped sweep:
`scripts/27_klpga_response_schema_sample.py` is deliberately
sample-only — `select_representative_sample`'s `per_family_cap`
(default 4) caps how many leaves are picked *per family* regardless
of `--sample-size`/`--max-requests`, by design (a REPRESENTATIVE
sample tool, not a full-sweep tool). This round adds
`scripts/29_execute_phase_b2_full_sweep.py`, the dedicated Phase B2
runner, still requiring separate, explicit authorization to actually
fire (this round authorizes the GATE and the tooling build, NOT a
live execution).

**Reuse, not duplication**: `fetch_and_analyze` (plus its
`_request_form`/`_sanitize_identity_key_for_filename` helpers) was
extracted verbatim from scripts/27 into a new shared module,
`klpga.discovery.record_fetch` — scripts/27 now imports and thinly
wraps the same functions (its own `_log`, which also updates
`_LAST_MARKER` for its Ctrl+C diagnostics, is passed in as the `log`
parameter) so Phase B1 and B2 can never diverge in how a single
metric is fetched, parsed, and logged. Script 27's own 35 tests were
re-run unchanged after this extraction and all still pass — the
refactor is behavior-preserving. `klpga.discovery.sampler` gained one
new function, `select_full_canonical_plan`, returning EVERY canonical
entry (not a sample) in deterministic `(menu1, menu2, menu3)` order,
with no `per_family_cap` and no rejection pass (the canonical plan is
already malformed-free/navigation-free by construction).

**Explicit checkpoint, independent of the HTTP cache**: new module
`klpga.discovery.b2_checkpoint` — a JSON file keyed by `identity_key`,
each entry recording `request_params`, `season`, `http_result`,
`parse_status`, `schema_fingerprint`, `player_row_count`,
`completion_status` (`SUCCESS` | `HTTP_FAILURE`), `timestamp`, and
(for `SUCCESS` entries) the full `sample_record`/`log_entry` payloads
so the human-facing output artifacts can be fully regenerated from
the checkpoint alone across multiple runs. Writes are ATOMIC
(temp file in the same directory + `os.replace`, which is atomic on
both POSIX and Windows) — a crash mid-write leaves the previous
checkpoint completely intact, never partially overwritten.
`PoliteHttpClient`'s own disk cache (`data/raw_cache/http/`, the SAME
directory Phase B1 already uses) remains a second, lower-level safety
net underneath this checkpoint, not a replacement for it.

**Safety behavior, matching the requested design exactly**:
- Request count is read from the canonical plan file at run time
  (`len(canonical_requestable_metrics)`), never hardcoded.
- `--season` required, never guessed; mandatory `--dry-run` prints
  the full plan and count with zero HTTP requests and zero files
  written; `--max-requests` caps live requests for a single
  invocation without changing the full count.
- Rate limiting is `PoliteHttpClient`'s existing, unmodified 1.5s
  minimum interval + jitter and 4-attempt retry/backoff.
- A 401/403/429 (`RateLimitBlockedError`) halts the ENTIRE sweep
  immediately — never retried, never bypassed — identical to Phase
  B1's existing behavior.
- A new consecutive-HTTP-failure circuit breaker (default 5) halts
  the sweep as an additional safety net a 20-request B1 sample never
  needed; it resets to 0 on the next successful request (in-memory
  only — a fresh process invocation starts it back at 0 regardless of
  checkpoint state, since a restart is itself already a strong enough
  signal to re-attempt).
- An individual metric's malformed/unexpected parse result
  (AMBIGUOUS/FAILED) does NOT halt the sweep — recorded and the run
  continues, exactly like Phase B1.
- Every output path lives under `--out-dir` (default
  `docs/discovery/phase_b2/`), never Phase B1's `docs/discovery/`
  directory directly — a B2 run structurally cannot overwrite a B1
  artifact.

Deliberately narrower than Phase B1's full report set: no schema-
report/raw-field-inventory/player-identity markdown output this
round — not required for the B2_GATE scope, and can be added later
against the accumulated checkpoint without any further live requests.

### C. Tests

`tests/test_sampler_canonical_plan.py` — 3 new tests for
`select_full_canonical_plan` (returns every entry despite exceeding
the B1 `per_family_cap`, deterministic order regardless of input
order, no navigation-rejection pass). `tests/test_b2_checkpoint.py`
(new, 7 tests) — round-trip, missing-file returns empty, atomic write
leaves no leftover temp file, a simulated mid-write crash leaves the
PREVIOUS checkpoint byte-for-byte intact, a genuinely corrupt file
raises rather than silently discarding progress.
`tests/test_execute_phase_b2_full_sweep_script.py` (new, 11 tests) —
dry-run makes zero requests, the full sweep is not subject to the B1
family cap, deterministic request ordering, `--max-requests`, already-
`SUCCESS` identities skipped on resume (a `NeverCalledClient` proves
zero requests), an `HTTP_FAILURE` identity remains visible and is the
ONLY one retried on resume, a 401/403/429 halts immediately with no
further attempts, 5 consecutive HTTP failures trip the circuit
breaker (stopping at exactly 5, not all 8 leaves), a scripted
fail/fail/success/fail/fail sequence proves the counter resets on
success (all 5 leaves attempted, breaker never trips — a non-resetting
implementation would have tripped early), a real B1 artifact file is
byte-for-byte unchanged (and its mtime unchanged) after a B2 run
against a sibling `phase_b2/` directory, and the output samples JSON
reflects the FULL cumulative checkpoint across two separate runs, not
just the latest one.

**623/623 tests passing** (602 before this round). No live requests
made — this round is tooling only. No change to Prediction #001,
`predictions/`, model/inference/probability logic, the production DB,
the archive, or the public website. **Phase B2 has NOT been
executed** — only its dry-run has been exercised in this sandbox
(against a synthetic canonical plan); a real invocation against the
live site remains a separate, explicit authorization the user has not
yet given.

## Round 10 (continued) — B2 Stage 1 STOP: canonical plan identity_key uniqueness

### A. Context

Before firing B2 Stage 1's authorized 10-request batch, the user
independently verified the real canonical plan: **281 total canonical
entries, 248 unique `identity_key` values, 30 duplicate groups, 33
excess entries.** Per explicit instruction, B2 Stage 1 was NOT run;
this became the single blocker to investigate first, offline, using
only the existing plan/taxonomy artifacts and code.

### B. Root cause (confirmed by reading `canonical_plan.py` directly — no live data needed)

`build_canonical_plan`'s exact-duplicate dedup key is
`(identity_tuple, label)` — **not** `identity_tuple` alone. Two DOM
leaves sharing the exact same `(menu1, menu2, menu3)` but carrying
DIFFERENT labels are therefore never deduplicated: both survive into
`canonical_requestable_metrics`, both carrying the SAME `identity_key`
string (derived from `identity_tuple` only — `identity_key` never
incorporates `label`). This is a genuinely different mechanism from
the pre-existing `menu3_collision_count`, which only tracks BARE menu3
codes shared across DIFFERENT `menu1`/`menu2` paths — it is blind to
menu2-level collisions entirely (no menu3 to collide on) and says
nothing about two entries sharing the exact same full identity.
**No counter anywhere in this codebase tracked this before this
round** — a real, previously-invisible reporting gap, confirmed
structurally rather than guessed.

One thing provable from the code alone, without seeing the real data:
**Category A (same `identity_key` AND same `label`) is structurally
impossible.** If two leaves shared identity AND label, they would
already have been collapsed by the exact-duplicate dedup step before
ever reaching the output plan. Every one of the real 30 groups is
therefore guaranteed to be Category B (different labels) by
construction — never A. Whether any of those 30 are actually
Category C (two genuinely distinct real-world metrics that Phase A's
DOM resolver wrongly mapped to the same `menu1`/`menu2`/`menu3`,
versus a genuine site-side ambiguity where two tab labels really do
resolve to the same request) cannot be determined from the plan
alone — it requires reviewing the actual label pairs, which the new
diagnostic report below exists to surface.

### C. The fix — reporting/diagnosis only this round, NOT a merge

Per explicit instruction ("prefer fixing the canonical-plan
construction/root cause rather than silently deduplicating in the B2
runner"), and because forcibly merging or dropping either side of a
genuine collision would violate this project's long-standing "never
silently resolve a collision" principle, this round adds DETECTION
and REPORTING at the canonical-plan layer — it does NOT change which
entries `build_canonical_plan` includes, and does NOT touch
`select_full_canonical_plan`/`scripts/29`'s B2 sampler.

`CanonicalPlanCounts` gains two new, purely additive fields:
`unique_identity_key_count` and `duplicate_identity_key_group_count`
— computed over BOTH menu2- and menu3-level canonical entries
combined (generalizing the narrower, menu3-only `menu3_collision_
count`). New `build_identity_key_collision_report(taxonomy)`: one row
per canonical entry that shares its `identity_key` with another,
grouped and sorted for direct comparison, including `menu1`/`menu2`/
`menu3`/`leaf_level`/`label`/`node_type`/`evidence_source`, `group_
size`, and — where retained on the original raw taxonomy leaf —
`label_resolution_method`/`is_menu3_collision` provenance. New
`to_identity_key_collision_report_csv`. `scripts/28` now prints both
new counts and, whenever `duplicate_identity_key_group_count > 0`,
writes `KLPGA_IDENTITY_KEY_COLLISION_REPORT.csv` alongside its
existing output.

### D. Open design question — NOT resolved this round

The user's requested invariant (`canonical_requestable_metric_count
== len(canonical_requestable_metrics) == unique_identity_key_count`)
is fundamentally in tension with the "never merge a genuine collision"
principle as currently implemented: satisfying it exactly would
require either (a) restructuring `canonical_requestable_metrics` to
one row per `identity_key` with multiple labels attached as an
explicit `label_candidates`-style field (preserves all evidence,
changes the plan's schema), or (b) treating `unique_identity_key_
count` — not `canonical_requestable_metric_count` — as the number
that actually governs B2 sizing/execution (leaves the audit-oriented
plan list untouched, but means a live request is fired once per
`identity_key`, with the case of a genuine Category-B collision
needing its own resolution for how the resulting single response gets
attributed back to two candidate labels). This round intentionally
did NOT choose between these — it is a design decision with real
data-provenance trade-offs, not a "smallest evidence-backed bug fix,"
and deserves the user's explicit direction once they have reviewed
the real 30 groups via the new collision report.

Also flagged, not yet touched: `scripts/29`'s B2 checkpoint
(`klpga.discovery.b2_checkpoint`) is keyed by `identity_key`. If a
Category-B collision identity is fired in a live B2 run, the
checkpoint will record only ONE `sample_record` for it — correct from
a "how many live HTTP requests were made" standpoint (firing the same
`menu1`/`menu2`/`menu3` twice would be a wasted duplicate request,
since the label is never part of the actual HTTP form), but it means
the checkpoint alone does not preserve which of the colliding
canonical-plan labels the one recorded response should be attributed
to. Not a blocker for counting/bounding live requests correctly, but
worth resolving before treating B2's output as fully evidence-
complete for a colliding identity.

### E. Tests

Seven new tests in `tests/test_canonical_plan.py`: the exact
mechanism (same identity, different label → not deduplicated, shares
one `identity_key`, `duplicate_identity_key_group_count == 1`); proof
that same-identity/same-label is structurally unreachable by this
count (collapsed by exact-duplicate dedup first); a menu2-level
collision (no menu3 at all) correctly detected by the new count
despite being invisible to `menu3_collision_count`; confirmation that
the shared fixture's pre-existing CROSS-FAMILY bare-menu3-code
collision does NOT register as an identity_key duplicate (the two
mechanisms are genuinely independent); `build_identity_key_collision_
report`'s empty-case, full-field/grouping correctness (including
provenance pass-through from the original raw leaf), and its CSV
writer's required columns.

**630/630 tests passing** (623 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. B2 Stage 1 remains STOPped pending the user's review of the
real collision report and a decision on the open design question in
section D.

### F. Zero-HTTP verification command

```
python scripts\28_build_canonical_metric_request_plan.py --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json
```

This is the exact existing script 28 command (unchanged usage) —
its output now additionally prints `unique identity_key count` and
`duplicate identity_key groups`, and writes
`KLPGA_IDENTITY_KEY_COLLISION_REPORT.csv` when any exist, alongside
the already-existing `total DOM-discovered nodes`, `malformed leaves`,
and `CANONICAL requestable metric count` lines.

## Round 10 (continued) — canonical metric identity vs HTTP request identity

### A. Confirmed architectural finding

The user checked already-saved raw evidence (no new HTTP requests)
for representative collision groups against `parse_record_response`'s
own `column_semantics`. Result: for `Around::Around04::030306`,
`Tee::Tee01::010101`, and `Putt::Putt01::040101`, the SAME shared
response genuinely contains a SEPARATE, distinctly-labeled value
column matching EACH of that identity's multiple canonical taxonomy
labels (e.g. `Around::Around04::030306`'s one response carries
distinct columns for "평균 남은 거리", "전체 남은 거리", and
"스크램블링수"). This directly confirms the hypothesis from this
round's earlier analytical pass: a single `loadLocationRecord`
response can legitimately serve MULTIPLE distinct canonical metrics
at once — this is a real, intentional site behavior, not a Phase A
resolver bug, for at least these representative cases.

This also confirms `record_fetch.request_form()`'s parameter set
(`{season, menu1, menu2, menu3-if-present}`) — already shown last
round to equal `identity_key` — really is what determines "one HTTP
request" independent of which/how-many canonical metric labels are
attached to it. "Canonical metric identity" (one row per DOM-
discovered label) and "HTTP request identity" (one row per distinct
live request) are therefore genuinely different concepts that happen
to share the same underlying `(menu1, menu2, menu3)` tuple.

### B. Tooling — offline collision-group audit, still zero live requests

New module `klpga.discovery.identity_key_audit` and
`scripts/31_audit_identity_key_collisions.py`: classifies EVERY
colliding `identity_key` group using ONLY already-saved raw responses
under `--raw-samples-dir` (the same directory/naming convention
scripts/27 and scripts/29 already use) — never fires a live request.
New `derive_request_identity_key(entry)`: computed independently from
`identity_key` (same value today, by design — both derive from
`menu1`/`menu2`/`menu3` only) so "canonical metric identity" and
"HTTP request identity" are two distinct concepts in the code, not
just in this document.

Per-group classification, in priority order:
1. **`A_EXACT_DUPLICATE_DOM_REPRESENTATION`** — two or more labels in
   the group normalize (whitespace-collapsed, case-folded) to
   IDENTICAL text despite not being byte-identical. Checked before
   any raw-response lookup — a pure taxonomy-label comparison. (Byte-
   identical same-label duplicates were already proven structurally
   impossible to reach a collision group at all, last round.)
2. **`UNRESOLVED_INSUFFICIENT_EVIDENCE`** — no saved raw response
   exists for this identity. Never guessed; excluded from the gate.
3. **`EMPTY_SHARED_RESPONSE`** — a saved response exists but has zero
   rows and no labeled columns (the confirmed `Sg::All` shape — no
   data exists for ANY label in that group, so "which metric does
   this belong to" doesn't apply).
4. **`C_MULTI_METRIC_ONE_REQUEST_CONFIRMED`** — every label in the
   group matches a distinct response column label. Direct evidence.
5. **`D_UNRESOLVED_REQUEST_IDENTITY_COLLISION`** — response is
   non-empty but NONE of the group's labels match any response
   column — the strongest signal available without a new request that
   this may be a genuine request-identity-model gap.
6. **`PARTIAL_MATCH_NEEDS_REVIEW`** — some (not all, not none) labels
   matched. Deliberately NOT auto-assigned to B or D — a real
   container/parent-label case and a genuinely missing metric look
   identical from label-matching alone; left for human review of the
   specific unmatched label(s).

The script prints `canonical taxonomy entry count`, `unique
request_identity_key count`, `duplicate identity_key groups`,
per-category counts, and a full per-group `request_identity_key ->
labels` mapping with matched/unmatched detail. Gate rule: if zero
groups land in `D_UNRESOLVED`/`PARTIAL_MATCH_NEEDS_REVIEW`/
`UNRESOLVED_INSUFFICIENT_EVIDENCE`, it declares `B2_REQUEST_COUNT =
<the canonical plan's unique_identity_key_count>` and exits 0 —
otherwise it lists exactly which groups remain unresolved and exits
non-zero. It does NOT authorize or execute Phase B2 either way, and
does NOT modify `scripts/29`'s B2 runner.

### C. Proposed minimum architectural fix — NOT yet implemented

Contingent on the real audit (run by the user against all 30 groups)
coming back clean: preserve all 281 canonical taxonomy entries exactly
as they are today (no merging, no deletion — the taxonomy/label
bookkeeping layer is untouched). In `scripts/29`'s B2 runner, group
`canonical_requestable_metrics` by `request_identity_key` before
firing anything; fire each DISTINCT `request_identity_key` exactly
once; attach the one resulting parsed response (and its own
`column_semantics`) to EVERY canonical metric entry that maps to that
`request_identity_key`, rather than firing (and checkpointing) once
per canonical entry. This directly changes `select_full_canonical_
plan`'s consumer in `scripts/29` and `b2_checkpoint`'s per-identity
provenance (today it silently collapses a colliding identity to one
`sample_record` with no record of which labels it serves — this fix
makes that mapping explicit instead of implicit/lost). Not
implemented this round — the user's gate rule ("if D=0 and all 281
canonical entries map deterministically onto the 248 unique request
identities") has not yet been confirmed against the real 30 groups.

### D. Tests

10 new tests in `tests/test_identity_key_audit.py`: `derive_request_
identity_key` for both leaf levels, non-colliding identities excluded
from the audit entirely, near-duplicate-label detection without
needing a raw sample, insufficient-evidence when no sample exists,
the confirmed `Sg::All` empty-response shape, the confirmed
`Around::Around04::030306` all-labels-matched shape, a no-labels-
matched (`D`) case, a some-labels-matched (`PARTIAL_MATCH`) case, and
independent classification of two separate collision groups in the
same taxonomy. 5 new tests in `tests/test_audit_identity_key_
collisions_script.py`: gate clean/not-clean end-to-end, the printed
`B2_REQUEST_COUNT` value, missing-taxonomy-file handling, and a full
CLI round-trip.

**645/645 tests passing** (630 before this round). No live requests
made — every classification in this round's tests and tooling reads
only already-saved/synthetic local files. No change to Prediction
#001, `predictions/`, model/inference/probability logic, the
production DB, the archive, or the public website. `scripts/29`'s B2
runner is untouched. Phase B2 has NOT been executed.

### E. Zero-HTTP verification command

```
python scripts\31_audit_identity_key_collisions.py --taxonomy docs\discovery\KLPGA_RECORD_TAXONOMY_DISCOVERED.json --season 2025
```

Reads only the already-produced taxonomy and any raw samples already
saved under `docs\discovery\raw_samples\`. Reports the full A/EMPTY/
C/D/PARTIAL/insufficient-evidence breakdown across all 30 real
groups, and declares `B2_REQUEST_COUNT` only if every group resolves
cleanly.

## Round 10 (continued) — fixed a false-negative in the matcher itself

### A. Root cause of the matcher's own false negative

The audit correctly ran with zero live requests, but its very first
real result was wrong: `Around::Around04::030306`, `Tee::Tee01::010101`,
and `Putt::Putt01::040101` — all three already confirmed by the user's
manual check to be genuine shared multi-column responses — classified
as `D_UNRESOLVED` instead of `C`/`B`. Traced (using the exact label
text the user pasted, no new evidence needed) to the matcher requiring
FULL-STRING equality after only whitespace-collapse/casefold
normalization:
- Response column labels carry a trailing `(yds)`/`(%)` unit
  annotation the taxonomy labels never do (`평균 티샷 거리` vs.
  `평균 티샷 거리(yds)`) — breaks exact equality even though it's the
  same real quantity.
- Some taxonomy labels are short, generic family names (`티샷`,
  `퍼팅`) that never equal any single column's full text, but ARE a
  substring of every column in their family — a container/parent
  label, not something exact-matching can ever resolve.
- One label genuinely has no textual relationship to any column at
  all (`Par4,5 티샷 비율` vs. the response's `Par4,5 티샷 횟수` —
  differ in their final word, rate vs. count) — this one is NOT a
  matcher bug; text comparison alone cannot prove whether it's a
  derived metric or a real gap, and the fix must not pretend it can.

### B. The fix (`klpga.discovery.identity_key_audit`)

`_normalize_label` now also strips a trailing `(...)` annotation
(`_TRAILING_PARENTHETICAL`) before comparing — directly justified by
the observed unit-suffix pattern, not a guess. Per-label matching is
now tiered instead of one exact-equality check:
1. **exact** (post-normalization) — unchanged, strongest evidence.
2. **substring** — bidirectional containment, counted as a confirmed
   match ONLY when it hits exactly one response column AND the
   shorter string is ≥ `_MIN_SUBSTRING_MATCH_LENGTH` (3 characters —
   picked because it's exactly the length of the real `성공률` match
   and one character above the real `티샷`/`퍼팅` non-matches, so it's
   derived from evidence, not arbitrary).
3. **container-candidate** — a substring relationship that's either
   ambiguous (hits 2+ columns) or below the length threshold — the
   generic/parent-label signal.
4. **none** — no relationship at all — left genuinely unresolved.

New group category `B_CONTAINER_CHILD`: at least one label confirmed-
matched (exact/substring) and every other label is a container-
candidate — nothing left unmatched. `PARTIAL_MATCH_NEEDS_REVIEW` is
now reserved for groups with a genuinely unmatched label alongside at
least one resolved one (exactly the real `Tee::Tee01::010101` case).
`D_UNRESOLVED` now only fires when NOTHING in the group — not even a
container-candidate relationship — relates to the response at all.

Re-running the fix against the real pasted evidence:
`Putt::Putt01::040101` → `B_CONTAINER_CHILD` (`1퍼트 성공률` matched,
`퍼팅` correctly identified as the container label) — fully resolved.
`Tee::Tee01::010101` → `PARTIAL_MATCH_NEEDS_REVIEW` (`평균 티샷 거리`
matched, `티샷` correctly identified as container, `Par4,5 티샷 비율`
correctly left unresolved rather than silently matched) — honestly
flags the one label the matcher genuinely cannot resolve from text
alone, instead of either false-negative-D'ing the whole group or
false-positive-C'ing it.

### C. Tests

3 new tests in `tests/test_identity_key_audit.py`, pinned against the
EXACT real label text pasted by the user for both groups (not
synthetic approximations): the `Tee::Tee01::010101` partial-match
case with its one genuinely-unresolved label, the
`Putt::Putt01::040101` fully-resolved container-child case, and a
minimal trailing-unit-annotation-only case confirming plain exact
matches still work post-normalization. All 10 pre-existing tests in
that file continue to pass unchanged, confirming the fix didn't
regress the earlier synthetic (empty-response, no-evidence, near-
duplicate-label, fully-unrelated) cases.

**648/648 tests passing** (645 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. `scripts/29`'s B2 runner untouched. Phase B2 not executed.

### D. Next step — rerun against the real 30 groups

The real breakdown you asked for (resolved from existing evidence /
unresolved because matching logic was insufficient / unresolved
because evidence is genuinely absent) can only be produced by rerunning
the actual tool against your real taxonomy and raw_samples — I have
neither. `C_MULTI_METRIC_ONE_REQUEST_CONFIRMED` + `B_CONTAINER_CHILD`
+ `EMPTY_SHARED_RESPONSE` counts = "resolved from existing evidence."
`PARTIAL_MATCH_NEEDS_REVIEW` + `D_UNRESOLVED` = "unresolved because
matching logic is insufficient" (or the labels are genuinely
different metrics — string comparison can flag this but not decide
it). `UNRESOLVED_INSUFFICIENT_EVIDENCE` = "raw/cache evidence
genuinely absent" — the ONLY category that could justify a bounded,
separately-authorized additional live request, per instruction. Not
executing B2.

## Round 10 (continued) — native diagnostic output in the audit script

The matcher fix took the real audit from 29 to 22 unresolved groups
(7 `PARTIAL_MATCH_NEEDS_REVIEW`, 1 `D_UNRESOLVED`, 14 `INSUFFICIENT_
EVIDENCE`). A PowerShell attempt to extract just those 8
evidence-backed groups from the script's existing free-form log lines
returned no matches, so rather than iterate on ad-hoc text extraction
against output not designed for it, `scripts/31_audit_identity_key_
collisions.py` now prints the diagnostic directly, in a fixed,
parseable structure, built entirely from evidence the audit already
loaded — still zero live requests.

**`klpga.discovery.identity_key_audit` changes**: `_classify_label_
against_response` now returns `(tier, matched_normalized_response_
label)` instead of just the tier, so a confirmed match can be traced
back to the SPECIFIC response column it resolved against, not merely
"matched: true". New `LabelMatchDetail` (`taxonomy_label`, `response_
column` — the original, non-normalized text — `method`: `"exact"` or
`"substring"`) and a `GroupAudit.match_details` list built from it.
`GroupAudit.raw_sample_path` is now populated for
`UNRESOLVED_INSUFFICIENT_EVIDENCE` too — the EXPECTED (not-yet-
existing) path — so the missing-evidence section can print it
directly without re-deriving it.

**`scripts/31` changes**: after the existing free-form per-group log,
three new sections:
- `=== UNRESOLVED_COLLISION_DIAGNOSTIC ===` — one block per
  `PARTIAL_MATCH_NEEDS_REVIEW`/`D_UNRESOLVED` group, in exactly the
  requested field order (`identity_key`, `taxonomy_labels`,
  `response_columns`, `confirmed_matches` as `label -> column
  [method]`, `container_candidates`, `unmatched_taxonomy_labels`,
  `raw_sample_path`).
- `=== MISSING_EVIDENCE_IDENTITIES ===` — `identity_key` +
  `expected_raw_sample_path` for every `INSUFFICIENT_EVIDENCE` group.
- `=== SUMMARY ===` — `EXISTING_EVIDENCE_PARTIAL`,
  `EXISTING_EVIDENCE_D_UNRESOLVED`, `MISSING_EVIDENCE_REQUESTS`,
  `TOTAL_UNRESOLVED`, computed directly from the audit's own category
  counts.

Diagnostic reporting only — no classification/matching logic changed
this round, no collision resolved, no formula or semantic equivalence
inferred, `scripts/29`'s B2 runner untouched, no live requests.

**Tests**: 4 new — `match_details` records the specific matched
column and method (not just a boolean), the new diagnostic section
prints every required field for a real-shaped `PARTIAL_MATCH_NEEDS_
REVIEW` group, the missing-evidence section lists the expected path
for an unresolved-insufficient-evidence group, and the summary counts
match a taxonomy with one of each of the three unresolved categories
plus one fully-resolved group. One pre-existing test updated
(`raw_sample_path` is no longer `None` for `INSUFFICIENT_EVIDENCE`,
by design).

**652/652 tests passing** (648 before this round). No live requests
made. No change to Prediction #001, `predictions/`, model/inference/
probability logic, the production DB, the archive, or the public
website. `scripts/29`'s B2 runner untouched. Phase B2 not executed.

---

*Numbers · Evidence · Oracle — Golf Intelligence. Research only. No
database, model, archive, or website changes were made to produce this
document.*
