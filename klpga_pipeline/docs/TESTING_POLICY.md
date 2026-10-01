# Testing policy — three levels

Added 2026-10-01 alongside `scripts/run_round_pipeline.py` (the
round-agnostic HITE JINRO PRE/R1/R2/R3/FR pipeline). Running the full,
unfiltered pytest suite (377 test files as of this writing) on every
commit is not sustainable: one pre-existing file alone
(`tests/test_10097_player_intelligence_provenance_v10.py`) takes
several minutes on its own (see `TECH_DEBT.md`), and the full suite's
total runtime makes it the wrong default for a small, scoped change.

## Level 1 — Targeted Regression Suite (every commit)

Run on every commit that touches the round pipeline or anything it
depends on:

```
python -m pytest -m round_pipeline
```

The `round_pipeline` marker (registered in `pytest.ini`) is applied to
every test file that imports or exercises:

- `klpga.neo_win.hitejinro_round_pipeline` / `hitejinro_round_page` /
  `hitejinro_player_metrics`
- `scripts/run_round_pipeline.py`, `scripts/190-203_*.py`
- shared modules the pipeline depends on: `previous_tournament_link`,
  home ownership/stage promotion, `player_intelligence_generator`,
  `round_score_format`, tournament chronology

When adding a new test file for round-pipeline-adjacent code, add
`pytestmark = pytest.mark.round_pipeline` near its top so it's picked
up automatically.

As of 2026-10-01: 117 tests, ~3m54s.

## Level 2 — Tournament Release Suite (before a R1/R2/R3/FR deploy)

Before publishing a real round page via
`python scripts/run_round_pipeline.py <game_code> <STAGE>` against
real operator-supplied evidence:

1. Level 1 (`-m round_pipeline`) must already be green.
2. Playwright verification (built into `run_round_pipeline.py` itself
   — HOME + PRE + the stage being published, desktop + mobile, no
   console errors beyond the known harmless favicon 404, HOME `<main>`
   byte-identical to whichever stage is currently most advanced).
3. Manual sanity check of the published page's real row count and a
   handful of real player values against the raw evidence.

This is what `run_round_pipeline.py` already does end-to-end for a real
round; there is no separate suite to invoke.

## Level 3 — Full Regression Suite (before merging to main, or before
FR / tournament close)

```
python -m pytest
```

Reserved for:

- merging this branch into `main`
- immediately before/after publishing FR (round 4, the tournament's
  last competitive round)
- a structural refactor (moving/renaming shared modules, changing a
  contract multiple tournaments rely on)
- a change to a genuinely shared library (e.g. `round_score_format`,
  `previous_tournament_link`, `home_ownership_guard`) that Level 1's
  marker doesn't already cover for every consumer

Known cost: this currently runs into pre-existing slow test files; see
`TECH_DEBT.md`. Budget real time for it — it is not a quick sanity
check, by design.
