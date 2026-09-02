# NEO Ranking Historical Truth Warehouse V1

> DATA FOUNDATION: **PARTIAL_FOUNDATION**
> NEO V1 PUBLIC RELEASE: **REJECT**

## Recovery conclusions

- Historical official K-Ranking: PARTIAL — 53 verified weekly responses, limited to 202535 through 202635.
- Publication dates: unverified. Week identifiers were not converted into assumed publication dates.
- Historical field truth: PARTIAL — 1/82 tournaments have a preserved pre-event entry snapshot; all remaining fields are SG-row reconstructions.

## Coverage

- Total tournaments: 82
- Fully verified/directly comparable: 0
- Partially verified: 82
- Comparable player-events: 0
- Frozen V1 and outcomes: 7830 player-events retained.

## K vs frozen V1

Direct benchmark and rank-divergence tests were not run. Without verified publication dates, selecting a weekly snapshot as pre-event truth would be an inference and could introduce after-start data.

## Hard validation

- future_leakage_count: 0
- K_snapshot_after_start_count: 0
- silent_current_W35_substitution_count: 0
- duplicate_tournament_player_count: 0
- duplicate_K_rank_count: 0
- invalid_player_mapping_count: 0
- fabricated_K_rank_count: 0
- fabricated_entry_status_count: 0
- frozen_V1_config_changed: False
- insufficient_sample_force_ranked_count: 0

## Remaining blockers

1. Official publication-date evidence for each K-Ranking week.
2. Historical K snapshots before 2025-W35, which the current official selector does not expose.
3. Pre-event entry/start-list evidence for 81 of 82 tournaments.

The warehouse keeps every missing K value and entry status null with an explicit reason. No current-W35 substitution or fabricated historical value is present.
