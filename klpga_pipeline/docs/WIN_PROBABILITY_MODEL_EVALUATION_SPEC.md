# NEO GOLF Win-Probability Model — Evaluation Specification (v1)

**Status: FROZEN before any model is fit.** This document defines how
any future KLPGA win-probability model will be evaluated, compared
against baselines, and promoted or rejected — written and committed
**before** a single coefficient exists, so the rules cannot be
adjusted after the fact to favor whatever the first model happens to
produce. No model is implemented, no coefficient is fitted, and no
live probability (including for the KG Ladies Open field,
`tournament_entry`) is computed anywhere in this document or its
companion work.

Date frozen: 2026-08-25.
Scope: evaluation methodology only. Implementation is a separate,
future, explicitly-approved step.

Everything below builds on the already-validated, already leak-tested
point-in-time architecture in `src/klpga/backtest/` (see
`docs/SITE_STRUCTURE_TODO.md` sections 7-8 for its full confirmation
log) and the production diagnostics in `scripts/16`-`21`. This document
does not re-derive or bypass that layer — any future model
implementation MUST consume `klpga.backtest.walk_forward.
build_walk_forward_dataset()`'s output directly, never recompute
features ad hoc.

---

## 1. Primary question

The model estimates, for every historical or live target tournament
`T` and every player `i` in `T`'s field:

```
P(player i wins tournament T | information available strictly before T)
```

This is a **field-conditional probability estimation problem**, not a
"predict the winner" classification problem. The distinction matters
for every metric chosen below: a classifier is scored on whether its
single top pick is right; a probability estimator is scored on whether
its entire distribution honestly reflects uncertainty. We are building
the latter. Framing this as "predicting the winner" would justify
optimizing metrics (plain accuracy, top-1 hit rate) that reward
overconfidence — exactly the failure mode Sections 3, 5, and 12 guard
against.

**Hard constraints on every candidate model, for every tournament it
predicts:**

1. Every player in `T`'s reconstructed field (via
   `klpga.backtest.historical_field.reconstruct_historical_field`)
   receives a probability — no player is dropped from the output.
2. Every probability is finite and non-negative.
3. The field's probabilities sum to `1.0` within numerical tolerance
   (`1e-6` absolute, pre-registered here — not chosen after seeing
   whether a candidate model's normalization is exact or approximate).
4. A rookie / zero-prior-history player (`prior_events_n == 0`) is
   NEVER automatically assigned probability `0`. She may legitimately
   receive a LOW probability if the model has genuinely learned that
   zero-history players win less often on average, but that must be an
   estimated, evaluated consequence of the model — not a hard-coded
   rule, a missing-feature crash, or a silent `NaN`-to-`0` coercion.
   Section 7 defines how this is verified.

The field itself is defined by `historical_field.py`'s documented
limitation, repeated here because it directly bounds what "field-
conditional" can honestly mean for historical evaluation: it is the
site's collected RESULT field (everyone who has a `player_event` row
for `T`), not a confirmed pre-tournament ENTRY list. A player who
withdrew before any round was ever posted is invisible to this
evaluation entirely — she is neither predicted for nor counted in the
field-size denominator. This is a real, disclosed gap (see Section 12,
"historical-field survivorship"), not something later sections attempt
to paper over.

---

## 2. Walk-forward evaluation

All evaluation reuses the already-built, already leak-tested
architecture — this document does not introduce a second feature
pipeline.

**Current production evidence** (real values, reported from the
production DB; not fabricated for this document):

- 100 USABLE historical tournaments (`klpga.backtest.walk_forward`'s
  unconditional population — see the "population-definitions audit" in
  `docs/SITE_STRUCTURE_TODO.md` section 8).
- At `threshold=5`: 95 ELIGIBLE target tournaments, 11,189
  player-target observations.
- **`threshold=5` is a v1 CANDIDATE ONLY, not fixed.** Every primary
  comparison in this document (Section 11) must be repeated at
  `threshold ∈ {5, 8, 10}` at minimum, using
  `scripts/17_eligibility_report.py` / `eligibility_sweep()`'s existing
  sweep — never a single silently-chosen threshold.

**Leakage guarantee (inherited, re-stated as a hard rule for this
layer):** every feature for target `T` is computed using only
`player_event`/`player_round` rows strictly before `T`'s effective
date (`klpga.backtest.temporal.is_strictly_before`), with `T`'s own
`event_id` excluded outright regardless of date. This is proven by 5
synthetic adversarial tests (`tests/test_point_in_time_features.py`)
and one real-production-data invariance check
(`scripts/18_leakage_invariance_check.py`). **No target-tournament
feature leakage, no later-event leakage — a model evaluation that
bypasses `build_walk_forward_dataset()` to "save time" forfeits this
guarantee and must not be trusted.**

**Historical field membership limitation (repeated from Section 1):**
`player_event`-based field reconstruction reflects RESULT
participation, not a true historical pre-event ENTRY list. This is a
methodological limitation of every historical backtest number in this
document, not a data quality bug to be fixed before evaluation can
proceed — it is disclosed everywhere the field size or field
membership matters (Sections 1, 3B, 7, 12).

