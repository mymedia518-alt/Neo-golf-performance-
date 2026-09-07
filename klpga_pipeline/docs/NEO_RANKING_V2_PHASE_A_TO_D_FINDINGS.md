# NEO Ranking V2 — Phase A–D Findings (VALIDATION_MODEL_NOT_PRODUCTION)

> Status: **IN PROGRESS**. This document records evidence-based findings
> from Phases A–D of the NEO GOLF DATA ranking-methodology audit. It does
> not authorize any production change. `home_ranking.py`'s
> `FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"` gate is untouched.

## PHASE A — OK Open (game_code 2026120001) evidence map

| Stage | Artifact | Last commit (KST) | Key state |
|---|---|---|---|
| PRE | `OK_OPEN_2026_PRE_PUBLIC_MASTER.json` | 2026-09-01 07:56:18 | generated_at 2026-08-31T22:42:53Z |
| R1 | `OK_OPEN_2026_R1_LIVE_SNAPSHOT.json` | 2026-09-05 14:33:48 | `holes_completed: "18"` for sampled rows — round closed |
| R2 | `OK_OPEN_2026_R2_LIVE_SNAPSHOT.json` | 2026-09-06 02:36:59 | row_count 118 (post-cut), `holes_completed: 18` for sampled rows — round closed |
| R3/FINAL | `OK_OPEN_2026_R3_LIVE_SNAPSHOT.json` | 2026-09-06 14:29:14 | `stage: "FINAL_LIVE"`, row_count 68, **leader row shows `holes_completed: 13`, `round3_score: null`** — round IN PROGRESS at capture time |
| stage state | `OK_OPEN_STAGE_STATE.json` | 2026-09-06 02:36:59 | `stages.r1.r1_status: "WAIT"`, `retrieved_at: 2026-09-04T07:43:00Z` |

**No `OK_OPEN_2026_FINAL_*` artifact exists.** The most recent artifact in the repository (R3, stage `FINAL_LIVE`) is itself a mid-round snapshot, not a completed result.

## PHASE A — OK OPEN FREEZE STATUS

R1 and R2 are genuinely closed (all sampled rows show 18/18 holes, real scores). **R3/FINAL is NOT closed inside this repository's evidence** — the last captured snapshot (`collected_at: 2026-09-06T05:26:32Z`) shows the tournament leader at hole 14 of round 3 (13 holes completed, `round3_score: null`). This is consistent with — not contradicting — the correction that the real-world tournament has finished: this sandbox's live collector (`scripts/96_ok_open_r1_active_cycle.py --live`) has returned `SKIP_WAIT` on every hourly run this entire session because `klpga.co.kr` is proxy-blocked (`403 Forbidden` on CONNECT) in this environment. The repository's evidence simply stopped updating when that block took effect — it does not, by itself, prove the real tournament is still live, but it also does not yet contain a real final result to build a postmortem from.

**Consequence:** a genuine FINAL-vs-prediction postmortem cannot be built from repository data alone right now. PRE→R1→R2 comparisons ARE buildable today; the R3→FINAL leg must be marked `MISSING_EVIDENCE` until either (a) a real final snapshot is committed from an environment with live network access, or (b) the final result is supplied directly.

## PHASE A — STALE STAGE-STATE ROOT CAUSE

`OK_OPEN_STAGE_STATE.json`'s `stages.r1.r1_status` field is frozen at `"WAIT"` from 2026-09-04T07:43:00Z, three commits and two days before R2/R3 data exists. This is a genuine repository defect, not evidence the real R1 was ever incomplete (R1's own live snapshot shows full 18-hole completion). Root cause (from reading `scripts/96_ok_open_r1_active_cycle.py`): the stage-state file's per-stage status field appears to only be written by the R1-specific active-cycle script; once R1 handed off to R2/R3 (a different code path — R2/R3 content was added via a "checkpoint: preserve tournament engine and OK Open R2-R3 work" commit, not through the same script), nothing went back and updated the R1 entry to a closed/terminal value. **This is a data-model gap: the stage-state file has no single writer responsible for keeping all stages' status fields current as later stages progress.** Recommendation (not yet implemented): either derive `r1_status` from the R1 snapshot's own hole-completion data at read time rather than trusting a separately-written field, or make every later-stage publisher also close out earlier stages explicitly.

## PHASE B — Unequal-participation red team

