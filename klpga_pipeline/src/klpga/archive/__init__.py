"""NEO Prediction Archive — immutable, append-only, pre-tournament
prediction snapshots.

This package does NOT compute a probability. It only maps an
already-computed `klpga.models.inference.InferenceResult` onto a
durable JSON+CSV record and writes that record atomically, once, to
`predictions/<year>/`. No model math, feature computation, shrinkage,
or fitting logic of any kind lives here — see
`klpga.models.inference` for that (unchanged, unmodified by this
package).

See `docs/PREDICTION_ARCHIVE.md` for the full schema, immutability
guarantees, and the distinction between MODEL VERSION, PREDICTION ID,
PREDICTION DATE/CUTOFF, and POST-TOURNAMENT RESULT.
"""
