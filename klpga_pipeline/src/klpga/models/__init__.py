"""M0-M6 win-probability model comparison — the FIRST MODEL
EXPERIMENTATION STAGE, implemented exactly against the frozen
`docs/WIN_PROBABILITY_MODEL_EVALUATION_SPEC.md`.

This package does NOT decide a winner. It fits and evaluates the seven
pre-registered candidate models (M0 uniform through M6) under a strict
walk-forward protocol on top of the already-validated
`klpga.backtest` point-in-time feature layer, and reports the metrics
the frozen spec requires. Model selection/promotion is a human decision
made from this package's OUTPUT, per the spec's Section 11 — nothing
in this package auto-selects or hard-codes a "winner."

No live KG Ladies Open probability is computed here, no
`tournament_entry` row is read or written, and no raw table
(`tournament_master`/`player_master`/`player_event`/`player_round`) is
written by anything in this package — every module here is read-only
with respect to the database, consuming
`klpga.backtest.walk_forward.build_walk_forward_dataset()`'s output
directly rather than re-deriving features.
"""
