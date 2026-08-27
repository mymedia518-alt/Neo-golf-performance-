# NEO WIN % v0.1 — BETA #001 Methodology

Status: implemented and offline-tested (`src/klpga/neo_win/`,
`src/klpga/analytics/neo_performance_dataset.py`,
`scripts/33_predict_neo_win.py`). Never executed against the real
production DB from this sandbox (no filesystem/network access to it —
see the standing constraint in every prior round's report). Entirely
separate from `klpga.models` (the frozen M0-M6 ladder behind
`Prediction #001`) and from `predictions/` — zero code coupling either
direction.

## 1. Why a new package, not a change to `klpga.models`

`klpga.models.candidates.MODEL_FEATURES` is explicitly documented as
frozen: "No other feature... is used anywhere in this module." NEO WIN
v0.1 needs two features that ladder doesn't have (a consistency/
downside-risk measure, a validated official-metric signal), so it is a
new, standalone model, reusing the SAME already-validated pure math
(`fit_shrinkage`, `apply_shrinkage_and_standardize`,
`softmax_from_logits`, `clip_and_renormalize`, `grid_refine_search`)
by import, never by copy-paste, and never touching the frozen dict or
`predictions/`.

## 2. Diagnostics investigated this round (real evidence, no code fix needed)

**`flagged_rows` (real run: 64,103/64,126 = 99.96%).** Investigated
against this repo's real committed evidence (32 identities, season
2025): `validation_status = FLAGGED` is dominated by
`duplicate_ranks` (31/41 files) and `non_numeric_numeric_fields`
(17/41), NOT missing/corrupted values. Direct inspection of one
flagged file (`Approach__Approach01__020101__2025.html`) shows rank
`"0"` shared by 131/246 rows — almost certainly a "did not qualify /
insufficient attempts" sentinel (the same category of finding as the
already-documented "999 rank sentinel" from leaderboard collection),
conflated with genuine statistical ties (e.g. rank `"76"` shared by 2
players with equal values, a real tie) by the current flag-counting
logic. **No classification change was made** — `duplicate_ranks` is
technically correct (duplicate rank values do exist) and downgrading
it would require confirming the "0 = unranked" semantic identity-by-
identity, which has not been done. Rows are never discarded based on
`validation_status` anywhere in the ingestion path (verified by
reading `build_official_metric_value_rows`) — the flag is informational
only. `klpga.neo_win.official_metrics.build_prior_season_official_
metrics` conservatively excludes FLAGGED responses from the model
feature by default, since a rank-column defect's blast radius on the
VALUE column specifically was not independently confirmed.

**248 unique request identities -> 46 distinct stored `identity_key`s
(real run).** `official_metric_value` only ever receives a row for a
canonical (identity_key, label) whose `identity_mapping.py` status is
`MAPPED` — every `UNMAPPED_*` status is refused ingestion by design
(Round 12), never guessed. This sandbox's own real 32-identity/281-
label evidence set independently shows the same order of coverage
(48/281 labels MAPPED = 17.1%, vs. the real production run's 46/248
identities = 18.5%) — closely consistent, not a new defect. **Verdict:
intentional canonical normalization, not data loss.** Improving MAPPED
coverage is legitimate future work on `identity_key_audit.py`'s
matcher, out of scope this round (no defect found to fix).

**6 unmatched player codes / 1 remaining `PARTIAL_MATCH_NEEDS_REVIEW`
collision.** Both are real data on the user's machine, not
reproducible here. Both are non-blocking by construction already: the
season collector never halts on an identity match/collision result
(`run_klpga_season_metrics_collector.py`'s own report already lists
`sample_unmatched` and the per-season collision category totals — see
Round 13). No code change needed; SKIP+LOG was already the standing
behavior before this round.

## 3. Feature set (4 features, all leakage-safe by construction)

| feature | source | orientation |
|---|---|---|
| `prior_avg_round_score_to_par` | `klpga.backtest.point_in_time_features` (existing, unmodified) | lower better |
| `prior_recent_form_10` | same | lower better |
| `neo_consistency_stddev` | NEW: population stdev of `player_round.round_to_par` over PRIOR rounds only (`klpga.neo_win.consistency`) | lower better |
| `neo_official_metric` | NEW: one validated `official_metric_value` label from the **prior completed season only**, from a small orientation-known allowlist (`klpga.neo_win.official_metrics`) | oriented to lower-better before reaching the model |

