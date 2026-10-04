# NEO Hole 12 — PIN-CORRECTED Analysis (replaces old CLOSE/MID/FAR)

Game: 2026100005 (하이트진로 챔피언십) · Hole 12, Par 4 · 331 real player-round tee shots

## 0. Status lock (as instructed)

| Item | Status |
|---|---|
| PIN PLACEMENT (72/72) | **PASS** — see `pin_placement_72hole_audit.json` |
| COURSE IDENTITY (Blue Heron West H3 ↔ hole_12.png) | **UNRESOLVED** — independent verification in progress (Playwright network-trace dispatch, see §9) |
| Old `green_side_miss_analysis.json` (CLOSE/MID/FAR by raw-magnitude distance) | **DISCARDED** — assumed pin at coordinate origin (0,0). Real per-round pins are nowhere near the origin (e.g. R1=(93,115)). Not fixed in place; replaced entirely by this file. |

## 1. Real per-round pins (method: every HOLED shot that round shares one exact `(green_x,green_y)` — definitional, not inferred)

| Round | pin (green-frame coords) | n (real players holed) |
|---|---|---|
| R1 | (93.0, 115.0) | 107 |
| R2 | (63.0, 80.0) | 102 |
| R3 | (83.0, 114.0) | 61 |
| R4 | (68.0, 122.0) | 61 |

Cross-validated earlier against the independent `baseHoleInfo.bi_gx/bi_gy` field (`bi_gx/2`, `bi_gy/2`) — matched within 0.5 units all 4 rounds.

## 2. IMPORTANT finding: green-frame coordinates are NOT yards

Cross-checking the pin-relative vector `dist = |(approach.green_x,green_y) − round_pin|` against KLPGA's own real, separately-reported **distance-to-pin field** (`pp_distance`, real yards) across all 331 real approach shots:

- mean |computed − official| = **32.2**, max = **452.3** — these do **not** agree.

