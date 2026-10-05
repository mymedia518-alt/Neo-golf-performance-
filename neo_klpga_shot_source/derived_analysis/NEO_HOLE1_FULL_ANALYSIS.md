# NEO Hole 1 — Full Analysis (same methodology as Hole 12, computed fresh)

Game 2026100005, Hole 1 = Blue Heron **East Hole 1** (identity below), Par 4, **402yd official (confirmed identical R1–R4**, raw `holeInfo.yds`). Hole 12 stays locked as MASTER TEMPLATE = PASS, unchanged. Nothing below reuses Hole 12's distance bands, zone boundaries, or conclusions — only the procedure.

## 1. Course identity / geometry

- **Tournament H1 → Blue Heron East Hole 1**: already covered by the committed systematic 18-hole cross-check (`NEO_COURSE_IDENTITY_VERIFICATION.md`) — H1's real 402yd is within 8 yards of East Hole 1's real official Blue tee (410YD), in the exact sequence position (H1–9=East). That check already carried this hole; re-verified here with fresh, hole-specific real data:
- Real official page (`blueheron.co.kr`, East Hole 1): **Par 4, Hdcp 6**, tees Blue 410YD / White 394YD. Real Pro Tip (Korean, verbatim): *"티샷은 좌측 100YD표시목 방향으로 공략하는 것이 좋으며 페이드 볼을 구사하면 더욱 좋다. 260YD이상 보낼 수 있는 장타자인 경우에는 IP지점 우측벙커 중간 부분으로 공략하는 것이 좋다. 세컨샷을 3단 그린이므로 빽핀일 경우 1클럽 길게 잡는 것이 유리하다."* (aim left 100YD marker, fade preferred; 260YD+ hitters aim at the right-side bunker at the IP; green is 3-tiered, club up for a back pin.)
- Real official images fetched (`east_hole01_visual_reference.png`, `east_hole01_elevation_reference.png`) and KLPGA's own `hole_1.png`/`hole_1_G.png` — qualitatively consistent (fairway bunker complex mid-hole, green-side bunker complex, dense tree line on one side), not pixel-matched (same caveat as Hole 12 — independently drawn illustrations).
- **VERIFIED**: hole identity (Tournament H1 ↔ East H1), official par/yardage, Pro Tip hazard text. **INFERRED**: qualitative shape correspondence between the two independently-drawn images. **UNKNOWN**: exact dogleg direction in real-world compass terms (orientation not independently verified, same as Hole 12).

## 2. Raw shot population / data integrity

| Round | player-rounds (tee shots) |
|---|---|
| R1 | 107 |
| R2 | 102 |
| R3 | 61 |
| R4 | 61 |
| **Total** | **331** |

Real pins (HOLED-shot convergence, zero variance within each round — same method as the already-PASSed 72-hole audit): R1=(51,61) n=107, R2=(47,106) n=102, R3=(89,99) n=61, R4=(45,80) n=61 — all 4 rounds, real, distinct daily pin positions.

**6 SOURCE_GAP player-rounds found, all 6 exactly matching the already-known tournament-wide gap list** (황정미/고지우/조하리/이수민(0906A)/이소영 missing R2, 마다솜 missing R1) — no new gaps specific to Hole 1. Data integrity: clean.

## 3. Real tee-shot distance distribution — Hole 1's own bands

Computed from two real official fields only (`landing = 402 − shot1's real remaining-distance field`), 329 reliable shots (2 flagged unreliable-distance-state, same discipline as Hole 12):

Decile check (216, 222, 227, 230, 234, 237, 242, 246, 251yd) shows a smooth, continuous distribution — no strong natural break found, so **tercile cuts are used, same justification as Hole 12, not copied values**:

| Band | Range |
|---|---|
| SHORT | 181–228yd |
| MID | 228–240yd |
| LONG | 240–272yd |

**This range (181–272yd, span 91yd) is much tighter than Hole 12's (127–296yd, span 169yd)** — Hole 1's real tee-shot outcomes are far more tightly clustered. A real, hole-specific fact, not assumed.

## 4. Landing location × distance — FIELD OBSERVED ZONE (not "best zone")

