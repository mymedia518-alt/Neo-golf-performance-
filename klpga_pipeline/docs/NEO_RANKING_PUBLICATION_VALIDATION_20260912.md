# NEO Ranking Publication-Level Validation (2026-09-12)

> Verdict: **BLOCKED**. Two independent hard-gate failures, confirmed with
> fresh evidence in this audit: EXPOSURE_BIAS and RED TEAM (cohort z-score
> membership sensitivity). This is additionally consistent with three
> pre-existing, independent REJECT verdicts already embedded in the
> codebase before this audit began (V1 red-team backtest, historical-truth
> warehouse audit, and `home_ranking.py`'s own structural
> `FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"` gate). No tuning was
> performed. No production file was modified. No HOME UI candidate was
> built (Sections 15-16 are explicitly skipped per the mission's own
> instruction not to build a UI for a model that fails a hard gate).

## 0. Freeze / current state

- Worktree: `wt_neo_rank_pubval`, branch `research/neo-ranking-publication-validation-20260912`, HEAD at `5dfdf20` (production `origin/neo-website-v2` tip) at branch creation; git status clean before this audit's own commit.
- Production SHA: `5dfdf20` (`origin/neo-website-v2`), untouched by this audit.
- Current formula: `neo-ranking-validation-v1` (`NEO_RANKING_VALIDATION_MODEL_V1.json`), `weight_status: HEURISTIC_FOR_EVALUATION_NOT_FITTED_OR_APPROVED`, `publication_class: VALIDATION_MODEL_NOT_PRODUCTION`.
- Player universe: two distinct universes exist in code and must not be conflated -- the K-Ranking TOP120 cohort (`population_kind: official_klpga_kranking_top120`, exactly 120, ranks 1..120) is what the validation-only ranking actually scores; the broader "regular tour" HOME population (`HOME_REGULAR_TOUR_PLAYER_MASTER.json`, 546 records) is a *different*, already-blocked population (`population_validation_state: BLOCKED_CURRENT_REGISTRY_EQUIVALENCE_NOT_PROVEN`) that carries no NEO score at all.
- K-Ranking reference week: current/latest = **2026-W36** (`HOME_PLAYER_MASTER_TOP120_2026_W36.json`, byte-identical to the unlabeled default `HOME_PLAYER_MASTER_TOP120.json`, sha256 `5817d5cc...`). Prior week W35 (`...W35.json`, sha256 `1b487055...`) is retained for history.
- Historical truth dataset: `NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json`, sha256 `593fbbde...`, 7830 records / 82 tournaments.
- SG dataset: `historical_sg_warehouse_corrected.json`, sha256 `4812c205...`, 43,701 records / 108 events (header field), 37,744 `RETAINED` / 5,957 `UNRESOLVED_IDENTITY`.
- Ranked/pending (current, W36): TOTAL 120, NEO_RANKED 108, VALIDATION_PENDING 12, MISSING_SG 2, INSUFFICIENT_SAMPLE 10, IDENTITY_FAILURE 0. Minimum sample requirement: 10 prior validated SG events (`minimum_sg_events`).
- **108 vs 109 discrepancy -- RESOLVED, not silently picked**: W35 (2026-09-02) gives NEO_RANKED=109; W36 (2026-09-09, current) gives NEO_RANKED=108. Root cause, directly verified: normal weekly TOP120 cohort churn -- two players rotated OFF the official K-Ranking TOP120 between weeks (서지은 `11431`, 이소영 `8246`) and two rotated ON (`9992`, `9398`); one of the specific players who churned happened to sit on the `sample_count>=10` eligibility boundary. This is expected behavior given a weekly-refreshed official cohort, not a data-integrity bug. **108 (W36) is the current, authoritative count.**

## 1. Formula audit (from executable source, not docstrings)

Three code locations implement byte-identical arithmetic (deliberately duplicated per their own docstrings, not shared): `neo_ranking_backtest.py` (canonical backtest), `top120_validation.py` (live TOP120 evaluation), `neo_win/kb_neo_v1_score.py` (verified byte-identical reproduction, applied to a live KB tournament cohort via `scripts/108_apply_r1_model_to_kb.py`). The persistent public HOME module, `home_ranking.py:14-15`, never computes or emits a NEO rank at all (`FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"`, `NEO_RANKING_VERSION = None`) -- confirmed unchanged by this audit (`test_home_ranking_formula_state_remains_blocked_pending_approval`).