Conclusion: `green_x/green_y` is a **map/rendering coordinate** (the same pixel-like frame used to draw `hole_12_G.png`, consistent with the site's own `×2 / ×1.815` transform discovered earlier), not a yard-scaled distance. **For real distance-to-pin (yards), KLPGA's own `distance` field is used — never the Euclidean magnitude of `green_x/green_y`.** The `(dx,dy)` vector from `green_x/green_y` is retained only for spatial/visual clustering (e.g. the Artifact map), explicitly labeled as map-frame units, never yards, and never given a left/right or short-side/long-side name (axis compass meaning is unverified — see COURSE IDENTITY).

## 3. Real chain built per player-round (no estimation)

```
TEE LANDING (shot1: x,y, lie, KLPGA's own remaining-distance field)
  -> ROUND PIN (real, round-specific)
  -> APPROACH ENDPOINT (shot2: green_x,green_y, lie)
  -> PIN-RELATIVE VECTOR (dx,dy in map-frame units; real yards from KLPGA's own distance field)
  -> GIR / MISS (literal: shot2 state=="3" at shot#2 <= par-2)
  -> RECOVERY (shots 3..N-1)
  -> FINAL SCORE (strokes - par)
```
Full 331-row table: `neo_hole12_pin_corrected_records.csv`. Full JSON: `hole12_pin_corrected_analysis.json`.

## 4. Counterexample census (real n, all 331 rows)

| Path | n |
|---|---|
| FW Hit → Par | 115 |
| FW Hit → Bogey | 40 |
| FW Hit → Birdie+ | 16 |
| FW Hit → Double+ | 1 |
| FW Miss → Par | 78 |
| FW Miss → Bogey | 57 |
| FW Miss → Double+ | 20 |
| FW Miss → Birdie+ | 4 |
| GIR → Par | 130 |
| GIR → Bogey | 26 |
| GIR → Birdie+ | 17 |
| GIR Miss → Bogey | 71 |
| GIR Miss → Par Save | 63 |
| GIR Miss → Double+ | 24 |

Real counterexamples exist in every category (FW Hit still produced a Double+; FW Miss still produced 4 birdies; GIR still produced 26 bogeys from 3-putts/etc.). Representative chains for each are in the JSON (`counterexample_census`).

## 5. Zone re-check with FW-hit held fixed — **the central finding**

| Lateral zone | FW-hit only: n / avg score / GIR% | Not-FW only: n / avg score / GIR% |
|---|---|---|
| LAT1 | n=4, +0.25, 75% (**LOW_SAMPLE**) | n=107, +0.449, 37% |
| LAT2 | n=108, +0.139, 72% | n=2, +0.5, 0% (**LOW_SAMPLE**) |
| LAT3 | n=60, **+0.167**, 75% | n=50, +1.00, 14% |

**LAT2's historical "advantage" is almost entirely confounded with being the fairway.** 98% of LAT2 landings (108/110) are on the fairway — there is essentially no "LAT2 but missed fairway" sample to compare against (n=2). Symmetrically, LAT1 is 96% rough (107/111) — its worse average is mostly "rough", not "LAT1 location."

LAT3 is the one zone with enough of both (FW-hit n=60, not-FW n=50) to actually separate the two effects — and **once FW is held fixed, LAT3's FW-hit average (+0.167) is statistically indistinguishable from LAT2's FW-hit average (+0.139).** This directly contradicts "MID-LAT2 is the better location": the real driver on Hole 12 is **hitting the fairway**, not which lateral corridor the fairway hit lands in. LAT2 looked best only because it is the zone where almost everyone who hits the fairway happens to land.

**Conclusion for item 7 (fairway-effect control): REJECTED as a standalone location effect.** "LAT2 location" cannot be recommended as a cause of good outcomes from this data — it should be reported as **"hit the fairway" (field evidence, n=331, FW-hit avg +0.14 to +0.17 across all three lateral bands vs rough avg +0.45 to +1.00)**, not as a specific corridor.

## 6. SHORT-LAT3 vs LONG-LAT3 interaction (item 5)

| Zone | n | avg score | Bogey+% | FW% | tee lie breakdown |
|---|---|---|---|---|---|
| SHORT-LAT3 | 42 | **+0.881** | 66.7% | 28.6% | ROUGH 18, **BUNKER 12 (28.6%)**, FAIRWAY 12 |
| LONG-LAT3 | 34 | +0.382 | 29.4% | 70.6% | FAIRWAY 24, ROUGH 9, LOST_BALL 1 (0% bunker) |
| MID-LAT3 | 34 | +0.294 | — | — | — |

LAT3 is **not** uniformly bad — only the **SHORT-LAT3 combination** is, and the real cause is locatable: a real fairway bunker sits specifically in the SHORT-LAT3 landing band (28.6% of balls landing there are in a bunker; 0% at LONG-LAT3 or MID-LAT3). This is a **distance × lateral interaction caused by a real, locatable hazard**, not a lateral effect alone — confirms item 5's hypothesis with direct evidence.

## 7. Round effect (item 8)

Full zone×round table in `hole12_pin_corrected_analysis.json → zone_x_round_table` (36 rows: 9 zones × 4 rounds). No single zone's overall average is produced by one outlier round — each zone has real samples spread across at least 3 of the 4 rounds (several cells are LOW_SAMPLE, flagged individually in the table; treat those zone×round cells as inconclusive, not the zone's overall n which pools rounds and is adequately sized for LAT2/LAT3/LAT1 as shown above).

## 8. 유해란 (winner, −4) counterexample — reported as-is, not forced to fit

| Round | tee zone | tee lie | approach lie | pin dist (official yd) | GIR | strokes | score |
|---|---|---|---|---|---|---|---|
| R1 | LONG-LAT2 | FAIRWAY | GREEN | 6.4 | **True** | 4 | Par |
| R2 | LONG-LAT1 | **ROUGH** | ROUGH | 43.4 | **False** | 6 | **Double bogey** |
| R3 | LONG-LAT1 | **ROUGH** | FRINGE | 11.6 | False | 4 | Par |
| R4 | LONG-LAT2 | FAIRWAY | FRINGE | 4.8 | False | 4 | Par |

She used the fairway-controlled "best" zone (LAT2) only twice, and missed the fairway entirely twice (both LAT1/ROUGH). Her one real blow-up on this hole (R2, double bogey) happened from ROUGH→ROUGH, i.e. the one time she neither hit the fairway nor saved par from short range. Her two scrambling pars (R3 from 11.6yd fringe after rough off the tee; R4 from a 4.8yd fringe miss after a fairway tee shot) came from short-range recoveries, not from being in a "recommended" zone. **Reading:** she did not win this hole through superior field-level zone placement on Hole 12 — she survived one bad tee shot (R2) with a double, and recovered the other misses from short range. This is a real, reported counterexample to "play the recommended zone," not an endorsement of playing into the rough.

## 9. COURSE IDENTITY — still UNRESOLVED

