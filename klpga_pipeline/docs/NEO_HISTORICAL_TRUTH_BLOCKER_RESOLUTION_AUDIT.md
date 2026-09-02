# NEO Historical Truth — Blocker Resolution Audit

> DATA FOUNDATION: **READY_FOR_V2**
> NEO V1 PUBLIC RELEASE: **REJECT**

## Results

- Official K temporal provenance: official Monday cadence recovered; 53 weeks verified.
- K point-in-time mapping: 29/82 tournaments.
- Official R1 starter fields: 82/82 tournaments.
- Fully comparable: 29 tournaments / 2863 player-events.
- Field mean Jaccard versus SG reconstruction: 0.8154.

## Benchmark (frozen V1, no tuning)

- finish_spearman: K=0.4683, NEO=0.4684, Δ=+0.0001, CI=[-0.021171407777713435, 0.02264966404041681], INCONCLUSIVE
- SG_spearman: K=0.4241, NEO=0.4231, Δ=-0.0009, CI=[-0.020397356163638435, 0.018906932454622376], INCONCLUSIVE
- top10: K=0.3207, NEO=0.3172, Δ=-0.0034, CI=[-0.03793103448275863, 0.034482758620689655], INCONCLUSIVE
- top20: K=0.4741, NEO=0.4603, Δ=-0.0138, CI=[-0.039655172413793106, 0.012068965517241386], INCONCLUSIVE
- made_cut_auc: K=0.7018, NEO=0.7064, Δ=+0.0046, CI=[-0.006910494404576312, 0.017675234335579316], INCONCLUSIVE

## Rank divergence

- 0-10 / NEO_BEARISH: N=353, outcome N=347, K error=0.2615, NEO error=0.2542, closer=NEO
- 0-10 / NEO_BULLISH: N=537, outcome N=519, K error=0.2219, NEO error=0.2308, closer=K
- 0-10 / TIE: N=73, outcome N=72, K error=0.2429, NEO error=0.2284, closer=NEO
- 11-25 / NEO_BEARISH: N=193, outcome N=183, K error=0.2677, NEO error=0.2452, closer=NEO
- 11-25 / NEO_BULLISH: N=655, outcome N=638, K error=0.2392, NEO error=0.2516, closer=K
- 26-50 / NEO_BEARISH: N=74, outcome N=73, K error=0.2606, NEO error=0.2733, closer=K
- 26-50 / NEO_BULLISH: N=538, outcome N=522, K error=0.2668, NEO error=0.2662, closer=NEO
- 51+ / NEO_BEARISH: N=7, outcome N=7, K error=0.4196, NEO error=0.4122, closer=NEO
- 51+ / NEO_BULLISH: N=433, outcome N=422, K error=0.2478, NEO error=0.2352, closer=NEO

## Hard validation

- future_leakage_count: 0
- K_snapshot_after_start_count: 0
- silent_current_W35_substitution_count: 0
- fabricated_publication_date_count: 0
- fabricated_K_rank_count: 0
- fabricated_entry_status_count: 0
- duplicate_tournament_player_count: 0
- invalid_player_mapping_count: 0
- frozen_artifacts_changed: False
- insufficient_sample_force_ranked_count: 0

## Reproducibility

- Cached official responses are immutable and hash-checked; two consecutive rebuilds produced zero changed output hashes.
- Build: `NEO_HISTORICAL_TRUTH_BLOCKER_RESOLUTION.bat`

## Limits

- Archive availability begins at 2025-W35; earlier tournaments have no official K snapshot and remain non-comparable.
- R1 grouping proves actual starters, not original entries, alternates, or pre-event WD status.
- Incremental predictive information is descriptive only; no V1 weights were changed and no V2 was created.
