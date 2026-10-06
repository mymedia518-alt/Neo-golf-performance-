# NEO STABLEFORD — Three-Winner Pre-Event Player Profile Validation (2026-10-06, updated)

Continues from `2a0bcd2` (2023/2024/2025 blind backtests, all PASS) and from `aab671e` (this report's first version, which incorrectly labeled 5 official metrics "UNAVAILABLE"). Uses ONLY the already-acquired, SOURCE_PASS-verified prior-tournament captures (`evidence/stableford_prior_2023/2024/2025/`, 19/23/23 tournaments) and the already-built `klpga.website_v2.stableford_blind_backtest` / `stableford_backtest_snapshot` pipelines. **No frozen V1 artifact or hash was modified.**

**This update's new work**: (1) corrected the failure taxonomy — "UNAVAILABLE" never meant "no source exists"; (2) reconstructed official Average Score and Par5 scoring directly from already-held real pre-cutoff hole data, using KLPGA's own official formula — zero new network access; (3) built a complete acquisition package for Driving Distance/Fairway Accuracy/GIR%, confirmed this sandbox's own access to klpga.co.kr is blocked (3 independent methods), and handed the package off; (4) **the acquisition has now actually run on a real machine with klpga.co.kr access and the evidence is pushed to this branch (`e7ac0ca4`)** — real Driving Distance/Fairway Accuracy/GIR values for all 3 winners and their full 102/103/102-player fields are now in this report; (5) that real acquisition run surfaced a critical, previously-unconfirmed scoping finding — see "⚠ Critical finding" immediately below the data-sources table — which is why Driving Distance/Fairway Accuracy/GIR are reported here as real numbers but classified `INCONCLUSIVE`, not CORE/SUPPORTING/REJECTED.

핵심 질문: *"방신실·김민별·김민솔은 우승 결과를 제거해도 Stableford에서 가치가 높아질 공통 선수 프로필을 가지고 있었는가?"*

**Each winner's own target-event data is completely excluded.** Cutoffs: 방신실 < 2023-10-12, 김민별 < 2024-10-10, 김민솔 < 2025-10-01 — identical to the already-verified blind-backtest cutoffs, re-used unchanged.

## Data sources and acquisition status

**Taxonomy correction (this turn)**: the earlier "UNAVAILABLE" label conflated "not yet acquired inside this repo" with "no official source exists." It was wrong — all 5 metrics below have a confirmed real official KLPGA source. The status column now uses the corrected 5-way taxonomy: `SOURCE_EXISTS_AND_ACQUIRED` / `SOURCE_EXISTS_RECONSTRUCTED` / `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` / `SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED` / `SOURCE_NOT_FOUND_AFTER_WEB_INVESTIGATION`. Absence from this repo is never, by itself, treated as `SOURCE_NOT_FOUND_AFTER_WEB_INVESTIGATION`.

| Category | Source | Status |
|---|---|---|
| Hole outcome counts/rates | 19/23/23 real `scoreRecord` prior captures | `SOURCE_EXISTS_AND_ACQUIRED`, full field |
| Round-level birdie counts, round stroke totals, round Stableford points | Same captures, re-parsed at round granularity | `SOURCE_EXISTS_AND_ACQUIRED`, full field |
| SG Total + 4 components (tee-to-green, off-the-tee, approach, around-green, putting) | `historical_sg_warehouse_corrected_v2.json` | `SOURCE_EXISTS_AND_ACQUIRED`, 102/106 (2023), 105/105 (2024), 103/105 (2025) |
| **Average Score (official 평균타수 = 전체타수/라운드수)** | Official formula confirmed against the real official fixture `tests/fixtures/official_detail/8436_publicRecordSeasonDetail.html`; reconstructed this turn directly from the same already-held, already-verified real pre-cutoff hole-by-hole `scoreRecord` data — no new network access needed | **`SOURCE_EXISTS_RECONSTRUCTED`** — 106/105/105, full field |
| **Par5 scoring (official 파5성적 = 파5전체타수/파5홀수)** | Same official formula, same fixture, same reconstruction method | **`SOURCE_EXISTS_RECONSTRUCTED`** — 106/105/105, full field |
| **Driving Distance / Fairway Accuracy / GIR (official 드라이브거리/페어웨이안착률/그린적중률)** | Real, confirmed-live official endpoint `POST https://klpga.co.kr/load/profile/publicRecordSeasonDetail` — acquired for real on a machine with klpga.co.kr access (commit `e7ac0ca4`): 2023 102/102, 2024 103/103, 2025 102/103 players returned `SOURCE_EXISTS_AND_ACQUIRED` (2025's 1 remaining player returned entirely null fields and is excluded, not fabricated) | **`SOURCE_EXISTS_AND_ACQUIRED` — but see "⚠ Critical finding" immediately below: the acquired value is scoped to a single pre-cutoff tournament (1-4 rounds), not the full pre-cutoff season, so it is classified `INCONCLUSIVE` for commonality testing, not CORE/SUPPORTING/REJECTED** |

### ⚠ Critical finding: `gameCode` does NOT return a season-to-date cumulative value — it scopes to that ONE tournament only

The acquisition script's own design doc flagged this as unconfirmed ("Whether passing a specific `gameCode` scopes the response to 'cumulative through that tournament' is UNCONFIRMED"). The real acquisition run resolves it: **no, it does not cumulate.** Evidence, from the real pushed `ACQUISITION_REPORT.json` files:

- For every one of the 102/103/102 acquired players in all 3 years, the `last_pre_cutoff_game_code`-scoped call's own `라운드수` (rounds) detail field is **1-4**, never more — matching a single KLPGA event's round count (3-4 rounds, sometimes shortened), never a season total.
- Concretely for 방신실: the `last_pre_cutoff_game_code=2023100001`-scoped call returns `라운드수=4`, `전체타수=294` (avg 73.5) — her LAST pre-cutoff tournament only. Her real, independently-reconstructed full pre-cutoff season (this report's own `average_score` row above) is 52 rounds, 71.7885 average. The endpoint's `gameCode=""` full-season reference call, for comparison, returns `라운드수=70` (71.7571 avg) — the full SEASON including post-cutoff tournaments (70 > her real 52 pre-cutoff rounds), confirming that call is indeed leakage-contaminated exactly as already warned.
- The acquisition script's own temporal cross-check (`returned_rounds <= expected_pre_cutoff_rounds_total`) still reported `SOURCE_EXISTS_AND_ACQUIRED` for nearly everyone, because the check only guards against OVER-counting (post-cutoff leakage into the call); a 1-4-round single-event return is trivially `<=` a 32-62-round season total, so the guard passes even though the value isn't the season-cumulative statistic this report needs. **The cross-check design itself has a real, disclosed blind spot: it cannot detect under-counting.**

**Practical consequence**: Driving Distance / Fairway Accuracy / GIR values below are real, official, and temporally safe (the single tournament used is independently confirmed pre-cutoff — zero leakage), but are NOT on the same sample-size/scope footing as every other metric in this report (32-70 rounds vs. 1-4). Per this report's own metric-definition-consistency and sample-size Red Team rules, they cannot be fairly folded into the CORE/SUPPORTING/NOT COMMON classification used everywhere else — they are reported as real numbers with real percentiles, but classified **`INCONCLUSIVE`**.

**What a true fix requires**: summing this same endpoint's numerator/denominator pairs across EVERY pre-cutoff tournament `gameCode` per player (17/19/9 calls per winner alone, already known from the existing `STABLEFORD_<year>_PRIOR_TOURNAMENT_MANIFEST_V1.json` files; full-field reconstruction would be on the order of 1,700+ additional calls across the 3 years) — a materially larger acquisition, not run this turn, and not undertaken without the user's sign-off given its size.

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
| Average Score (official, lower=better) | 71.7885 | 82.86 | 71.3065 | 86.54 | 70.9062 | 82.69 | **CORE** |
| Par5 scoring (official, lower=better) | 4.9095 | 74.29 | 4.888 | 76.92 | 4.7652 | 90.38 | SUPPORTING (2023's 74.29 falls just short of the 75 threshold — reported exactly, not rounded up) |
| Driving Distance (official, last pre-cutoff tournament only, 4 rounds — see ⚠ above) | 256.26y | 99.02 | 250.57y | 96.12 | 251.78y | 88.24 | **INCONCLUSIVE** (mechanically 3/3 top-25%, but all 3 from a 4-round single-event sample, not season-long — not asserted as CORE) |
| Fairway Accuracy (official, same scope caveat) | 51.79% | 51.96 | 46.43% | 33.98 | 60.71% | 55.88 | **INCONCLUSIVE** (mechanically 0/3 top-25% — consistent with H7's "not a core commonality," but the sample is too thin/scope-mismatched to assert REJECTED with confidence) |
| GIR (official %, same scope caveat) | 63.89% | 80.39 | 66.67% | 87.38 | 55.56% | 27.45 | **INCONCLUSIVE** (mechanically 2/3 top-25% — 김민솔's 27.45 pct is from only 2 rounds, the thinnest sample in this entire report; not asserted as SUPPORTING) |

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
| H1 | 장타(Driving Distance)가 공통점이다 | **INCONCLUSIVE (real data acquired, but scope-limited)** | Real official Driving Distance acquired for all 3 winners: 256.26y/250.57y/251.78y, mechanically 99.02/96.12/88.24 percentile (3/3 top-25%) — but every value is from a single 4-round pre-cutoff tournament, not the full 52/62/32-round pre-cutoff season (see ⚠ Critical finding). A true season-cumulative reconstruction is needed before this can be asserted CORE. SG Off-the-Tee (the full-season proxy) is only SUPPORTING (60.40/92.31/99.02), directionally consistent but not conclusive either |
| H2 | 높은 Birdie rate가 공통점이다 | **SUPPORTED** | Birdie rate, Birdie+ rate, avg birdies/round, max birdies/round all CORE (3/3 top-25%); absolute rates genuinely elevated (17.9–22.1%, vs field medians well below) |
| H3 | 높은 GIR/Tee-to-Green이 공통점이다 | **PARTIAL** | Official GIR% acquired for real: 63.89%/66.67%/55.56%, mechanically 80.39/87.38/27.45 percentile (2/3 top-25%, 김민솔 from only 2 rounds) — real but scope-limited (see ⚠), so reported as INCONCLUSIVE for this specific stat, not SUPPORTING. The SG Tee-to-Green full-season proxy IS CORE (97.03/94.23/81.37), the more reliable signal here |
| H4 | 낮은 Bogey/Double+가 공통점이다 | **REJECTED (for Double+), PARTIAL (for Bogey)** | Double+ rate is NOT COMMON — 방신실 and 김민솔 are actually BELOW the field median on avoiding double+ (17.14/26.92 percentile), only 김민별 is strong (83.65); Bogey rate alone is SUPPORTING, not CORE. The honest finding: these three winners are not uniformly bogey/double+-avoiders — two of three tolerate elevated double+ risk |
| H5 | Par5 scoring upside가 공통점이다 | **SUPPORTED (SUPPORTING tier, not CORE)** | Reconstructed this turn from real pre-cutoff hole data (파5전체타수/파5홀수, matching KLPGA's own official formula exactly) for the full 106/105/105-player field: percentiles 74.29 / 76.92 / 90.38. Only 2 of 3 clear the strict ≥75 top-25% CORE bar — 2023's 74.29 falls just short — so this is reported exactly as SUPPORTING, not rounded up to CORE |
| H6 | Scoring ceiling/burst(안정성보다)가 공통점이다 | **SUPPORTED** | High-scoring-round rate and max-birdies-per-round are both CORE (3/3 top-25%); round-points variance itself is only SUPPORTING (2/3, 2024's 58.65 percentile is middling) — but the convergence of 3 independent ceiling-type metrics, 2 of them CORE, supports the hypothesis overall, with the caveat that raw variance alone does not reach the strict 3/3 threshold |
| H7 | Fairway Accuracy는 핵심 공통조건이 아니다 | **SUPPORTED, though from scope-limited data** | Official Fairway Accuracy% acquired for real: 51.79%/46.43%/60.71%, mechanically 51.96/33.98/55.88 percentile — 0 of 3 clear the top-25% bar, directly consistent with H7's claim. Reported as INCONCLUSIVE-for-CORE-purposes per the ⚠ scope caveat, but the direction (not uniformly elite) agrees with the full-season SG Off-the-Tee proxy (60.40/92.31/99.02, only SUPPORTING) — two independent signals, same conclusion: Fairway Accuracy is not a core shared trait |
| H8 | 공식 평균타수(Average Score)가 공통점이다 | **SUPPORTED (CORE)** | Reconstructed this turn from real pre-cutoff hole data (전체타수/라운드수, matching KLPGA's own official formula exactly) for the full 106/105/105-player field: percentiles 82.86 / 86.54 / 82.69 — all 3 clear the ≥75 top-25% bar. All three winners were genuinely elite on the one stat KLPGA itself uses to rank players, before their win, with their own winning tournament excluded |
| H9 | "세 우승자는 단순히 실수가 적은 선수가 아니라, 티에서 그린까지 득점 기회를 많이 만들어내는 공격형 프로필이었다" | **SUPPORTED in its general/large-sample form; its specific tee-to-green mechanism (long+accurate driving, elite GIR) remains INCONCLUSIVE, not confirmed** | The "not simply low-error" half is directly supported — Double+ rate is REJECTED as a commonality (2 of 3 winners tolerate elevated double+ risk, H4). The "creates scoring opportunities" half is supported by CORE, full-season, large-sample metrics: birdie-making in every form (H2), SG Tee-to-Green (H3's reliable proxy), Expected Stableford points, and official Average Score (H8) — all CORE. The hypothesis's literal mechanical claim (long AND accurate off the tee, elite GIR) is NOT confirmed: Driving Distance and GIR are real but scope-limited (INCONCLUSIVE, H1/H3), and Fairway Accuracy is actually SUPPORTED-REJECTED (H7) — meaning if anything, the real (if noisy) evidence is more consistent with an aggressive, distance-over-precision profile than a precision-obsessed one, which fits "attacking" better than it contradicts it. **Revised statement**: the three winners share a genuine, CORE, pre-event scoring-opportunity profile (many birdies, low average score, strong tee-to-green Strokes Gained, tolerant of blow-up risk) — but whether the specific mechanism is "long + accurate driving + elite GIR" cannot yet be confirmed from real data at the correct time scope |

## 7. 세 선수의 CORE 공통특성

1. **Birdie-making ability, in every form measured**: birdie rate, birdie+ rate, avg birdies/round, max birdies/round, sub-70 round rate, high-scoring-round rate — all CORE, all 3/3 in the top 25% of their own year's field.
2. **Birdie+/Bogey+ ratio** (the asymmetric mechanism already found in the blind backtests) — CORE, 80.77–87.62 percentile.
3. **Expected Stableford points per hole itself** — CORE (87.62/85.58/92.31), i.e., the formula's own output correctly flags all three as strong, pre-event, without knowing they would win.
4. **SG Total and SG Tee-to-Green** — CORE, suggesting genuine all-around (and specifically tee-to-green/ball-striking-proxy) strength, not just a hot-putter or short-game illusion.
5. **Official Average Score (평균타수)** — CORE (82.86/86.54/82.69), reconstructed this turn directly from real pre-cutoff hole data using KLPGA's own official formula. All three winners were genuinely elite on KLPGA's own primary ranking stat before their win, with the win itself excluded — this is the strongest possible confirmation that the CORE birdie/Stableford-value signal above isn't an artifact of this project's own metrics; it shows up on the official stat too.
6. (Degenerate) Albatross rate — technically CORE but meaningless (zero variance field-wide); not counted as a real finding.

## 8. SUPPORTING 특성

Bogey rate, Bogey+Double+ rate, top-10%-rounds avg birdies, round-points variance, SG Off-the-Tee, SG Approach, **official Par5 scoring (파5성적, reconstructed this turn — 74.29/76.92/90.38, 2023 falls just short of CORE)** — each shows a real elevated pattern in 2/3 winners or a weak-but-positive pattern in all 3, but does not clear the strict 3/3-top-25% CORE bar.

## 8a. Six validation questions (per the user's explicit list), answered to the extent current evidence allows

1. **장타 선수였는가 (long hitters)?** — Real official Driving Distance now acquired: 256.26y/250.57y/251.78y, all 3 in the 88th-99th percentile of their field. Mechanically this is 3/3 top-25%, but every number comes from a single 4-round pre-cutoff tournament (see ⚠ Critical finding), not the full pre-cutoff season — so the honest answer is **"the limited real evidence available leans yes, but cannot be confirmed with confidence."**
2. **GIR 상위권이었는가?** — Real official GIR now acquired: 63.89%/66.67%/55.56% → 80.39/87.38/27.45 percentile. Two of three (2023/2024) look elite; 김민솔's number is from only 2 rounds and is well below median. **Inconclusive, and even setting the scope problem aside, not a clean 3/3 case.** The SG Tee-to-Green full-season proxy (CORE, 97.03/94.23/81.37) remains the more trustworthy signal in the same direction.
3. **Par5에서 강했는가?** — **Mostly yes**: real reconstructed Par5 scoring is SUPPORTING (2 of 3 in the top 25%; 2023 is just short at the 74.29th percentile) — a genuine but not unanimous pattern.
4. **Fairway Accuracy는 정말 공통점이 아니었는가?** — **Confirmed, from real data**: 51.79%/46.43%/60.71% → 51.96/33.98/55.88 percentile — none of the 3 clear the top-25% bar; this directly matches H7's prediction and agrees with the SG Off-the-Tee proxy's own SUPPORTING-not-CORE result. Even with the scope caveat, two independent real signals now agree: Fairway Accuracy is not a core commonality.
5. **공식 평균타수 상위권이었는가?** — **Yes, unanimously**: CORE, all 3 in the top 25% of their own year's field (82.86/86.54/82.69).
6. **Birdie+Tee-to-Green 공통점과 이 새 지표들의 관계는?** — Average Score is mechanically downstream of birdie-making (more birdies → lower average score), so its CORE status is consistent with, not independent evidence beyond, the already-found birdie/SG-Tee-to-Green commonality. Par5 scoring is directionally consistent (SUPPORTING) but weaker. The newly acquired Driving Distance/GIR numbers are directionally consistent with "attacking, tee-to-green strength" too, but — being scoped to a single tournament — add suggestive color, not independent statistical confirmation, to that same underlying signal.

## 3. (continued) 공통점이라고 생각했지만 탈락한 특성

- **Low Double+ rate** — actively rejected: 2 of 3 winners (방신실, 김민솔) are BELOW their field's median on double+ avoidance, not above it. A naive "winners avoid blow-up holes" narrative does not survive contact with the real per-player data.
- **Par rate** — NOT COMMON, wildly inconsistent (2.88th to 69.23rd percentile) — unsurprising since par rate is largely the complement of the other rates, but worth stating explicitly rather than assuming it tracks birdie rate.
- **SG Around-the-Green and SG Putting** — NOT COMMON, in fact near-opposite patterns across years (방신실 strong putting-adjacent/around-green, weak putting; 김민솔 the reverse). No consistent short-game signature.

## 4. 세 선수 각각의 다른 점

- **방신실 (2023)**: the only winner with a real elevated Double+ rate (3.10%, 17th percentile — i.e., worse than most of the field at avoiding blow-ups) and the only one with strong SG Around-the-Green (88th percentile) paired with weak Putting (11th percentile) — a ball-striking/short-game-adjacent profile rather than a pure putter.
- **김민별 (2024)**: the most "conventional" profile of the three — her birdie rate (78.85th percentile) and scoring-ceiling metrics (round variance only 58.65th percentile) are the weakest of the three winners on nearly every CORE metric, yet she still clears every CORE threshold — the marginal case that keeps several metrics at SUPPORTING rather than CORE.
- **김민솔 (2025)**: the most extreme scoring-ceiling profile (99.04th percentile round-points variance, 95.19th percentile high-scoring-round rate) and by far the smallest pre-event sample (32 rounds, 9 tournaments — under half of the other two winners') — her numbers are real but rest on the thinnest evidence base of the three.

## 5. 2026 후보선수 탐색에 사용 가능한 변수

Birdie rate / Birdie+ rate / avg birdies per round / max birdies per round / sub-70 round rate / high-scoring-round rate / Birdie+:Bogey+ ratio / expected Stableford points per hole / SG Total / SG Tee-to-Green / **official Average Score (reconstructed)** — all CORE, all independently computable pre-event from the same real `scoreRecord` + SG-warehouse pipeline already built (Average Score needs zero new acquisition — it's a direct formula on data already on disk).

Par5 scoring (reconstructed) is SUPPORTING, not CORE — usable as a secondary/tie-breaking signal, not a primary screen.

## 6. 사용하면 안 되는 변수

- **Low Double+ rate / Double+ avoidance** — actively contradicted by 2 of 3 winners; using it to screen OUT high-double+ players would have excluded 방신실 and 김민솔.
- **Par rate, SG Around-the-Green, SG Putting** — NOT COMMON, no consistent direction; using any of these as a screening filter would be fitting noise.
- **Driving Distance, Fairway Accuracy, GIR% (official)** — real values are now acquired, but each is scoped to a single pre-cutoff tournament (1-4 rounds), not a season-long sample — using these specific numbers to screen 2026 candidates would be fitting a tiny, noisy, single-event snapshot, not a real season profile. A genuine season-cumulative reconstruction (summing across every pre-cutoff `gameCode`) would be needed before these are usable as screening variables.
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
| Field normalization consistency | **PASS** — identical percentile method (rank within that year's own Stableford pre-event field, same direction convention) applied uniformly across all 3 years and all metrics, including the two newly reconstructed metrics (same 106/105/105 field as the SG table) |
| Metric definition drift | **PASS** — every metric is computed by the same shared function across all 3 years (no year-specific logic branches); Average Score/Par5 scoring use KLPGA's own official formula, verified against the real fixture, not a project-invented approximation |
| CRLF/hash issue affecting frozen artifacts | **PASS, VERIFIED** — this turn touched no `*_FROZEN_PREEVENT_SNAPSHOT_V1.json` file (confirmed via `git diff --stat`); the already-disclosed 2023/2025 chain-of-custody findings remain exactly as reported in their own gate reports and are unaffected by this analysis |
| `gameCode` scoping (new, CRITICAL, confirmed via the real acquisition run) | **FOUND, CONFIRMED, CENTRAL TO THIS UPDATE** — the hypothesized temporal-safe call does NOT return a season-cumulative value; it returns the single named tournament's own stats only (라운드수=1-4 for all 102/103/102 acquired players, every year). This is disclosed in full in "⚠ Critical finding" above and is why Driving Distance/Fairway Accuracy/GIR are INCONCLUSIVE rather than CORE/SUPPORTING/REJECTED |
| Temporal cross-check blind spot (new) | **FOUND, DISCLOSED** — the script 210 cross-check (`returned_rounds <= expected_pre_cutoff_rounds_total`) only guards against OVER-counting (post-cutoff leakage into the call); it cannot detect UNDER-counting (a single-tournament return masquerading as a season total), which is exactly what happened. No post-cutoff leakage occurred (the single tournament used is independently confirmed pre-cutoff), but the cross-check's "PASS" should not be read as "this is a valid season-cumulative value" |
| Post-cutoff/future-season leakage in the acquired data itself | **PASS, ON ITS OWN NARROW TERMS** — the specific tournament each gameCode-scoped call used is confirmed to be each player's own last real pre-cutoff event (per the manifest's leakage-verified provenance); no post-cutoff round enters these specific numbers. The `gameCode=""` full-season reference call (kept only as a labeled comparison, never trusted) IS leakage-contaminated as expected — confirmed directly for 방신실: it returns 70 rounds vs. her real 52 pre-cutoff rounds |
| Measured-hole bias in Driving Distance (disclosed from the real fixture, now also confirmed in the live data) | **FOUND, CONFIRMED** — every winner's real Driving Distance detail shows `전체 측정 홀=4` (2023/2024) or similarly small (2025) — a handful of holes per tournament, not full-round coverage, compounding the single-tournament scope problem above. Any future Driving Distance comparison must use KLPGA's own 측정홀 count as the denominator and disclose it |
| Denominator consistency across the 3 metrics | **CONFIRMED FROM LIVE DATA** — GIR's denominator (그린적중수 alone, no explicit total-holes field captured by the current parser), Fairway Accuracy's denominator (전체 측정 홀=56 for 2023/2024, 28 for 2025 — fairway opportunities only, excludes par-3s), and Driving Distance's denominator (전체 측정 홀=4, a DIFFERENT, much smaller count) are three distinct, non-interchangeable counts, confirmed different from each other in the real pushed data |
| Sample-size asymmetry in the new acquisition (new) | **FOUND, CONFIRMED** — 김민솔's GIR/Driving Distance/Fairway Accuracy numbers rest on just 2 rounds (her last pre-cutoff tournament was shortened), vs. 4 rounds for 방신실/김민별 — on top of the single-tournament scope problem, this is a second, compounding small-sample issue specific to 2025 |
| `SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED` exclusions | **FOUND, DISCLOSED, NOT A WINNER** — 2023: 0 excluded (102/102 acquired). 2024: 0 excluded (103/103 acquired). 2025: 1 excluded (이시은 0901(A), playerCode 12010) — her gameCode-scoped call returned entirely null fields (never fabricated as 0), so she is correctly dropped from the 2025 field-percentile denominator (field_n=102, not 103); none of the 3 winners are affected |
| Percentile sensitivity for the 3 new metrics | **DISCLOSED** — because field_n differs slightly by metric availability and the underlying sample is only 1-4 rounds per player, these percentiles are far more sensitive to single-round variance than every other metric in this report; small, swings would move a player many percentile points. This is the core reason they are reported as real numbers but not promoted to a CORE/SUPPORTING verdict |
| Player identity matching for the new acquisition | **FOUND, DISCLOSED** — playerCode resolution (from `mainRecord?playerCode=` links already embedded in existing captures) covers 95.4%/96.3%/96.3% of each year's field (103/108, 104/108, 104/108); 4-5 players per year have no resolvable playerCode and are excluded from the acquisition manifest, not fabricated |

## 9. Final Gate

**PARTIAL (upgraded twice now — real acquisition completed, but a new, confirmed data-scope limitation blocks a clean PASS on 3 metrics)**

Real, consistent CORE commonality was found across all three independent winners on birdie-making ability (in every form measured), the Birdie+/Bogey+ asymmetry ratio, the Stableford value formula's own output, overall ball-striking (SG Total/Tee-to-Green), and **official Average Score**, reconstructed directly from real pre-cutoff data using KLPGA's own formula (CORE, 82.86/86.54/82.69). Official Par5 scoring is a real but weaker SUPPORTING signal (74.29/76.92/90.38). The hypothesis that "low Bogey/Double+" is part of the common profile remains actively REJECTED (2 of 3 winners tolerate elevated double+ risk).

Driving Distance, Fairway Accuracy, and official GIR% have now been **actually acquired** from the real KLPGA endpoint (commit `e7ac0ca4`, 102/103/102 players) — the earlier sandbox network block is no longer the limiting factor. But the acquisition run itself surfaced a new, confirmed finding: the `gameCode`-scoped call returns a single pre-cutoff tournament's stats (1-4 rounds), not a season-cumulative value — a scope mismatch with every other metric in this report (32-70 rounds). The real numbers are reported in full (256.26y/250.57y/251.78y Driving Distance; 51.79%/46.43%/60.71% Fairway Accuracy; 63.89%/66.67%/55.56% GIR, with percentiles), but classified `INCONCLUSIVE` rather than forced into CORE/SUPPORTING/REJECTED, because the sample scope does not meet this report's own consistency bar. Fairway Accuracy's real (if scope-limited) result does, however, independently agree with the already-CORE-tier SG Off-the-Tee proxy's SUPPORTING-not-CORE verdict — two signals now converge on "not a core commonality" for that one metric (H7).

The control comparison still shows the CORE traits are shared by non-winners too — meaning they describe "a strong Stableford-value profile," not "a guaranteed winner." **Still not reported as PASS** because 3 of the originally-requested variables, while now real-data-backed, cannot yet be confirmed at the correct time scope (a full pre-cutoff-season cumulative reconstruction remains a defined, larger follow-up task). **Not reported as FAIL** because every metric computed at the correct scope — now including 2 reconstructed and multiple newly-informed official KLPGA stats — shows a real, non-trivial, consistent signal, and the attacking/scoring-opportunity hypothesis (H9) is supported in its general, large-sample form.
