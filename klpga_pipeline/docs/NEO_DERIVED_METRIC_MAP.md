# NEO Derived Metric Map — Player DNA transformation + cross-tour portability

**Status: research/documentation only, 2026-08-26 (Round 2).** Mission
6 (NEO transformation map) and Mission 7 (cross-tour portability) from
`NEO GOLF — KLPGA OFFICIAL DATA DISCOVERY, ROUND 2`. No formula is
implemented here — naming/mapping only, per instruction. No DB, model,
archive, prediction, or website change.

This document only transforms metrics already `CONFIRMED` in
`docs/KLPGA_OFFICIAL_DATA_MAP.md` (Round 1). Where a dimension is
listed for a metric that is still `DISCOVERED-NOT-VALIDATED` or
`UNKNOWN`, that row is explicitly marked **aspirational** — a plan for
if/when the underlying data is confirmed, not a claim that it exists.

---

## Product principle, restated

KLPGA RAW → NEO DATA LAYER → NEO DERIVED FEATURES → **NEO PLAYER DNA**
→ NEO PREDICTION → NEO LIVE → fan-facing explanation. Nothing in this
document is intended to render as a KLPGA-shaped table on NEO's site —
every row below ends in a named DNA dimension or synthesized
interpretation, not a republished statistic.

---

## Transformation map — CONFIRMED raw metrics only

