"""NEO Predictions public site — a static-site generator over the
immutable NEO Prediction Archive (`klpga.archive.prediction_archive`).

This package computes nothing and touches no database. It only reads
already-archived `PredictionSnapshot` JSON files
(`klpga.archive.prediction_archive.read_prediction_snapshot`, reused
unmodified) and renders them into plain, static HTML/CSS/vanilla-JS —
no server-side logic runs when a visitor loads a page, and the site
never calls `klpga.models.inference.run_inference` or opens the
production SQLite database. A new prediction appears only after this
generator is re-run against the updated `predictions/` directory and
the output is redeployed — this is a rebuild, not a live push.

See `docs/PREDICTIONS_SITE.md` for the full architecture, routes, and
the reviewed Korean wording used for every derived label.
"""
