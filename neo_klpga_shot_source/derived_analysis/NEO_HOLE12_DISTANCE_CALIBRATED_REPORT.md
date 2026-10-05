# NEO Hole 12 — DISTANCE-CALIBRATED Zone Analysis

Game 2026100005, Hole 12, Par 4, official yardage **410yd (confirmed identical R1–R4** from raw `holeInfo.yds`, not assumed).

## 0. Method — two real official fields, no coordinates, no estimation

```
landing_distance  = HOLE_YARDAGE(410) − shot1.distance   (real KLPGA remaining-to-pin field)
approach_distance = shot1.distance                        (= the real starting distance of shot 2)
```
Both numbers come directly from two real Shot Tracker fields (`holeInfo.yds`, `pp_distance`/`distance`) — **no coordinate transform, no DERIVED flag needed.** Lateral zone (LAT1/LAT2/LAT3) still requires the earlier-verified coordinate tee→green axis projection — that piece is explicitly DERIVED-COORDINATE, kept separate from the two distance numbers above.

2 of 331 real tee shots (0.6%) carry PENALTY_AREA/LOST_BALL states where the distance field is 0.0 or anomalous (0.0yd and 382.4yd) — flagged `unreliable_distance_state=true` per-row in the CSV, never dropped, excluded only from the quantile-cut calculation (not from any player's or zone's reported n).

## 1. Distance bands are now real yards, not coordinate terciles

Data-driven tercile cuts on the real 329-shot landing-distance distribution (min 127.2, max 295.7):

| Band | Range |
|---|---|
| SHORT | 127–246 yd |
| MID | 246–261 yd |
| LONG | 261–296 yd |

(Full field range is unusually wide — 127yd is a badly pulled/mishit tee shot, 296yd a strong one; median 254yd.)

## 2. Zone table — landing distance, approach distance, and outcome, together

| Zone (distance × lateral) | n | Landing median | Approach median | avg score_to_par | GIR% | Bogey+% |
|---|---|---|---|---|---|---|
| 127–246yd × LAT1 | 40 | 236.8 | 173.3 | +0.525 | 40% | 42% |
| 127–246yd × LAT2 | 24 | 235.0 | 175.1 | +0.167 | 62% | 25% |
| 127–246yd × LAT3 | 47 | 235.9 | 174.1 | **+0.894** | 26% | **66%** |
| 246–261yd × LAT1 | 40 | 254.0 | 156.0 | +0.375 | 42% | 38% |
| 246–261yd × LAT2 | 39 | 254.1 | 155.9 | **+0.051** | **72%** | 20% |
| 246–261yd × LAT3 | 31 | 253.8 | 156.2 | +0.387 | 61% | 36% |
| 261–296yd × LAT1 | 31 | 272.3 | 137.7 | +0.419 | 32% | 32% |
| 261–296yd × LAT2 | 47 | 270.3 | 139.7 | +0.213 | 74% | 28% |
| 261–296yd × LAT3 | 32 | 267.7 | 142.3 | +0.188 | 66% | 22% |

Field-wide best cell: **246–261yd × LAT2** (avg +0.051, GIR 72%, Bogey+ 20%). Worst: **127–246yd × LAT3** (avg +0.894, Bogey+ 66%, GIR 26% — this is the short-fairway-bunker band identified earlier). Consistent with the earlier coordinate-tercile finding (MID-LAT2 was previously n=38/avg+0.079 — nearly identical real numbers under the new, more defensible distance-based banding).

Full zone×round breakdown (36 cells) in `hole12_distance_calibrated_analysis.json → zone_x_round`.

## 3. Approach-distance value (does a shorter remaining distance always help?)

| Band (quartile) | n | avg score_to_par | GIR% | Bogey+% |
|---|---|---|---|---|
| Q1 (≤145yd) | 85 | +0.235 | 61% | 25% |
| Q2 (≤156yd) | 82 | +0.268 | 61% | 32% |
| Q3 (≤169yd) | 82 | +0.280 | 55% | 30% |
| Q4 (>169yd) | 82 | **+0.732** | 32% | **56%** |

Field-wide: yes, shorter approach is generally better, but the effect is flat across Q1–Q3 (+0.235 to +0.280, GIR 55–61% — no meaningful difference) and only bites hard past ~170yd (Q4). **"Get as close as possible" is not supported inside 170yd on this hole — only "stay inside ~170yd" is.**

## 4. Player reachability — the same zone is not equally reachable for all three

Real par-4-tournament-wide landing-distance distribution (10 par-4 holes × up to 4 rounds, same official-field formula):

| Player | n | median | mean ± stdev | range |
|---|---|---|---|---|
| 유해란 | 39 | 263.8 | 266.5 ± 22.0 | 222.8–315.6 |
| 이재윤 | 40 | 260.4 | 261.4 ± 21.4 | 208.5–310.6 |
| 박서현 | 40 | **243.7** | **242.6 ± 15.5** | 217.1–279.3 |