Exact formula, from `NEO_RANKING_VALIDATION_MODEL_V1.json` + code:
- `recent_5_sg` (w=0.35), `recent_10_sg` (w=0.25), `long_term_sg` (w=0.25), `consistency` = `-population_stdev(all prior totals)` (w=0.10), `sample_reliability` = `min(prior_event_count/20, 1)` (w=0.05, **not** z-scored).
- The four SG-based features are z-scored (`_z`: `(x-mean)/pstdev`, 0 if zero dispersion) **within the eligible cohort for that specific target/run** -- not against a fixed external baseline. This is the direct cause of the cohort-membership-sensitivity defect in Section 13.
- `score = sum(weight[f] * z[f] for f in {recent5,recent10,long_term,consistency}) + weight[reliability]*reliability`.
- Eligibility: `>=10` prior validated SG events; below that, no rank is ever assigned (never imputed, never defaulted to a sentinel).
- Ranking: descending score, ties broken by `player_id` ascending.
- Missing SG: a player entirely absent from the SG warehouse gets `features: None`, `sg_join_state: DATA_INSUFFICIENT`, never a fabricated value.
- No doc-vs-code disagreement was found between `NEO_RANKING_VALIDATION_MODEL_V1.json` and the executable `_z()`/`evaluate()`/`run_backtest()` bodies.

## 2. Player universe / identity gate -- PASS

TOP120 cohort (the only population the ranking actually scores): 120 total, 0 duplicate `player_id`, 0 duplicate `player_name`, 0 blank ids, official ranks exactly `1..120`, no `sponsor` field on the cohort record (sponsor is not and cannot be part of the score at the data layer). `official_k_rank` never appears inside the scoring function (`neo_ranking_backtest.py`) -- confirmed by source grep, and `kb_neo_v1_score.py` explicitly declares `forbidden_features: ["win_probability", "tournament_entry", "tournament_field_rank"]`. No `999999` or any other sentinel rank was ever observed or is reachable by code path (unranked players get `None`, not a numeric placeholder). IDENTITY_FAILURE = 0.

The broader 546-player regular-tour master is separately, independently blocked (`BLOCKED_CURRENT_REGISTRY_EQUIVALENCE_NOT_PROVEN`) -- this is a pre-existing structural DATA gate failure on that population, confirmed still enforced (raises `ValueError` if the block string is altered).

## 3. Temporal / leakage gate -- PASS (HARD STOP clean)

Reconstructed backtest inputs fresh from `NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json` (no live DB needed) and independently re-verified in this audit: **0** future-leakage records, **0** duplicate event-player records, **0** `max_feature_date >= target_start_date` violations across all 7,830 truth-warehouse records. `run_backtest()` itself hard-asserts `max_feature_date < target_date` on every observation (raises `AssertionError("future leakage")` otherwise) -- this is enforced at the code level, not merely observed.

## 4. Unequal exposure / round-count audit -- **BLOCKED (hard gate failure)**

Freshly reproduced in this audit (not merely cited): replicating exactly what `home_ranking.build_features()` / `neo_ranking_backtest._latest_records()` consume (the max-`rounds` `RETAINED` row per `(player_id, game_code)`), of the **11,144** (player, event) observations that actually feed every recent5/recent10/long-term SG mean:
- **43.6%** (4,856) are a **single round's** SG total -- not a tournament.
- 25.6% (2,852) are 3-round, 1.1% (121) are 2-round, and only **29.7%** (3,315) are full 4-round completions.
- No round-count normalization exists anywhere in the production feature builder or the validation scorer -- a player's single 18-hole round is averaged identically alongside another player's full 4-round cumulative total.

