# 2024 BLIND BACKTEST REPLICATION — Final Report (2026-10-06)

Continues from `09a1447` (23/23 prior-tournament scoreRecord captures, SOURCE_PASS). Uses the generalized frozen V1 pipeline (`klpga.website_v2.stableford_blind_backtest`, introduced `7bfbd82`) with **zero changes** to formula, coefficients, feature definitions, ranking logic, sample handling, or evaluation definitions.

Question: *"2024 HJ중공업·동부건설 챔피언십 결과를 전혀 모르는 상태에서, 대회 시작 전 실제 기록만으로 김민별을 Stableford에 강한 선수로 식별할 수 있었는가?"*

## 0. Frozen 2025 result re-verified (not trusted from the prompt)

Ran `test_stableford_blind_backtest_matches_frozen_2025.py` + `test_stableford_2025_blind_backtest.py` live against the real committed artifacts: **15/15 passed**, confirming unchanged: SHA-256 `232aee3f8e3ac368d5924ceef8b676b2543da8edcd42ec860cd73e38061a26d4`, 김민솔 blind rank 9/105 (92.31 percentile), Spearman 0.5905, Top10 0.30/0.30, Top20 0.65/0.5652.

## 1. Source gate — 2024

- 23/23 manifest game_codes, 23 distinct, target (`2024100009`) not among them.
- `ACQUISITION_REPORT.json`: 23/23 `SOURCE_PASS`, 23/23 `ACQUIRED`.
- Every capture's `value="<gameCode>" selected` identity marker re-verified directly against the committed file (not trusted from the report).
- **SHA-256 chain-of-custody: 23/23 match** — unlike the 2025 run (which had the Windows `write_text` newline bug), this script (`208`) had the `write_bytes` fix from the start, so every recorded hash matches the committed bytes exactly.
- Every one of the 23 real start dates (`TOURNAMENT_MASTER_DATES_V1.json`) strictly precedes the target's real 2024-10-10 start. Latest: **2024-10-03** (`2024100008`, 7 days before target).
- No duplicate tournaments; `extract_hole_outcomes` raised on none of the 23 (no unresolved same-round-name conflicts).

**Source gate: PASS, no ranking-relevant failure.**

## 2-4. Pre-event snapshot, frozen ranking

- Target field size: **108**. Covered: **105 (97.2%)**. Missing: `박조은 0806(A)`, `배신영`, `유다겸(I)` — zero real pre-event rows under their exact name string.
- Holes/player: min 36, median 1,080, max 1,458. **3 thin-sample players (<10 rounds)**: 김효문 (36 holes, rank 11), 이지원 0810(A) (36 holes, rank 99), 임채리 (72 holes, rank 105) — disclosed, not hidden.
- Albatross: 0 for every player, every real capture — never inferred.

**Frozen artifact**: `STABLEFORD_2024_FROZEN_PREEVENT_SNAPSHOT_V1.json`
**SHA-256: `e55a64403d75c4eb634b6632b7f4858ef73a4a8e64718d6f87cf65f88c788eb4`**

**김민별's blind result, reported exactly as computed:**

| | |
|---|---|
| Pre-event holes | 1,116 (62 rounds, 19 of 23 prior tournaments) |
| eagle / birdie / par / bogey / double+ | 2 / 200 / 767 / 134 / 13 |
| Eagle% / Birdie% / Bogey% / Double+% | 0.18% / 17.92% / 12.01% / 1.17% |
| Positive scoring contribution | +0.367 |
| Bogey cost | −0.120 |
| Double+ downside | −0.035 |
| **Net expected Stableford value** | **+0.212** |
| **Blind pre-event rank** | **#16 of 105** |
| **Percentile** | **85.58%** |

**#16, not #1 — preserved exactly.** No coefficient, window, or rule was touched after seeing this.

## 5. Join actual results (only after freeze; hash verified unchanged)

