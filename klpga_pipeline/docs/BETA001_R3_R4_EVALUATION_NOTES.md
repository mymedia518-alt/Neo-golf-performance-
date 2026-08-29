# BETA #001 FINAL Validation — R3 → R4 Next-Round Prediction Evaluation

## What this is

`scripts/evaluate_r3_to_r4.py` (+ `klpga.neo_win.r3_r4_evaluation` /
`klpga.neo_win.r3_r4_evaluation_archive`) evaluates, once Round 4 has
officially concluded, how well BETA #001's own POST-R3 remaining-round
distribution (mu = `expected_round_score_to_par`, sigma = `spread`)
predicted each cutmaker's real Round-4 score.

It never modifies `klpga.neo_win.round_update_r3` or any other #001
model code, never touches the PRE/R1/R2/R3 frozen artifacts, never
touches `BETA_R3_FULL.csv`, and never writes into
`neo_tournament_history/`. It only reads them, and writes new files
under its own `--output-dir` (a CSV) and `--archive-root`
(`neo_r3_r4_evaluation/`, an append-only record, only with `--freeze`).

## How mu/sigma are obtained

`scripts/evaluate_r3_to_r4.py` calls
`klpga.neo_win.round_update_r3.build_r3_sim_inputs_from_frozen_snapshot`
directly — the exact, unmodified function `scripts/46_predict_neo_win_
post_r3.py` and `scripts/run_beta001_r3_update.py` already use at
POST-R3 time. This script never re-derives the formula.

## Future-data-leakage guard

Round-4 data is read into `actual_r4_scores` via a query that is
textually and functionally separate from the three `round_number IN
(1,2,3)` queries that feed `build_r3_sim_inputs_from_frozen_snapshot` —
that function's own signature has no parameter Round-4 data could even
be passed through. `scripts/evaluate_r3_to_r4.py` hard-stops entirely
(writes nothing) if zero real `round_number=4` rows exist yet.

## Important precision note: does r1/r2/r3/made_cut affect mu/sigma?

Per a direct read of `build_r3_sim_inputs_from_frozen_snapshot`'s
implementation: **no.** `expected_round_score_to_par` and `spread` are
derived only from the frozen PRE snapshot's own `feature_values`
(`prior_avg_round_score_to_par` / `neo_consistency_stddev`), with
population-mean shrinkage computed over *every* `pre_snapshot.
predictions` entrant — a computation that never reads r1/r2/r3/made_cut
at all. Those four real DB inputs only decide (a) which players are
reported as `missing` (excluded from simulation) and (b) each
`PlayerR3SimInput`'s own real cumulative score — never the mu/sigma
*values* themselves.

`source_r1_r2_r3_made_cut_input_sha256` on every frozen
`R3R4EvaluationSnapshot` is recorded as full audit provenance of what
live DB state was actually read at evaluation time — it is not evidence
that mu/sigma would have differed under a different one, given the
current code.

## Implementation note: `neo_consistency_stddev` — sample vs. population stddev

`klpga/neo_win/consistency.py::compute_consistency_feature()`'s
docstring states this computes a **population standard deviation**.
The actual implementation calls `statistics.stdev(prior_values)` —
Python's **sample** standard deviation (n−1 denominator), not
`statistics.pstdev()` (population, n denominator).

This was confirmed by direct code inspection while auditing the R3→R4
evaluation design (see the conversation this design originated from).
**The #001/#001-C model code was deliberately NOT changed** to resolve
this discrepancy — that would be a model-logic change, out of scope for
this evaluation tooling. This note exists so the discrepancy is a
documented, disclosed fact rather than something silently carried
forward or silently "corrected" without evidence of which convention is
actually intended. A future model (e.g. #002) should decide the
sample-vs-population convention deliberately, informed by this note.

## #002 reuse

`klpga.neo_win.r3_r4_evaluation_archive.read_all_evaluations(archive_root,
game_code=None)` reads every recorded R3→R4 evaluation (across every
`prediction_id`, i.e. every model version that has ever been evaluated
for a given tournament) into a plain list — the intended baseline
dataset loader for a future #002 model's own accuracy comparison
research. Records are stored per `(game_code, prediction_id)`, so a
future #002 evaluation of the same real tournament is a sibling record,
never a collision with #001's.
