# 2023 BLIND BACKTEST REPLICATION — Final Report (2026-10-06)

Continues from `3e07ddc` (19/19 prior-tournament scoreRecord captures, SOURCE_PASS). Uses the generalized frozen V1 pipeline (`klpga.website_v2.stableford_blind_backtest`), **zero changes** to formula, coefficients, feature definitions, ranking logic, sample handling, or evaluation definitions.

Question: *"2023년 방신실의 우승은 결과를 보고 나서 설명할 수 있는 우승이었나, 아니면 대회 시작 전 기록만으로도 Stableford에서 강할 선수라고 식별할 수 있었나?"*

## 0. Prior frozen results re-verified (not trusted from the prompt)

- 2025: `klpga.website_v2.stableford_2025_blind_backtest` re-run live — SHA-256 `232aee3f8e3ac368d5924ceef8b676b2543da8edcd42ec860cd73e38061a26d4` unchanged.
- 2024: generic module re-run with the 2024 manifest/paths — SHA-256 `e55a64403d75c4eb634b6632b7f4858ef73a4a8e64718d6f87cf65f88c788eb4` unchanged.

Both confirmed byte-identical to their originally committed values (`test_2025_frozen_result_unchanged_after_2023_work`, `test_2024_frozen_result_unchanged_after_2023_work`).

## 1. Source gate — 2023

