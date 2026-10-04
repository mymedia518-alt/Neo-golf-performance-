# NEO Blue Heron Shot Deep Dive — 하이트진로 챔피언십 2026100005

Derived analysis layer built on top of the immutable, already-validated
Shot Tracker RAW/normalized data (`collector-output/2026100005-shot-tracker-full-field`).
This layer is **read-only against RAW** — nothing in the source table was
modified to produce it. 6 confirmed SOURCE_GAP player-rounds are carried
as explicit NULL rows throughout; none were estimated or interpolated.

## Scope confirmed from real data

| | |
|---|---|
| 분석 가능한 선수 수 | **107** / 108 (전체 필드) |
| 분석 player-hole 수 (실데이터) | **5,958** |
| SOURCE_GAP hole-rows (NULL, 추정 없음) | 108 (6 player-round × 18홀) |
| 총 shots | **24,993** |

## Methodology (defined before computing results)

- **par**: `holeInfo.stdScore`, extracted directly from the real RAW response files and confirmed identical across all 72 (round,hole) real samples checked — never assumed.
- **GIR**: literal — first shot reaching `state_code == "3"` (GREEN) must occur by shot number ≤ par−2. `state_code == "12"` (FRINGE) never counts.
- **fairway hit / tee miss state**: computed only for par-4/par-5 holes, from shot #1's `state_code` (1=FAIRWAY else ROUGH/BUNKER/PENALTY/OB/OTHER).
- **LOW_SAMPLE flag**: any metric with n < 5.
- **Hole classification thresholds**: median birdie-or-better rate, median bogey-or-worse rate, and median FW-miss cost-vs-FW-hit (in strokes) across the 18 holes — computed once, applied mechanically, never adjusted after seeing the per-hole results.
  - median birdie-or-better rate = 0.0982
  - median bogey-or-worse rate = 0.2583
  - median FW-miss cost vs FW-hit = 0.3260 strokes
  - ATTACK: birdie rate > median AND miss penalty ≤ median
  - DEFEND: bogey rate > median AND miss penalty > median
  - CONTROL: everything else
  - Par-3 holes (no fairway target) are classified on birdie/bogey rate alone against the same medians.
- **Hypothesis eligibility**: a player needs ≥10 par-4/5 holes analyzed and ≥3 FW-miss holes to be included in the correlation/group analysis. All 107 analyzable players met this bar.

## Overall transition metrics (aggregate across all real holes, n shown)

| Transition | Rate | n |
|---|---|---|
| FW Hit → GIR | 68.9% | 2,802 |
| FW Hit → GIR Miss | 31.1% | 2,802 |
| Rough → GIR | 42.5% | 1,668 |
| Rough → GIR Miss | 57.6% | 1,668 |
| Bunker → GIR | 37.2% | 129 |
| Other Tee Miss → GIR | 0.0% | 35 (LOW_SAMPLE) |
| **FW Miss → GIR** | **41.3%** | **1,832** |
| FW Hit → Par-or-Better | 81.4% | 2,802 |
| FW Miss → Par-or-Better | 61.7% | 1,832 |
| **GIR Miss → Par Save** | **49.3%** | **2,348** |
| Rough → Par Save | 63.2% | 1,668 |
| Bunker → Par Save | 58.9% | 129 |

## Biggest miss-penalty hole

**Hole 8 (par 4): FW Miss costs +0.550 strokes vs FW Hit (n=143, not LOW_SAMPLE)** — the largest reliable miss penalty on the course. Hole 8 also has the field's 2nd-highest bogey-or-worse rate (34.4%) and is classified DEFEND. (One single-occurrence Penalty/OB sample on hole 18 showed a nominally larger +3.05 gap, but n=1 — flagged LOW_SAMPLE and excluded from this headline claim.)

## Course strategy classification (18 holes)

- **ATTACK** (6): holes 2, 4, 7, 14, 16, 18
- **CONTROL** (8): holes 1, 3, 5, 9, 11, 13, 15, 17
- **DEFEND** (4): holes 6, 8, 10, 12

Full per-hole numbers (birdie/bogey rate, miss penalty, thresholds) are in `neo_course_strategy.csv`.

## Hypothesis test

> "블루헤런에서는 페어웨이 적중 자체뿐 아니라 페어웨이를 놓친 뒤에도 GIR을 살리는 능력이 최종 스코어를 강하게 갈랐다."

Player-level correlations (n=107 eligible players) against each player's average score-to-par:

| Metric | r | n |
|---|---|---|
| FW hit rate vs score | −0.511 | 107 |
| **GIR rate vs score** | **−0.821** | 107 |
| **FW-Miss → GIR survival vs score** | **−0.554** | 107 |
| FW-Hit → GIR vs score | −0.567 | 107 |
| Rough → GIR vs score | −0.519 | 107 |
| GIR-Miss → Par-Save vs score | −0.770 | 107 |

Group comparison (bottom half vs top half of players by FW-Miss→GIR survival rate, n=53 each): average score-to-par **+0.327** (low-survival group) vs **+0.169** (high-survival group) — a **0.158-stroke/hole** gap in the hypothesized direction.

**Verdict: CONFIRMED.**

FW-Miss→GIR survival (r = −0.554) correlates with final score *more strongly* than plain fairway-hit rate alone (r = −0.511) — meaning the ability to still find the green after missing the fairway carries real, independent explanatory power, not just redundant with hitting fairways in the first place. The honest caveat: overall GIR rate (r = −0.821) and GIR-Miss→Par-Save (r = −0.770) are the single strongest predictors in this dataset — recovery after a GIR miss (the short game) matters even more than recovery after a fairway miss specifically. The hypothesis as stated is supported, but is a secondary driver underneath overall GIR performance, not the dominant one.

## SOURCE_GAP impact

6 player-rounds (108 hole-rows, 1.78% of all player-hole combinations) have **no real shot-level data at the source** — confirmed via both the group and per-player endpoints (`diagnose_result.json`), not a collector defect. These are carried as explicit NULL rows in every CSV and excluded from every rate/average computed above. Given they represent <2% of the dataset and are concentrated in only 2 of the 4 rounds, they do not materially change any headline finding, but no value for them was ever estimated.

## Files

- `neo_player_hole_shot_derived.csv` — 6,066 rows (5,958 real + 108 SOURCE_GAP), one per (player, round, hole).
- `neo_player_event_shot_metrics.csv` — 107 rows, one per analyzable player.
- `neo_hole_shot_metrics.csv` — 18 rows, one per hole.
- `neo_miss_penalty.csv` — 18 rows, one per hole, with LOW_SAMPLE flags.
- `neo_course_strategy.csv` — 18 rows, classification + the exact thresholds used.
- `hypothesis_report.json` — full correlation/group-comparison detail behind the verdict above.
