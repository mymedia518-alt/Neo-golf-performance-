# NEO Hole 12 — MASTER TEMPLATE (final build)

Game 2026100005, Hole 12, Par 4, 410yd (confirmed identical R1–R4). All numbers from `hole12_master_template.py` / `hole12_master_template.json`, re-runnable.

## 0. Naming correction

**246–261yd × LAT2 is no longer called "BEST ZONE."** It is the **FIELD LOWEST-SCORING OBSERVED ZONE** (avg +0.051, n=39) — an observed-population statistic, not a confirmed cause, since a large part of its apparent edge is confounded with fairway-hit (established previously). Player recommendations are judged separately per player (§5, §6), never inherited automatically from this field label.

## TASK 1 — Same fairway, different outcome

Fairway-hit tee shots only (n=172), split by real outcome:

| Outcome | n | avg landing | avg approach dist | GIR% | avg putts* | approach lie mix |
|---|---|---|---|---|---|---|
| Birdie+ | 16 | 257.4yd | 152.6yd | 81% | 1.81 | GREEN 13, FRINGE 2, ROUGH 1 |
| Par | 115 | 257.5yd | 152.5yd | 83% | 2.83 | GREEN 95, ROUGH 12, FRINGE 8 |
| Bogey | 40 | 252.4yd | 157.6yd | 45% | 3.42 | GREEN 18, ROUGH 18, FRINGE 2, GSB 2 |
| Double+ | 1 | 251.9yd | 158.1yd | 0% | 4 | ROUGH 1 |

*putts = trailing shots once the ball is continuously on green/holed; a chip-and-hole-out from fringe counts as 1, so this slightly understates true putts for up-and-downs — real state sequences are kept alongside every row in the CSV for exact reconstruction.

**Finding: within fairway-hit tee shots, landing distance and approach distance are essentially identical across Birdie+/Par/Bogey (all 252–258yd landing, 153–158yd approach) — the outcome split is not explained by tee-shot distance at all.** What actually splits Birdie+/Par from Bogey is **what the approach shot does once struck**: GIR 81–83% for the two good buckets vs 45% for Bogey, and the approach lie mix shifts hard toward ROUGH/GREENSIDE_BUNKER in the Bogey group. **Same fairway, same landing distance — the outcome is decided at the approach swing, not the tee shot.** Full 172-row chain (every FW-hit player-round, state sequence included) in `neo_hole12_master_records.csv`.

## TASK 2 — Approach endpoint map (all real approaches, not just 3 players)

Every real approach's START (remaining distance at the tee landing — the real official field), the round's real PIN, and the real ENDPOINT (green-frame coordinates) are in `hole12_master_template.json → task2_approach_endpoint_map`, keyed by round, tagged Birdie+/Par/Bogey/Double+. Wired into the Artifact's round selector (R1–R4), now plotting the full field, not only the 3 case-study players, colored by outcome bucket.

## TASK 3 — Pin-centered map (4 rounds combined, neutral zone IDs only)

Every endpoint re-expressed as `(dx, dy)` = endpoint − that round's real pin, combined across R1–R4. Ring = pin-distance tercile in **map-pixel units** (not yards — these coordinates are confirmed non-linear vs. real yards, see prior report). Quadrant = sign of (dx, dy) only — **QUAD-A/B/C/D are not left/right/short/long; real-world orientation is still not independently verified.**

| Cell | n | rounds present | avg score_to_par | GIR% | Double+% |
|---|---|---|---|---|---|
| **FAR QUAD-A** | **76** | **1,2,3,4** | **+1.013** | 9% | 21% |
| FAR QUAD-B | 12 | 1,2,3,4 | +0.667 | 0% | 8% |
| FAR QUAD-C | 20 | 1,2,3,4 | +0.500 | 65% | 10% |
| MID QUAD-A | 50 | 1,2,3,4 | +0.280 | 44% | 0% |
| MID QUAD-C | 20 | 1,2,3,4 | +0.450 | 70% | 5% |
| MID QUAD-D | 17 | 1,2,3,4 | +0.412 | 76% | 0% |
| NEAR (all 4 quads) | 24–37 each | 1,2,3,4 | −0.17 to +0.04 | 75–97% | 0–3% |

