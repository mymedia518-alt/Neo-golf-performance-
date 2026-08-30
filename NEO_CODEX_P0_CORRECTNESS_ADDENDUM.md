# NEO CODEX P0 Correctness Addendum

## P0-A — consistency standard deviation

**LEGACY_BEHAVIOR:** `compute_consistency_feature` uses
`statistics.stdev` (sample standard deviation, denominator `n-1`), rounded to
three decimals, over strictly prior rounds only; values are `None` for n<2.

**INTENDED_BEHAVIOR:** The source docstrings and methodology documents call
the metric population standard deviation, which conflicts with the executable
implementation. The model and all round-update callers consume the returned
feature without a second conversion.

**NUMERICAL_IMPACT:** For n=2, sample SD is √2 times population SD; the gap
shrinks as n grows. A silent switch to `pstdev` would alter feature values,
shrinkage inputs, rankings, and probabilities.

**FROZEN_PREDICTION_IMPACT:** `neo_consistency_stddev` is a BASE_FEATURE in
`NEO_WIN_V0_1` and is consumed by PRE/R1/R2/R3 update paths. Existing frozen
prediction artifacts do not embed a recomputable alternate convention; their
provenance must therefore preserve the legacy sample-SD behavior. No code
change was made to the historical implementation or protected evidence.

**RECOMMENDED_VERSIONING:** Keep legacy feature/model semantics versioned as
`neo_consistency_stddev_sample_v1` (compatibility alias may retain the current
name for old snapshots). If population SD is desired, introduce a new
explicit feature/model version and run a separate promotion/backtest gate;
never silently rewrite historical forecasts.

**TESTS_REQUIRED:** n=2 sample-vs-population numeric fixture, n<2 NULL
contract, strict prior-date/leakage tests, and frozen-snapshot compatibility
tests before any future version promotion.

## P0-B — prediction archive reality

The actual `klpga_pipeline/evidence/beta001/manifest.json` classifies:

| Checkpoint | Classification | Artifact / provenance |
|---|---|---|
| PRE #1 | FROZEN_ARTIFACT_VERIFIED (reconstructed, disclosed) | `evidence/beta001/artifacts/pre_prediction_001.json`, model M4/v1, commit `6aa44cbb`, build `2026-08-26T00:30:29Z`, SHA-256 `0e1fbd...5301ea` |
| R1 #2 | FROZEN_ARTIFACT_VERIFIED | `docs/tournaments/2026/kg-ladies-open/r1/index.html`, published original, model `neo_win_beta_round_update_v1`, SHA-256 `be9b5f...b3400c` |
| R2 #3 | FROZEN_ARTIFACT_VERIFIED | `docs/tournaments/2026/kg-ladies-open/r2/index.html`, published original, model R2 remaining-round simulation, SHA-256 `531cac...49eeae` |
| R3 #4 | FROZEN_ARTIFACT_VERIFIED | `evidence/beta001/artifacts/post_r3_published_index.html`, published original, commit `c8b0a16`, SHA-256 `307977...ffde15` |

The manifest records timestamps/cutoffs where available and explicitly does
not invent unavailable build timestamps. The 7.47% protected lineage is the
R3 artifact/validated display record. Legacy/prototype surfaces containing
7.40% are lower-precedence rendered/prototype artifacts; they are not allowed
to overwrite protected evidence and remain a separate forensic discrepancy.

## P0-C — next-tournament freeze guarantee

Added pure reusable gate `klpga.neo_win.stage_freeze_gate`:

- PRE/R1/R2/R3 require an immutable artifact before transition (prediction IDs 001–004).
- FINAL is review-only and creates no prediction #005.
- Expected rounds derive from official `total_holes` metadata (54→3, 72→4); invalid formats hard-stop.
- Unresolved weather/player-hole completion blocks transition.
- Unresolved playoff blocks FINAL; official FINAL completion is required.

Focused gate tests cover missing artifacts, 54/72-hole formats, playoff and
weather blockers, and FINAL review-only semantics.