---

## 3. Primary probability metrics

### A. Tournament-level multiclass log loss (PRIMARY #1)

For target tournament `T` with field `{1, ..., n_T}` and actual winner
`w`:

```
LogLoss(T) = -log(p_w)
```

where `p_w` is the model's predicted probability for the actual
winner. This is a **categorical log loss over a per-tournament,
variable-cardinality outcome set** — `T`'s "classes" are literally its
own field members, which differ in count and identity from every other
tournament's. This is NOT a fixed global class label set the way a
textbook multiclass classifier assumes; each tournament is its own
independent categorical distribution with `n_T` outcomes.

**Aggregation:** report the **mean per-tournament log loss** across
all eligible target tournaments as the headline number (not the sum —
the sum would conflate "more tournaments evaluated" with "worse
average performance," and the tournament count changes across
threshold sensitivity checks). Also report the full per-tournament
distribution (Section 11's stability check needs it, not just the
mean).

**Why this is PRIMARY and heavily penalizes confident wrong
predictions:** `-log(p)` diverges to infinity as `p → 0`. A model that
assigns a plausible-looking but tiny probability (e.g. 0.5%) to a
player who then wins pays a catastrophic, effectively unbounded
penalty — far worse than a model that honestly said "I don't know, ~1%
for everyone in a 100-player field." This directly rewards calibrated
humility over false confidence, which is exactly the property Section
1 requires and a pure ranking metric (Section 5) cannot enforce.

**Floor policy (pre-registered, identical across every candidate
model, never tuned post-hoc):** `p_w` must never literally be `0`
under Section 1's constraints, but to guard against a degenerate
near-zero output dominating the aggregate, clip every predicted
probability to `[ε, 1]` before computing log loss, `ε = 1e-6`,
re-normalizing the field to sum to 1 after clipping. This value is
fixed here, before any model exists — changing it after seeing which
model it favors is exactly the goalpost-moving this document exists to
prevent.

### B. Multiclass Brier score (PRIMARY #2)

For target tournament `T`, one-hot outcome vector `y` (`y_w = 1`,
`y_i = 0` for `i ≠ w`), predicted vector `p`:

```
Brier_raw(T) = Σ_i (p_i - y_i)²   over i = 1..n_T
             = (p_w - 1)² + Σ_{i≠w} p_i²
```

This is the standard multi-category Brier formulation (Brier's
original sum-of-squared-errors-over-categories definition), computed
per tournament.

**Normalization (specified, not left ambiguous):** `Brier_raw(T)`
grows with field size `n_T` (more categories contribute more
non-negative terms), and real KLPGA fields vary (confirmed field
sizes: the live-verified KG Ladies Open field was 120; historical
fields are of comparable but not identical size). Report BOTH:

- `Brier_raw(T)` — diagnostic, not used for cross-tournament averaging.
- `Brier_norm(T) = Brier_raw(T) / n_T` — **the PRIMARY comparison
  metric**, dividing out the field-size confound so a model isn't
  penalized or rewarded merely for being evaluated on a larger or
  smaller field that tournament.

Aggregate `Brier_norm(T)` as a mean across eligible tournaments,
exactly parallel to log loss's aggregation, for the same reason.

### C. Calibration

**The question:** do probabilities mean what they claim — do players
assigned ~10% collectively win ~10% of comparable opportunities?

**The sample-size constraint, taken seriously:** there are only ~95
eligible tournaments at `threshold=5` (fewer at 8 or 10). The 11,189
player-target rows are NOT 11,189 independent Bernoulli trials for
calibration purposes — within one tournament, every row's outcome is
mechanically linked (probabilities sum to 1; exactly one row is the
true winner), so treating rows as independent understates uncertainty
severely (this exact failure mode is named explicitly in Section 12
and must not recur here). The effective sample size for any
calibration claim is bounded by the tournament count, not the row
count.

**Proposed diagnostic, sized to what ~95 tournaments can actually
support:**

1. **Coarse probability bins only** — no more than 4-6 bins (e.g.
   `[0, 2%), [2%, 5%), [5%, 10%), [10%, 20%), [20%, 100%]`, exact edges
   to be finalized against the real predicted-probability distribution
   once a model exists, not chosen to flatter one). Fine-grained bins
   (e.g. 1%-wide) are explicitly rejected as unsupportable at this
   sample size.
2. For each bin: `Σ p_i` (expected wins, summed over every player-row
   whose prediction falls in that bin) vs. `Σ y_i` (actual wins in
   that bin). Both are unbiased regardless of within-tournament
   correlation (expectation is linear), so this comparison is valid
   even though independence is not.
3. **Confidence intervals via tournament-level bootstrap, not
   row-level.** Resample the ~95 (or 8/10-threshold-count) TOURNAMENTS
   with replacement (not the 11,189 rows), recompute the bin
   statistics each resample, and report a percentile interval (e.g.
   1,000 resamples, 90% interval). This correctly propagates the
   within-tournament correlation structure that a naive row-level CI
   would ignore.