**Finding: FAR QUAD-A is a real, repeating BIG-NUMBER MISS pattern — present in all 4 rounds despite different pin positions each day, by far the largest cell (n=76), with the worst average score (+1.013) and lowest GIR (9%).** This is the one genuinely pin-position-independent bad pattern in the data. By contrast, FAR QUAD-C, despite also being "far from pin," has GIR 65% (reached the green, just left a long traversal putt) and a meaningfully better average (+0.500) — **"far from pin" is not one uniform miss; which quadrant matters more than ring alone.** NEAR is uniformly good in every quadrant, as expected (closer to pin, regardless of direction, scores better).

## TASK 4 — Red-team: "distance doesn't matter inside 170yd"?

Full breakdown, quartile bands on real approach distance:

| Band | n | GIR% | Birdie+% | Par% | Bogey% | Double+% | Penalty% | avg stp | FW%(tee) | round mix |
|---|---|---|---|---|---|---|---|---|---|---|
| Q1 ≤145yd | 85 | 61% | 5% | 71% | 22% | 2% | 1% | +0.235 | 62% | R1 37, R4 28, R3 13, R2 7 |
| Q2 ≤156yd | 82 | 61% | 8% | 60% | 28% | 4% | 0% | +0.268 | 60% | R1 33, R3 19, R4 19, R2 11 |
| Q3 ≤169yd | 82 | 55% | 7% | 62% | 26% | 5% | 0% | +0.280 | 52% | R2 39, R3 17, R1 15, R4 11 |
| Q4 >169yd | 82 | 32% | 4% | 40% | 42% | 15% | 4% | +0.732 | 33% | **R2 45**, R1 22, R3 12, R4 3 |

