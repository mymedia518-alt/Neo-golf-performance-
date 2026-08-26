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

---

*Numbers · Evidence · Oracle — Golf Intelligence. Research only. No
database, model, archive, or website changes were made to produce this
document.*
