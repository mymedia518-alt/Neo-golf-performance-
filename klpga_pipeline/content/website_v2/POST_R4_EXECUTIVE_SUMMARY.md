# POST-R4 (FINAL) Executive Summary — Hana Financial Group Championship (2026090002)

**Status:** PREVIEW — not yet promoted to any published page or artifact. No push to `neo-website-v2` has occurred; this document is part of the pre-push evidence package awaiting operator approval.

**Stage:** R3 official leaderboard is final (64/64 confirmed cut-survivors, 0 WD at this stage). This is the model's forecast for the still-unplayed FINAL round (R4).

---

## 1. What changed and why

R3's official leaderboard and Strokes Gained data are now available. Per operator instruction ("Proceed with Option 1"), the FINAL forecast:

- Reuses the **already-validated, already-promoted `R1SG_R2SG` model exactly as promoted** — same coefficients (`r1_sg_total = -0.095010`, `r2_sg_total = -0.112655`), same Monte Carlo engine, same `n_simulations = 60000`, same `seed = 20260918`, `remaining_rounds = 1`.
- Uses each player's `updated_expected_round_score_to_par` / `spread` **verbatim** from the immutable `2026090002_POST_R3_CANDIDATE_FREEZE_V1.json` — no recompute, no refit, no new coefficient.
- Treats the official R3 leaderboard only as current tournament state (score, position).
- Treats R3 Strokes Gained (`r3_sg_total`) strictly as an **evidence/diagnostic/reporting field**, never a predictive feature (see §4 — the 3-feature extension was tested and did not pass its own promotion gate).

## 2. FINAL (R4) forecast — top of leaderboard

| Rank | Player | R3 (to par) | Win % | Top5 % | Top10 % | Top20 % |
|---|---|---|---|---|---|---|
| 1 | 김민선7 | -8 | 45.543 | 99.818 | 100.000 | 100.000 |
| 2 | 장은수 | -7 | 35.258 | 99.068 | 99.998 | 100.000 |
| 3 | 황유민 | -6 | 10.202 | 94.153 | 99.977 | 100.000 |
| 4 | 양윤서 0801(A) | -6 | 6.058 | 93.063 | 99.978 | 100.000 |
| 5 | 박민지 | -6 | 2.750 | 94.162 | 99.993 | 100.000 |
| 6 | 이와이 치지 | -1 | 0.147 | 3.908 | 33.112 | 76.465 |
| 7 | 이와이 아키 | 0 | 0.040 | 1.577 | 20.212 | 63.300 |
| 8 | 홍진영2 | -3 | 0.002 | 8.430 | 96.900 | 100.000 |

Field: 64 players, all confirmed cut-survivors (no cut event occurs at R3 — the cut was already settled at R2). `win_pct` sums to exactly **100.0** across all 64.

## 3. How R3 moved the forecast (Current SG impact)

Comparing this FINAL forecast against a baseline that ignores current-tournament SG entirely (historical expectation only):

- Mean absolute win-% shift: **0.118 pts**; sum of absolute shifts: **7.54 pts** across the field.
- 3 players' win probability increased, 5 decreased, 56 unchanged (players far from contention move ~0).
- **Largest increase:** 장은수 (+3.31 pts win%) — R3's strong SG round pulled the model's expected R4 score down further.
- **Largest decrease:** 양윤서 0801(A) (-2.17 pts win%) — R3's weaker SG pushed the expected R4 score back up.
- Field-wide concentration: Top1-probability mass fell from 54.26% (post-R2) to 45.54% (post-R3), while Top5 mass rose from 93.79% to 99.81% — the contention group tightened around the two leaders rather than staying with one runaway favorite.

## 4. R3 Strokes Gained — research finding (kept OUT of the production forecast)

An extension of the validated architecture to a 3rd feature (`R1SG_R2SG_R3SG`, predicting R4) was tested under the same 6-criterion promotion gate used to validate `R1SG_R2SG` originally:

| Criterion | Result |
|---|---|
| Wilcoxon p < 0.05 | **FAIL** |
| 5000-resample bootstrap 95% CI excludes zero | **FAIL** |
| r1/r2/r3 SG coefficients all negative | PASS |
| Chronological split-half same-sign | PASS |

**Verdict: NOT PROMOTED.** Coefficient signs point the expected direction and are stable across a chronological split, but the effect is not statistically significant on the corpus (n=3,219 player-rounds, 50 evaluated events) to clear the pre-registered bar. Full numbers: `HANA_2026090002_R4_SG_VALIDATION_REPORT_V1.json`.

Consistent with this, an honest out-of-sample check for this single tournament (`HANA_2026090002_R2_R3_OOS_VALIDATION_REPORT_V1.json`) showed the SG-updated R2→R3 prediction **underperformed** the plain historical baseline for this 64-player sample (MAE 2.621 vs 2.483; 46/64 regressions vs 18/64 improvements). This is a real, single-tournament negative result, reported as-is — it does not overturn the model's validated aggregate performance across the full historical corpus, but it is a reason R3 SG stays a diagnostic field rather than a model input.

## 5. Validation gates (all PASS)

- **Identity gate:** candidate freeze ⇄ R3 freeze ⇄ R2 freeze ⇄ R3 SG population all match 64/64, 0 duplicates, 0 missing.
- **Probability gate:** win_pct sums to 100.0, no NaN, no negative values, TOP20 ≥ TOP10 ≥ TOP5 ≥ Win monotonicity holds for all 64.
- **Monte Carlo sanity:** same-seed reruns are bit-identical; matches the published FINAL preview exactly.
- **SG decomposition check:** `current_sg_update` reconstructs cleanly from `r1_part + r2_part` (max error 1.1e-06 — float precision only).
- Most accurate single prediction: 장은수 (error 0.045 strokes vs actual R3 score). Worst: 방신실 (error 11.74 strokes — a real outlier round the model could not have anticipated).

## 6. Deployment status

Committed locally to branch `research/hana-r3-final-current-sg-20260919` (commit `ff756f6a3788549c5a69506ab8357b05f48902e1`), fast-forward-safe against current production (`origin/neo-website-v2` @ `31cbb7918f6ded6e5e3fb96b1deb87df4fd5f4cf`). **Not pushed.** See the PRE-PUSH REPORT for full git/QA/test detail. Awaiting explicit operator approval before push.
