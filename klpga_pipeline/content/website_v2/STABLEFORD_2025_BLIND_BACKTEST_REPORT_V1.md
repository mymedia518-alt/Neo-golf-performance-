# 2025 TRUE BLIND BACKTEST — Final Report (2026-10-06)

Continues from `a86ab9e` (23/23 prior-tournament scoreRecord captures, SOURCE_PASS).

Question: *"2025 HJ중공업·동부건설 챔피언십 결과를 전혀 모르는 상태에서, 대회 시작 전 실제 기록만으로 김민솔을 Stableford에 강한 선수로 식별할 수 있었는가?"*

## 1. Pre-event snapshot

Built from ONLY the 23 real captures under `evidence/stableford_prior_2025/`, all independently re-verified strictly before the target event's own real start date (2025-10-01, quoted from the page itself — see `stableford_historical_dates`). No cell from `evidence/stableford_source_probe_2025100001/` was ever read except the field's own NAME column (never a score/outcome).

- Target field size: **108**
- Players with usable pre-event hole history: **105** (97.2%)
- Missing: `박조은 0806(A)`, `윤민아`, `이지유 0901(A)` — zero real pre-event rows found for these 3 under their exact name string in any of the 23 captures. Not inferred, not estimated.
- Holes/player distribution: min 36 (2 rounds), median 1,116 (62 rounds), max 1,386 (77 rounds). **3 players have a thin sample (<10 rounds / 180 holes)**: 김서윤2 (90 holes, rank 11), 신이솔 (90 holes, rank 93), 이시은 0901(A) (36 holes, rank 101) — flagged, not hidden.

## 2. Frozen formula (unchanged)

`8·P(Albatross) + 5·P(Eagle) + 2·P(Birdie) − P(Bogey) − 3·P(Double+)`. Albatross is 0 for every one of the 105 players — zero albatross-classed cells exist anywhere across all 23 real captures (confirmed, not assumed).

## 3. Frozen ranking (persisted BEFORE any actual result was joined)

File: `STABLEFORD_2025_FROZEN_PREEVENT_SNAPSHOT_V1.json`
**SHA-256: `232aee3f8e3ac368d5924ceef8b676b2543da8edcd42ec860cd73e38061a26d4`**

`tests/test_stableford_2025_blind_backtest.py::test_freeze_hash_is_deterministic_and_unaffected_by_joining_actual_results` proves this hash is byte-identical whether computed before or after `join_actual_results` runs — the ordering is enforced, not just claimed.

**김민솔's blind result, reported exactly as computed:**

| | |
|---|---|
| Pre-event holes | 576 (32 rounds, across 9 of the 23 prior tournaments) |
| eagle / birdie / par / bogey / double+ | 4 / 127 / 359 / 73 / 13 |
| birdie% / eagle% / bogey% / double+% | 22.0% / 0.7% / 12.7% / 2.3% |
| Positive scoring contribution | +0.476 |
| Bogey cost | −0.127 |
| Double+ downside | −0.068 |
| **Net expected Stableford value** | **+0.281** |
| **Blind pre-event rank** | **#9 of 105** |
| **Percentile** | **92.31%** |

**#9, not #1.** Reported exactly as computed — no coefficient, window, or feature was touched because of this number. Top 8 ahead of her: 유현조, 홍정민, 방신실, 이동은, 노승희, 이예원, 정윤지, 김민선7.

## 4. Join actual results (only after the freeze above)

File: `STABLEFORD_2025_BLIND_EVALUATION_V1.json`. Evaluation population: the 61 real made-cut finalists (100% of them have a pre-event record — clean join, no gaps).

**Tie rule** (stated explicitly, per instruction): competition ranking (T-rank) — players tied on actual Stableford points share the same rank; the next distinct total skips ahead by the tie-block size, same convention a real leaderboard uses. "Actual Top10/Top20" means rank≤10/≤20 and may include more than 10/20 names when a tie straddles the boundary.