**박서현's realistic range (mean±1stdev ≈ 227–258yd) barely touches the field's best zone (246–261yd×LAT2, avg+0.051) and does not reliably reach 261–296yd×LAT2 (avg+0.213) at all** — her single longest tournament par-4 tee shot all event was 279.3yd, well short of that band's 261–296 range being a comfortable target. 유해란 and 이재윤 both average in the 260s and their ranges span both the MID and LONG bands.

**Consequence: the field's single best zone (246–261yd×LAT2) is not an equally valid recommendation for all three players.** For 박서현, forcing a 246yd+ carry is asking for a tee shot near her personal max, not her typical shot — the realistic, reachable comparison for her is among the SHORT-band (127–246yd) lateral options, where LAT2 (avg+0.167, GIR 62%, Bogey+ 25%) is still clearly the best of her three realistic choices, far ahead of LAT3 (avg+0.894, Bogey+ 66%) and LAT1 (avg+0.525).

## 5. Player-specific approach ability by distance (par-4 tournament-wide, not just Hole 12)

| Player | Q1(≤145) | Q2(≤156) | Q3(≤169) | Q4(>169) |
|---|---|---|---|---|
| 유해란 | n=25, **−0.16**, GIR 76%, ParOrBetter 92% | n=5, +0.60 | n=6, +0.167 | n=3, +0.667 (LOW_SAMPLE) |
| 이재윤 | n=24, +0.042, GIR 58% | n=5, +0.20 | n=6, +0.500 | n=5, 0.000, ParOrBetter 100% |
| 박서현 | n=15, **+0.733**, Bogey+ 47% | n=5, +0.40 | n=6, **+0.167**, ParOrBetter 83% | n=14, +0.571, GIR **64%** (her own best GIR band) |

Counterexample worth flagging: 박서현's own data does **not** show "closer is simply better" — her worst band is actually her closest (Q1 ≤145yd, avg +0.733), and her best score is from Q3 (157–169yd). Sample sizes are real but modest (n=15 and n=6) — reported as a real pattern in her own data, not asserted as a mechanism, and not acted on with full confidence (n=6 for her best band is on the edge of LOW_SAMPLE).

## 6. Per-player final read for Hole 12 (not a single zone for all three)

**유해란** — PRIMARY LANDING DISTANCE: ~246–280yd (within her real ±1stdev range and overlapping both of the hole's two better-scoring distance bands). PRIMARY CORRIDOR: LAT2 (best in both MID and LONG bands she reaches). EXPECTED APPROACH DISTANCE: ~140–156yd. ACCEPTABLE MISS: LAT3 at LONG distance (avg+0.188, close to LAT2). NO-GO: LAT3 at SHORT distance if she's badly off (avg+0.894, real bunker zone) and LAT1 generally (worst lateral band in 2 of 3 distance bins for her reachable range).

**이재윤** — PRIMARY LANDING DISTANCE: ~246–280yd (same reasoning as 유해란, very similar reach profile, median 260.4 vs 263.8). PRIMARY CORRIDOR: LAT2. EXPECTED APPROACH DISTANCE: ~140–156yd. Field evidence only here — no Hole-12-specific pattern beyond n=4, and her own approach-ability-by-distance sample doesn't show a band she is distinctly stronger or weaker in (all four bands are within a fairly narrow +0.0 to +0.5 range, n too thin past Q1 to call a real difference).

**박서현** — PRIMARY LANDING DISTANCE: ~227–258yd, i.e. the SHORT band (127–246yd), not the field's best MID band — because that is what she actually, reliably produces. PRIMARY CORRIDOR within that reachable range: LAT2 (avg+0.167, GIR62%, Bogey+25% — clearly best of her three realistic options). ACCEPTABLE MISS: cautiously LAT1 (avg+0.525, meaningfully worse but not catastrophic). NO-GO: LAT3 at SHORT distance (avg+0.894, Bogey+66%, the real bunker band) — this is the single highest-cost combination in her realistic reach and should be avoided above all else. EXPECTED APPROACH DISTANCE from her realistic LAT2 landing: ~175yd (that band's approach median) — note this falls in her Q4 approach-ability band, where her own data shows her best GIR% (64%) despite a middling average score (+0.571); i.e. the "longer-than-ideal" approach she'd realistically face from this corridor is not clearly worse for her specifically than a shorter one, per her own (modest-sample) data.

**No single zone or landing distance is issued to all three players** — field evidence (§1–3) is shared, but the realistic/reachable corridor and expected approach distance differ by player (§4–6), per the required FIELD TRUTH / PLAYER TRUTH / PLAYER×COURSE separation.