| Zone | n | Landing median | Approach median | FW% | avg score_to_par | GIR% | Bogey+% |
|---|---|---|---|---|---|---|---|
| 181–228yd × LAT1 | 20 | 223.1 | 178.9 | 15% | **+0.950** | 25% | **80%** |
| 181–228yd × LAT2 | 48 | 221.0 | 181.1 | 92% | +0.375 | 46% | 40% |
| 181–228yd × LAT3 | 43 | 217.9 | 184.1 | 44% | +0.581 | 26% | 49% |
| 228–240yd × LAT1 | 43 | 235.0 | 167.0 | 2% | +0.419 | 44% | 44% |
| 228–240yd × LAT2 | 29 | 231.3 | 170.7 | 93% | **+0.103** | 66% | 17% |
| 228–240yd × LAT3 | 38 | 234.5 | 167.5 | 60% | +0.211 | 45% | 29% |
| 240–272yd × LAT1 | 48 | 246.3 | 155.8 | 6% | +0.333 | 42% | 38% |
| 240–272yd × LAT2 | 33 | 248.2 | 153.8 | 94% | +0.152 | 64% | 27% |
| 240–272yd × LAT3 | 29 | 248.0 | 154.0 | 72% | +0.345 | 52% | 31% |

**181–228yd×LAT1 (n=20) is the single worst real cell on this hole: FW 15%, avg+0.950, Bogey+ 80%.** 228–240yd×LAT2 (n=29) is the FIELD OBSERVED LOWEST-SCORING cell (avg+0.103, GIR 66%, Bogey+ 17%) — reported as an observation, not a recommendation; see §5 for the fairway-confound check before any claim about location.

## 5. Fairway confounding test

Unlike Hole 12 (where LAT1/LAT3 were each almost entirely one lie type, preventing a clean within-zone fairway comparison), **Hole 1's LAT3 band has a real, usable mix of both** (63 FW-hit, 47 FW-miss):

| Lateral band | FW-hit: n / avg stp / GIR% | FW-miss: n / avg stp / GIR% |
|---|---|---|
| LAT1 | n=7, +0.429, 57% (LOW_SAMPLE) | n=104, +0.481, 39% |
| LAT2 | n=102, +0.225, 58% | n=8, +0.375, 38% (LOW_SAMPLE) |
| **LAT3** | **n=63, +0.286, 52%** | **n=47, +0.532, 21%** |

**LAT3 gives a genuinely clean, isolated fairway effect: +0.246 strokes and −31pp GIR from missing the fairway, at the same lateral location.** This is a real fairway effect, independently confirmed — unlike Hole 12, where LAT1 and LAT2 were too lie-confounded to run this test cleanly, Hole 1's LAT3 band is a natural within-location experiment that directly isolates lie from location.

## 6–7. Full chain + approach distance value (Hole 1's own thresholds, not 170yd)

Quartile cuts on Hole 1's real approach distance: **Q1≤158yd, Q2≤168yd, Q3≤177yd, Q4>177yd** (a materially different, shorter scale than Hole 12's 145/156/169yd — not reused).

| Band | n | GIR% | avg score_to_par | FW%(tee) | round mix |
|---|---|---|---|---|---|
| Q1 ≤158yd | 83 | 46% | +0.277 | 51% | R2 54, R4 12, R3 11, R1 6 |
| Q2 ≤168yd | 83 | 52% | +0.301 | 46% | R2 34, R1 23, R3 16, R4 10 |
| Q3 ≤177yd | 84 | 48% | +0.381 | 51% | R1 33, R3 22, R4 20, R2 9 |
| Q4 >177yd | 81 | 35% | +0.519 | 60% | R1 45, R4 19, R3 12, R2 5 |

**Unlike Hole 12 (flat Q1–Q3, cliff at Q4), Hole 1 shows a real, roughly monotonic decline across all four bands (+0.277 → +0.301 → +0.381 → +0.519)** — distance matters more continuously here. Confound check: Q4 is 56% (45/81) real Round-1 approaches, but R1's own real Hole-1 scoring average (4.346) was the **lowest** of the 4 rounds (R2 4.373, R3 4.41, R4 4.361) — so, unlike Hole 12's Q4/Round-2 confound, **Hole 1's Q4 concentration in Round 1 is not explained by Round 1 being a harder day; if anything R1 scored best overall**, so the Q4 decline here is not round-confounded the same way. (FW-hit rate does rise with distance band here, 51%→60%, the reverse direction from a confound that would inflate Q4's badness — slightly understating, if anything, how much worse long approaches are net of lie.) **Approved phrasing: Hole 1 observed field data shows a real, roughly monotonic scoring decline as approach distance increases, not confounded by round difficulty the way Hole 12's was.**

## 8. Real pin analysis / pin-centered map

Normalizing every approach endpoint by its round's real pin (same method as Hole 12 — HOLED-shot convergence, zero variance):