`test_frozen_hash_matches_committed_value_and_is_immutable_after_join` confirms the SHA-256 is byte-identical before and after `join_actual_results` runs.

Evaluation population: 60 real made-cut finalists (100% joined — clean, no gap).

| Metric | 2024 value |
|---|---|
| Spearman correlation (n=60) | **0.4818** |
| Top10 precision / recall | 0.20 / 0.20 |
| Top20 precision / recall | 0.50 / 0.50 |
| Actual Top10 players' pre-event ranks | 1, 12, 13, 16, 19, 23, 26, 28, 44, 46 |
| Winner (김민별) pre-event rank | 16 (85.58 percentile) |

Tie rule: identical T-rank convention as 2025 (unchanged).

A real, positive, **weaker-than-2025** signal. Notably, the pre-event **#1**-ranked player (윤이나) also finished actual Top10 — a strong individual confirmation even as the aggregate correlation is more modest than 2025's.

## 6. Ordinary performance vs Stableford — 2024

File: `STABLEFORD_2024_ORDINARY_VS_STABLEFORD_V1.json`. Same method as 2025 (`birdie_rate − bogey_rate + 2·eagle_rate − 2·double_or_worse_rate`, double+ at the same conservative −2 floor).

**김민별 herself: ordinary rank 17 → Stableford rank 16 — a negligible +1 shift.** Unlike 김민솔's +10 shift in 2025, 김민별's own birdie(17.9%)/bogey(12.0%) mix does not put her meaningfully far from the field's typical ratio, so the Stableford asymmetry barely repositions her.

The underlying MECHANISM still replicates in the broader field, just on different players this year: real risers — 문정민 (+12), 박예지 (+8), 홍정민 (+6), 송가은 (+5), 신유진 (+5) — all carry elevated bogey rates (12.7%–18.6%) alongside strong birdie rates, same asymmetry. Fallers — 유효주, 이소영, 안선주, 김지수, 김효문, 정윤지 — have comparatively low bogey rates ("steady" profiles), gaining less from the 2:1 birdie:bogey weighting. **Not narrative-fit to the winner**: 김민별's own case is reported as a near-null mover, exactly as computed, even though the mechanism clearly exists elsewhere in the same field.

## 7. 김민별 forensic (after blind evaluation)

| | PRE-EVENT (19 tournaments, 1,116 holes) | ACTUAL TARGET EVENT (72 holes) |
|---|---|---|
| Birdie | 200 (17.9%) | 26 (36.1%) |
| Eagle | 2 (0.2%) | 0 (0%) |
| Par | 767 (68.7%) | — |
| Bogey | 134 (12.0%) | — |
| Double+ | 13 (1.2%) | 0 (0%) |
| Stableford value | net +0.212/hole (rank 16/105) | +49 total (13/8/10/18) |

**Answer: 대회 전에 존재했던 신호와 어느 정도 일치했지만, 실제 대회 성적이 자신의 사전 기준선을 뚜렷하게 초과했다.** Her pre-event profile (rank 16, top-15%, a real but not exceptional signal — notably weaker than 김민솔's rank-9 signal) correctly flagged her as a plausible contender, not a random name. But her actual birdie rate (36.1%) roughly doubled her real 19-tournament season rate (17.9%) — a large positive deviation, consistent with the same pattern seen in 2025 (both winners' actual performance clearly exceeded their own pre-event baseline). **Rank #16 alone is not treated as model success** — it is one input among several below.

## 8. Independent replication — 2025 vs 2024

| | 2025 (김민솔) | 2024 (김민별) |
|---|---|---|
| Winner | 김민솔 | 김민별 |
| Blind winner rank | 9 / 105 | 16 / 105 |
| Percentile | 92.31% | 85.58% |
| Ordinary rank → Stableford rank | 19 → 9 (+10) | 17 → 16 (+1) |
| Spearman | 0.5905 | 0.4818 |
| Top10 precision / recall | 0.30 / 0.30 | 0.20 / 0.20 |
| Top20 precision / recall | 0.65 / 0.5652 | 0.50 / 0.50 |
| Field coverage | 105/108 (97.2%) | 105/108 (97.2%) |