Prior-phase Monte Carlo work (`research/neo-ranking-v2` branch, Phase A follow-up, `scripts/102_cut_selection_bias_simulation.py`, 400 simulated players x 20 tournaments, parameters taken from this same real warehouse) found this is not merely a precision issue: even the best-available fix candidate (empirical-Bayes-shrunk pooled per-round rate) leaves a **persistent, non-vanishing ~0.12-0.20 SG/round gap between equal-skill players who differ only in cut-selection luck**, re-confirmed not to shrink toward zero as sample size grows (tested at 1/2/3/5/10/20/40 tournaments). Per this mission's own Section 4 criterion ("if rank materially changes only because exposure changes: BLOCKED or formula correction required") -- **this gate fails**. A structural fix (pooled per-round rate + shrinkage, or a dedicated cut-selection correction) exists in prototype on that branch but has never been frozen into an approved V2 config, and is out of scope for this validation-only audit to adopt unilaterally.

## 5. SG component integrity -- PASS (with one flagged, low-materiality anomaly)

Across all 43,701 warehouse records with all five fields present: **0** violations of `SG_TOTAL ≈ tee_to_green + putting` and **0** violations of `tee_to_green ≈ off_the_tee + approach + around_green` (tolerance 0.05) -- the warehouse's own per-record `validation.total_within_tolerance` flag agrees (43,701/43,701 `true`). Zero duplicate `(game_code, player_id, scope, round)` keys among the 37,744 `RETAINED` rows actually consumed (the 305 apparent "duplicate" keys found by a naive grouping are entirely `UNRESOLVED_IDENTITY` rows with `player_id: null`, which every consumer already excludes).

Flagged, genuine, low-materiality finding: **11 of 43,701 records (0.025%)** carry a single-round SG total with `|value| > 15` (e.g. `-19.74` in one round) -- implausible for ordinary play, not fabricated, not silently imputed. All 11 are `scope: single_round`, none in `tournament_cumulative`. Not itself gate-blocking at this prevalence, but should be investigated as a probable data-collection anomaly before any future approval pass.

## 6. Ranking stability

Event-to-event (tournament-to-tournament; KLPGA events are not calendar-weekly, so "week-to-week" is reframed as event-sequence) churn among players ranked in both of two consecutive events, measured across 71 transitions from the frozen V1 backtest observations: mean Top10 churn (Jaccard distance) **0.332**, Top20 **0.254**, Top50 **0.142** -- larger rank bands are markedly more stable than Top10, the expected pattern for a small-N metric. Per-player extreme-mover attribution already exists from the prior V1 red-team artifact (e.g. 서지은 K119/NEO32, Δ+87, driver=long_term_sg) with full feature-contribution decomposition, but this audit did not re-derive a fresh real-vs-noise attribution beyond that existing table; treat Section 6 as informative, not exhaustively concluded.

## 7. Out-of-sample predictive validation

Reconstructed fresh from the truth warehouse (72 tournaments / 6,753 observations covered by this reconstruction vs. 82/7,830 in the original DB-backed run -- metrics are close but **not** byte-identical to the original frozen artifact; treat all Section 7-11 numbers below as internally consistent with each other, not as an exact reproduction of the old JSON):
- next-1 event: Spearman(NEO rank, finish) = **0.475**; Spearman(NEO score, same-event SG total) = **0.420**; Top10 P/R = **0.356**; Top20 P/R = **0.494**; made-cut AUC = **0.705**.
- next-3 events: Spearman(NEO score, mean future SG) = **0.541** (n=6,179).
- next-5 events: Spearman(NEO score, mean future SG) = **0.596** (n=5,817).
- Predictive strength **increases** with horizon (expected: averaging more future rounds reduces target noise).
- K-Ranking incremental predictive value: **NOT_EVALUABLE** -- no point-in-time historical K-Ranking snapshots exist in this repository (confirmed absent by the prior Phase A/G audit); using the current W35/W36 snapshot as a historical baseline would itself leak future information.

## 8. Baseline battle