A Playwright-based headless-browser dispatch against `blueheron.co.kr` (capturing XHR/fetch calls, JS bundle references, and any course-API/image-asset URLs, not just static DOM) has been built and queued (see `verify_course_identity_playwright.py` / `.github/workflows/verify-course-identity-playwright-oneoff.yml`). Until real official West H3 geometry/imagery is recovered this way, **COURSE IDENTITY remains UNRESOLVED** and Hole 12's zone recommendations below are reported as **PLAYER × COURSE candidates conditional on coordinate-registration only**, not as confirmed-identity findings.

## 10. Three-layer framework (per the latest instruction — no single zone is handed to all players)

### LAYER 1 — COURSE TRUTH (field, n=331, all players pooled)
- Hitting the fairway (any lateral band) → avg score +0.14 to +0.17, GIR 72–75%.
- Missing the fairway → avg score +0.45 (LAT1 band) to +1.00 (LAT3 band), GIR 14–37%.
- SHORT-LAT3 carries a real, locatable bunker (28.6% of landings there) and is the single worst zone (+0.881, Bogey+ 66.7%).
- "LAT2 is the best corridor" is **not supported** once fairway-hit is controlled (§5) — the field-level truth is **"hit the fairway; avoid the SHORT-LAT3 bunker band,"** not a specific preferred lateral corridor.

### LAYER 2 — PLAYER TRUTH (Hole-12-specific n=4 per player — explicitly LOW_SAMPLE; tournament-wide 72-hole context given separately, not hole-specific)

| Player | Hole12 n | Tournament-wide (72 holes) FW%/n | GIR%/n | FW-Miss→GIR%/n | GIR-Miss→ParSave%/n | Shot shape |
|---|---|---|---|---|---|---|
| 유해란 (9115) | 4 (LOW_SAMPLE) | 64.3% / 56 | 73.6% / 72 | 16.7% / 36 | 68.4% / 19 | UNKNOWN |
| 이재윤 (9708) | 4 (LOW_SAMPLE) | 57.1% / 56 | 59.7% / 72 | 31.3% / 32 | 65.5% / 29 | UNKNOWN |
| 박서현 (9111) | 4 (LOW_SAMPLE) | 55.4% / 56 | 58.3% / 72 | 35.5% / 31 | 43.3% / 30 | UNKNOWN |

### LAYER 3 — PLAYER × COURSE (candidate, not a uniform recommendation)

For all three players, FIELD EVIDENCE is identical (§Layer 1). PLAYER EVIDENCE is their own n≤4 Hole-12 zone usage (§8 for 유해란; full 12-case table in `hole12_pin_corrected_analysis.json → three_case_study_players_full_12case_reconstruction`).

- **유해란**: Field evidence favors hitting the fairway; her own Hole-12 sample (n=4) shows she scored worse the one time she missed it badly (R2, double from rough) and fine both times she hit it. Tournament-wide she is also the field's best fairway-finder among the three (64.3%) with the best GIR-Miss scrambling (68.4%). **Counter-evidence/uncertainty**: n=4 cannot statistically confirm this for her alone; her two "fine" fairway rounds both still missed the green (R1 GIR true, R4 false) — recovery skill, not just location, is doing real work here.
- **이재윤**: tournament-wide FW 57.1%/GIR 59.7% — middling. No Hole-12-specific zone pattern can be claimed from n=4 (LOW_SAMPLE). Field evidence (fairway >> rough) is the only usable guidance; player-specific target zone is **UNKNOWN**.
- **박서현**: tournament-wide FW 55.4% (weakest of the three) and GIR-Miss→ParSave only 43.3% (weakest scrambler of the three — real, n=30). This matters for her specifically: if her particular tendency is to miss zones the field also punishes (LAT1/rough, SHORT-LAT3/bunker), her downside from a miss is **worse than average** because her own scrambling recovery rate is below the field's two comparison players. **This is a PLAYER-SPECIFIC WEAKNESS candidate** (field already penalizes these misses; her own recovery data makes the penalty larger for her than for 유해란) — flagged as a candidate, not confirmed, since it is not yet decomposed from a controlled subset of her own Hole-12 shots (n=4 is too small to test in isolation).

**No single "Primary Target / Acceptable Miss / No-Go Combination" is issued identically to all three players.** The only safely field-wide, evidence-backed statement for Hole 12 is: *hit the fairway; the SHORT-LAT3 band carries a real bunker and should be treated as a No-Go combination regardless of player.* Anything more specific than that, per player, is currently UNKNOWN or LOW_SAMPLE-flagged, pending either course-identity resolution (§9) or a larger per-player sample across comparable holes (not yet built).
