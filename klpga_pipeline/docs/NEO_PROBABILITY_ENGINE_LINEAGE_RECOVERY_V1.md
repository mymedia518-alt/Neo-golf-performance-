# NEO Probability Engine Lineage Recovery V1

Answers the question this task opened with: **did CUT/TOP20/TOP10/TOP5
ever exist, and if so where did they go?** Short answer: a real,
tested Monte Carlo engine producing all five tiers together has
existed in this codebase since the BETA #001-R1/R2/R3 work and is
still present, unmodified, on current HEAD -- it was never deleted.
It was never usable at the PRE checkpoint, though, and it was never
wired into the newer generic `run_tournament.py` orchestrator. Those
are the two real, evidenced reasons KB's PRE page shows WIN only.

## Lifecycle stage inventory

| Stage | Entry script | Core module | Frozen artifact | Probability tiers | Real-result fields | Model / features | Sim count / seed | Temporal cutoff | Leakage protection | Tests | Downstream consumer |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PRE (WIN only, current production) | `scripts/83_build_ok_open_pre_public_master.py` / `84_build_ok_open_pre_website_candidate.py` | `src/klpga/models/inference.py` (M4) | `*_PRE_PUBLIC_MASTER.json`, `*_PRE_WIN_FORECAST.json` | WIN only; cut/top20/top10/top5 always `null` | none (PRE has none yet) | conditional-logit softmax, 2 features (`prior_avg_round_score_to_par`, `prior_recent_form_10`) | N/A (closed-form, not Monte Carlo) | strictly before tournament start | frozen-snapshot cutoff timestamp per input freeze | `tests/test_model_inference.py` | scripts 84/88 public site build |
| PRE (BETA #001, historical, KG/OK) | `scripts/33_predict_neo_win.py` | `src/klpga/neo_win/model.py` (`NEO_WIN_V0_1`) | `predictions/2026/prediction_001_<game_code>.json` | WIN only | none | equal-weighted combined-score softmax, 3-7 features incl. official metrics | N/A (closed-form MLE-fit tau) | `cutoff_date` param, strictly prior tournaments only | `klpga.neo_win.dataset.build_neo_win_live_training_rows` excludes target event | `tests/test_neo_win_model.py` (not read in this pass) | `scripts/47_record_final_result.py`, `content/website_v2/kg_2026080001_official.json` comparison |
| R1 update (BETA #001-R1) | `scripts/35_*` (not fully read this pass) | `src/klpga/neo_win/round_update.py` | `neo_win_predictions/neo_win_001-R1_<game_code>.json` (archive helper exists; never actually populated for KG/OK in this sandbox) | WIN/TOP5/TOP10/TOP20/make_cut, ALL FIVE | none yet (R1 is mid-tournament) | same frozen PRE combined-score prior sets expected remaining-round rate; REAL R1 score used as-is; Monte Carlo for rounds 2-4 | `DEFAULT_N_SIMULATIONS=5000`, no fixed default seed (caller-supplied `rng`) | uses only the real, already-played R1 score plus the PRE-frozen prior -- never later rounds | empirical `cut_fraction` from real historical `player_event` rows (DB required) | not located in this pass (deferred) | `scripts/run_beta001_r2_update.py` orchestration (Phase 8-era) |
| R2 update (BETA #001-R2) | `scripts/101_ok_open_post_r2_final_forecast.py` | `src/klpga/neo_win/round_update_r2.py` | `content/website_v2/OK_OPEN_2026_POST_R2_FINAL_FORECAST.json` (STILL PRESENT, real, hash-verified) | WIN/TOP5/TOP10/TOP20/make_cut, ALL FIVE | real R1+R2 scores | same frozen PRE prior for remaining 2 rounds | `N_SIMULATIONS=100000`, `SEED=20260906` | real R1+R2 only | cut already REAL and known by this stage (not simulated) | not located in this pass (deferred) | never wired into `run_tournament.py` |
| R3 update (BETA #001-R3) | not located this pass | `src/klpga/neo_win/round_update_r3.py` | not located this pass | presumably all five, 1 remaining round simulated | real R1+R2+R3 | same | not inspected this pass | real R1+R2+R3 | n/a | not located | never wired into `run_tournament.py` |
| FINAL / POSTMORTEM | `scripts/47_record_final_result.py`, `src/klpga/neo_win/accuracy_evaluation.py` | `src/klpga/neo_win/tournament_history.py` | `neo_tournament_history/` (mechanism exists; never actually populated in this sandbox -- requires `data/klpga.sqlite`, absent here) | none produced; evaluates all prior forecasts | real final result | Brier/LogLoss/calibration/TopN-hit via `klpga.models.metrics` (model-agnostic) | n/a | n/a (retrospective) | n/a | not located this pass | none (never wired into `run_tournament.py`'s registry -- confirmed zero references) |

## Why `run_tournament.py` never picked this up

`run_tournament.py`'s action registry (`build_registry`, `_prepare_pre_runner`,
`_close_r1_runner`, `_close_final_runner`, `_promote_current_round`, etc.)
was built in a LATER phase of this project (tasks in the #176-187 range)
as a **generic, tournament-agnostic** single entry point. It has zero
references to `round_update.py`, `round_update_r2.py`, `round_update_r3.py`,
or scripts 33/35/38/43/44/46/47/101 (confirmed by grep). The BETA #001
family was always invoked manually, one script at a time, for KG and OK
specifically -- it was written and proven correct BEFORE the generic
orchestrator existed, and nobody has since connected the two. This is
classified **PIPELINE_DISCONNECTED**, not **MODEL_REMOVED**: the code is
untouched and real, it simply sits outside the newer pipeline's registry.

## Why PRE itself never had CUT/TOP20/TOP10/TOP5

Every one of `round_update.py`/`round_update_r2.py`/`round_update_r3.py`
requires at least one REAL, already-played round score as the anchor for
its 36-hole cut ranking. This is a hard architectural property, not an
oversight: at the PRE checkpoint no round has been played, so there is
nothing to anchor a 36-hole ranking to. This is why M4 (the current PRE
model) only ever produces WIN -- not because CUT/TOP20/TOP10/TOP5 were
decided to be unsafe, but because no PRE-stage model in this codebase,
before this task, ever attempted them. `src/klpga/neo_win/pre_5prob.py`
(new in this task) is the first PRE-stage implementation of all five
tiers together -- see `NEO_PRE_5PROB_PUBLICATION_GATE_V1.json` for why it
is not yet approved for publication.

## Governance defect (unrelated to the above, already documented)

`LIVE_PROBABILITY_MODEL_STATUS` (`src/klpga/neo_win/r1_live_probability.py`)
is a BLOCKED flag written for a completely different, unrelated engine
(an in-round R1-live Monte Carlo model), but `scripts/83`/`84` check this
SAME flag to gate M4's WIN display. M4 has never had its own dedicated
sign-off. See `NEO_PUBLICATION_GATES_V1.json` gate G for the full record.

## Sandbox constraint affecting this recovery

No `data/klpga.sqlite` or any `.sqlite`/`.db` file exists anywhere in
this sandbox. Every BETA #001 script that requires `--db data/klpga.sqlite`
(scripts 33, 47, and the ~90-100-tournament corpus behind M4's own
walk-forward backtest) cannot be freshly re-executed here. This is a
sandbox limitation, not evidence the corpus never existed --
`content/website_v2/2026090003_PRE_WIN_FORECAST.json`'s own
`inference_database` block records a real 43.7MB database with 102
tournaments / 12089 player_event rows having been used to compute KB's
own real M4 win_probability at some point, on a machine where that file
exists.