4. **Always report, alongside every bin's calibration ratio:** the
   number of player-rows in the bin AND the number of tournaments that
   contributed at least one winning outcome to the bin's actual-win
   count. A bin with 3 tournament-level winner-observations is not
   reportable with the same confidence as one with 40, however many
   thousand non-winning rows pad it out.
5. A single scalar Expected Calibration Error (ECE) MAY be reported as
   a summary, but only alongside its tournament-bootstrap CI — never
   as a bare number implying more precision than ~95 tournaments can
   support.

Calibration is diagnostic evidence for Section 11's promotion decision
(a stark, CI-clearing miscalibration is disqualifying), not a single
pass/fail gate computed to arbitrary precision.

---

## 4. Baselines — mandatory

No candidate can be called useful merely because its numbers "look
plausible." Every comparison in Section 11 is against these baselines,
computed under the exact same walk-forward protocol (Section 8) and
scored with the exact same metrics (Section 3) — never a separate,
easier standard for baselines.

### Baseline 0 — Uniform field probability

```
P(i) = 1 / n_T
```

No parameters, no fitting, no features. The floor every candidate must
clear. If a candidate cannot beat this out-of-sample on Section 3's
primary metrics, it is not ready regardless of how sophisticated its
feature set looks.

### Baseline 1 — Single scoring-strength feature, fitted transform

One defensible point-in-time scoring measure, converted to field
probabilities via the simplest structurally-sound transform: a softmax
over the (sign-adjusted) strength value with a single temperature
parameter,

```
P(i) = exp(-s_i / τ) / Σ_j exp(-s_j / τ)
```

where `s_i` is the chosen scoring feature (more negative
`score_to_par` = better, hence the sign), and `τ` is the ONLY fitted
parameter. **`τ` must be fit via direct maximum-likelihood on the
walk-forward TRAINING fold only (Section 8) — never hand-picked, never
tuned against the tournaments being evaluated.** A 1-parameter MLE fit
on strictly-prior data is a normal, leakage-safe parametric fit, not
"peeking."

Baseline 1's feature choice is not decided in isolation here — it is
identical in methodology to the ablation ladder's `M1`/`M2` (Section
6), so Baseline 1 is effectively "whichever of `M1`/`M2` is used,
evaluated as the baseline it structurally is." This avoids defining
the same single-feature-softmax model twice under two names.

**Optional, non-mandatory naive baselines:** an additional baseline
(e.g., probability proportional to raw historical win RATE with no
transform) may be reported if it requires no hand-picked parameter,
but Section 4 does not require inventing extra weak competitors for
their own sake — "do not invent complexity just to create weak
competitors" applies to baselines exactly as it applies to challenger
features in Section 6.

**Gate:** a candidate model that cannot beat BOTH Baseline 0 and
Baseline 1 out-of-sample, on the primary metrics, with the paired
significance test defined in Section 11, provides no evidence it is
useful — full stop, regardless of any other diagnostic looking
favorable.

---

## 5. Secondary ranking metrics

Diagnostic / communication metrics only — never a substitute for
probability quality (Section 3).

- **Actual winner's predicted rank** — the 1-based position of the
  true winner when the field is sorted by predicted probability
  descending.
- **Top-3 / Top-5 / Top-10 hit rate** — fraction of tournaments where
  the actual winner's predicted rank is `≤ 3 / 5 / 10`.
- **Mean and median predicted rank of the actual winner**, across
  eligible tournaments (median is likely the more robust summary given
  the small tournament count and potential outliers).
- **Reciprocal rank / Mean Reciprocal Rank (MRR)** = mean of
  `1 / rank(winner)` across tournaments — a single scalar summary, but
  purely rank-based.

**Explicit, non-negotiable framing (restated because it is easy to
forget once numbers look good):** a model can rank the true winner
highly while producing badly calibrated probabilities — e.g. a model
that is systematically overconfident about its top pick and
underconfident about everyone else can still show a good Top-5 hit
rate while failing log loss and calibration badly. **Ranking metrics
therefore cannot select the final probability model by themselves.**
They are reported in Section 14's final recommendation as secondary
diagnostics, never as tie-breakers that override Section 11's
primary-metric gate.

---

## 6. Feature ablation plan

**Redundancy evidence** (from `scripts/20_feature_redundancy_report.py`,
reported figures — pairwise Pearson `r` on the walk-forward dataset):

| pair | r |
|---|---|
| `prior_avg_round_score_to_par` vs `prior_avg_round_to_par` | ≈ 1.00 |
| career scoring vs field-relative | ≈ 0.98 |
| `prior_top5` vs `prior_top10` | ≈ 0.96 |
| career scoring vs `prior_recent_form_20` | ≈ 0.94 |
| `prior_recent_form_10` vs `prior_recent_form_20` | ≈ 0.94 |
| `prior_recent_form_5` vs `prior_recent_form_10` | ≈ 0.90 |
| `prior_cut_rate` vs field-relative | ≈ -0.84 |
| `prior_wins` vs `prior_top5` | ≈ 0.78 |