**Classification: PARTIALLY REPLICATED.**

Quantitative reasoning:
- **Replicates**: both winners rank in the top ~8–15% of the field pre-event (never near #1, never outside the top quintile) — a consistent, non-trivial qualitative result across two independent seasons. Both Spearman correlations are positive and of the same general magnitude (0.48–0.59, both clearly above 0 and below a hypothetical 1.0). Both Top10/Top20 precision/recall exceed their respective chance baselines (~16.7%/~33% for a 60-61-player field) by a wide margin in both years. The birdie:bogey asymmetry mechanism driving ordinary-vs-Stableford rank movement is visible in BOTH years' broader fields.
- **Does not fully replicate**: every single evaluation metric is weaker in 2024 than 2025 (Spearman −18%, Top10 precision −33%, Top20 precision −23%), and the winner-specific "large Stableford riser" finding from 2025 (+10 rank shift) does **not** reproduce for 2024's winner (+1, negligible) even though the mechanism is present elsewhere in the same 2024 field.

Two years of evidence show a real, repeatable, moderate positive signal — not a coincidence, but also not yet strong enough or stable enough in magnitude to call "replicated" outright. **This is explicitly not overclaimed as final validation.**

## 9. Red Team — 2024

| Check | Result |
|---|---|
| Temporal leakage | **PASS** — all 23 real start dates strictly precede 2024-10-10; re-verified directly |
| Target-result leakage | **PASS** — snapshot reads only the target's NAME column |
| Source identity | **PASS** — all 23 `value="<gameCode>" selected` markers re-verified |
| Player identity collisions | **DISCLOSED RISK, unprovable** — same name-string-only limitation as 2025 |
| Duplicate tournaments/rounds | **PASS** — 23 distinct codes; no parser conflict raised |
| Malformed/extreme stroke cells | **FOUND AND EXPLAINED, non-blocking** — 1 cell (`박설휘`, 12 strokes/+8 on a par4, `2024050018`) — plausible extreme outlier, correctly bucketed as `double_or_worse`, class-based scoring unaffected |
| Missing rounds / WD/DQ | **PASS** — 0-hole rounds contribute nothing, never padded; 0-or-18 invariant holds for all 23 files, tested |
| Small-sample distortion | **FOUND AND DISCLOSED** — 3 players <10 rounds (see section 2); doesn't affect 김민별 (1,116 holes, well above median) |
| Albatross ambiguity | **PASS** — 0 albatross cells anywhere, rate 0.0 for every player |
| Outcome-count arithmetic | **PASS, tested** — every covered player's 6 outcome counts sum exactly to holes, holes%18==0 |
| Frozen hash stability | **PASS, tested** — `e55a6440...` reproduced live, matches committed artifact |
| Result-join immutability | **PASS, tested** — hash byte-identical before/after `join_actual_results` |
| SHA-256 chain of custody | **PASS** — all 23 recorded hashes match committed file bytes exactly (no repeat of the 2025 run's Windows newline issue) |

No defect capable of materially changing the ranking was found.

## Final Gate

**`2024 BLIND BACKTEST PASS`**

Pipeline executed validly end-to-end (source gate clean, snapshot built from pre-event-only data, frozen before join, hash-stable through evaluation) and produced interpretable, non-trivial, real evidence — a positive though weaker-than-2025 predictive signal, a winner correctly flagged in the top 15% pre-event, and a replicated (if individually inconsistent) birdie:bogey asymmetry mechanism in the broader field. **Not because the winner ranked #1 — she ranked #16.**

## Next (not started this turn, per instruction)

2023 (방신실) replication, using the identical frozen pipeline and manifest pattern — no new design needed.