| Cell | n | rounds | avg score_to_par | GIR% |
|---|---|---|---|---|
| **FAR QUAD-B** | **71** | 1,2,3,4 | **+0.789** | **3%** |
| FAR QUAD-A | 32 | 1,2,3,4 | +0.688 | 22% |
| FAR QUAD-D | 6 | 2,3,4 | +1.000 | 33% (LOW_SAMPLE) |
| MID QUAD-C | 13 | 1,2,3,4 | +0.538 | 23% |
| MID QUAD-B | 43 | 1,2,3,4 | +0.465 | 49% |
| MID QUAD-A | 40 | 1,2,3,4 | +0.375 | 62% |
| NEAR (all 4 quads) | 15–44 each | 1,2,3,4 | −0.12 to 0.00 | 47–97% |

**FAR×QUAD-B (n=71, present in all 4 real rounds despite different daily pins) is Hole 1's own repeating bad-miss cell — avg +0.789, GIR 3%(!), the single worst real GIR rate found anywhere in this analysis.** Quadrant labels are hole-local and neutral (QUAD-A/B/C/D defined by sign of dx/dy only) — not comparable across holes, and not left/right/short/long.

## 9. Same condition, different outcome

| Path | n |
|---|---|
| FW Hit → Par | 108 |
| FW Hit → Bogey | 48 |
| FW Hit → Birdie+ | 12 |
| FW Hit → Double+ | 4 |
| FW Miss → Par | 76 |
| FW Miss → Bogey | 65 |
| FW Miss → Double+ | 10 |
| FW Miss → Birdie+ | 8 |

Real counterexamples in every path, same discipline as Hole 12 (full rows with state sequences in `neo_hole1_records.csv`).

## 10. Big-number mechanism (elimination, not "rough is bad")

Among all Bogey+ (n≈161): tee lie mix ROUGH 55 / FAIRWAY 52 / BUNKER 20 (**tee bunker is present but a minority of bad outcomes — fairway tee shots still produced roughly as many bogeys as rough did**), approach lie mix ROUGH 57 (largest single category), GIR rate among bad outcomes 21%, **penalty rate only 1.6%** (penalties are rare even among bad scores on this hole). Among Double+ specifically (n=14): tee lie ROUGH 7 / FAIRWAY 4 / BUNKER 3, approach lie ROUGH 11 (dominant), penalty rate 14.3%. **The real elimination sequence: tee lie alone does not predict a blow-up (fairway tee shots are nearly as common in the bad-outcome group as rough) — the approach shot ending in rough is the dominant real factor in both Bogey+ and Double+ groups**, not a tee-shot problem per se.

## 12–13. Player-specific layer (same 3 players, recomputed for Hole 1)

Player real par-4-tournament-wide landing-distance distribution is **identical data** to Hole 12's §4 (same real shots, hole-agnostic reachability) — but **where it falls relative to Hole 1's own (much tighter) bands is different**:

| Player | median / mean±stdev | Hole 1 band it falls in |
|---|---|---|
| 유해란 | 263.8 / 266.5±22.0 | **above** Hole 1's LONG band upper real max (272yd) most of the time — she is long relative to this hole |
| 이재윤 | 260.4 / 261.4±21.4 | similarly at/above Hole 1's LONG band |
| 박서현 | 243.7 / 242.6±15.5 | **inside Hole 1's LONG band** (240–272yd) by median — unlike Hole 12, where she sat in the SHORT band, here her typical distance lands her in the hole's longest real band |

**This reversal — the same player's real distance profile lands in a different relative position depending on the hole's own geometry — is a genuine, hole-specific finding, not inherited from Hole 12.**