Coverage of the main candidate features is ~95% (non-NULL rate; exact
per-feature figures in `scripts/21_data_coverage_report.py`'s output —
this document does not re-derive them).

**Exclusions from the v1 ladder, justified individually (not silently
dropped):**

- **`prior_avg_round_to_par` is EXCLUDED.** `r ≈ 1.00` against
  `prior_avg_round_score_to_par` means it carries no distinguishable
  signal in this dataset, AND it has structurally worse coverage
  (genuinely sparse — only collected for directly-queried rounds, see
  `point_in_time_features.py`'s module docstring). Near-perfect
  correlation plus worse coverage is a strict case for dropping the
  redundant, sparser twin.
- **`prior_recent_form_20` is EXCLUDED from the initial ladder.**
  `r ≈ 0.94` against BOTH career scoring and `prior_recent_form_10`
  means it adds little incremental information over features already
  in the ladder while consuming a full feature slot. It may be
  revisited as a post-ladder challenger (Section 6.3) if the chosen
  core model shows unexplained residual pattern a longer window might
  capture — not added by default.
- **Career scoring and field-relative scoring are NEVER combined in
  the same v1 model.** `r ≈ 0.98` — combining them buys negligible
  independent signal while roughly doubling the model's effective
  parameter count relative to the sample size (Section 8's "prefer
  simplicity"). They are tested as ALTERNATIVES (`M1` vs `M2`), and
  this is itself a genuine test: field-relative scoring is
  hypothesized to be more course/day-difficulty-robust than the raw
  career rate (Section 12, "course-strength limitations") — the
  ablation is designed to actually probe that hypothesis, not just to
  pick whichever number is marginally better.

### 6.1 Core ablation ladder (run first, in this exact order)

| id | model | features | notes |
|---|---|---|---|
| M0 | Uniform baseline | — | = Baseline 0 |
| M1 | Career scoring strength only | `prior_avg_round_score_to_par` | = Baseline 1's methodology |
| M2 | Field-relative strength only | `prior_avg_field_relative_round_score` | tests course/day-robustness hypothesis vs M1 |
| M3 | Career + Recent5 | `prior_avg_round_score_to_par`, `prior_recent_form_5` | |
| M4 | Career + Recent10 | `prior_avg_round_score_to_par`, `prior_recent_form_10` | |
| M5 | Field-relative + Recent5 | `prior_avg_field_relative_round_score`, `prior_recent_form_5` | |
| M6 | Field-relative + Recent10 | `prior_avg_field_relative_round_score`, `prior_recent_form_10` | |

`M1`-`M6` are all ≤2-parameter models (a softmax weighting over 1-2
standardized features, temperature/weights fit by MLE on the training
fold) — deliberately kept small enough that Section 8's simple fitting
protocol (no nested CV needed) applies. Compare `M0`-`M6` on Section
3's primary metrics (paired across the same tournament set, Section
11) to select a single "core" model before proceeding.

### 6.2 Challenger round (only after 6.1 is resolved)

Exactly one conceptual signal added to the winning core model at a
time — never combined, never defaulted into an "everything model":

- Core + `prior_wins`
- Core + `prior_top5`
- Core + `prior_top10`
- Core + `prior_cut_rate`
- Core + `prior_events_n` (an experience/sample-size signal not
  covered by the redundancy table above — its correlation with the
  core features is UNKNOWN from the figures given and must be checked
  via `scripts/20_feature_redundancy_report.py` against the real data
  before treating it as an independent challenger, not assumed clean)

Given `prior_top5`/`prior_top10`/`prior_wins` are mutually correlated
(`r` 0.78-0.96), they are three SEPARATE one-at-a-time challengers
against the same core, compared against each other as alternatives —
never combined with each other in a single v1 challenger.

### 6.3 Explicitly deferred, not forbidden

`prior_recent_form_20` and combined career+field-relative models may
be tested LATER as second-round challengers if the core+winning-
challenger model shows a specific, articulable residual gap they might
address — never added as a default "more features can't hurt" move.
"More variables" is never, by itself, a reason a model advances past a
simpler one (Section 11).

---

## 7. Rookie / sparse-history evaluation

**Production evidence** (real, at `threshold=5`): some player-target
rows have exactly zero prior events; ~9.8% have fewer than 5 prior
events; ~20.3% have fewer than 10. This is a real, load-bearing part of
the field on every tournament — not an edge case to special-case away.
Raising the eligibility threshold (Section 2) reduces which
TOURNAMENTS are evaluated; it does NOT reduce how many sparse-history
PLAYERS appear within an eligible tournament's field, since threshold
filtering operates on the target tournament, not on individual field
members. This problem must be evaluated directly, not sidestepped.

**Mandatory evaluation slices**, by `prior_events_n` at prediction
time:

| slice | prior_events_n |
|---|---|
| cold | 0 |
| very sparse | 1-4 |
| sparse | 5-9 |
| moderate | 10-19 |
| established | 20+ |

For each slice, report (never drop a slice for having few observations
— report the count and move on):

1. **Row count** in the slice, across all eligible tournaments.
2. **Winner count** — how many eligible tournaments were actually won
   by a player in this slice. If this is non-trivially non-zero (a
   real KLPGA field regularly includes rookies who contend), any model
   assigning that slice near-zero probability across the board is
   directly falsified by this count, not just "conservatively cautious."
3. **Mean/median assigned probability** within the slice, for (a) all
   rows in the slice and (b) specifically the rows where that slice's
   player went on to win.
4. **Log loss / Brier restricted to tournaments whose actual winner
   fell in this slice** — the direct test of whether the model
   systematically under-scores sparse-history winners, isolated from
   the (larger) established-player-winner tournaments that would
   otherwise dominate the aggregate.
5. **"Systematically absurd" probability check** — report, per slice,
   what fraction of rows receive a probability below a fixed,
   pre-registered structural floor (`1 / (10 · n_T)`, i.e. an order of
   magnitude below the naive uniform allocation for that field). This
   is reported as a distributional fact, not gated against an
   invented "this is wrong" cutoff — Section 11 interprets it.

**Shrinkage / empirical-Bayes rule:** any pooling of sparse-history
players toward a population or field-average strength (e.g., a
James-Stein-style shrinkage target) must itself be an expanding-window
statistic — computed from strictly-prior tournaments only, refit at
each walk-forward step exactly like every other parameter (Section 8)
— and evaluated out-of-sample by the same slices above. **No manually
chosen "rookie probability" constant, ever, at any point in this
pipeline.**

---

## 8. Walk-forward training discipline

**Outer loop (mandatory, for every candidate model):** for target
tournament `T`, the training set is every row in
`build_walk_forward_dataset()`'s output whose `target_event_id`
belongs to a USABLE tournament strictly before `T`'s effective date —
i.e. an **expanding window**, reusing the walk-forward dataset's own
existing per-target point-in-time features directly (each training row
was ALREADY computed point-in-time relative to its OWN target
tournament by the existing architecture — no new feature computation
is introduced by "training," only a chronological row filter).

**Why expanding window, not a fixed rolling window:** with only ~100
usable tournaments total, a fixed-size rolling window discards
already-scarce historical training data for no benefit; expanding
window uses everything available at each point in time, which is both
the most sample-efficient choice and the most realistic simulation of
"how much history would actually have been available" at each
historical decision point.

**Hyperparameter fitting — resolved by "prefer simplicity" (explicit
instruction), not by defaulting to a heavy nested-CV scheme:**

- Every model in the core ladder (`M1`-`M6`, Section 6.1) has **1-2
  free parameters** (temperature / feature weights in a softmax),
  fit by **direct maximum-likelihood on the training fold** for each
  `T`. This is a standard, well-posed, leakage-safe parametric fit —
  not hyperparameter *tuning* in the model-selection sense, so no
  separate held-out validation split is needed for it.
- If (and only if) a challenger model (Section 6.2 or later) has
  enough free parameters that in-sample MLE risks meaningfully
  overfitting the training fold, use a **crude nested expanding-window
  check**: a single chronological split within the training set
  (early training tournaments fit the parameter, the most recent few
  training tournaments validate it) — not k-fold, not a complex
  Bayesian scheme. Given the overall data scarcity, added modeling
  complexity in the VALIDATION step is exactly the kind of
  false-sophistication this document's "prefer simplicity" principle
  rules out by default.
- **Under no circumstances** may `T` itself, or any tournament
  chronologically at or after `T`, contribute to fitting any parameter
  (core or hyperparameter) used to predict `T`. This applies to model
  parameters, shrinkage targets (Section 7), AND calibration (Section
  9) equally.

---

## 9. Calibration discipline

**No calibrator (Platt scaling, isotonic regression, or any other
recalibration layer) may be fit using the tournament being predicted
or any later tournament** — if a calibration layer is used at all, it
follows the exact same expanding-window discipline as Section 8:
fit only on strictly-prior tournaments' predicted-vs-actual pairs.

**Explicit, pre-registered expectation for v1:** at ~95 (or
fewer, at higher thresholds) tournaments, the EFFECTIVE sample size
for calibration is bounded by the tournament count (Section 3C) —
almost certainly too small to reliably fit a nonparametric
recalibration layer (isotonic regression in particular can easily
overfit a ~95-point effective sample). **The default recommendation
for v1 is: do NOT fit a separate calibration layer.** Report the raw
model's calibration diagnostics honestly (Section 3C) instead. We
prefer an honestly imperfect raw probability model over a falsely
precise calibrated one — a recalibration layer fit on this little data
would very plausibly make the reported numbers look better while
making the true out-of-sample calibration worse or no different,
which is the opposite of what calibration is for.

If a future, larger dataset (more collected seasons) changes this
calculus, that is a decision for a future version of this document —
not something this version pre-approves.

---

## 10. Uncertainty and presentation

**The false-precision problem, named explicitly:** a displayed value
like "Player A — 8.4%" implies a level of resolution that a ~95-
tournament backtest, with the calibration sample-size constraints of
Section 3C, cannot actually support. This document does not choose
final display rules (that is a downstream, partly product/marketing
decision this document explicitly defers, per instruction), but it
DOES require that some form of honesty-about-precision be present
before any number reaches a viewer:

- **Rounding**: candidate approaches include coarser rounding (e.g. to
  the nearest whole percent, or even nearest 5% for low-confidence
  ranges) than a raw 1-decimal computation would suggest — the actual
  rounding rule should be chosen from Section 3C's real calibration
  bin widths once they exist, not guessed now.
- **Uncertainty / stability diagnostics**: e.g. a tournament-level
  bootstrap over the fitted parameters (resample training tournaments,
  refit, observe how much a given player's probability moves) or a
  leave-one-training-tournament-out sensitivity check — reported
  alongside the point estimate, not replacing it.
- **Probability tiers** (e.g. "Contender" / "In the mix" / "Long
  shot") are a plausible presentation mode, but tier boundaries must
  be derived from Section 3C's actual calibration bins once measured,
  not chosen for how the tiers "read."
- **Model-version labels**: every displayed probability must be
  traceable to the exact `model_id` / `model_version` /
  `training_cutoff` that produced it (Section 13) — critical here
  specifically because threshold sensitivity (Section 2) and the
  ablation ladder (Section 6) mean multiple candidate models will
  exist simultaneously during evaluation, and none of them are
  interchangeable with a future promoted model.

**Explicit non-goal, restated:** none of the above is decided by this
document. It only establishes that a presentation-precision decision
is REQUIRED before any public number ships, and that decision must be
made from real calibration evidence, not marketing appeal.

---

## 11. Model success / failure rules

Pre-registered promotion criteria — a model is not promoted merely
because a single metric moved in the right direction.

1. **Primary gate — paired log loss comparison.** For a candidate to
   even be considered, its per-tournament log loss (Section 3A) must
   beat BOTH Baseline 0 and Baseline 1 (Section 4), evaluated on the
   IDENTICAL set of eligible tournaments (a **paired** comparison,
   since both models are scored on the same tournaments — this is more
   powerful than an unpaired test and doesn't require assuming
   normality across ~95 samples). Use a paired non-parametric test
   (e.g. Wilcoxon signed-rank on the per-tournament log-loss
   differences, or a paired permutation test) at a pre-registered
   `α = 0.05`, two-sided. **No arbitrary magnitude threshold (e.g. "must
   improve 5%") is used** — the gate is statistical significance of the
   paired difference, in the improving direction, not a hand-picked
   percentage. (If a future version of this document wants a magnitude
   threshold, it must justify it statistically — e.g. from an effect-
   size/power analysis given the realistic tournament count — not
   invent a round number.)
2. **Brier consistency.** A promoted model should also improve, or at
   minimum not significantly worsen, `Brier_norm` (Section 3B) under
   the same paired test. A model that wins on log loss while
   meaningfully worsening Brier is flagged for scrutiny, not
   auto-promoted.
3. **Calibration.** No gate on a single scalar given the wide
   bootstrap CIs realistic sample sizes produce (Section 3C) — but a
   stark, CI-clearing DIRECTIONAL bias (e.g. every high-confidence bin
   consistently over- or under-realizing) is disqualifying and must be
   reported even if 1-2 pass.
4. **Stability across walk-forward periods.** Split the eligible
   tournaments into early/mid/late thirds by date; the candidate's
   improvement over baselines must not be driven entirely by one
   sub-period (e.g. one hot streak or one anomalous season). Report
   per-period log loss/Brier; a model whose entire advantage lives in
   one third is flagged, not promoted on the pooled number alone.
5. **Threshold sensitivity.** The full comparison above (1-4) is
   repeated at `threshold ∈ {5, 8, 10}` (Section 2). A model whose
   promotion verdict flips across these thresholds is itself a red
   flag — report this explicitly rather than picking whichever
   threshold makes the model look best.
6. **Sparse-player behavior.** Per Section 7, a promoted model must
   not show a systematic, slice-level absurdity (near-zero probability
   for a slice with a non-trivial real win count). This is a
   qualitative red-team check on top of the quantitative gates above.
7. **Complexity tie-break.** If two candidates are NOT statistically
   distinguishable on gate 1 (i.e. the paired test does not reject the
   null), the SIMPLER model (fewer features/parameters) is preferred —
   explicitly, "one metric improved slightly" is never sufficient
   justification for a more complex model to replace a simpler one.

Report every model actually evaluated against these criteria — not
only the eventual winner — per Section 12's "repeated testing" failure
mode.

---

## 12. Red-team failure modes

Each addressed explicitly, with the concrete mitigation already in
place or required going forward:

- **Future leakage / target-event leakage.** Structurally prevented by
  `klpga.backtest.temporal`/`point_in_time_features` (strict date
  ordering + hard `event_id` exclusion), verified by 5 synthetic
  adversarial tests and 1 real-production invariance check. Extends to
  hyperparameter fitting (Section 8) and calibration fitting (Section
  9) — leakage through a "secondary" fitting step is still leakage.
- **Overfitting ~95 tournaments.** Mitigated by: preferring ≤2-
  parameter models in the core ladder (Section 6.1), the paired
  significance gate (Section 11.1) rather than eyeballing metric
  deltas, and crude (not elaborate) nested validation only when a
  challenger genuinely needs it (Section 8).
- **Multicollinearity.** Directly measured (Section 6's correlation
  table) and mitigated by the ablation ladder's explicit exclusions
  and one-at-a-time challenger rule — never combining features with
  `r ≳ 0.9` in one v1 model without a stated hypothesis (as with
  M1/M2's course-robustness test).
- **Winner-count bias.** Exactly one winner per tournament, always.
  Larger fields are mechanically harder (lower base rate per player) —
  addressed by (a) `Brier_norm`'s field-size normalization (Section
  3B) and (b) comparing each candidate against baselines on the SAME
  tournament (paired), which cancels out field-size difficulty since
  both models face the identical field.
- **Cut survivorship bias.** `player_event`-derived features (career
  rate) already include made-cut=0 events via the confirmed CUT-drop
  fix (`docs/SITE_STRUCTURE_TODO.md` section 5). However, ROUND-level
  features (`prior_avg_field_relative_round_score`) only ever see
  rounds actually played — a chronic cut-line player's round sample is
  systematically biased toward "rounds she was still competitive in."
  **Flagged as an open, unresolved risk to monitor** (e.g. via the
  ablation comparing M1 vs M2), not a solved problem.
- **Historical-field survivorship.** Repeated from Section 1: a
  pre-round withdrawal is invisible to both training features and
  field-size normalization. Disclosed, not fixed by this document.
- **Rookie suppression.** Directly addressed by Section 7's mandatory
  slice evaluation and the ban on hand-set rookie constants.
- **Probability overconfidence.** Log loss's unbounded penalty
  (Section 3A) is the primary technical defense. The pre-registered
  clipping floor (`ε = 1e-6`, identical across all models, fixed
  before any model exists) prevents one catastrophic tournament from
  distorting the aggregate in a way that obscures overall model
  quality, without being tunable after the fact to flatter a
  particular candidate.
- **Calibration overfitting.** Directly addressed by Section 9's
  default recommendation against fitting any calibration layer at
  this sample size.
- **Era drift.** KLPGA conditions may shift across the ~100-tournament
  window (multiple seasons). The stability-across-periods check
  (Section 11.4) is the direct diagnostic; expanding-window training
  assumes reasonable stationarity, which is monitored, not assumed
  true by default.
- **Course-strength / course-par limitations.** No course-par proxy
  exists in this project (explicit prior decision — see
  `docs/SITE_STRUCTURE_TODO.md` section 6) and none is introduced
  here. `prior_avg_field_relative_round_score` partially compensates
  (benchmarked within the same historical round, hence the same
  course/day conditions) but the career-rate feature does not correct
  for course difficulty at all — the M1-vs-M2 ablation comparison is
  designed to actually probe whether this matters, not just to report
  whichever number is marginally better.
- **Treating 11,189 player-target rows as 11,189 independent
  tournament outcomes.** Named explicitly as its own failure mode,
  addressed everywhere it matters: calibration CIs (Section 3C),
  promotion significance testing (Section 11), all computed at the
  TOURNAMENT level with tournament-level (not row-level) resampling.
- **Choosing the model after repeatedly looking at the same 95
  tournaments (data-dredging / repeated-testing risk).** This is the
  meta-purpose of freezing this entire document before any model
  exists. The concrete process defenses: (1) the ablation ladder and
  promotion criteria are fixed here, in advance; (2) EVERY model
  actually evaluated is logged in the registry (Section 13), not just
  the eventual winner, so a post-hoc "we tried 40 things and this one
  worked" pattern is visible in the record rather than hidden; (3) any
  deviation from this pre-registered plan after seeing results must be
  disclosed explicitly as post-hoc in whatever report follows, never
  silently folded in as if it were the original plan. This defense is
  procedural, not automatic — it still depends on whoever runs the
  evaluation actually following it.

**The tournament, not the individual player-row, is the key evaluation
unit** — restated as the single sentence that resolves the majority of
the failure modes above when in doubt.

---

## 13. Model registry / reproducibility (schema sketch — NOT created)

A future result record, once a model is actually implemented, should
contain at minimum:

```
model_id                    -- stable identifier for the model family (e.g. "M4")
model_version                -- specific fitted instance / refit date
feature_set                  -- exact list of point-in-time feature columns used
eligibility_threshold        -- the walk-forward threshold this run used (5 / 8 / 10 / ...)
training_cutoff               -- effective_date this fit's training window ends strictly before
target_game_code
target_event_id
field_size                   -- n_T at prediction time
player_code
raw_probability
calibrated_probability       -- nullable; per Section 9, likely unused for v1
predicted_rank
label_finish_position         -- reusing walk_forward.py's existing label_* naming
label_finish_position_numeric
label_is_winner
evaluation_run_id            -- groups every row produced by one evaluation pass,
                                 so Section 12's "log every model evaluated" requirement
                                 is mechanically satisfiable
```

This is a **specification, not a database migration** — no
`tournament_entry`-style table is created by this document (see
`docs/SITE_STRUCTURE_TODO.md` section 7 for how that table's own spec
preceded its implementation by a full review cycle; this follows the
same pattern). Building it is a future, explicitly-approved step once
an actual model exists to populate it.

---

## 14. Final recommendation

**A. Recommended primary metric(s):** mean per-tournament log loss
(Section 3A) as the headline gate; field-size-normalized multiclass
Brier score (`Brier_norm`, Section 3B) as a required secondary
confirmation. Both are reported together, always — neither alone.

**B. Secondary diagnostics:** actual winner's predicted rank
(mean/median), Top-3/5/10 hit rate, Mean Reciprocal Rank (Section 5).
Communication and sanity-check value only — never a substitute for A.

**C. Baseline models:** Baseline 0 (uniform, `P(i) = 1/n_T`, no
parameters) and Baseline 1 (single-feature softmax with an MLE-fit
temperature, methodologically identical to `M1`/`M2`). A candidate
that cannot beat both, out-of-sample, is not evidence of anything
useful yet (Section 4).

**D. Exact first ablation sequence:** `M0`(=Baseline 0) → `M1`(=career
scoring, =Baseline 1) and `M2`(=field-relative scoring) compared
head-to-head → `M3`/`M4` (career + recent5/10) and `M5`/`M6`
(field-relative + recent5/10) → select the single best "core" model by
Section 11's criteria → THEN one-at-a-time challengers (`+wins`,
`+top5`, `+top10`, `+cut_rate`, `+prior_events_n`) against that core,
never combined, never defaulting to "add everything" (Section 6).

**E. Walk-forward fitting protocol:** expanding window over the
already-built `build_walk_forward_dataset()` rows, direct MLE for
every ≤2-parameter core-ladder model, a crude single-split nested
check only if a challenger genuinely needs more parameters, and a hard
rule that nothing at or after the target tournament ever contributes
to any fit — model parameters, shrinkage targets, or calibration alike
(Section 8).

**F. Rookie / sparse-history evaluation protocol:** five fixed slices
by `prior_events_n` (0, 1-4, 5-9, 10-19, 20+), each reported with row
count, real winner count, assigned-probability distribution,
slice-restricted log loss/Brier, and a structural-floor absurdity
check — with any shrinkage fit exclusively via the same walk-forward
discipline as every other parameter, never hand-set (Section 7).

**G. Model promotion criteria:** paired tournament-level significance
test on log loss as the primary gate (no arbitrary magnitude
threshold), Brier consistency, no CI-clearing directional
miscalibration, stability across time sub-periods, consistent verdict
across `threshold ∈ {5, 8, 10}`, no sparse-slice absurdity, and a
complexity tie-break toward the simpler model whenever the primary
gate does not clearly distinguish two candidates (Section 11).

**H. Reasons NOT to trust the model yet:**

- No model has been fit. Every mechanism described in this document is
  currently untested machinery, not evidence of a working model.
- ~95 (or fewer, at higher thresholds) eligible tournaments is a small
  sample for any of these metrics — every confidence interval in
  Section 3C and every significance test in Section 11 will be wide,
  and that width is real, not a formality to wave past.
- The historical field is a RESULT field, not a confirmed pre-
  tournament ENTRY list (Sections 1, 2, 12) — a real, disclosed
  survivorship gap in every historical number this document's future
  companion evaluation will produce.
- Course/day difficulty is only partially addressed (by the
  field-relative feature family) and not at all by the career-rate
  feature family — a genuine, unresolved confound the ablation is
  designed to probe, not one already solved.
- Calibration at fine grain is unverifiable at this sample size
  (Section 3C, 9) — any future display of a precise-looking calibrated
  percentage should be treated with the same skepticism this section
  is asking of the model itself.
- Repeated evaluation against the same ~95 tournaments carries a real
  data-dredging risk (Section 12) that this document's pre-
  registration defends against procedurally, not automatically — it
  still depends on whoever implements and evaluates the model actually
  following Sections 6, 8, and 11 as written, not adjusting them once
  results are in.

---

**STOP.** This document is a specification only. No model code, no
fitted coefficients, and no live probabilities (KG Ladies Open or any
other tournament) exist as a result of it. Implementation is a
separate, future step requiring explicit approval.