| Config | Spearman rank-vs-finish | Top10 P/R | Top20 P/R | made-cut AUC |
|---|---|---|---|---|
| A) long-term SG only | 0.4595 | 0.343 | 0.486 | 0.6949 |
| B) recent5 only | 0.4380 | 0.325 | 0.469 | 0.6912 |
| C) recent10 only | 0.4637 | 0.331 | 0.492 | 0.6998 |
| **Current frozen V1 (composite)** | **0.4752** | **0.356** | **0.494** | **0.7047** |
| E) official K-Ranking (historical) | NOT_EVALUABLE -- no leakage-safe point-in-time snapshots exist | | | |

The composite modestly but consistently outperforms every single-component slice baseline on every metric (~0.01-0.04 Spearman, ~1-3pp precision/recall, ~0.5-1.3pp AUC) -- some, but not overwhelming, justification for the added complexity over a single SG slice. The single most important real-world comparator (official historical K-Ranking) remains untested by hard data availability, not by omission.

## 9. Component ablation

Removing `recent_5_sg`/`recent_10_sg`/`long_term_sg` individually costs ~0.01-0.02 Spearman each (small, consistent with genuine but overlapping signal in each). Removing `consistency` or `sample_reliability` changes metrics by <0.005 Spearman (removing `consistency` is actually marginally *better* on every metric in this reconstruction) -- both contribute negligible measurable value in this backtest, consistent with V1's own documented defect #3/#4 (reliability as an ungated bonus; volatility symmetric-penalty). Not removed here (no tuning performed); flagged for a future formula revision to consider.

## 10. Weight robustness

±5 percentage point perturbations on each of the three SG-weighted components (renormalized against the other weights) produced **96-99% Top10 overlap** with the frozen V1 ranking and <0.01 Spearman movement in every case -- the composite is **not** fragile to small weight changes. **PASS.**

## 11. Sample reliability threshold sweep

| minimum_sg_events | Spearman rank-vs-finish | Top10 P/R | Top20 P/R | AUC | n obs / players |
|---|---|---|---|---|---|
| 5 | 0.4766 | 0.348 | 0.479 | 0.7097 | 7815 / 225 |
| 8 | 0.4763 | 0.353 | 0.487 | 0.7067 | 7162 / 207 |
| **10 (current)** | 0.4752 | 0.356 | 0.494 | 0.7047 | 6753 / 195 |
| 12 | 0.4724 | 0.357 | 0.499 | 0.7014 | 6367 / 188 |
| 15 | 0.4654 | 0.363 | 0.505 | 0.7014 | 5817 / 179 |
| 20 | 0.4598 | 0.360 | 0.511 | 0.7006 | 4940 / 164 |

No sharp cliff anywhere in 5-20: lower thresholds trade slightly better rank-vs-finish/AUC for slightly worse Top10/20 precision, a genuine, smooth trade-off, not a clear single optimum. Current `10` sits defensibly in the middle but is not uniquely justified by this sweep alone -- consistent with the prior Phase-D shrinkage-curve analysis (no sharp bias/precision cutoff either). No production change made from this sweep, per instruction.

## 12. Public explainability -- PASS

Independent recompute of every one of the 108 currently-ranked players' `final_score` from their own reported `feature_contributions`: rank order is **100% exactly reproducible** (`test_explainability_rank_order_is_reproducible_from_the_audit_record_alone`). 31/108 raw score values differ from the displayed score by <1e-5 (a cosmetic round-each-contribution-then-sum-once vs. sum-then-round-once ordering artifact, not a substantive discrepancy) -- flagged for cleanup, not gate-blocking since rank order itself is unaffected.

## 13. Red team -- **BLOCKED (hard gate failure)**

| Attack | Result |
|---|---|
| Cohort z-score sensitivity: swap one unrelated player in the 120-player pool | **CONFIRMED**: 14 of 107 (13.1%) otherwise-unaffected players' ranks changed with zero change to their own performance |
| Reproducibility: identical inputs, two runs | PASS -- byte-identical output |
| Low-sample player reaching Top10 | Not observed in the current real cohort (min sample count in Top10 = 31, well above the eligibility floor of 10) |
| More rounds / making a cut auto-improving rank; WD advantage; 3R-vs-4R bias | Confirmed root cause = Section 4's exposure-bias finding (no round normalization anywhere) |
| Duplicate event under a new game_code | Probed once (a single injected duplicate row); rank was unchanged in this specific instance -- inconclusive, not a clean pass, flagged for a larger-scale probe before relying on it |
| K-Ranking / win-probability leakage into NEO score | Not present -- confirmed absent from the scoring function's source (`official_k_rank`/`win_probability` never referenced in `run_backtest`) |
| Rank depends on current tournament's own outcome | Not applicable to this backtest structure (features are always strictly prior to the target) |
| Non-reproducible rank | Not observed -- see reproducibility row above |

