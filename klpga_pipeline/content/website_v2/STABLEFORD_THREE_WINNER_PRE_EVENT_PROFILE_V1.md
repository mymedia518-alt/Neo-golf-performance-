# NEO STABLEFORD — Three-Winner Pre-Event Player Profile Validation (2026-10-06)

Continues from `2a0bcd2` (2023/2024/2025 blind backtests, all PASS). Uses ONLY the already-acquired, SOURCE_PASS-verified prior-tournament captures (`evidence/stableford_prior_2023/2024/2025/`, 19/23/23 tournaments) and the already-built `klpga.website_v2.stableford_blind_backtest` / `stableford_backtest_snapshot` pipelines. **No frozen V1 artifact or hash was modified.** Two new, read-only analysis modules were added (`stableford_round_level_profile.py` for scoring-ceiling metrics; this report's SG figures reuse the existing `stableford_backtest_snapshot.build_event_snapshot`) — no new network access, no new data acquisition.

핵심 질문: *"방신실·김민별·김민솔은 우승 결과를 제거해도 Stableford에서 가치가 높아질 공통 선수 프로필을 가지고 있었는가?"*

**Each winner's own target-event data is completely excluded.** Cutoffs: 방신실 < 2023-10-12, 김민별 < 2024-10-10, 김민솔 < 2025-10-01 — identical to the already-verified blind-backtest cutoffs, re-used unchanged.

## Data sources and what's UNAVAILABLE

| Category | Source | Status |
|---|---|---|
| Hole outcome counts/rates | 19/23/23 real `scoreRecord` prior captures | Available, full field |
| Round-level birdie counts, round stroke totals, round Stableford points | Same captures, re-parsed at round granularity (new this turn, no new data) | Available, full field |
| SG Total + 4 components (tee-to-green, off-the-tee, approach, around-green, putting) | `historical_sg_warehouse_corrected_v2.json` (same source already used in the gate decision and blind backtests) | Available, 102/106 (2023), 105/105 (2024), 103/105 (2025) |
| **Driving Distance (yards)** | — | **UNAVAILABLE** — no real temporal-safe source in this repo (`player_stats_snapshot` schema has the column, 0 rows) |
| **Fairway Accuracy (%)** | — | **UNAVAILABLE** — same reason |
| **GIR (%)** | — | **UNAVAILABLE** — same reason; SG Tee-to-Green is used as a partial, non-equivalent proxy below, explicitly labeled as such |
| **Par5-specific scoring** | — | **UNAVAILABLE** — no per-par-type official stat captured anywhere in this repo |
| **Average Score (official scoring average)** | — | **UNAVAILABLE** as an official stat; the round-level data above gives a real but differently-defined substitute (sub-70 round rate) |

## 1-3. Full metric table (value / percentile within that year's own Stableford pre-event field)

Percentile = this player's standing among that year's covered field (106/105/105 players), 0–100, higher = better **after** orienting each metric to its hypothesized "good" direction (bogey/double+ rates inverted; `round_points_variance` oriented HIGH-is-better per H6's own framing — Stableford caps downside at −3/hole but uncaps upside, so a scoring-ceiling/burst profile is the hypothesized advantage, not stability — decided before computing, not after).

| Metric | 방신실 2023 | pct | 김민별 2024 | pct | 김민솔 2025 | pct | Commonality |
|---|---|---|---|---|---|---|---|
| Total holes (pre-event) | 936 | — | 1,116 | — | 576 | — | n/a (sample size, see Red Team) |
| Rounds | 52 | — | 62 | — | 32 | — | n/a |
| Tournaments | 17 | — | 19 | — | 9 | — | n/a |
| Albatross rate | 0.0 | 100.0 | 0.0 | 100.0 | 0.0 | 100.0 | **CORE (degenerate — see note)** |
| Eagle rate | 0.32% | 98.10 | 0.18% | 80.77 | 0.69% | 100.0 | CORE (weak absolute magnitude) |
| Birdie rate | 19.55% | 98.10 | 17.92% | 78.85 | 22.05% | 97.12 | **CORE** |
| Par rate | 64.74% | 17.14 | 68.73% | 69.23 | 62.33% | 2.88 | NOT COMMON |
| Bogey rate | 12.29% | 86.67 | 12.01% | 83.65 | 12.67% | 67.31 | SUPPORTING |
| Double+ rate | 3.10% | 17.14 | 1.17% | 83.65 | 2.26% | 26.92 | NOT COMMON |
| Birdie+ rate (eagle+albatross+birdie) | 19.87% | 99.05 | 18.10% | 79.81 | 22.74% | 98.08 | **CORE** |
| Bogey+Double+ rate | 15.38% | 67.62 | 13.17% | 84.62 | 14.93% | 58.65 | SUPPORTING |
| Birdie+/Bogey+ ratio | 1.292 | 87.62 | 1.374 | 85.58 | 1.523 | 80.77 | **CORE** |
| Expected Stableford pts/hole | +0.191 | 87.62 | +0.212 | 85.58 | +0.281 | 92.31 | **CORE** |
| Avg birdies/round | 3.52 | 98.10 | 3.23 | 78.85 | 3.97 | 97.12 | **CORE** |
| Max birdies in one round | 7 | 77.14 | 8 | 89.42 | 9 | 94.23 | **CORE** |
| Top-10%-rounds avg birdies | 6.33 | 85.71 | 5.86 | 65.38 | 7.75 | 97.12 | SUPPORTING |
| Sub-70 round rate | 28.85% | 92.38 | 25.81% | 83.65 | 34.38% | 87.50 | **CORE** |
| Round Stableford-points variance | 27.40 | 83.81 | 21.02 | 58.65 | 43.68 | 99.04 | SUPPORTING |
| High-scoring round rate (≥10 pts/round) | 11.54% | 93.33 | 8.06% | 77.88 | 21.88% | 95.19 | **CORE** |
| SG Total | +1.118 | 85.15 | +1.049 | 86.54 | +1.534 | 89.22 | **CORE** |
| SG Tee-to-Green (GIR/ball-striking proxy) | +1.809 | 97.03 | +1.587 | 94.23 | +1.146 | 81.37 | **CORE** |
| SG Off-the-Tee (driving proxy) | +0.198 | 60.40 | +0.580 | 92.31 | +1.124 | 99.02 | SUPPORTING |
| SG Approach | +1.375 | 97.03 | +1.089 | 96.15 | +0.204 | 60.78 | SUPPORTING |
| SG Around-the-Green | +0.238 | 88.12 | −0.082 | 38.46 | −0.183 | 18.63 | NOT COMMON |
| SG Putting | −0.691 | 10.89 | −0.536 | 15.38 | +0.391 | 83.33 | NOT COMMON |
| Driving Distance | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE |
| Fairway Accuracy | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE |
| GIR (official %) | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE |
| Par5 scoring | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE | — | UNAVAILABLE |

**Classification rule applied exactly as predeclared**: CORE = 3/3 in top 25% (percentile ≥75) same direction; SUPPORTING = 2/3 in top 25%, or 3/3 above the 50th percentile but not strongly; NOT COMMON = real player-to-player spread crossing the field average in different directions; no metric here required post-event data, so none fall in POST-HOC/REJECT.

**Degenerate-CORE note**: `albatross_rate` registers as CORE only because every one of the 106/105/105 covered players — not just the three winners — has exactly 0 albatrosses in these captures. A 100th-percentile tie among an entire field with zero variance is not a real shared elite trait; it is reported here for completeness and immediately discounted below.

## 4. Field-normalized comparison — already embedded above (percentile column)

## 5. Control comparison (separating "winner-only" from "generally Stableford-valuable")

| | #1 pre-event Stableford rank (did NOT win) | Winner's own rank | Ordinary-high / Stableford-low control |
|---|---|---|---|
| 2023 | 이예원 (rank 1, birdie 19.49%, bogey 10.08%, net +0.281) | 방신실 (rank 14) | 임채리 (ordinary rank 45 → Stableford 57; birdie 11.11%, bogey 13.89%) |
| 2024 | 윤이나 (rank 1, birdie 22.99%, bogey 10.17%, net +0.338) | 김민별 (rank 16) | 유효주 (ordinary 78 → Stableford 85; birdie 12.85%, bogey 15.54%) |
| 2025 | 유현조 (rank 1, birdie 22.37%, bogey 9.70%, net +0.348) | 김민솔 (rank 9) | 신다인 (ordinary 38 → Stableford 45; birdie 16.18%, bogey 11.36%) |

**Key finding**: the #1 pre-event-ranked player each year — who did NOT win — has a birdie/bogey profile essentially indistinguishable in character from the eventual winner (same high-birdie, moderate-bogey shape). This directly separates "traits that make a player Stableford-valuable" (shared by many players, including non-winners) from "traits that predict a win" (which these pre-event metrics do not claim to do — see the blind-backtest reports' own winner-rank results: 14th, 16th, 9th, never 1st). The ordinary-high/Stableford-low controls show consistently lower birdie rates and (in 2/3 years) higher bogey rates than either the winners or the #1-ranked non-winners — confirming the CORE metrics discriminate real field variation, not noise.

## 6. Hypothesis tests (predeclared, attacked adversarially)

| | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | 장타(Driving Distance)가 공통점이다 | **UNAVAILABLE** | No real temporal-safe Driving Distance source exists in this repo for any of the 3 cutoffs |
| H2 | 높은 Birdie rate가 공통점이다 | **SUPPORTED** | Birdie rate, Birdie+ rate, avg birdies/round, max birdies/round all CORE (3/3 top-25%); absolute rates genuinely elevated (17.9–22.1%, vs field medians well below) |
| H3 | 높은 GIR/Tee-to-Green이 공통점이다 | **PARTIAL** | Official GIR% is UNAVAILABLE; the SG Tee-to-Green proxy IS CORE (97.03/94.23/81.37 — all top-25%), but a Strokes-Gained composite is not the same statistic as GIR%, so this is reported as partial support via proxy, not a direct confirmation |
| H4 | 낮은 Bogey/Double+가 공통점이다 | **REJECTED (for Double+), PARTIAL (for Bogey)** | Double+ rate is NOT COMMON — 방신실 and 김민솔 are actually BELOW the field median on avoiding double+ (17.14/26.92 percentile), only 김민별 is strong (83.65); Bogey rate alone is SUPPORTING, not CORE. The honest finding: these three winners are not uniformly bogey/double+-avoiders — two of three tolerate elevated double+ risk |
| H5 | Par5 scoring upside가 공통점이다 | **UNAVAILABLE** | No per-par-type official stat exists in this repo |
| H6 | Scoring ceiling/burst(안정성보다)가 공통점이다 | **SUPPORTED** | High-scoring-round rate and max-birdies-per-round are both CORE (3/3 top-25%); round-points variance itself is only SUPPORTING (2/3, 2024's 58.65 percentile is middling) — but the convergence of 3 independent ceiling-type metrics, 2 of them CORE, supports the hypothesis overall, with the caveat that raw variance alone does not reach the strict 3/3 threshold |
| H7 | Fairway Accuracy는 핵심 공통조건이 아니다 | **UNAVAILABLE (cannot test directly); not contradicted by the available proxy** | Official Fairway Accuracy% is UNAVAILABLE. SG Off-the-Tee (a distance+accuracy blend, not accuracy alone) is only SUPPORTING (2023's 60.40 percentile is middling) — consistent with H7's claim that pure accuracy is not a strong common thread, but this cannot be directly confirmed without the real stat |

## 7. 세 선수의 CORE 공통특성

1. **Birdie-making ability, in every form measured**: birdie rate, birdie+ rate, avg birdies/round, max birdies/round, sub-70 round rate, high-scoring-round rate — all CORE, all 3/3 in the top 25% of their own year's field.
2. **Birdie+/Bogey+ ratio** (the asymmetric mechanism already found in the blind backtests) — CORE, 80.77–87.62 percentile.
3. **Expected Stableford points per hole itself** — CORE (87.62/85.58/92.31), i.e., the formula's own output correctly flags all three as strong, pre-event, without knowing they would win.
4. **SG Total and SG Tee-to-Green** — CORE, suggesting genuine all-around (and specifically tee-to-green/ball-striking-proxy) strength, not just a hot-putter or short-game illusion.
5. (Degenerate) Albatross rate — technically CORE but meaningless (zero variance field-wide); not counted as a real finding.

## 8. SUPPORTING 특성

Bogey rate, Bogey+Double+ rate, top-10%-rounds avg birdies, round-points variance, SG Off-the-Tee, SG Approach — each shows a real elevated pattern in 2/3 winners or a weak-but-positive pattern in all 3, but does not clear the strict 3/3-top-25% CORE bar.

## 3. (continued) 공통점이라고 생각했지만 탈락한 특성

- **Low Double+ rate** — actively rejected: 2 of 3 winners (방신실, 김민솔) are BELOW their field's median on double+ avoidance, not above it. A naive "winners avoid blow-up holes" narrative does not survive contact with the real per-player data.
- **Par rate** — NOT COMMON, wildly inconsistent (2.88th to 69.23rd percentile) — unsurprising since par rate is largely the complement of the other rates, but worth stating explicitly rather than assuming it tracks birdie rate.
- **SG Around-the-Green and SG Putting** — NOT COMMON, in fact near-opposite patterns across years (방신실 strong putting-adjacent/around-green, weak putting; 김민솔 the reverse). No consistent short-game signature.

## 4. 세 선수 각각의 다른 점

- **방신실 (2023)**: the only winner with a real elevated Double+ rate (3.10%, 17th percentile — i.e., worse than most of the field at avoiding blow-ups) and the only one with strong SG Around-the-Green (88th percentile) paired with weak Putting (11th percentile) — a ball-striking/short-game-adjacent profile rather than a pure putter.
- **김민별 (2024)**: the most "conventional" profile of the three — her birdie rate (78.85th percentile) and scoring-ceiling metrics (round variance only 58.65th percentile) are the weakest of the three winners on nearly every CORE metric, yet she still clears every CORE threshold — the marginal case that keeps several metrics at SUPPORTING rather than CORE.
- **김민솔 (2025)**: the most extreme scoring-ceiling profile (99.04th percentile round-points variance, 95.19th percentile high-scoring-round rate) and by far the smallest pre-event sample (32 rounds, 9 tournaments — under half of the other two winners') — her numbers are real but rest on the thinnest evidence base of the three.

## 5. 2026 후보선수 탐색에 사용 가능한 변수

Birdie rate / Birdie+ rate / avg birdies per round / max birdies per round / sub-70 round rate / high-scoring-round rate / Birdie+:Bogey+ ratio / expected Stableford points per hole / SG Total / SG Tee-to-Green — all CORE, all independently computable pre-event from the same real `scoreRecord` + SG-warehouse pipeline already built.

## 6. 사용하면 안 되는 변수

- **Low Double+ rate / Double+ avoidance** — actively contradicted by 2 of 3 winners; using it to screen OUT high-double+ players would have excluded 방신실 and 김민솔.
- **Par rate, SG Around-the-Green, SG Putting** — NOT COMMON, no consistent direction; using any of these as a screening filter would be fitting noise.
- **Driving Distance, Fairway Accuracy, GIR%, Par5-specific scoring, official Average Score** — UNAVAILABLE; any claim about these for 2026 candidates would be fabricated, not evidenced.
- **Albatross rate** — degenerate (zero variance in every real sample seen); carries no discriminating information.

## 7. Red Team

| Check | Result |
|---|---|
| Target-event leakage | **PASS** — every metric above is computed exclusively from the same pre-cutoff prior-tournament captures already leakage-verified for the blind backtests; no winner's own Stableford-event round ever enters these numbers |
| Future-season leakage | **PASS** — same manifests, same season/month-bounded sources as the already-verified blind backtests; no change |
| Survivorship bias | **DISCLOSED, addressed via controls** — these are 3 winners who, by definition, survived to win; section 7's control comparison (the #1-ranked non-winner shares the same profile shape) is the direct mitigation, not a claim this report "solves" survivorship bias entirely |
| Winner-selection bias | **DISCLOSED, same mitigation** — see above; a true test would need a random sample of the full field, not just winners + 2 controls per year, which is a real scope limit of this report |
| Small sample | **FOUND, DISCLOSED** — 김민솔's 2025 pre-event sample (32 rounds / 9 tournaments) is roughly half of 방신실's (52/17) and about half of 김민별's (62/19); her most extreme-looking numbers (round variance, high-scoring rate) carry more sampling noise than the other two winners' |
| Unequal sample size | **FOUND, SAME AS ABOVE** — 17/19/9 tournaments is a real, uncorrected asymmetry; no normalization attempted beyond using rate-based (not count-based) metrics throughout |
| Player identity collision | **DISCLOSED, unprovable** — same name-string-only limitation carried from every prior Red Team section this session; no playerCode available in `scoreRecord` |
| Missing hole outcomes | **PASS** — every round record used has exactly 18 real hole cells; the extractor discards (never pads) any row that doesn't |
| SG availability differences by year | **FOUND, MINOR** — 102/106 (2023), 105/105 (2024), 103/105 (2025) SG-covered; the 4 uncovered 2023/2025 players are not any of the 3 winners, so this does not affect the headline table, but is disclosed for completeness |
| Field normalization consistency | **PASS** — identical percentile method (rank within that year's own Stableford pre-event field, same direction convention) applied uniformly across all 3 years and all metrics |
| Metric definition drift | **PASS** — every metric is computed by the same shared function across all 3 years (no year-specific logic branches) |
| CRLF/hash issue affecting frozen artifacts | **PASS, VERIFIED** — this turn touched no `*_FROZEN_PREEVENT_SNAPSHOT_V1.json` file (confirmed via `git diff --stat`); the already-disclosed 2023/2025 chain-of-custody findings remain exactly as reported in their own gate reports and are unaffected by this analysis |

## 8. Final Gate

**PARTIAL**

Real, consistent CORE commonality was found across all three independent winners on birdie-making ability (in every form measured), the Birdie+/Bogey+ asymmetry ratio, the Stableford value formula's own output, and overall ball-striking (SG Total/Tee-to-Green) — none of this was assumed, all of it computed fresh from pre-event-only data with the winner's own tournament completely excluded. But the hypothesis that "low Bogey/Double+" is part of the common profile is actively REJECTED by the real data (2 of 3 winners tolerate elevated double+ risk), half of the originally-named ball-striking variables (Driving Distance, Fairway Accuracy, GIR%, Par5 scoring) are UNAVAILABLE and were not estimated, and the control comparison shows the CORE traits are shared by non-winners too — meaning they describe "a strong Stableford-value profile," not "a guaranteed winner." **Not reported as PASS** because several originally-requested variables could not be tested at all, and not reported as FAIL because the metrics that WERE computable show a real, non-trivial, three-for-three consistent signal.