| Metric | Value |
|---|---|
| Spearman correlation (pre-event net value vs actual points, n=61) | **0.5905** |
| Top10 precision | 0.30 (3 of the 10 predicted also finished actual Top10: 방신실, 김민선7, 김민솔) |
| Top10 recall | 0.30 |
| Top20 precision | 0.65 |
| Top20 recall | 0.5652 |
| Actual Top10 players' pre-event ranks | 3, 8, 9, 12, 18, 20, 23, 25, 33, 37 (median 19) |
| Winner (김민솔) pre-event rank | 9 (92.31 percentile) |

A real, moderate, non-trivial signal (0.59 Spearman is a meaningful correlation for this kind of outcome prediction — far from both 0 and 1). Top10 precision is modest (0.30); Top20 precision is considerably stronger (0.65). The signal is real but far from deterministic — exactly what an honest pre-event indicator of a high-variance scoring format should look like, not a claim of near-certain prediction.

## 5. Stableford vs. ordinary pre-event value — concrete mechanism

File: `STABLEFORD_2025_ORDINARY_VS_STABLEFORD_V1.json`. `ordinary_value_per_hole = birdie_rate − bogey_rate + 2·eagle_rate − 2·double_or_worse_rate` (double+ at a conservative −2 floor since this project's hole-outcome buckets don't preserve exact stroke magnitude beyond "double or worse" — see `klpga.collectors.score_record`'s `Dbogeys` class investigation).

**김민솔 herself is a real riser**: ordinary pre-event rank **19** → Stableford pre-event rank **9**. Mechanism, from her own real rates: birdie 22.0% (strong) combined with a RELATIVELY HIGH bogey rate of 12.7% (above the field median). Ordinary scoring treats a birdie and a bogey symmetrically (±1), so her bogeys partly cancel her birdies in a plain scoring-average view. Stableford's table rewards birdie at +2 against bogey's −1 — a 2:1 asymmetry — so the same birdie:bogey mix nets meaningfully more favorably under Stableford. This is the same mechanism found and verified against real *in-event* data for the 3 target events earlier (`stableford_vs_strokeplay.py`), now independently reproduced from *pre-event* season data for the same player.

Other real risers (ordinary→Stableford): 한지원, 정지효, 정소이, 강가율, 이재윤 — same pattern, moderate-to-high bogey rate + moderate double+ rate, still net-positive under the formula's 2:1 birdie:bogey weighting.
Fallers: 전예성, 박현경, 김수지, 현세린, 이지현3, 신다인 — low bogey rate ("steady" profiles) gain comparatively less from the asymmetry.

**Answer to "같은 선수인데 왜 Stableford에서는 가치가 달라졌는가?"**: because Stableford's point table is not symmetric around par the way plain stroke-to-par is — a player's value shift is a direct, computable function of her own birdie:bogey (and, less sharply observed here, double+) ratio, not a narrative about her "playing style." 김민솔's own real pre-event numbers demonstrate exactly this, not a hypothetical case.

## 6. 김민솔 forensic section (after all blind evaluation above)

| | PRE-EVENT (23 real prior tournaments, 576 holes) | ACTUAL TARGET EVENT (72 holes) |
|---|---|---|
| Birdie | 127 (22.0%) | 27 (37.5%) |
| Eagle | 4 (0.7%) | 0 (0%) |
| Par | 359 (62.3%) | 42 (58.3%) |
| Bogey | 73 (12.7%) | 3 (4.2%) |
| Double+ | 13 (2.3%) | 0 (0%) |
| Stableford value | net +0.281/hole (rank 9/105) | +51 total (actual winner) |

**Verdict: the win materially EXCEEDED what the pre-event record suggested, on top of a real pre-event signal that already existed.** Her pre-event profile (rank 9, top-decile, birdie:bogey asymmetry already working in her favor) correctly flagged her as a strong Stableford candidate — not a random pick, not an invisible-until-the-fact player. But her actual tournament birdie rate (37.5%) was far above her own real 23-tournament season birdie rate (22.0%), and her bogey/double+ rates dropped to near zero (4.2%/0% vs 12.7%/2.3% pre-event) — a real, large positive deviation from her own established baseline, not merely "the model worked." **This is not characterized as predictive success based on her rank alone** (per instruction) — rank #9 correctly says "a real contender," not "the winner."

## 7. Red Team

| Check | Result |
|---|---|
| Temporal leakage | **PASS** — all 23 prior captures' real start dates (from `TOURNAMENT_MASTER_DATES_V1.json`) strictly precede 2025-10-01; re-verified directly, not assumed from the manifest alone |
| Target-result leakage | **PASS** — `build_preevent_snapshot` reads only the target event's own NAME column, never a score/outcome cell from it |
| Player identity collisions | **DISCLOSED RISK, not fully provable** — aggregation keys on exact name string across 23 separate tournament pages; KLPGA's own site-side disambiguation suffixes (e.g. "이정민2") are assumed (not proven) to refer to the same individual consistently across tournaments, since `scoreRecord`'s `td.name` carries no playerCode. No contradiction was found in practice (no player's aggregate holes were a non-multiple of 18, which a genuine identity collision mixing two different players' round-counts could plausibly produce), but this is not a proof |
| Duplicate tournaments/rounds | **PASS** — 23 distinct gameCodes in the manifest (no duplicates, tested); `extract_hole_outcomes` itself raises on any same-round same-name conflicting row, and no capture raised |
| Malformed hole cells | **FOUND AND EXPLAINED, non-blocking** — 2 cells with stroke values >10 (`황민정` 11 on a par5, `장하나` 12 on a par4, both in 2 of the 23 prior files) — rare but not physically impossible real golf outcomes; both already correctly bucketed as `double_or_worse`, and Stableford scoring depends only on that class, not the stroke digit, so neither affects any computed value |
| Missing rounds | **PASS, disclosed** — a 0-hole round (WD/no-show) contributes nothing to a player's aggregate, never padded or inferred |
| WD/DQ handling | **PASS** — same 0-or-18-holes invariant already verified for the 3 target events holds across all 23 prior files (never independently re-asserted as a blanket test this turn beyond the holes%18==0 check, which would catch a genuine partial-row bug) |
| Small-sample distortion | **FOUND AND DISCLOSED** — 3 players with <10 rounds of pre-event data (see section 1); their ranks are reported but should be read with reduced confidence; does not affect 김민솔 (576 real holes, well above median) |
| Albatross ambiguity | **PASS** — 0 albatross-classed cells anywhere in any of the 23 real captures; rate is 0.0 for every player, never inferred |
| Outcome counts sum to observed holes | **PASS, tested** — every one of the 105 covered players: `albatross+eagle+birdie+par+bogey+double_or_worse == holes` exactly, and `holes % 18 == 0` for all |
| Chain-of-custody (sha256 bookkeeping) | **FOUND AND FIXED, non-blocking** — the sha256 values recorded in `ACQUISITION_REPORT.json` at capture time do not match the committed files' actual bytes. Root cause: the acquisition script used `Path.write_text`, which on Windows silently translates `\n`→`\r\n`, changing the on-disk bytes after the hash was already computed in memory. Content itself was independently re-verified (identity marker present, parser succeeds, structurally sound, same player/round counts expected) — this is a provenance bookkeeping gap, not a sign of wrong or corrupted data. Fixed in `scripts/207_acquire_2025_prior_tournaments.py` (now `write_bytes` on the same encoded string that was hashed) for future runs |

No Red Team finding changes the ranking or invalidates the result.

## Final Gate

**`2025 BLIND BACKTEST PASS`**

Not because 김민솔 ranked #1 — she ranked #9 — but because: (a) the full pipeline is leak-free (temporal and target-result leakage both checked and clean), (b) the full-field evaluation shows a real, non-trivial signal (Spearman 0.59, Top20 precision 0.65/recall 0.57 — far from both random noise and perfect prediction), (c) the one player this task specifically asked about was correctly identified as a top-decile Stableford-value candidate before the event, using only information available before it started, and (d) every data-quality anomaly found (2 extreme stroke cells, 1 chain-of-custody hash mismatch, 3 missing players, 3 thin samples, unprovable name-identity assumption) was investigated to the cell/class level, explained, and shown not to change the result.

## Next (not started this turn, per instruction)

Reuse this identical frozen methodology for 2024 (김민별) and 2023 (방신실) — same manifest-build → acquire → snapshot → freeze+hash → join pattern, nothing new to design.