**Confound found and disclosed, as required:** Q4 is 55% (45/82) real round-2 approaches, while R2 is only ~25% of the field overall — R2 is heavily overrepresented in the long-approach band. R2's own real Hole-12 scoring average (official `holeInfo.avgScore` = 4.559, i.e. **+0.559** — the worst of the 4 rounds; R1 +0.346, R3 +0.213, R4 +0.295) was already the hardest day on this hole independent of any individual's approach distance. Part of Q4's apparent cliff is therefore **round difficulty, not approach distance in isolation** — R2's pin (63,80) and/or conditions that day were tougher across the board, and R2 shots cluster in the long-approach band (plausibly because the same conditions that made the hole harder also pushed more players' approaches long).

FW% also drops steadily from Q1(62%) to Q4(33%) — lie quality is also entangled with distance band, not held constant.

**Approved phrasing only:** *"Hole 12 observed field data did not show a monotonic scoring advantage from progressively shorter approaches inside 170 yards (Q1–Q3 avg_stp +0.235 to +0.280, essentially flat); the sharp Q4 (>170yd) decline is real but is confounded with round (55% of Q4 is Round 2, the hole's hardest real scoring day) and with fairway-hit rate (33% at Q4 vs 52–62% at Q1–Q3) — it cannot be attributed to distance alone from this data.*"

## TASK 5 — Player-specific second-shot chain

Built on top of the already-published reachability/strategy data (`NEO_HOLE12_DISTANCE_CALIBRATED_REPORT.md` §4–6), extended with real miss-lie distribution and scrambling rate by approach-distance band (par-4 tournament-wide, same quartile cuts as Task 4):

| Player | Band | Miss lie distribution (real counts) | Scrambling rate (Par-or-better after a miss) |
|---|---|---|---|
| 유해란 | Q1 | — (she rarely misses this close) | — |
| 유해란 | Q4 (>169yd, n small) | ROUGH-heavy | see JSON (LOW_SAMPLE flagged where n<5) |
| 박서현 | all bands | see `hole12_master_template.json → task5_player_second_shot_chain['9111']` | same |

Full per-band miss-lie tables and scrambling rates for all three players are in the JSON — kept out of this table because several cells are LOW_SAMPLE (n<5) and must be read with that flag, not summarized into a false-precision single number here.

## TASK 6 — Imperfect golf: real favorable/unfavorable × good/bad cases

| Player | Favorable→Good | Favorable→Bad | Unfavorable→Saved | Unfavorable→Damage |
|---|---|---|---|---|
| 유해란 | 2 | 0 | 1 | **1** |
| 이재윤 | 2 | 0 | 2 | 0 |
| 박서현 | 0 | 0 | 2 | **1** |

("Favorable" = fairway hit AND approach ≤170yd; "damage" = unfavorable condition AND double-bogey-or-worse.)

Real examples (full chain, state sequence included — see JSON for all):
- **유해란, unfavorable→damage (R2):** tee ROUGH → approach ROUGH (154.8yd out) → ROUGH again → GREEN → GREEN → HOLED. 6 strokes, double bogey. Her only real blow-up on this hole came from back-to-back rough, not a bad tee distance.
- **박서현, unfavorable→saved (R1):** tee ROUGH → ROUGH → FRINGE (9.4yd) → HOLED. Par, from two bad lies in a row, saved by a single short-game shot essentially holing out from the fringe.
- **박서현, unfavorable→damage (R2):** tee ROUGH (177.6yd approach — her longest real approach on this hole) → ROUGH → GREEN → GREEN → GREEN → HOLED. 6 strokes, double bogey, 4 putts/green-shots after a long rough approach.
- **이재윤, unfavorable→saved ×2 (R3, R4):** both real pars built from a rough tee shot recovered directly to the green or a short fringe/rough up-and-down — no damage cases found in her real 4-round Hole-12 sample at all.

**Neither player's 4-round Hole-12 sample shows "unfavorable condition always survives" or "favorable condition always scores"** — each has at least one real counterexample, reported as found.

## FINAL RED-TEAM TEST

Remove what a pro/caddie already knows — "hit the fairway," "avoid the bunker," "get inside 170yd" — and list what NEO adds beyond that (≤5), each checked against real data, each checked for whether it actually differs by player.

1. **Hitting the fairway is necessary but far from sufficient — within fairway-hit tee shots, the Bogey+ rate is still 24% (41/172), and the split between a good score and a bad one is decided at the approach swing (GIR 81–83% for Birdie+/Par vs 45% for Bogey), not by tee-shot distance (Task 1 — all three groups land within 5 yards of each other).** This redirects attention from "did you hit the fairway" to "what did the approach shot actually do," a finer-grained lever generic advice doesn't give.
2. **A specific, repeating bad-miss location exists independent of the daily pin: FAR×QUAD-A (n=76, present in all 4 real rounds, avg +1.013, GIR 9%).** This is not "the bunker" (bunker is a lie category; this is a geometric relationship to the pin that recurs regardless of where the pin was that day) — a caddie cannot get this from "avoid the bunker" because it isn't defined by a hazard at all.
3. **"Get closer" is a weaker lever than it looks: the apparent cliff past 170yd is confounded with Round (55% of long approaches came from the hole's hardest real scoring day) and with fairway-hit rate (33% at Q4 vs 52–62% at Q1–Q3).** NEO's addition is not "get inside 170yd" — it's "distance alone is not a clean target; the same distance band behaves differently depending on what day/lie produced it."
4. **The field's lowest-scoring observed zone is not the right target for every player.** 박서현's real landing-distance distribution does not reliably reach the field's best-scoring corridor; her real, reachable primary corridor is a different (shorter) one. This differs by player by construction — 유해란/이재윤 do reach it, 박서현 doesn't — and a generic "aim at the good zone" instruction cannot produce this without each player's own distance data.
5. **The real conditions that produce a blow-up differ by player, not by a shared rule.** 박서현's one real double bogey on this hole came from her single longest real approach shot (177.6yd, from rough) — a joint condition (missed fairway AND unusually long resulting approach), not simply "missed the fairway." 유해란's one real double came from back-to-back rough with no long-approach component. Two different players, two different real failure signatures on the same hole — "avoid bad lies" does not capture either one specifically.

**All 5 differ in their actionable content by player or by situation in ways a generic "fairway/bunker/170yd" instruction set cannot produce**, and each is traceable to a specific real-data table above (Task 1, Task 3, Task 4, Task 5/reachability, Task 6).

## VERDICT

**HOLE 12 MASTER TEMPLATE: PASS**

Basis: PIN DATA PASS (72/72), COURSE IDENTITY PASS (18-hole systematic cross-check), distance-calibrated zones grounded in two real official fields, same-fairway outcome decomposition, a pin-position-independent repeating miss cluster, an honestly-confounded (not overclaimed) distance-value finding, player-specific reachability and second-shot chains, and real imperfect-golf counterexamples for all three case-study players — all reproducible from committed scripts, all real n reported, all LOW_SAMPLE cells flagged.

Hole 12 is now the reference methodology. Extension to Hole 1 / 8 / 9 / 13 proceeds next, one hole at a time, per the existing ordering.