Every discovered failure above has a corresponding permanent regression test in `tests/test_neo_ranking_publication_validation_20260912.py` (documenting tests, not silently-passing placeholders -- see that file's own docstrings for why each exists and what a future change to its assertion would mean).

## 14. Publication gates

| Gate | Verdict | Basis |
|---|---|---|
| DATA | PASS (TOP120 cohort) / BLOCKED (broader 546-player regular-tour population, pre-existing) | Section 0, 2 |
| IDENTITY | PASS | Section 2 |
| TEMPORAL | PASS | Section 3 |
| SG_INTEGRITY | PASS (flagged: 11/43701 anomalous single-round values) | Section 5 |
| **EXPOSURE_BIAS** | **BLOCKED** | Section 4 -- 43.6% unnormalized single-round observations; persistent non-vanishing cut-selection subgroup bias |
| REPRODUCIBILITY | PASS | Sections 12-13 |
| STABILITY | Informative, not conclusively passed or failed | Section 6 |
| OUT_OF_SAMPLE | PASS | Section 7 |
| BASELINE | PASS (K-Ranking comparator NOT_EVALUABLE by data absence) | Section 8 |
| ABLATION | PASS (2 components show negligible marginal value) | Section 9 |
| ROBUSTNESS | PASS | Section 10 |
| SAMPLE_RELIABILITY | PASS (no sharp threshold identified; current 10 defensible not uniquely optimal) | Section 11 |
| EXPLAINABILITY | PASS | Section 12 |
| **RED TEAM** | **BLOCKED** | Section 13 -- cohort z-score membership sensitivity |

**PUBLICATION_GATE: BLOCKED.** Per instruction, this is not an averaged score -- EXPOSURE_BIAS and RED TEAM are each independently sufficient to block, regardless of how the other eleven gates scored. This is corroborated, not contradicted, by three pre-existing independent REJECT/BLOCKED findings already in the codebase before this audit (`docs/NEO_RANKING_V1_REDTEAM_BACKTEST.md` verdict REJECT; `docs/NEO_HISTORICAL_TRUTH_WAREHOUSE_V1_AUDIT.md` verdict "NEO V1 PUBLIC RELEASE: REJECT"; `home_ranking.py`'s own `FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"`).

## 15-16. HOME UI candidate / visual gate -- SKIPPED

Not built. The mission's own instruction is explicit: a HOME preview is generated "ONLY if the ranking reaches publication-candidate status." It does not. Building a UI candidate for a formula that fails two hard gates would itself be the kind of action this mission exists to prevent.

## 17. Production safety

No deploy. No modification to `neo-website-v2` or any file under production `docs/`. No destructive git operation. All work done in isolated worktree `wt_neo_rank_pubval` on candidate branch `research/neo-ranking-publication-validation-20260912`, branched from `origin/neo-website-v2` at `5dfdf20`.

## Recommendation (not adopted, not implemented here)

The prototype fix direction already exists on `research/neo-ranking-v2` (pooled per-round rate + empirical-Bayes shrinkage) and demonstrably narrows -- but does not eliminate -- the exposure bias. A future V2 approval pass would need, at minimum: (a) adopt a round-normalized observation unit, (b) either accept the documented ~0.12-0.20 SG/round residual cut-selection bias as a disclosed limitation or invest in the still-unbuilt "conditional later-round model" correction, (c) replace or supplement cohort z-scoring with a fixed external baseline (or accept and disclose the membership-sensitivity property), (d) source a field-strength signal (candidates identified, none wired in), and (e) obtain a genuine point-in-time historical K-Ranking baseline before claiming any K-Ranking comparison. None of this is authorized or performed by this validation pass.