| Official raw metric | Status | → NEO derived feature | → Fan-facing interpretation | Model use | Player DNA dimension |
|---|---|---|---|---|---|
| SG Total | CONFIRMED | Season Strokes-Gained Index *(name only — gated on the PIT test in `KLPGA_OFFICIAL_DATA_MAP.md`, not usable as a model feature until resolved)* | "종합적으로 필드 평균보다 얼마나 앞서는가?" | Pending PIT resolution | **FORM** (overall — see note below on overlap with NEO's existing recent-form features) |
| SG Tee Shot | CONFIRMED | component of Power-Control Tradeoff | "티샷에서 얼마나 이득을 만드는가?" | Pending PIT resolution | **POWER** |
| SG Approach | CONFIRMED | component of Approach DNA *(the metric itself confirmed; the richer distance-bucketed Approach DNA in Table 4 of Round 1 stays aspirational until GIR/proximity data is confirmed)* | "그린을 노리는 샷에서 얼마나 이득을 만드는가?" | Pending PIT resolution | **APPROACH** |
| SG Around the Green | CONFIRMED | component of Recovery DNA | "그린 주변에서 실수를 얼마나 만회하는가?" | Pending PIT resolution | **RECOVERY** |
| SG Putting | CONFIRMED | component of Putting DNA | "퍼팅에서 얼마나 이득을 만드는가?" | Pending PIT resolution | **PUTTING** |
| measured rounds (SG sample size) | CONFIRMED | Reliability Weight *(cross-cutting meta-feature, not itself fan-facing)* | *(internal — feeds confidence into every SG-derived dimension above)* | Confidence gate on every SG-derived feature | *(none — modifies all dimensions)* |
| 280yd+ tee-shot rate + qualifying count | CONFIRMED | component of Power-Control Tradeoff | "얼마나 자주 멀리 치는가, 그리고 그게 안정적으로 반복되는가?" | Course-fit feature (long-course suitability) | **POWER** |
| Fairway-accuracy (260–280yd bucket) rate + qualifying count | CONFIRMED | component of Power-Control Tradeoff | "거리를 늘려도 정확도가 얼마나 유지되는가?" *(the brief's own worked example)* | Course-fit feature | **CONTROL** |

**Worked composite example** (naming only, no formula): **Power-Control
Tradeoff** = f(avg tee-shot distance, distance-bucket rate, paired
fairway-accuracy-bucket rate, all weighted by their qualifying-shot
counts) → DNA dimensions **POWER** + **CONTROL** jointly → "거리를
늘려도 정확도가 얼마나 유지되는가?"

**Note on FORM overlap:** NEO already computes a real "recent form"
signal from data it already has — `prior_recent_form_10`/`_20`/`_5` in
`point_in_time_features.py`, built purely from historical round scores,
with a strictly-prior-cutoff PIT guarantee this new `loadLocationRecord`
data does not yet have. A future **FORM** DNA dimension should almost
certainly be anchored on that existing, already-PIT-safe feature, with
KLPGA's SG Total treated as a secondary/supplementary signal once (and
only if) its own PIT status is resolved favorably — not the other way
around.

---

## Aspirational dimensions — pending Round 3+ confirmation

These mirror Round 1's Table 4, restated here for structural
completeness per Mission 6's requested format. **No underlying raw
field has been confirmed for any of these** — do not treat this
section as evidence anything below exists.

| Aspirational raw metric | Status | → NEO derived feature (planned) | → Fan-facing interpretation | Player DNA dimension |
|---|---|---|---|---|
| GIR by distance + proximity | UNKNOWN | Approach DNA (full form) | "어느 거리에서 가장 많은 타수를 만드는가?" | **APPROACH** |
| Scrambling / sand save + proximity | UNKNOWN | Recovery DNA (full form) | "실수 후 얼마나 잘 만회하는가?" | **RECOVERY** |
| Putting distance buckets + attempts/makes | UNKNOWN | Putting DNA (full form) | "짧은 퍼트형인가, 중거리에서 차이를 만드는가?" | **PUTTING** |
| Course par/yardage + hole-level detail | UNKNOWN | Course-Fit Index | "이 코스가 이 선수의 스타일에 맞는가?" | *(cross-cutting — combines with POWER/CONTROL/APPROACH)* |
| Live hole-by-hole state | UNKNOWN | Live Momentum signal | "지금 이 선수의 흐름이 어떻게 바뀌고 있는가?" | *(NEO LIVE only — must stay outside the prediction-model pipeline, per the PIT discipline already established for live data in `KLPGA_OFFICIAL_DATA_MAP.md`)* |

---

## Cross-tour portability (Mission 7)

Goal restated: NEO's vocabulary should describe golfers, not just
relabel KLPGA's menu categories. Evidence below is general
golf-statistics domain knowledge (how Strokes Gained and related
concepts are publicly known to be used across tours), not new KLPGA-
specific capture — it required no live access to reason about.

| Concept | KLPGA | PGA TOUR | LPGA | DP World Tour | Other | Cross-tour analogue? |
|---|---|---|---|---|---|---|
| Strokes Gained (Total + 4-component split) | CONFIRMED this round (season-level, via `loadLocationRecord`) | Origin of the modern SG framework (ShotLink-based) | Publishes its own SG suite | Publishes a version of SG | Widely adopted concept beyond golf broadcasting too | **Yes — strong, well-established analogue.** SG is not a KLPGA-specific term; NEO can use it as-is without inventing new vocabulary. |
| Driving distance | Confirmed (avg tee-shot distance) | Standard published stat | Standard published stat | Standard published stat | — | **Yes** |
| Fairway accuracy | Confirmed (bucketed by distance) | Standard published stat (also has distance-bucketed variants) | Standard published stat | Standard published stat | — | **Yes** |
| Distance-bucketed driving (e.g. "280yd+ rate") | Confirmed | ShotLink-era PGA Tour data has comparable buckets | Less commonly publicized at this granularity | Less commonly publicized | — | **Partial** — the underlying concept (rate within a distance band) is universal, but the specific bucket boundaries (280/260/240…) are KLPGA's own choice, not a standard — NEO should not assume these exact cutoffs are meaningful outside KLPGA's own reporting. |
| GIR / GIR by distance | Not yet confirmed for KLPGA | Standard | Standard | Standard | — | **Yes**, concept-wise — but KLPGA's own exposure of it is still `UNKNOWN`, not the portability question |
| Scrambling / sand save | Not yet confirmed for KLPGA | Standard | Standard | Standard | — | **Yes**, concept-wise, same caveat |
| Putting average / 1-putt / 3-putt | Not yet confirmed for KLPGA | Standard | Standard | Standard | — | **Yes**, concept-wise, same caveat |
| "Power-Control Tradeoff" (NEO term) | — | No standard tour uses this exact term | — | — | — | **NEO-native** — this is intentionally NEO's own synthesis name for a real, portable underlying concept (distance vs. accuracy trade-off), which *is* discussed informally across all tours even without a standard published metric name |
| "Player DNA" framing itself | — | No tour publishes anything called this | — | — | Some third-party golf-analytics products use "profile"/"style" framing informally | **NEO-native** — the framing (not the underlying stats) is NEO's differentiation |

**Conclusion for Mission 7:** the underlying statistical *concepts*
KLPGA exposes (SG, driving distance, fairway accuracy, and — pending
confirmation — GIR/scrambling/putting) are not KLPGA-specific; they
are the same vocabulary used across every major tour. This supports
the product principle directly: NEO's DNA-dimension naming
(POWER/CONTROL/APPROACH/RECOVERY/PUTTING/FORM) can be built on
genuinely portable golf concepts, not on KLPGA's own menu taxonomy —
so if NEO ever needs a non-KLPGA data source for the same underlying
concept (a different tour, a licensed alternative provider), the DNA
framework does not need to be redesigned, only re-fed.

---

*Numbers · Evidence · Oracle — Golf Intelligence. Research only. No
formula implemented, no database/model/archive/website change.*
