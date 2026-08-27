"""NEO WIN % — BETA #001. A new, standalone win-probability pipeline,
deliberately separate from `klpga.models` (the frozen M0-M6 ladder /
Prediction #001) and from `predictions/` (that archive). Nothing here
imports anything as a mutable dependency from those trees; where it
reuses their code (point-in-time features, softmax/shrinkage math,
tournament_entry fetch) it imports pure, already-tested functions
read-only, never their frozen model-selection state.

See docs/NEO_WIN_V0_1_METHODOLOGY.md for the full design writeup.
"""
