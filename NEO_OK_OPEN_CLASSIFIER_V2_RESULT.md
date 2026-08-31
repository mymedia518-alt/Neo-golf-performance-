# OK OPEN PERFORMANCE CLASSIFIER V2

STATUS: PASS — corrected PRE interpretation layer; original frozen artifact untouched.

## Original freeze status

`OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json` remains byte-identical. SHA-256 is recorded in the V2 artifact. V2 is explicitly marked `PRE_TOURNAMENT_CORRECTION=true`, retains the original cutoff/freeze timestamp, and contains no post-start data.

## V2 artifact

`klpga_pipeline/content/website_v2/OK_OPEN_2026_PRE_PERFORMANCE_CORRECTED_V2.json`

Machine-readable diff: `OK_OPEN_2026_PRE_PERFORMANCE_CLASSIFIER_DIFF_V2.json`.

## Coverage and fixes

- 120/120 entrants retained.
- LEVEL is ranked by Recent5 SG Total against one all-pre-cutoff multi-season baseline; no array-order slicing.
- DIRECTION preserves Recent3/Recent5/Recent10 states and emits `WINDOW_CONFLICT` for reversals; 80 entrants have a conflict.
- CONSISTENCY variance cohorts use observed population/sample dispersion and bad-tail evidence; sample count alone cannot create HIGH VARIANCE.
- COMPOSITION compares Recent5/Recent10/Season leading components and has independent confidence/agreement fields.
- Evidence fields are separated into sample sufficiency, window agreement, materiality evidence and dimension confidence.

## Diff summary

104 direction classifications changed; 40 composition classifications changed; 135 per-dimension transitions are SUPPORTED → PARTIALLY_SUPPORTED; 5 SUPPORTED → CONTRADICTED; 80 new window-conflict cases. All 120 entrant-level diffs are retained.

## Tests

Focused classifier + PRE tests: 6 passed. Full repository suite: 1645 passed, 11 skipped, 2 existing legacy homepage failures (finalist roster and old post-tournament homepage assertions), unrelated to this cycle.

PHASE 0 evidence verifier: PRE/R1/R2/R3 PASS.

## Boundaries

Website 2.0, production homepage, forecast model, historical evidence, 7.40/7.47 provenance, AUTO OPS and raw SG warehouse were not modified.

## Next active task

OK Open operational readiness: official metadata → entry change/withdrawal detection → PRE forecast readiness → 54-hole lifecycle → R1 ingestion/checkpoint/freeze readiness.