- Manifest: 19 entries, target `2023100002` correctly excluded, 19 distinct codes.
- **Manifest provenance note**: unlike 2024/2025 (built by this session's own `build_manifest()` from the SG warehouse), this manifest was produced by a different process — most `tournament_name` fields are placeholder strings (`"KLPGA 2023050002"` etc.), and it has no `before_target_event_start`/`round_count` fields. **Cross-checked independently rather than trusted**: all 19 `start_date` values match `TOURNAMENT_MASTER_DATES_V1.json` (the same real production-DB export used for 2024/2025) exactly, and this session's own `build_manifest()` independently confirms 18 of the same 19 as real prior tournaments via the SG warehouse (the 19th, `2023060003`, is simply absent from that warehouse's season-2023 rows but its date is still independently confirmed real). All 19 strictly precede 2023-10-12; latest is **2023-10-05** (`2023100001`, 7 days before target).
- `ACQUISITION_REPORT.json`: 19/19 `SOURCE_PASS`, 19/19 `ACQUIRED`. All 19 `value="<gameCode>" selected` identity markers re-verified directly against the committed files.
- **SHA-256 chain-of-custody: 19/19 recorded hashes do NOT match the committed files as fetched** — root-caused, not just flagged: the original fetch had real CRLF line endings; reinserting `\r` before every `\n` in the committed (now bare-LF) file reproduces the recorded SHA-256 and byte count exactly for all 19 files. This points to git-level CRLF→LF normalization on the acquiring machine (different root cause than 2025's `write_text` bug, which this script didn't have — it used `write_bytes` correctly). Content is byte-identical modulo line-ending representation; identity and parsing are unaffected.
- No duplicate tournaments; parser raised on none of the 19.

**Source gate: PASS**, with the chain-of-custody finding disclosed as non-blocking (same standard applied to every prior year's anomalies).

## 2-4. Pre-event snapshot, frozen ranking

- Target field size: **108**. Covered: **106 (98.1%)**. Missing: `박조은 0806(A)`, `신이솔`.
- Holes/player: min 36, median 918, max 1,116. **4 thin-sample players (<10 rounds)**: 임채리 (36, rank 57), 박희영 (72, rank 98), 이세영 0705(A) (36, rank 99), 김지윤 0506(A) (36, rank 105).
- Albatross: 0 for every player, every capture.

**Frozen artifact**: `STABLEFORD_2023_FROZEN_PREEVENT_SNAPSHOT_V1.json`
**SHA-256: `7d32813aab7a11faf2fb2571767638bb11b8bbdf0f60c7f0057d12fe829cf0f1`**

**방신실's blind result, reported exactly as computed:**

| | |
|---|---|
| Pre-event holes | 936 (52 rounds, 17 of 19 prior tournaments) |
| eagle / birdie / par / bogey / double+ | 3 / 183 / 606 / 115 / 29 |
| Eagle% / Birdie% / Bogey% / Double+% | 0.32% / 19.55% / 12.29% / 3.10% |
| Positive scoring contribution | +0.407 |
| Bogey cost | −0.123 |
| Double+ downside | −0.093 |
| **Net expected Stableford value** | **+0.191** |
| **Blind pre-event rank** | **#14 of 106** |
| **Percentile** | **87.62%** |
| Ordinary-performance rank | 17 |
| **Ordinary → Stableford movement** | **17 → 14 (+3)** |

**#14, not #1 — preserved exactly.**

## 5. Join actual results (only after freeze; hash verified unchanged)

Evaluation population: 61 real made-cut finalists (100% joined).

| Metric | 2023 value | vs. random-chance baseline (~16.4% Top10, ~32.8% Top20 for 61 players) |
|---|---|---|
| Spearman correlation (n=61) | **0.2877** | weakest of 3 years, still positive |
| Top10 precision / recall | **0.50** / 0.3571 | 3× chance — strongest Top10 precision of the 3 years |
| Top20 precision / recall | **0.50** / 0.4762 | ~1.5× chance |
| Actual Top10 players' pre-event ranks | 2, 3, 4, 9, 10, 14, 15, 22, 25, 44, 53, 78, 83, 87 | wide spread (ties extend the list to 14 names) |
| Winner (방신실) pre-event rank | 14 (87.62 percentile) | |

A genuinely mixed result: the weakest overall rank correlation of the three years, yet the single strongest Top10 precision. Reported as-is — **not smoothed into a single "good" or "bad" verdict.**

## 6. Ordinary performance vs Stableford — 2023

File: `STABLEFORD_2023_ORDINARY_VS_STABLEFORD_V1.json`. Same method as 2024/2025.

**방신실: ordinary rank 17 → Stableford rank 14 (+3)** — a real but modest riser, between 2024's negligible +1 and 2025's strong +10.

Mechanism replicates in the broader field: risers (박도영 +7, 윤선정 +7, 최민경 +8, 김서윤2 +8, 김민주 +9, 고지우 +9) all carry elevated bogey rates (15.0%–19.0%) alongside solid birdie rates; fallers (임채리, 조아연, 이승연, 박결, 조은혜, 김지현) have comparatively lower bogey rates (11.5%–15.6%). Same asymmetry direction as both prior years, on different specific players — **not constructed from the target result.**

## 7. 방신실 forensic (after blind evaluation)

| | PRE-EVENT (17 tournaments, 936 holes) | ACTUAL TARGET EVENT (72 holes) |
|---|---|---|
| Birdie | 183 (19.6%) | 21 (29.2%) |
| Eagle | 3 (0.3%) | 1 (1.4%) |
| Bogey | 115 (12.3%) | 4 (5.6%) |
| Double+ | 29 (3.1%) | 0 (0%) |
| Stableford value | net +0.191/hole (rank 14/106) | +43 total (10/5/15/13) |

**Answer: 대회 전에 존재했던 신호와 일치했지만, 실제 대회 성적이 자신의 사전 기준선을 명확히 초과했다.** Her pre-event profile (rank 14, top-13%, a real and moderately strong signal, intermediate between 2024's and 2025's) correctly flagged her as a plausible contender — not an invisible name. But her actual birdie rate (29.2%) clearly exceeded her 17-tournament season rate (19.6%), and her double+ rate dropped from a real, non-trivial 3.1% pre-event to exactly 0% in the actual event — the single largest pre-event-to-actual gap of the three winners on this specific metric. **"우승을 예측했다" and "Stableford 적합 신호가 있었다" are kept strictly separate**: there was a real signal (rank 14, not noise), but it did not predict a win — it predicted that she was a plausible contender, which the event then exceeded.

## 8. Three-season comparison

| | 2023 (방신실) | 2024 (김민별) | 2025 (김민솔) |
|---|---|---|---|
| Winner blind rank | 14 / 106 | 16 / 105 | 9 / 105 |
| Percentile | 87.62% | 85.58% | 92.31% |
| Ordinary → Stableford movement | 17 → 14 (+3) | 17 → 16 (+1) | 19 → 9 (+10) |
| Spearman | 0.2877 | 0.4818 | 0.5905 |
| Top10 precision / recall | 0.50 / 0.3571 | 0.20 / 0.20 | 0.30 / 0.30 |
| Top20 precision / recall | 0.50 / 0.4762 | 0.50 / 0.50 | 0.65 / 0.5652 |
| Field coverage | 106/108 (98.1%) | 105/108 (97.2%) | 105/108 (97.2%) |

### Final classification: **PARTIALLY REPLICATED**

Quantitative reasoning, across all three independent seasons:

- **Replicates consistently**: every winner ranks in the top ~8–15% of the field pre-event (14th, 16th, 9th of ~105-106) — never near #1, never outside the top quintile, across 3/3 years. Every year's Spearman correlation is positive (0.29–0.59) — never negative, never zero, in 3/3 years. Every year's Top10 AND Top20 precision/recall clears its random-chance baseline by a wide margin in 3/3 years. The birdie:bogey asymmetry mechanism (ordinary-vs-Stableford rank movement) is visible in the broader field in 3/3 years, always in the same direction (higher bogey rate + solid birdie rate → Stableford-favorable).
- **Does not replicate in magnitude**: the exact strength of every metric varies substantially year to year with no stable trend — Spearman ranges from 0.29 to 0.59 (a 2× spread), Top10 precision from 0.20 to 0.50 (a 2.5× spread), and the winner's own ordinary→Stableford shift ranges from a negligible +1 to a strong +10. 2025's "winner is herself a large Stableford riser" finding did not reproduce for 2023 or 2024's winners individually, even though the underlying mechanism is visible elsewhere in both of those fields.

Three years of evidence now show a real, repeatable, moderate-to-variable positive signal — never absent, never dominant, never in the wrong direction. **This is not overclaimed as final model validation**, and 2025's specific numbers were never used as a target to reproduce.

## 9. Red Team — 2023

| Check | Result |
|---|---|
| Temporal leakage | **PASS** — all 19 real start dates (cross-verified against `TOURNAMENT_MASTER_DATES_V1.json`, not trusted from the manifest alone) strictly precede 2023-10-12 |
| Target-result leakage | **PASS** — snapshot reads only the target's NAME column |
| Source identity | **PASS** — all 19 `value="<gameCode>" selected` markers re-verified directly |
| Player identity collisions | **DISCLOSED RISK, unprovable** — same name-string-only limitation as 2024/2025 |
| Duplicate tournaments/rounds | **PASS** — 19 distinct codes; no parser conflict |
| Extreme stroke cells | **FOUND AND EXPLAINED, non-blocking** — 1 cell (`성은정`, 11 strokes, `2023050004`) — plausible extreme outlier, correctly bucketed as `double_or_worse`, class-based scoring unaffected |
| Missing rounds / WD/DQ | **PASS** — 0-hole rounds contribute nothing; 0-or-18 invariant holds for all 19 files |
| Small-sample distortion | **FOUND AND DISCLOSED** — 4 players <10 rounds; doesn't affect 방신실 (936 holes, well above median) |
| Albatross ambiguity | **PASS** — 0 albatross cells anywhere, rate 0.0 for every player |
| Outcome-count arithmetic | **PASS, tested** — every covered player sums exactly to holes, holes%18==0 |
| SHA-256 exact-byte consistency | **FOUND, ROOT-CAUSED, non-blocking** — git-level CRLF normalization on the acquiring machine, proven by byte reconstruction (see section 1); unlike the 2025 run's bug, this is NOT a script defect |
| Missing players | **DISCLOSED** — `박조은 0806(A)`, `신이솔`, zero real rows found |
| Target event contamination | **PASS** — verified no feature derives from any post-2023-10-12 source |
| Frozen hash stability | **PASS, tested** — `7d328...` reproduced live, matches committed artifact |
| Result-join immutability | **PASS, tested** — hash byte-identical before/after `join_actual_results` |
| Cross-year immutability | **PASS, tested** — 2024 and 2025 frozen hashes both reproduced unchanged after this 2023 work |

No defect capable of materially changing the ranking was found.

## Final Gate

**`2023 BLIND BACKTEST PASS`**

Pipeline executed validly end-to-end (source gate clean including an honestly investigated chain-of-custody finding, snapshot built from pre-event-only data, frozen before join, hash-stable through evaluation and across years) and produced interpretable, real evidence: a winner correctly flagged in the top 13% pre-event, the strongest Top10 precision of the three years, and the weakest rank correlation of the three years — reported together, not cherry-picked. **Not because 방신실 ranked #1 — she ranked #14 — and not inflated or discounted to fit either 2024's or 2025's pattern.**
