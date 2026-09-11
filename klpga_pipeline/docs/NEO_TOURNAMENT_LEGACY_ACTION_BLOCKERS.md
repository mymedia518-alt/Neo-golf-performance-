# NEO Tournament Engine ? Legacy Action Blockers

The generic Tournament Engine must not implicitly execute
tournament-specific recovery scripts.

## Blocked as generic production runners

- `84_build_ok_open_pre_website_candidate.py`
- `96_ok_open_r1_active_cycle.py`
- `98_ok_open_r1_final_reconciliation.py`
- `99_ok_open_r2_live_recovery.py`
- `deploy_r2_production_homepage.py`
- `run_beta001_r2_update.py`
- `run_beta001_r3_update.py`
- `generate_r2_frozen_forecast.py`
- `evaluate_r1_cut_ground_truth.py`
- `evaluate_r3_to_r4.py`

These files may remain as historical/recovery tools.

They become eligible for the generic action registry only after
their tournament-specific assumptions are removed and their
inputs/outputs satisfy the Tournament Engine validation contract.

## Safety rule

Missing generic runner = HARD BLOCK.

A missing runner must never silently fall back to an OK Open,
KG Ladies Open, BETA #001, or other event-specific script.

Validated factual publication and model publication remain
separate gates.

## KB 2026090003 (R2 HOUSE, 2026-09-11): a deliberately separate operator surface

KB's PRE/R1/R2 pages are built by their own dedicated, hardcoded-identity
scripts (`109_build_kb_r1_page.py`, `111_promote_top120_root_home_only.py`,
`112_kb_r2_active_cycle.py`) -- NOT through `run_tournament.py`'s generic
`TournamentActionRegistry`, and NOT tracked via `config/active_tournament.json`
(that file tracks OK Open's own R1/R2 live-polling lineage, `96`/`98`/`99`,
a completely separate identity system). This predates run_tournament.py's
"Phase 5" generic-engine work and was confirmed, not assumed: pointing
script 112 at `load_tournament_context()` with no argument (the generic
"active tournament" resolver `96`/`99` use) was tried during R2 HOUSE's
P1 pass and reverted after it proved actively wrong -- with OK Open as
the real active tournament, it silently made script 112 evaluate OK
Open's R2 state while still presenting itself as KB's operator, exactly
the silent-wrong-tournament failure a "single canonical entry point"
requirement exists to prevent.

Within KB's own scope, there is exactly one canonical R2 entry point:
`112_kb_r2_active_cycle.py`'s own module docstring classifies every
other script that could plausibly touch KB's R2
(`101_ok_open_post_r2_final_forecast.py`, `71_ok_open_r2_readiness.py`,
`run_beta001_r2_update.py`, `deploy_r2_production_homepage.py`,
`generate_r2_frozen_forecast.py`) as LEGACY/EVENT_SPECIFIC/NOT_PRODUCTION.

Fully merging KB onto the generic engine (so `run_tournament.py
--game-code 2026090003` drives it too, retiring the hardcoded scripts
entirely) is real, larger work -- tracked as Phase 5.1 above
("Investigate real scheduler path + retire competing operator paths"),
not a P1 item this pass claims to have done.