**Why prior season, never current season, for the official metric:**
`official_metric_value` is season-level with no PIT granularity
(`pit_status` is hardcoded `PIT_UNVERIFIED` — see `schema.sql` section
8's own comment). Using season Y's own metrics to predict a
tournament IN season Y risks leaking later-in-season data. Season
Y-1 is unambiguously prior to every tournament in season Y. Checked,
not just asserted — `klpga.neo_win.leakage.validate_official_metric_
temporal_safety` re-derives `prior_season = target_season - 1` and
flags any row that disagrees.

**Why an orientation allowlist instead of an arbitrary metric:**
combining a feature into an equal-weight z-score sum requires knowing
whether higher-is-better or lower-is-better; guessing wrong would be
silently, confidently incorrect. The allowlist
(`평균 티샷 거리`→higher, `그린 적중률`→higher, `페어웨이 안착률`→higher,
`평균 퍼트 수`/`평균 퍼트수`→lower) uses only EXACT labels copied
verbatim from the real, committed taxonomy, using unambiguous,
universal golf terminology — deliberately excluding parenthetical-
context variants (e.g. `그린 적중률(RTP)`) not confirmed to share the
base label's meaning. At feature-build time the first allowlisted
label with real values for >= 20 distinct players in the prior season
is used; if none qualify, the feature is cleanly OMITTED (never a
different metric silently substituted, never a guessed value).

**Missing-data treatment (every feature, per player):** the identical
shrink-to-training-mean formula `klpga.models.candidates.apply_
shrinkage_and_standardize` already uses — `n=0` or `value=None` yields
`z=0.0` exactly (the training fold's average), never a dropped player,
never a fabricated non-zero value. Reported per-run in
`missing_data_report`.

## 4. Model form

```
combined_score_i = sum(z_f_i for f in NEO_WIN_FEATURES)   (EQUAL weight)
P(i) = softmax(-combined_score_i / tau)
```

`tau` is the only free parameter (1-D grid-refine MLE, identical
method to every M0-M6 candidate). Equal-weighting — no fitted
per-feature beta — is a deliberate v0.1 simplicity choice given a
modest training-tournament count and 4 conceptual feature axes;
learning per-feature weights via the same walk-forward promotion-gate
methodology as M0-M6 is a disclosed, natural future refinement, not
silently assumed superior.

## 5. Leakage validation (checked, not just claimed)

`klpga.neo_win.leakage` re-derives, independently of the feature
computation itself, that (a) every PIT feature only used rows strictly
before the target date, (b) every official-metric feature row's season
is exactly `target_season - 1`, (c) the predicted field sums to 1.0
within `1e-6`. `run_neo_win_inference` runs all three on every
prediction and reports `leakage_validation.clean` / `.violations`.

## 6. Storage: `official_metric_value` (existing table, no new schema)

No new table was added this round. The "NEO Performance Dataset" is a
pure, read-only JOIN function (`klpga.analytics.neo_performance_
dataset.build_neo_performance_dataset`) over `tournament_master` +
`player_event` + `official_metric_value` + `player_master`, using the
`player_id <-> player_code` join CONFIRMED safe by the user's own real
run (`98.65%` match). Unmatched official-metric player_codes are
reported, never guessed into a row; the underlying `player_event`
result rows are never dropped over a metrics-join miss.

## 7. Frozen PRE snapshot

`klpga.neo_win.archive` mirrors `klpga.archive.prediction_archive`'s
atomic-hardlink, append-only, never-overwrite discipline exactly (own,
independent implementation — zero shared code), writing to
`neo_win_predictions/<year>/neo_win_<id>_<game_code>.{json,csv}`, a
directory that has never existed before this round and is fully
separate from `predictions/`.

## 8. `LOCAL_EXECUTION_REQUIRED`

Everything above is implemented and offline-tested. Running it for
real against `data/klpga.sqlite` requires the user's machine — see the
final report for the exact command.