New files: `src/klpga/website_v2/neo_ranking_v2_candidate.py`, `tests/test_neo_ranking_v2_unequal_participation_redteam.py` (13 tests, all passing after one real correction — see below). Confirmed against the real corrected SG warehouse (43,701 rows / 11,144 unique player-events after taking each event's most-complete snapshot): **only 3,315 of 11,144 events (30%) are full 4-round completions; 4,856 (44%) are single-round events, 2,852 (26%) are 3-round, 121 (1%) are 2-round.** The production feature builder (`home_ranking.build_features`) averages each event's raw cumulative total with no round normalization — this bug affects the majority of its real input, not an edge case.

Results per case (all using `neo_ranking_v2_candidate.py`'s `pooled_per_round_rate` / `estimate_skill` against the CURRENT naive method for comparison):

- **Case 1** (equal per-round rate, unequal rounds): naive method ranks them unequal (documents the bug); candidate ranks them equal. PASS.
- **Case 2** (equal totals, unequal rounds): naive method calls them equal (documents the bug); candidate correctly distinguishes +1/round from +2/round. PASS.
- **Case 3** (same true rate, different sample size): candidate gives identical raw rate and strictly higher confidence (shrinkage weight) to the larger sample. PASS.
- **Case 4** (many mediocre rounds vs one elite round): shrinkage narrows the gap sharply (15x → ~3.2x) but — **genuine finding, not swept away** — a single sufficiently extreme small-sample observation can still out-rank a large mediocre sample under simple homoscedastic empirical-Bayes shrinkage, because the shrunk estimate is linear in the raw observation at a weight that depends only on sample size, not on how extreme the value is. Shrinkage narrows but does not guarantee elimination of this effect; a minimum-rounds eligibility floor (distinct from shrinkage) is still required as a backstop.
- **Case 5** (missed cut vs completed, identical early rate): candidate ranks them equal per-round; naive method penalizes the missed-cut player. PASS (documents + fixes the bug).
- **Case 6** (1-round WD/DQ vs full event): candidate gives the 1-round event a lower confidence weight. **Documented limitation**: round-count weighting treats "1 round" as "1/4 the evidence of a full event," not as categorically noisier — a single round's own variance cannot be estimated from one observation, so an unusually noisy single round is not distinguished from a representative one.
- **Case 7** (extreme small sample vs large sample): small-sample player's estimate regresses toward the population mean proportionally more than the large-sample player's. PASS.
- **Case 8** (field-strength normalization): **genuine data gap, not fabricated** — neither the real warehouse nor this candidate carries any field-strength/field-average column. `EventObservation` deliberately has no such field. Flagged as new data-collection work, not implemented here.
- **Case 9** (same mean, different volatility): candidate's point estimate is provably volatility-invariant (mean-only); volatility is computed and exposed separately, never added to or subtracted from the skill estimate (this was V1's documented defect #4 — now structurally prevented rather than just avoided by convention).

One test initially failed (`test_case4_...`) and forced a real correction to the test's own expectation, not the code: the test originally over-claimed that shrinkage would always fully suppress a small-sample outlier below a large-sample mediocre player, which is not true in general for this class of estimator. The corrected test now asserts the true, defensible property (a large proportional narrowing, not a guaranteed rank flip) and documents the residual limitation inline.

## PHASE C — Observation unit decision

Compared: (A) raw event-total SG [current production behavior — rejected, fails Cases 1/2/5], (B) unweighted mean of per-event per-round rates [ties events of very different lengths equally, verified numerically to diverge from the weighted version once round-counts differ — `test_pooled_rate_is_the_correct_weighted_average_across_unequal_round_events`], (C) individual round-level SG observations [not available in the warehouse — only per-event cumulative totals + a rounds count are stored], (D) **event SG weighted by rounds, pooled as `sum(total_sg) / sum(rounds)`** — chosen. This is the statistically correct pooled per-round rate under the (only currently checkable) assumption that a player's rounds within one event are exchangeable, and it is what `pooled_per_round_rate()` implements.

## PHASE D — Shrinkage

Implemented as classic empirical-Bayes: `shrunk = w·observed + (1-w)·population_mean`, `w = tau²/(tau² + sigma²/n_rounds)`. Parameters were **estimated from the real warehouse by method of moments**, not hand-picked (`estimate_shrinkage_prior_from_warehouse`, re-run live against 476 players / 291 with ≥3 events):

- `sigma²` (within-player, round-to-round rate noise) ≈ **3.84**
- `tau²` (between-player, true-skill spread) ≈ **1.95**
- population mean ≈ **−1.27 SG/round**
- resulting weight: ≈0.34 at 1 round of evidence, ≈0.72 at 5, ≈0.84 at 10, ≈0.91 at 20

These are reported as the audit trail for this specific run — re-derive them whenever the warehouse is rebuilt rather than hard-coding them.

## PHASE A follow-up — Cut-selection / survivorship bias (Monte Carlo)

New: `scripts/102_cut_selection_bias_simulation.py` + `tests/test_cut_selection_bias_simulation.py` (5 tests, all passing). Simulation parameters (sigma, tau, population mean, field size 118, cut fraction 68/118) are all taken from the real, already-calibrated warehouse numbers above — nothing invented. 400 simulated players × 20 tournaments each, field-relative cut rule (not a fixed score).

- **Test A1 (identical true skill for everyone)**: the naive production method shows a huge, opposite-signed bias between players who happen to survive cuts more often vs less often (+0.48 vs −0.29 SG/round — a 0.77 gap for players of literally identical skill). The pooled per-round rate candidate shrinks this gap by ~4x (+0.12 vs −0.08, gap 0.20) but **does not eliminate it**. Empirical-Bayes shrinkage shrinks it slightly further (+0.09 vs −0.11, gap 0.20) — shrinkage does not specifically target this bias since it only reacts to sample size, not to whether the data was cut-selected.
- **Test A2 (realistic skill distribution)**: pooled/shrunk estimators are both nearly unbiased in aggregate (mean bias ≈ −0.01), with rank correlation to true skill ≈0.98. Confirms cut rate itself correlates strongly with true skill (0.958) as expected (better players make more cuts) — this is NOT a bug, it's the real relationship the ranking is trying to measure; the bias question is specifically about players of the *same* skill being ranked apart by cut-selection luck (A1), not about better players correctly ranking higher (A2).
- **Test A3 (cut-line noise, matched true skill = 0)**: players who barely survived the cut averaged +0.33 SG/round in R1+R2 alone; players who barely missed averaged −2.44. That 2.77-point gap is entirely R1/R2 selection noise, not a skill difference — direct, mechanical proof that "made the cut" is partly a coin flip at the margin.
- **Test A4 (complete-case fallacy — discard every missed-cut event, keep only full 4-round completions)**: severely biased, +0.47 SG/round in the main run — roughly **45x larger** than the full-data pooled estimator's ~0.01 bias. This is now a regression-tested guard: production code must never silently switch to "only use completed events."
- **Test A5 (R1/R2-only common window, used for every tournament regardless of cut outcome) vs using all available rounds**: both are nearly unbiased (−0.01 to −0.01), but the R1/R2-only restriction has *higher* variance (RMSE 0.30 vs 0.24) for no bias benefit — confirms that keeping R3/R4 data for cut-survivors is not what's driving the residual A1 bias, and throwing it away only costs precision.
- **Test A6 (is the bias material relative to the information gained?)**: mixed, honest answer. In *aggregate* (A2, across a realistic skill distribution) the bias is small and does not materially distort rank correlation. But at the *subgroup* level (A1, comparing "lucky" vs "unlucky" players of equal skill) a real, persistent ~0.12-0.20 SG/round gap remains even with large total-rounds samples — re-running the simulation at n_tournaments = 1/2/3/5/10/20/40 showed this residual gap does **not** monotonically shrink toward zero with more data; it stabilizes around 0.12-0.13 rather than vanishing. This means: **more rounds mainly buys estimation precision (shrinkage weight climbs smoothly from 0.62 at ~3 rounds to 0.99 at ~126 rounds), not a cure for this specific selection effect.** A structural correction (Test A6's "conditional later-round model") is not implemented here — per the explicit instruction not to choose a correction before measuring the problem, this is flagged as necessary future work, not solved.

## Recommended observation model (updated)

Pooled per-round rate (`sum(total_sg)/sum(rounds)`), same as before, remains the best available choice: it beats naive-event-total badly on every test, and beats the R1/R2-only restriction on precision without added bias. But it should be **documented as leaving a known, quantified residual cut-selection bias** (~0.12-0.20 SG/round at the subgroup level) rather than presented as a fully solved problem.

## Shrinkage recalibration note

The σ²≈3.84 / τ²≈1.95 / mean≈−1.27 values were NOT recalculated this pass — the instruction was to recalibrate "after the cut-selection experiment" establishes whether the observation construction itself needs to change. Since Test A6 concluded the pooled per-round rate is still the best available observation unit (no structural change to how observations are built), there is no new observation construction to recalibrate against yet. These values should be recalculated once a corrected observation model (if one is built to address the residual bias) exists.

## Public vs internal minimum-rounds recommendation

Tested candidate thresholds via the shrinkage weight curve (not an arbitrary pick): weight climbs from 0.62 at ~3 rounds (about one tournament) to 0.89 at ~16 rounds, 0.94 at ~32, 0.97 at ~63, 0.98 at ~126. Recommendation, framed as confidence bands rather than a single magic number:
- **Internal estimation floor**: ~4 rounds (one completed tournament, weight ≈0.66) — enough to compute *something* shrinkage-adjusted, clearly marked low-confidence.
- **Public NEO Ranking floor**: ~20 rounds (roughly 5 tournaments, weight ≈0.89-0.91) — matches the order of magnitude of the existing production concept (`home_ranking.py`'s `sample_count >= 10` events, which at ~3.5 avg rounds/event ≈35 rounds, weight ≈0.95).

These are **candidates for further testing**, not adopted thresholds — Test A6 did not identify a sharp threshold where bias vs. precision trades off cleanly, since the residual A1 bias doesn't shrink with more rounds while precision does.

## Field-strength source audit (Phase G — candidates only, nothing implemented)

Two legitimate, real, point-in-time-safe candidates exist in the repository, neither yet used as a field-strength proxy:
1. **`OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json`** — real official K-Ranking snapshot, `retrieved_at: 2026-08-31T15:58:02Z`, confirmed BEFORE the tournament's own start — no leakage risk from its own timestamp. Average/median official K-Rank of the 120 entrants could proxy field strength.
2. **`OK_OPEN_2026_ENTRY_SNAPSHOT.json`** — real entry list with `qualification_category`/`qualification_reason` per player (e.g. "2025 정규투어 상금순위 60위 이내" — within top-60 2025 money list), a verifiable strength-tier signal already present per-player.

Leakage risk: using EITHER as a proxy is safe only if the snapshot's own `retrieved_at` is confirmed to precede the specific prediction point being validated — this must be checked per-use, not assumed globally. Not implemented this pass, per instruction.

## Remaining gaps before Phase F/G/H/I

- **Phase E** (missed-cut selection bias) is only partially addressed: Cases 5/6 show per-round normalization removes the *arithmetic* penalty for missing a cut, but the deeper selection-bias question — does surviving to R3/R4 itself carry information because making the cut required good R1/R2 play — has not yet been tested and needs a dedicated backtest against real cut/no-cut outcomes.
- **Phase F** (a complete, explainable V2 formula combining skill + recent form + field strength + volatility) is only partially built: skill/uncertainty/volatility are structurally separated (as required), but field-strength has no data source yet, and no single `NEO_RANKING_VALIDATION_MODEL_V2.json` config/artifact has been produced.
- **Phase G** (V1 vs V2 backtest) has not been run — it requires the same real SQLite tournament database V1's backtest used (`scripts/89_redteam_neo_ranking_v1.py --db ...`); this sandbox's local `data/klpga.sqlite` is a 0-byte placeholder, so this backtest cannot be executed here and needs to run in an environment with the real database.
- **Phase H** (OK Open validation) is blocked on Phase A's finding: no real FINAL result exists in the repository yet.
- **Phase I** (two-event framework) has not been started.
- **Phase J** (sponsor integrity) was separately audited this session: `src/klpga/collectors/player_team_sponsor.py` and the OK Open PRE/R1 renderer (`scripts/84_build_ok_open_pre_website_candidate.py::_player_identity_cell`) already implement the exact rule requested (blank when unknown, never a placeholder, never inferred) and 7 of 8 existing tests in `tests/test_ok_open_player_affiliation.py` confirm it. The one failing test in that file (`test_scores_probabilities_and_rankings_unchanged_by_affiliation_join`) is an unrelated, pre-existing regression where the R1 leader's factual score is being replaced by a "산출 불가" placeholder — not a sponsor-integrity defect, and not fixed here (out of this phase's scope, flagged for separate follow-up). Sponsor is **not yet wired into `home_ranking.py`** at all (no sponsor field exists on HOME rows today) — this is the concrete gap for whenever the permanent-HOME work resumes.