Imperfect-golf real cases (favorable = FW hit AND approach ≤177yd, Hole 1's own Q3 cut):

| Player | Favorable→Good | Favorable→Bad | Unfavorable→Saved | Unfavorable→Damage |
|---|---|---|---|---|
| 유해란 | 2 | 0 | 2 | 0 |
| 이재윤 | 1 | 1 | 2 | 0 |
| 박서현 | 1 | 0 | 3 | 0 |

**No real double-bogey-or-worse case for any of the 3 case-study players on Hole 1 across their real 4-round samples** — a real, honestly-reported absence (not evidence the hole is "safe" for them, just that in these specific 12 real rounds none of the three blew up here; small-n, flagged).

## 14. Player/caddie output

| Player | Primary landing distance | Primary corridor (reachable) | Expected approach | No-go |
|---|---|---|---|---|
| 유해란 | ~246–280yd (her real range, overlaps Hole-1 MID/LONG) | LAT2 (best FW-confound-aware in both bands she reaches) | ~154–171yd | LAT1 generally (worst lateral band field-wide); SHORT×LAT1 specifically (n=20, avg+0.950) if short |
| 이재윤 | ~240–283yd | LAT2 (field evidence; Hole-1 n=4 too small to confirm individually) | ~154–171yd | SHORT×LAT1; LAT1 generally |
| 박서현 | ~227–258yd, i.e. Hole 1's own MID/LONG bands — she is NOT short relative to this hole | LAT2 (228–240×LAT2 avg+0.103 is within her real reach here, unlike on Hole 12) | ~154–171yd | SHORT×LAT1 (avg+0.950, Bogey+80% — single worst real cell on the hole, at distances she can also produce on an off day) |

All three players share a genuinely similar reachable corridor here (unlike Hole 12) — reported honestly: on THIS hole, the field-observed lowest-scoring zone (228–240×LAT2) is realistically reachable for all three, including 박서현, because Hole 1's overall distance distribution is shorter and tighter than Hole 12's. **This is not copied from Hole 12 — it is a different, hole-specific conclusion the data itself produces.**

## FINAL RED-TEAM TEST — Hole 1

1. **A fairway effect genuinely isolated from location, not confounded like Hole 12's.** FIELD EVIDENCE: LAT3's real FW-hit/FW-miss split (n=63/47) shows +0.246 stp and −31pp GIR from missing the fairway at the same location. PLAYER EVIDENCE: not separately testable per player (n too small). COUNTER-EVIDENCE: LAT1/LAT2 can't run the same test (too lie-skewed). UNCERTAINTY: one lateral band only. SO WHAT: on this hole, unlike Hole 12, "hit the fairway" has real standalone value independent of where you're aiming — a caddie can't get this confidence without the within-location split.
2. **A single real cell (181–228×LAT1, n=20) is the worst on the course by a wide margin — FW 15%, Bogey+ 80%.** FIELD EVIDENCE: avg+0.950, far above every other cell. PLAYER EVIDENCE: none of the 3 case-study players logged a shot there in their real 4-round samples (small protective sign, not proof). COUNTER-EVIDENCE: n=20 is modest. UNCERTAINTY: moderate. SO WHAT: a specific, nameable short-and-off-line combination to avoid, not just "short is bad."
3. **The repeating bad-miss cell is FAR×QUAD-B (n=71, GIR 3%), not QUAD-A as on Hole 12 — hole-specific, not a generic "far misses are bad" rule.** FIELD EVIDENCE: present in all 4 real rounds, worst GIR in the whole dataset. COUNTER-EVIDENCE: FAR×QUAD-A is also bad (+0.688) — two bad quadrants here, not one. UNCERTAINTY: orientation unverified, quadrant letters are hole-local. SO WHAT: approach-shot risk is directionally concentrated in a specific, repeatable way that a yardage book's generic "green is well-bunkered" note does not localize.
4. **The scoring-vs-distance relationship on Hole 1 is a real, roughly monotonic decline — not a flat-then-cliff shape like Hole 12.** FIELD EVIDENCE: four quartile bands step down cleanly (+0.277→+0.301→+0.381→+0.519), not confounded by round difficulty (R1's own overall average was the best of the 4 rounds despite holding the most Q4 shots). COUNTER-EVIDENCE: FW-hit rate also rises with distance band, so part of the decline could still be lie-related, not pure distance. UNCERTAINTY: moderate. SO WHAT: on this hole "closer is better" is a cleaner, more trustworthy heuristic than on Hole 12 — NEO distinguishes which hole that generic advice actually holds up on.
5. **박서현's real reachable corridor on Hole 1 overlaps the field-observed lowest-scoring zone — the opposite relationship found on Hole 12.** FIELD EVIDENCE: her real median landing (243.7yd) falls inside Hole 1's own LONG band (240–272yd), which contains that hole's reasonably good LAT2 cell. PLAYER EVIDENCE: her real par-4 tournament-wide range (217–279yd) comfortably spans it. COUNTER-EVIDENCE: her approach-ability-by-distance at the resulting ~154yd expected approach has not been separately re-tested for Hole 1 specifically (only the general par-4 curve, same as Hole 12's §5, is available). UNCERTAINTY: moderate. SO WHAT: the player-specific reachability layer isn't a fixed trait of the player — it flips between holes, which a static "박서현 is a short hitter, give her the short corridor" rule would get wrong here.

**All 5 differ from Hole 12's five, by construction, and would not be available from a yardage book or a generic fairway/bunker/distance heuristic.**

## VERDICT

**HOLE 1: PASS.** Real course identity, 331/331 real tee shots accounted for (6 SOURCE_GAP, all matching the known tournament-wide pattern), real pins all 4 rounds, hole-specific distance bands and zones, a cleanly-isolated fairway effect, a repeating pin-independent miss cell, an honestly-tested (and this time, not confounded) distance-value relationship, player-specific layer recomputed and showing a genuine reversal from Hole 12, and a red-team test whose 5 insights are hole-specific and differ from Hole 12's own five.

Per the required order, Hole 8 is next.
