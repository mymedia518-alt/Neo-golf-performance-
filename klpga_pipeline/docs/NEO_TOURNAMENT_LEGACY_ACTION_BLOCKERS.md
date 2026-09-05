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
